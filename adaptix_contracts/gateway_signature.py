"""Gateway signed-auth-context verifier for downstream Adaptix services.

This is the *consumer* (verify) side of the gateway → downstream auth contract.
The Adaptix gateway validates the external Cognito JWT at the edge, then stamps
every authenticated request with a signed internal context so downstream
services can trust the injected identity headers WITHOUT re-validating the JWT.

Two signing schemes, one verifier
---------------------------------
``gateway-v2`` (**Ed25519, issuer-bound — the target state, D-053**)
    The gateway signs with an Ed25519 PRIVATE key that nothing else in the fleet
    holds. Verifiers hold only PUBLIC keys (``ADAPTIX_GATEWAY_PUBLIC_KEYS``) and
    select by the ``kid`` in ``X-Adaptix-Auth-Key-Id``. Compromising a verifier
    yields **zero** ability to forge a context accepted by another verifier.

``gateway-v1`` (**HMAC-SHA256, symmetric — legacy, being removed**)
    The gateway and all ~52 domain services shared one secret
    (``ADAPTIX_GATEWAY_SHARED_SECRET``). Verification proved possession of a
    fleet-wide secret, never issuer identity: any service holding it could mint
    an arbitrary context including ``is_founder=true``. This is D-053, and v1 is
    retained only for the migration window.

``ADAPTIX_GATEWAY_TRUST_MODE`` selects which are accepted:

===============  ==========================================================
``asymmetric``   v2 only. A v1 context is rejected. **Target state.**
``dual``         v2 verified asymmetrically; v1 still accepted. Migration.
``hmac``         v1 only. Pre-migration state.
===============  ==========================================================

Unset resolves to ``dual`` when public keys are configured and ``hmac`` when
they are not, so installing the public keys is what advances a service — no
lockstep redeploy. A v2 context is **never** verified by HMAC in any mode: the
downgrade the mode ladder exists to prevent cannot be reached from a header.

Contract
--------
Headers the gateway stamps and this module reads::

  X-Adaptix-Auth-Context    : base64url(JSON payload), no ``=`` padding
  X-Adaptix-Auth-Signature  : v2 base64url(Ed25519 sig) / v1 hex(HMAC-SHA256)
  X-Adaptix-Auth-Path       : "gateway-v2" | "gateway-v1"
  X-Adaptix-Auth-Key-Id     : v2 only — ``kid`` of the signing key

Payload claims (``json.dumps(payload, separators=(",", ":"), sort_keys=True)``):
``sub, user_id, tenant_id, agency_id, email, roles, scopes,
iss="adaptix-gateway", aud=<downstream-service>, iat, exp, jti``.

Audience handling (D-034)
-------------------------
``adaptix-contracts`` is a SHARED package consumed by ~52 services, each with
its own ``aud``. Audience checking is layered:

1. **Presence — always enforced.** No Adaptix producer emits a context without
   an audience, so accepting one was the silent case: "no audience" read as
   "any audience".
2. **Registry membership — always enforced.** ``aud`` must name a live Adaptix
   service (``service_audiences.KNOWN_SERVICE_AUDIENCES``).
3. **Exact pin — per service.** ``ADAPTIX_GATEWAY_EXPECTED_AUDIENCE`` closes
   cross-service replay outright: a context minted for A is rejected by B. Only
   this layer stops A→B replay.

Layer 3 used to be optional, so a task definition that forgot the variable
silently lost replay protection (D-034). It is now **mandatory in production**:
:func:`assert_gateway_verifier_ready` fails startup/readiness when it is unset,
and verification itself fails closed rather than degrading to a warning.
Outside production an unset pin still warns once per process.

Method/path binding (ledger item 1, gap 1)
-------------------------------------------
The signed payload did not originally bind the HTTP method and upstream path
the gateway forwarded the context for, so a context minted for one route
verified identically when replayed against any other route of the same
audience/tenant/user (e.g. a signed context for ``GET /patients/{id}`` would
also verify against ``DELETE /patients/{id}``). The gateway producer
(``adaptix-gateway`` ``app/services/auth_context.py::sign_context``) now signs
``method`` (upper-cased) and ``path`` (query string stripped) into the same
payload. This module compares those claims — WHEN THE PAYLOAD CARRIES THEM —
against the actual request the caller is verifying for, via the optional
``request_method``/``request_path`` arguments to
:func:`verify_gateway_signature`.

Rollout is staged because producer and verifier deploy independently:

1. Ship this Contracts release; repin every downstream service onto it.
   Nothing changes yet — a caller that does not pass
   ``request_method``/``request_path`` gets no binding check, and a payload
   without the claims is accepted unchanged.
2. Ship the Gateway producer change so every NEW signed context carries
   ``method``/``path``. Still no enforcement — old and new payload shapes both
   verify.
3. Update each downstream call site to pass its own request's method/path
   into :func:`verify_gateway_signature`, so the binding is actually checked
   once claims are present.
4. Only once every live caller does step 3, set
   ``ADAPTIX_GATEWAY_SIGNATURE_REQUIRE_PATH=true`` on that service. From then
   on a context without ``method``/``path`` claims, or a call site that does
   not supply the actual request to compare against, fails closed
   (:class:`GatewaySignatureError` / :class:`GatewayVerifierConfigurationError`
   respectively) rather than silently skipping the check.

The flag is per-service, defaults to **off**, and only governs how an ABSENT
binding is treated. A payload that DOES carry ``method``/``path`` is always
checked against the actual request when the caller supplies one — independent
of the flag — because verifying a claim the payload already makes never
widens what is accepted.

Replay protection (ledger item 1, gap 2)
-----------------------------------------
A captured, still-valid signed context could be replayed verbatim within its
60-second TTL. :func:`verify_gateway_signature` now records each verified
context's ``jti`` in a bounded, in-process cache (keyed by ``jti``, entries
expire with the context's own ``exp``) and rejects a repeat. This is a FIRST
LAYER, not a claim of exactly-once or global replay protection. It does not protect
a horizontally-scaled service across instances: the cache is
per-process, so a context replayed against a *different* instance of a
horizontally-scaled service is not caught here. Closing that gap needs a
shared store (e.g. Redis/DynamoDB) keyed the same way, which is out of scope
for this change. A context signed without a ``jti`` (pre-jti v1 producers)
is not replay-tracked — there is nothing to key the cache on — exactly as
:func:`_verify_identity_claims` already only requires ``jti`` on v2.
"""

