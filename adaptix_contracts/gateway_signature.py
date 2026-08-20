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
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from typing import Any

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

#: Name of the variable that declares the deployment environment. Production is
#: the only value that makes the audience pin mandatory, so it is read here
#: rather than inferred from anything ambient.
ENVIRONMENT_ENV = "ENVIRONMENT"

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


def is_production() -> bool:
    """Return whether this process is running in the production environment."""
    return os.environ.get(ENVIRONMENT_ENV, "").strip().lower() in {"production", "prod"}


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
    if mode in (TRUST_MODE_ASYMMETRIC, TRUST_MODE_DUAL):
        if not has_verification_keys():
            if mode == TRUST_MODE_ASYMMETRIC:
                raise GatewayVerifierConfigurationError(
                    f"{GATEWAY_TRUST_MODE_ENV}={mode!r} requires "
                    f"{GATEWAY_PUBLIC_KEYS_ENV} but it is not configured; this "
                    "service would reject every gateway request"
                )
        else:
            try:
                load_public_keyset()
            except GatewayKeyError as exc:
                raise GatewayVerifierConfigurationError(str(exc)) from exc

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
    expected = hmac.new(
        secret.encode("utf-8"),
        context_b64.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected.lower(), signature_hex.lower()):
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
        payload: Any = json.loads(b64url_decode(context_b64).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise GatewaySignatureError(f"payload decode failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise GatewaySignatureError("payload is not a JSON object")
    return payload


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
    except (TypeError, ValueError) as exc:
        raise GatewaySignatureError("exp/iat claims are not integers") from exc

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


def verify_gateway_signature(
    *,
    context_b64: str,
    signature_hex: str,
    shared_secret: str | None = None,
    auth_path: str | None = None,
    key_id: str | None = None,
    clock_skew_seconds: int = GATEWAY_CLOCK_SKEW_SECONDS,
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
    return payload


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
    "verify_gateway_signature",
]