from __future__ import annotations

import hashlib
import heapq
import hmac
import json
import logging
import os
import re
import threading
import time
from collections.abc import Callable
from typing import Any

from adaptix_contracts.environment import ENVIRONMENT_ENV, is_production
from adaptix_contracts.gateway_keys import (
    GATEWAY_PUBLIC_KEYS_ENV,
    GATEWAY_SIGNING_ALGORITHM,
    GatewayKeyError,
    b64url_decode,
    has_verification_keys,
    load_public_keyset,
    public_key_for_kid,
)
from adaptix_contracts.service_audiences import is_known_service_audience

logger = logging.getLogger(__name__)

# One-shot log guards (reset only on process restart), kept in one mutable
# mapping so no function rebinds module globals.
_WARN_ONCE = {"audience_unpinned": False}

# Environment-variable NAMES (never values) — single source of truth for the
# consumer side, and the only definition of these names in the package.
#
# The gateway shared secret itself is NEVER stored in source. It is read from
# the process environment at call time (``gateway_shared_secret`` below) and is
# supplied in production from AWS Secrets Manager via the task definition.
# Each name is composed from ``_GATEWAY_ENV_PREFIX`` so the name/value
# distinction is explicit at the assignment site: a literal credential can no
# longer be introduced here by an edit that merely mimics the surrounding code.
_GATEWAY_ENV_PREFIX = "ADAPTIX_GATEWAY_"
GATEWAY_SHARED_SECRET_ENV = _GATEWAY_ENV_PREFIX + "SHARED_SECRET"
GATEWAY_EXPECTED_AUDIENCE_ENV = _GATEWAY_ENV_PREFIX + "EXPECTED_AUDIENCE"
GATEWAY_TRUST_MODE_ENV = _GATEWAY_ENV_PREFIX + "TRUST_MODE"
#: Makes the ``method``/``path`` binding claims mandatory when set truthy
#: (``1``/``true``/``yes``/``on``, case-insensitive). Default OFF — see the
#: "Method/path binding" section of the module docstring for the required
#: rollout order before a service may set this.
GATEWAY_SIGNATURE_REQUIRE_PATH_ENV = _GATEWAY_ENV_PREFIX + "SIGNATURE_REQUIRE_PATH"

# ENVIRONMENT_ENV and is_production are imported above from
# adaptix_contracts.environment (the canonical, single-source definition);
# both names stay importable from this module unchanged for every existing
# consumer.

# Matches the producer (auth_context.py GATEWAY_ISS) and Core verifier.
_EXPECTED_ISSUER = "adaptix-gateway"
_GATEWAY_V1_PATH = "gateway-v1"
_GATEWAY_V2_PATH = "gateway-v2"

#: Trust modes, most-secure first.
TRUST_MODE_ASYMMETRIC = "asymmetric"
TRUST_MODE_DUAL = "dual"
TRUST_MODE_HMAC = "hmac"
_TRUST_MODES = frozenset({TRUST_MODE_ASYMMETRIC, TRUST_MODE_DUAL, TRUST_MODE_HMAC})

# Clock-skew tolerance for replay window. The producer's ``verify_context``
# uses 5s; Core's ``verify_gateway_context`` uses 5s. Match them exactly.
GATEWAY_CLOCK_SKEW_SECONDS = 5

# Maximum lifetime (exp - iat) the verifier will accept, in seconds. The gateway
# producer mints 60s contexts (gateway_signing._DEFAULT_TTL_SECONDS = 60), so no
# legitimate context comes close. The ceiling exists because replay protection
# that the token's own author can opt out of is not replay protection: without
# it, any holder of the shared secret (every service verifying gateway-v1)
# could mint a context with exp = iat + 10 years — a forever-valid forged
# identity, is_founder included. Enforced at the verifier, never trusted from
# the emitter. Matches core_app.auth.gateway_context._MAX_CONTEXT_LIFETIME_SECONDS
# so the shared verifier and Core's own hand-rolled verifier agree (D-053).
_MAX_CONTEXT_LIFETIME_SECONDS = 300


class GatewaySignatureError(ValueError):
    """Raised when a present gateway signature cannot be verified.

    Callers translate this into HTTP 401. It is only raised when a signature
    IS present — an absent signature is handled by the calling dependency's
    enforcement flag, never by this function.
    """


class GatewayVerifierConfigurationError(GatewaySignatureError):
    """Raised when this service's own verifier configuration is unusable.

    Subclasses :class:`GatewaySignatureError` deliberately: every existing
    caller already maps that to 401, so a misconfigured verifier **fails
    closed** even in code that has not been taught about this type. Startup and
    readiness paths should catch this specific type instead and surface 503 —
    see :func:`assert_gateway_verifier_ready` — because the fault is a deploy
    fault, not a bad request.
    """


def gateway_shared_secret() -> str | None:
    """Return the configured gateway shared secret, or ``None`` if unset.

    Never raises: a missing secret is a configuration state the caller must
    handle, not a crash. Returns ``None`` when the env var is unset or blank.

    Deprecated by D-053. A service running in :data:`TRUST_MODE_ASYMMETRIC` has
    no use for this value and should not be injected it at all.
    """
    secret = os.environ.get(GATEWAY_SHARED_SECRET_ENV, "").strip()
    return secret or None


def gateway_trust_mode() -> str:
    """Return the effective trust mode for this process.

    An explicit ``ADAPTIX_GATEWAY_TRUST_MODE`` always wins. Unset resolves to
    :data:`TRUST_MODE_DUAL` when public keys are configured and
    :data:`TRUST_MODE_HMAC` when they are not — so distributing the public
    keyset is the single action that moves a service forward, and a service that
    has not been migrated keeps working unchanged.

    Raises:
        GatewayVerifierConfigurationError: when the variable names a mode that
            does not exist. Guessing here would silently pick a weaker mode than
            the operator asked for.
    """
    raw = os.environ.get(GATEWAY_TRUST_MODE_ENV, "").strip().lower()
    if not raw:
        return TRUST_MODE_DUAL if has_verification_keys() else TRUST_MODE_HMAC
    if raw not in _TRUST_MODES:
        raise GatewayVerifierConfigurationError(
            f"{GATEWAY_TRUST_MODE_ENV}={raw!r} is not a known trust mode "
            f"(expected one of {sorted(_TRUST_MODES)})"
        )
    return raw


def _expected_audience() -> str | None:
    """Return this service's pinned audience, validated against the registry.

    A misconfigured pin is indistinguishable from an attack at the request
    layer: every real request fails the exact-match check and the service
    returns a 401 storm that looks exactly like forged traffic. Validating the
    CONFIGURED value against ``KNOWN_SERVICE_AUDIENCES`` turns that into a
    named, actionable error at first use.

    Returns:
        The pinned audience, or ``None`` outside production when unset.

    Raises:
        GatewayVerifierConfigurationError: In production when unset (D-034 — a
            forgotten task-definition variable must not silently disable
            cross-service replay protection), or in any environment when the
            configured value does not name a live Adaptix service.
    """
    aud = os.environ.get(GATEWAY_EXPECTED_AUDIENCE_ENV, "").strip()
    if not aud:
        if is_production():
            raise GatewayVerifierConfigurationError(
                f"{GATEWAY_EXPECTED_AUDIENCE_ENV} is required in production. "
                "Without it a signed context minted for another Adaptix service "
                "is accepted here (cross-service replay). Set it to this "
                "service's own audience in the task definition."
            )
        return None
    if not is_known_service_audience(aud):
        raise GatewayVerifierConfigurationError(
            f"{GATEWAY_EXPECTED_AUDIENCE_ENV}={aud!r} does not name a live "
            "Adaptix service audience (see adaptix_contracts.service_audiences."
            "KNOWN_SERVICE_AUDIENCES). Every request would fail the audience "
            "check with this value."
        )
    return aud


def _assert_key_material_ready(mode: str) -> None:
    """Validate that ``mode``'s key material is present and parseable.

    Raises:
        GatewayVerifierConfigurationError: on missing/malformed material.
    """
    _assert_public_keys_ready(mode)
    _assert_shared_secret_ready(mode)


def _assert_public_keys_ready(mode: str) -> None:
    """Validate the gateway-v2 public keyset for modes that verify EdDSA.

    ``dual`` tolerates an absent keyset — that is the migration state, where a
    service still verifies gateway-v1 by HMAC while the public keyset is being
    distributed. ``asymmetric`` does not: with no keyset it would reject every
    request.

    Raises:
        GatewayVerifierConfigurationError: on missing/malformed material.
    """
    if mode not in (TRUST_MODE_ASYMMETRIC, TRUST_MODE_DUAL):
        return
    if not has_verification_keys():
        if mode == TRUST_MODE_ASYMMETRIC:
            raise GatewayVerifierConfigurationError(
                f"{GATEWAY_TRUST_MODE_ENV}={mode!r} requires "
                f"{GATEWAY_PUBLIC_KEYS_ENV} but it is not configured; this "
                "service would reject every gateway request"
            )
        return
    try:
        load_public_keyset()
    except GatewayKeyError as exc:
        raise GatewayVerifierConfigurationError(str(exc)) from exc


def _assert_shared_secret_ready(mode: str) -> None:
    """Validate the legacy shared secret for modes that verify gateway-v1.

    Raises:
        GatewayVerifierConfigurationError: if the secret is not configured.
    """
    if mode in (TRUST_MODE_HMAC, TRUST_MODE_DUAL) and gateway_shared_secret() is None:
        raise GatewayVerifierConfigurationError(
            f"{GATEWAY_TRUST_MODE_ENV}={mode!r} requires "
            f"{GATEWAY_SHARED_SECRET_ENV} to verify legacy gateway-v1 contexts, "
            "but it is not configured"
        )


def _warn_if_symmetric_in_production(mode: str) -> None:
    """Log the D-053 residual-risk warning for non-asymmetric production modes.

    Not fatal — ``dual`` is the deliberate migration state — but it must be
    enumerable from CloudWatch so the fleet-wide cutover can be driven from
    evidence rather than from a spreadsheet.
    """
    if is_production() and mode != TRUST_MODE_ASYMMETRIC:
        logger.warning(
            "gateway verifier running in %s=%r in production: legacy symmetric "
            "gateway-v1 contexts are still accepted, so any holder of %s can "
            "still mint an identity this service trusts (D-053). Move to %r "
            "once every caller signs gateway-v2.",
            GATEWAY_TRUST_MODE_ENV,
            mode,
            GATEWAY_SHARED_SECRET_ENV,
            TRUST_MODE_ASYMMETRIC,
        )


def assert_gateway_verifier_ready() -> None:
    """Validate this service's verifier configuration. Call at startup/readiness.

    Fails the process (or its readiness probe) rather than letting a
    misconfiguration surface later as an unexplained 401 storm, and rather than
    letting a missing audience pin silently disable replay protection (D-034).

    Raises:
        GatewayVerifierConfigurationError: on the first problem found.
    """
    mode = gateway_trust_mode()
    _expected_audience()
    _assert_key_material_ready(mode)
    _warn_if_symmetric_in_production(mode)


def _audience_names_a_live_service(aud: Any) -> bool:
    """Return whether a signed ``aud`` claim names a live Adaptix service.

    Accepts the string shape every Adaptix producer emits, and a list
    defensively (RFC 7519 §4.1.3) where at least one member must be known.

    Args:
        aud: The raw ``aud`` claim from the verified payload.

    Returns:
        ``True`` when the claim names a live service.
    """
    if isinstance(aud, str):
        return is_known_service_audience(aud)
    if isinstance(aud, list):
        return any(isinstance(a, str) and is_known_service_audience(a) for a in aud)
    return False


def has_gateway_signature(
    *,
    context_b64: str | None,
    signature_hex: str | None,
) -> bool:
    """True when both the context and signature headers carry a value."""
    return bool((context_b64 or "").strip()) and bool((signature_hex or "").strip())


def _is_v2_request(auth_path: str | None, key_id: str | None) -> bool:
    """Return whether the request presents an asymmetric (gateway-v2) context.

    A request is v2 when it says so — either by ``X-Adaptix-Auth-Path:
    gateway-v2`` or by carrying a key id. Both are attacker-controlled, which is
    exactly why this only ROUTES: claiming v2 forces asymmetric verification
    (strictly harder to forge), and claiming v1 does not escape the trust-mode
    check below. There is no header an attacker can set that downgrades a
    verifier.
    """
    if (auth_path or "").strip() == _GATEWAY_V2_PATH:
        return True
    return bool((key_id or "").strip())


def _decoded_v2_signature(signature_b64: str) -> bytes:
    """Decode a gateway-v2 signature header value.

    Raises:
        GatewaySignatureError: when the value is not base64url.
    """
    try:
        return b64url_decode(signature_b64)
    except (ValueError, TypeError) as exc:
        raise GatewaySignatureError(
            "gateway-v2 signature is not base64url-encoded"
        ) from exc


#: A hex digest and nothing else. Validated BEFORE ``hmac.compare_digest``,
#: which raises TypeError -- not a verification failure -- on a str containing
#: any non-ASCII character.
_HEX_DIGEST = re.compile(r"\A[0-9a-fA-F]+\Z")


def _require_ascii_header(value: str, what: str) -> None:
    """Reject a header value that cannot be ASCII-encoded.

    Starlette decodes header bytes as latin-1, so a caller controls whether a
    header contains a byte above 0x7F. Both verification paths encode the
    context as ASCII, and the HMAC path compares digests with
    ``hmac.compare_digest``; each raises a bare ``UnicodeEncodeError`` or
    ``TypeError`` on such input. Those are not ``GatewaySignatureError``, so
    they escape the contract every caller relies on and surface as an
    UNAUTHENTICATED 500 on every gateway-authenticated route rather than a 401.

    Raises:
        GatewaySignatureError: when ``value`` is not ASCII.
    """
    try:
        value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise GatewaySignatureError(f"{what} contains non-ASCII characters") from exc


def _verify_asymmetric(
    *, context_b64: str, signature_b64: str, key_id: str | None
) -> None:
    """Verify an Ed25519 gateway-v2 signature over ``context_b64``.

    Raises:
        GatewaySignatureError: on an unusable signature encoding or a signature
            that does not verify.
        GatewayVerifierConfigurationError: when the keyset is missing or the
            ``kid`` is unknown — a distribution fault, not a bad request, and it
            must not be reported as though the caller forged something.
    """
    kid = (key_id or "").strip()
    if not kid:
        raise GatewaySignatureError(
            "gateway-v2 context carries no key id; cannot select a verification key"
        )
    try:
        public_key = public_key_for_kid(kid)
    except GatewayKeyError as exc:
        raise GatewayVerifierConfigurationError(str(exc)) from exc

    signature = _decoded_v2_signature(signature_b64)
    if not public_key.verify(signature=signature, message=context_b64.encode("ascii")):
        raise GatewaySignatureError(
            f"{GATEWAY_SIGNING_ALGORITHM} signature mismatch — context may be "
            f"tampered, or was not signed by the gateway key {kid!r}"
        )


def _verify_hmac(
    *, context_b64: str, signature_hex: str, shared_secret: str | None
) -> None:
    """Verify the legacy symmetric gateway-v1 HMAC over ``context_b64``.

    Raises:
        GatewaySignatureError: on a signature mismatch.
        GatewayVerifierConfigurationError: when no shared secret is configured.
    """
    secret = (shared_secret or "").strip() or (gateway_shared_secret() or "")
    if not secret:
        raise GatewayVerifierConfigurationError(
            f"{GATEWAY_SHARED_SECRET_ENV} is not configured; this service cannot "
            "verify legacy gateway-v1 contexts"
        )
    signature = signature_hex.strip()
    if not _HEX_DIGEST.match(signature):
        # compare_digest raises TypeError on a str with any non-ASCII
        # character, so the shape is checked before it is reached.
        raise GatewaySignatureError("signature is not a hex digest")
    expected = hmac.new(
        secret.encode("utf-8"),
        context_b64.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected.lower(), signature.lower()):
        raise GatewaySignatureError("signature mismatch — context may be tampered")


def _verify_signature_for_scheme(
    *,
    context_b64: str,
    signature_value: str,
    shared_secret: str | None,
    auth_path: str | None,
    key_id: str | None,
    is_v2: bool,
) -> None:
    """Route to the correct signature check, gated by the trust mode.

    A header can only ever select a STRICTER path: claiming v2 forces
    asymmetric verification; claiming v1 runs into the ``asymmetric``-mode
    rejection below.

    Raises:
        GatewaySignatureError / GatewayVerifierConfigurationError: as the
            underlying checks do.
    """
    mode = gateway_trust_mode()
    if is_v2:
        if mode == TRUST_MODE_HMAC:
            raise GatewayVerifierConfigurationError(
                f"a gateway-v2 (asymmetric) context was presented but this "
                f"service runs {GATEWAY_TRUST_MODE_ENV}={mode!r}; install "
                f"{GATEWAY_PUBLIC_KEYS_ENV} so it can be verified"
            )
        _verify_asymmetric(
            context_b64=context_b64, signature_b64=signature_value, key_id=key_id
        )
        return

    if mode == TRUST_MODE_ASYMMETRIC:
        raise GatewaySignatureError(
            "legacy gateway-v1 (symmetric HMAC) context rejected: this "
            f"service runs {GATEWAY_TRUST_MODE_ENV}="
            f"{TRUST_MODE_ASYMMETRIC!r} and accepts only contexts signed by "
            "the gateway's private key (D-053)"
        )
    path = (auth_path or "").strip()
    if path and path != _GATEWAY_V1_PATH:
        raise GatewaySignatureError(f"auth path not gateway-v1 (got {path!r})")
    _verify_hmac(
        context_b64=context_b64,
        signature_hex=signature_value,
        shared_secret=shared_secret,
    )


def _decoded_payload(context_b64: str) -> dict[str, Any]:
    """Decode the (already signature-verified) context payload.

    Raises:
        GatewaySignatureError: when the payload is not a JSON object.
    """
    try:
        payload: Any = json.loads(
            b64url_decode(context_b64).decode("utf-8"),
            # Python's decoder accepts Infinity/-Infinity/NaN, which RFC 8259
            # does not define and no Adaptix producer emits. Left enabled they
            # put a float in a claim that every consumer treats as a number it
            # can compare or cast -- int(inf) raises OverflowError, which is
            # not a ValueError and so escapes this module's error contract.
            # Rejected at the boundary so it cannot reach any claim.
            parse_constant=_reject_json_constant,
        )
    except (ValueError, UnicodeDecodeError) as exc:
        raise GatewaySignatureError(f"payload decode failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise GatewaySignatureError("payload is not a JSON object")
    return payload


def _reject_json_constant(constant: str) -> None:
    """Refuse Infinity/-Infinity/NaN in a signed context.

    Raises:
        GatewaySignatureError: always; these are never valid in a context.
    """
    raise GatewaySignatureError(f"context contains invalid JSON constant: {constant}")


def _verify_replay_window(payload: dict[str, Any], clock_skew_seconds: int) -> None:
    """Enforce the ``iat``/``exp`` freshness window.

    Raises:
        GatewaySignatureError: on missing/non-integer/expired/future claims.
    """
    exp, iat = payload.get("exp"), payload.get("iat")
    if exp is None or iat is None:
        raise GatewaySignatureError("context missing exp or iat claim")
    try:
        exp_i, iat_i = int(exp), int(iat)
    except (TypeError, ValueError, OverflowError) as exc:
        # OverflowError is int(float("inf")). Unreachable now that the decoder
        # rejects those constants, but this cast is the load-bearing one and an
        # uncaught type here is an unauthenticated 500 rather than a 401.
        raise GatewaySignatureError("exp/iat claims are not integers") from exc

    # exp must not precede iat (a malformed or hostile window), and the issued
    # lifetime must not exceed the ceiling — both independent of the current
    # clock, so a forged long-lived context is rejected regardless of when it
    # is presented. Core's verifier enforces the identical pair.
    if exp_i < iat_i:
        raise GatewaySignatureError(
            f"context exp precedes iat (exp={exp_i}, iat={iat_i})"
        )
    if exp_i - iat_i > _MAX_CONTEXT_LIFETIME_SECONDS:
        raise GatewaySignatureError(
            f"context lifetime {exp_i - iat_i}s exceeds the maximum "
            f"{_MAX_CONTEXT_LIFETIME_SECONDS}s (exp={exp_i}, iat={iat_i})"
        )

    now = int(time.time())
    if now > exp_i + clock_skew_seconds:
        raise GatewaySignatureError(
            f"context expired (exp={exp_i}, now={now}, skew={clock_skew_seconds}s)"
        )
    if iat_i > now + clock_skew_seconds:
        raise GatewaySignatureError(
            f"context issued in the future (iat={iat_i}, now={now})"
        )


def _verify_identity_claims(payload: dict[str, Any], *, is_v2: bool) -> None:
    """Require the identity claims the platform depends on.

    ``jti`` is required on v2 only: v1 producers predate it and requiring it
    there would 401 traffic this migration exists to keep alive. On v2 it is
    the anti-replay handle, so a context without one is refused outright.

    Raises:
        GatewaySignatureError: on a missing claim.
    """
    for claim in ("user_id", "tenant_id"):
        if not payload.get(claim):
            raise GatewaySignatureError(f"context missing required claim: {claim!r}")
    if is_v2 and not payload.get("jti"):
        raise GatewaySignatureError("gateway-v2 context missing required claim: 'jti'")


def _require_path_binding() -> bool:
    """Return whether ``ADAPTIX_GATEWAY_SIGNATURE_REQUIRE_PATH`` is set truthy."""
    raw = os.environ.get(GATEWAY_SIGNATURE_REQUIRE_PATH_ENV, "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _normalize_path(path: str) -> str:
    """Strip a query string and fragment from ``path`` for signed comparison.

    Matches the producer's normalization (``request.url.path`` already
    excludes the query string in Starlette, but a defensive strip keeps this
    side correct even for a caller that passes a raw ``PATH_INFO``-style
    value that has not been through that framework).
    """
    bare = path.split("?", 1)[0].split("#", 1)[0]
    # Producer and consumer frameworks may disagree on a trailing slash
    # (redirect_slashes, mounted routers); both sides are compared after the
    # same normalization so that difference can never fail a genuine request.
    return bare.rstrip("/") or "/"


def _verify_method_path_binding(
    payload: dict[str, Any],
    *,
    request_method: str | None,
    request_path: str | None,
) -> None:
    """Enforce the signed ``method``/``path`` binding, when applicable.

    See the "Method/path binding" section of the module docstring for the
    full rollout contract. Summary:

    * Payload carries neither claim: accepted unless
      :func:`_require_path_binding` is true, in which case it fails closed —
      the producer has not been upgraded yet but this service now demands it.
    * Payload carries the claim(s) and the caller supplies
      ``request_method``/``request_path``: always compared, regardless of the
      flag — a claim the payload itself makes is never left unchecked.
    * Payload carries the claim(s) but the caller supplies neither: accepted
      when the flag is off (nothing to compare against yet); fails closed
      when the flag is on, because the flag is the operator's declaration
      that every call site has been wired to supply the real request.

    Raises:
        GatewaySignatureError: the signed method or path does not match the
            actual request.
        GatewayVerifierConfigurationError: the flag requires the binding but
            either the payload was signed without it, or this call site does
            not supply the actual request to check it against.
    """
    signed_method = payload.get("method")
    signed_path = payload.get("path")
    require = _require_path_binding()
    if signed_method is None and signed_path is None:
        _reject_if_binding_required(
            require, "the signed context carries no method/path binding"
        )
        return
    if request_method is None or request_path is None:
        if require:
            raise GatewayVerifierConfigurationError(
                f"{GATEWAY_SIGNATURE_REQUIRE_PATH_ENV} is enabled but this "
                "verifier was not given request_method/request_path to check "
                "the signed binding against; pass the inbound request's method "
                "and path"
            )
        return
    _compare_method_path(signed_method, signed_path, request_method, request_path)


def _reject_if_binding_required(require: bool, reason: str) -> None:
    """Fail closed when the require-path flag is set but no binding is present."""
    if require:
        raise GatewaySignatureError(
            f"{GATEWAY_SIGNATURE_REQUIRE_PATH_ENV} is enabled but {reason}; "
            "the gateway producer must be upgraded before this service can require it"
        )


def _compare_method_path(
    signed_method: Any, signed_path: Any, request_method: str, request_path: str
) -> None:
    """Compare signed method/path claims against the inbound request."""
    if not isinstance(signed_method, str) or not isinstance(signed_path, str):
        raise GatewaySignatureError(
            "context method/path claims are not strings — cannot verify binding"
        )
    if signed_method.upper() != request_method.strip().upper():
        raise GatewaySignatureError(
            f"signed method {signed_method!r} does not match request method "
            f"{request_method!r}"
        )
    normalized_signed = _normalize_path(signed_path)
    normalized_request = _normalize_path(request_path)
    if normalized_signed != normalized_request:
        raise GatewaySignatureError(
            f"signed path {signed_path!r} does not match request path "
            f"{normalized_request!r}"
        )


#: Bounded in-process replay cache: ``jti`` -> the context's own ``exp``
#: (unix seconds), so an entry is pruned once the context it guarded would
#: have expired anyway. A hard cap on entry count exists so an attacker who
#: can present many distinct signed contexts (e.g. from a genuinely high-QPS
#: legitimate caller) cannot grow this dict without bound; hitting the cap
#: fails closed (raises) rather than silently disabling replay tracking.
#:
#: Pruning is a min-heap of ``(exp, jti)`` ordered by expiry, NOT a scan of
#: the dict. Codacy flagged the prior implementation for doing an O(N) scan
#: of up to 50,000 entries under the global lock on every verification
#: call — real lock-contention/DoS risk across the 50+ services sharing
#: this library. A heap lets pruning touch only entries that have ACTUALLY
#: expired, popping the front while it is stale, so the amortized cost per
#: entry is one push (O(log n)) and at most one pop (O(log n)), each paid
#: exactly once over that entry's life — never a full-cache walk. The dict
#: and heap are kept 1:1 for every live jti: an unexpired jti is rejected
#: as a replay before any push happens (see :func:`_check_and_record_replay`),
#: and an expired jti is always popped and deleted before a new entry for
#: the same jti is pushed, so no stale heap tuple can ever outlive the dict
#: entry it was superseded by.
_MAX_REPLAY_CACHE_ENTRIES = 50_000
_replay_seen: dict[str, int] = {}
_replay_expiry_heap: list[tuple[int, str]] = []
_replay_lock = threading.Lock()


def reset_gateway_replay_cache_for_tests() -> None:
    """Clear the replay cache. Test-only — production code never calls this."""
    with _replay_lock:
        _replay_seen.clear()
        _replay_expiry_heap.clear()


def _prune_expired_locked(now: int) -> None:
    """Pop and drop entries whose guarded context has already expired.

    Caller must hold ``_replay_lock``. Only touches entries that are
    actually expired — it stops the instant the heap's earliest expiry is
    still in the future — so cost is bounded by how many entries expired
    since the last call, never by how many live entries the cache holds.
    """
    while _replay_expiry_heap and _replay_expiry_heap[0][0] < now:
        exp, jti = heapq.heappop(_replay_expiry_heap)
        # The dict is authoritative. A popped tuple only matches a real,
        # still-current entry when its exp is unchanged; a jti reused after
        # its prior entry already expired carries its own newer heap tuple,
        # so this stale one is simply discarded without touching the dict.
        if _replay_seen.get(jti) == exp:
            del _replay_seen[jti]


def _context_expiry(payload: dict[str, Any], now: int) -> int:
    """The context's ``exp`` as an int, or ``now`` + clock skew when absent/invalid."""
    try:
        return int(payload["exp"])
    except (KeyError, TypeError, ValueError):
        return now + GATEWAY_CLOCK_SKEW_SECONDS


def _check_and_record_replay(payload: dict[str, Any]) -> None:
    """Reject a context whose ``jti`` this process has already verified.

    Only a FIRST layer — see the "Replay protection" section of the module
    docstring for why this does not protect a horizontally-scaled service
    across instances. A payload without a ``jti`` (pre-jti v1 producers) is
    not tracked: there is nothing to key the cache on, and
    :func:`_verify_identity_claims` already lets v1 through without one.

    Raises:
        GatewaySignatureError: this ``jti`` was already verified and has not
            yet expired (replay), or the cache is full and cannot safely
            record a new entry.
    """
    jti = payload.get("jti")
    if not jti or not isinstance(jti, str):
        return

    now = int(time.time())
    exp = _context_expiry(payload, now)

    with _replay_lock:
        _prune_expired_locked(now)
        existing = _replay_seen.get(jti)
        if existing is not None and existing >= now:
            raise GatewaySignatureError(f"context jti {jti!r} already used (replay)")
        if len(_replay_seen) >= _MAX_REPLAY_CACHE_ENTRIES:
            # Still full after pruning what has actually expired. Failing
            # closed here is deliberate: silently skipping the record would
            # look like normal operation while quietly disabling replay
            # protection for every request that follows.
            raise GatewaySignatureError(
                "gateway signature replay cache is full; refusing to verify "
                "without replay protection"
            )
        _replay_seen[jti] = exp
        heapq.heappush(_replay_expiry_heap, (exp, jti))


def verify_gateway_signature(
    *,
    context_b64: str,
    signature_hex: str,
    shared_secret: str | None = None,
    auth_path: str | None = None,
    key_id: str | None = None,
    clock_skew_seconds: int = GATEWAY_CLOCK_SKEW_SECONDS,
    request_method: str | None = None,
    request_path: str | None = None,
) -> dict[str, Any]:
    """Verify a signed gateway auth context. Raises on any failure.

    Scheme selection is by ``auth_path``/``key_id`` (see :func:`_is_v2_request`)
    and is then gated by :func:`gateway_trust_mode`, so a header can only ever
    select a STRICTER path, never a weaker one.

    Steps, after the signature verifies:

    1. ``iss`` must equal ``"adaptix-gateway"``.
    2. ``aud`` must be present and name a live Adaptix service, and must equal
       ``ADAPTIX_GATEWAY_EXPECTED_AUDIENCE`` when that is set (always, in
       production — D-034).
    3. ``iat``/``exp`` replay window with ``clock_skew_seconds`` tolerance.
    4. ``user_id``/``tenant_id`` must be present; ``jti`` is additionally
       required on gateway-v2.
    5. ``method``/``path`` binding, when the payload carries those claims —
       see :func:`_verify_method_path_binding` and the module docstring.
    6. Single-process replay: this exact ``jti`` must not have been verified
       before — see :func:`_check_and_record_replay` and the module docstring.

    Args:
        context_b64: Value of ``X-Adaptix-Auth-Context``.
        signature_hex: Value of ``X-Adaptix-Auth-Signature`` — hex for
            gateway-v1, base64url for gateway-v2. The parameter keeps its
            historical name so existing call sites are unchanged.
        shared_secret: ``ADAPTIX_GATEWAY_SHARED_SECRET`` value, for gateway-v1
            only. Optional: falls back to the environment, and is not consulted
            at all for gateway-v2.
        auth_path: Value of ``X-Adaptix-Auth-Path``. ``"gateway-v2"`` selects
            asymmetric verification; ``"gateway-v1"`` (or ``None``, which the
            legacy gateway emits on some code paths) selects HMAC.
        key_id: Value of ``X-Adaptix-Auth-Key-Id`` — the ``kid`` of the gateway
            signing key. Required for gateway-v2.
        clock_skew_seconds: Replay-window tolerance. Default 5s.
        request_method: The actual inbound request's HTTP method (e.g.
            ``"GET"``), for the method/path binding check. Optional; when
            omitted the binding check is a no-op unless
            ``ADAPTIX_GATEWAY_SIGNATURE_REQUIRE_PATH`` is set, in which case
            omitting it is a verifier configuration error.
        request_path: The actual inbound request's path (no query string), for
            the same check.

    Returns:
        The verified payload dict.

    Raises:
        GatewaySignatureError: on any verification failure.
        GatewayVerifierConfigurationError: when this service's own verifier
            configuration prevents the check from being made.
    """
    ctx = (context_b64 or "").strip()
    sig = (signature_hex or "").strip()
    if not ctx or not sig:
        raise GatewaySignatureError("context or signature header missing")
    # Both schemes sign the context as ASCII bytes; a non-ASCII character here
    # raises UnicodeEncodeError deep inside either path.
    _require_ascii_header(ctx, "auth context header")

    is_v2 = _is_v2_request(auth_path, key_id)
    _verify_signature_for_scheme(
        context_b64=ctx,
        signature_value=sig,
        shared_secret=shared_secret,
        auth_path=auth_path,
        key_id=key_id,
        is_v2=is_v2,
    )

    # Only reached once the signature is proven, so the payload below is
    # authenticated bytes, not attacker-chosen JSON.
    payload = _decoded_payload(ctx)
    if payload.get("iss") != _EXPECTED_ISSUER:
        raise GatewaySignatureError(
            f"unexpected issuer {payload.get('iss')!r} (expected {_EXPECTED_ISSUER!r})"
        )
    _verify_audience(payload)
    _verify_replay_window(payload, clock_skew_seconds)
    _verify_identity_claims(payload, is_v2=is_v2)
    _verify_method_path_binding(
        payload, request_method=request_method, request_path=request_path
    )
    _check_and_record_replay(payload)
    return payload


#: Attribute name under which the per-request verified-assertion cache lives on
#: ``request.state``. Starlette creates a fresh ``state`` for every request, so
#: this cache is inherently request-scoped: it cannot outlive, leak into, or be
#: observed from another request. Never read or write this on any longer-lived
#: object.
_REQUEST_VERIFIED_ATTR = "_adaptix_gateway_verified_assertions"


def _request_scope(request: Any) -> tuple[str | None, str | None, Any]:
    """Pull ``(method, path, state)`` defensively from a request object.

    Returns ``(None, None, None)`` when ``request`` is ``None`` or lacks the
    attributes. Isolated from :func:`verify_gateway_signature_for_request` so
    that function reads as the verify-once DECISION rather than as Starlette
    attribute plumbing.
    """
    if request is None:
        return None, None, None
    method = getattr(request, "method", None)
    url = getattr(request, "url", None)
    path = getattr(url, "path", None) if url is not None else None
    state = getattr(request, "state", None)
    return method, path, state


def _verified_once_in_scope(
    state: Any, key: tuple[Any, ...], verify: Callable[[], dict[str, Any]]
) -> dict[str, Any]:
    """Return the assertion verified once within this request scope.

    The per-request cache lives on ``state`` (``request.state``). The first call
    for ``key`` runs ``verify`` -- the full crypto verification, which records
    the single-use replay entry -- and stores the payload; later calls for the
    same key return it without re-verifying. Only a SUCCESSFUL verification is
    cached: ``verify`` raising ``GatewaySignatureError`` propagates and records
    nothing, so a later check re-attempts and is rejected identically.
    """
    cache = getattr(state, _REQUEST_VERIFIED_ATTR, None)
    if cache is None:
        cache = {}
        setattr(state, _REQUEST_VERIFIED_ATTR, cache)
    cached = cache.get(key)
    if cached is not None:
        return cached
    payload = verify()
    cache[key] = payload
    return payload


def verify_gateway_signature_for_request(
    request: Any,
    *,
    context_b64: str,
    signature_hex: str,
    shared_secret: str | None = None,
    auth_path: str | None = None,
    key_id: str | None = None,
    clock_skew_seconds: int = GATEWAY_CLOCK_SKEW_SECONDS,
) -> dict[str, Any]:
    """Verify the gateway auth assertion EXACTLY ONCE for one request, then reuse.

    This is the request-authentication boundary. The FIRST
    authentication-dependent check in a request (whichever of the module
    entitlement gate or ``get_auth_context`` runs first) performs the full
    :func:`verify_gateway_signature` -- signature, issuer, audience, replay
    window, identity, method/path binding, AND the single-use replay recording
    -- and binds the verified payload to ``request.state``. Every later check in
    the SAME request that presents the SAME assertion receives that verified
    payload without re-verifying and without re-touching the replay guard.

    WHY THIS EXISTS. Contracts >= 5.2.0 records each verified assertion as
    single-use. A legitimate request that was verified by two different
    authentication-dependent checks (the entitlement gate, then
    ``get_auth_context``) therefore had its second verification rejected as a
    replay, 401-ing a legitimate request. Verification was scoped to each
    authorization check instead of to the request. This scopes it to the
    request, so any number of authorization / entitlement / tenancy / RBAC /
    ABAC checks consume ONE verified principal.

    REPLAY PROTECTION IS UNCHANGED ACROSS REQUESTS, AND THAT IS THE POINT.
    ``request.state`` is created fresh by Starlette for every request, so a
    genuinely separate request -- including one that replays an assertion --
    has an empty cache, calls :func:`verify_gateway_signature` itself, and is
    rejected by the single-use replay guard exactly as before. The reuse here
    is confined to repeated cryptographic verification WITHIN one already
    authenticated request; it can never span requests, users, tenants,
    processes, or time.

    The method/path binding is derived from ``request`` itself, so the single
    verification always binds against the real inbound method and path -- the
    strictest of the two former call sites, applied consistently.

    ``request`` is required for the once-per-request guarantee. When it is
    ``None`` -- a non-HTTP caller with no request scope, e.g. a worker or a unit
    test invoking the dependency directly -- this performs the full verification
    directly, identical to calling :func:`verify_gateway_signature`, because
    there is no request boundary to fold a second verification into.
    """
    method, path, state = _request_scope(request)

    def _verify() -> dict[str, Any]:
        return verify_gateway_signature(
            context_b64=context_b64,
            signature_hex=signature_hex,
            shared_secret=shared_secret,
            auth_path=auth_path,
            key_id=key_id,
            clock_skew_seconds=clock_skew_seconds,
            request_method=method,
            request_path=path,
        )

    # No request, or a request object without ``state`` (defensive): there is no
    # request scope to cache in, so verify directly. This is NOT a weakening --
    # without a request there is no second in-request verification to fold, and
    # the full replay guard still runs.
    if state is None:
        return _verify()

    # Key on the assertion identity. Two checks in one request present the same
    # context+signature (and the same path/key-id), so they hit the same entry;
    # a request carrying a different assertion verifies it independently rather
    # than borrow an unrelated principal.
    key = (context_b64, signature_hex, auth_path, key_id)
    return _verified_once_in_scope(state, key, _verify)


def _check_audience_pin(signed_aud: Any, expected_aud: str) -> None:
    """Enforce the exact per-service audience pin.

    Raises:
        GatewaySignatureError: when the signed audience is not this service's.
    """
    if isinstance(signed_aud, list):
        if expected_aud not in signed_aud:
            raise GatewaySignatureError(
                f"audience {signed_aud!r} does not include {expected_aud!r}"
            )
    elif signed_aud != expected_aud:
        raise GatewaySignatureError(
            f"unexpected audience {signed_aud!r} (expected {expected_aud!r})"
        )


def _warn_audience_unpinned(signed_aud: Any) -> None:
    """Warn once per process that the audience pin is not configured.

    Non-production only: warn so the services still missing the variable can
    be enumerated from CloudWatch before they are promoted.
    """
    if _WARN_ONCE["audience_unpinned"]:
        return
    logger.warning(
        "gateway context carries a signed audience %r but %s is not "
        "configured, so the audience is NOT verified; a context minted "
        "for another service would be accepted here. Set %s to this "
        "service's audience to close cross-service replay.",
        signed_aud,
        GATEWAY_EXPECTED_AUDIENCE_ENV,
        GATEWAY_EXPECTED_AUDIENCE_ENV,
    )
    _WARN_ONCE["audience_unpinned"] = True


def _verify_audience(payload: dict[str, Any]) -> None:
    """Apply the three audience layers to a verified payload.

    Layers 1-2 (presence, registry membership) are enforced for every service,
    pinned or not — every legitimate producer already satisfies them, so this
    rejects only contexts no Adaptix producer emits. Layer 3 (exact pin) is the
    only layer that stops cross-service replay and is mandatory in production
    (D-034).

    Raises:
        GatewaySignatureError: when the signed audience is absent, unknown, or
            not this service's.
        GatewayVerifierConfigurationError: when the pin itself is unusable
            (unset in production, or naming a service that does not exist).
    """
    signed_aud = payload.get("aud")
    if not signed_aud:
        raise GatewaySignatureError("context missing required claim: 'aud'")
    if not _audience_names_a_live_service(signed_aud):
        raise GatewaySignatureError(
            f"audience {signed_aud!r} does not name a live Adaptix service"
        )

    expected_aud = _expected_audience()
    if expected_aud is not None:
        _check_audience_pin(signed_aud, expected_aud)
    else:
        _warn_audience_unpinned(signed_aud)


__all__ = [
    "ENVIRONMENT_ENV",
    "GATEWAY_CLOCK_SKEW_SECONDS",
    "GATEWAY_EXPECTED_AUDIENCE_ENV",
    "GATEWAY_SHARED_SECRET_ENV",
    "GATEWAY_SIGNATURE_REQUIRE_PATH_ENV",
    "GATEWAY_TRUST_MODE_ENV",
    "TRUST_MODE_ASYMMETRIC",
    "TRUST_MODE_DUAL",
    "TRUST_MODE_HMAC",
    "GatewaySignatureError",
    "GatewayVerifierConfigurationError",
    "assert_gateway_verifier_ready",
    "gateway_shared_secret",
    "gateway_trust_mode",
    "has_gateway_signature",
    "is_production",
    "reset_gateway_replay_cache_for_tests",
    "verify_gateway_signature",
    "verify_gateway_signature_for_request",
]
