"""Gateway signed-auth-context verifier for downstream Adaptix services.

This is the *consumer* (verify) side of the gateway → downstream auth
contract. The Adaptix gateway validates the external Cognito JWT at the edge,
then stamps every authenticated request with an HMAC-signed internal context
so downstream services can trust the injected identity headers WITHOUT
re-validating the JWT.

Byte-compatible source of truth
-------------------------------
The signing scheme implemented here is copied byte-for-byte from the gateway
producer and the existing Core verifier so a real gateway-signed request
verifies and a forged one does not:

* Producer:
  ``Adaptix-Core-Service/adaptix-gateway/backend/app/services/auth_context.py``
  -> ``sign_context`` (payload serialize + HMAC) and ``verify_context``
  (reference verify), and ``sign_legacy_gateway_headers`` (legacy ts/sig).
* Core verifier:
  ``Adaptix-Core-Service/core/backend/core_app/auth/gateway_context.py``
  -> ``verify_gateway_context``.

Contract
--------
Gateway signs with ``HMAC-SHA256(shared_secret, context_b64)`` and sends:

  X-Adaptix-Auth-Context    : base64url(JSON payload), no ``=`` padding
  X-Adaptix-Auth-Signature  : hex(HMAC-SHA256(shared_secret, context_b64))
  X-Adaptix-Auth-Path       : "gateway-v1"

Payload claims (json.dumps(payload, separators=(",", ":"), sort_keys=True)):
  sub, user_id, tenant_id, agency_id, email, roles, scopes,
  iss="adaptix-gateway", aud=<downstream-service>, iat, exp, jti

Audience handling
-----------------
``adaptix-contracts`` is a SHARED package consumed by ~52 services, each with
its own ``aud`` (``adaptix-core``, ``adaptix-epcr``, ``adaptix-billing`` ...).
This verifier therefore does NOT pin a single audience by default — doing so
would break every service whose audience is not the hardcoded value. A service
that wants audience-pinning (defense-in-depth against cross-service replay)
sets ``ADAPTIX_GATEWAY_EXPECTED_AUDIENCE`` to its own audience string; when set,
the ``aud`` claim must match (string-equal, or membership when the claim is a
list). When unset, the signature + issuer + replay-window checks still fully
close the in-VPC identity-spoofing path this verifier exists to fix.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

# One-shot guard so the unpinned-audience warning below does not flood logs on
# every request. Reset only on process restart.
_warned_audience_unpinned = False

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

# Matches the producer (auth_context.py GATEWAY_ISS) and Core verifier.
_EXPECTED_ISSUER = "adaptix-gateway"
_GATEWAY_V1_PATH = "gateway-v1"

# Clock-skew tolerance for replay window. The producer's ``verify_context``
# uses 5s; Core's ``verify_gateway_context`` uses 5s. Match them exactly.
GATEWAY_CLOCK_SKEW_SECONDS = 5


class GatewaySignatureError(ValueError):
    """Raised when a present gateway signature cannot be verified.

    Callers translate this into HTTP 401. It is only raised when a signature
    IS present — an absent signature is handled by the calling dependency's
    enforcement flag, never by this function.
    """


def gateway_shared_secret() -> str | None:
    """Return the configured gateway shared secret, or ``None`` if unset.

    Never raises: a missing secret is a configuration state the caller must
    handle (allow-with-warning), not a crash. Returns ``None`` when the env
    var is unset or blank.
    """
    secret = os.environ.get(GATEWAY_SHARED_SECRET_ENV, "").strip()
    return secret or None


def _expected_audience() -> str | None:
    aud = os.environ.get(GATEWAY_EXPECTED_AUDIENCE_ENV, "").strip()
    return aud or None


def _b64url_decode(value: str) -> bytes:
    # Restore padding exactly as the producer/Core verifier do.
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def has_gateway_signature(
    *,
    context_b64: str | None,
    signature_hex: str | None,
) -> bool:
    """True when both the context and signature headers carry a value."""
    return bool((context_b64 or "").strip()) and bool((signature_hex or "").strip())


def verify_gateway_signature(
    *,
    context_b64: str,
    signature_hex: str,
    shared_secret: str,
    auth_path: str | None = None,
    clock_skew_seconds: int = GATEWAY_CLOCK_SKEW_SECONDS,
) -> dict[str, Any]:
    """Verify an HMAC-signed gateway auth context. Raises on any failure.

    Implements the EXACT scheme of the gateway producer ``sign_context`` and
    the Core verifier ``verify_gateway_context``:

    1. ``expected = hex(HMAC-SHA256(shared_secret, context_b64.encode("ascii")))``
       compared timing-safely against ``signature_hex``.
    2. base64url-decode ``context_b64`` (padding restored) -> JSON payload.
    3. ``iss`` must equal ``"adaptix-gateway"``.
    4. ``aud`` checked ONLY when ``ADAPTIX_GATEWAY_EXPECTED_AUDIENCE`` is set
       (string-equal or list-membership).
    5. ``iat``/``exp`` replay window with ``clock_skew_seconds`` tolerance.
    6. ``user_id``/``tenant_id`` claims must be present.

    Args:
        context_b64: Value of ``X-Adaptix-Auth-Context``.
        signature_hex: Value of ``X-Adaptix-Auth-Signature``.
        shared_secret: ``ADAPTIX_GATEWAY_SHARED_SECRET`` value.
        auth_path: Value of ``X-Adaptix-Auth-Path``. When provided and
            non-empty it must equal ``"gateway-v1"``; when ``None`` the check
            is skipped (the legacy gateway emits the context headers without
            always setting the path header on every code path).
        clock_skew_seconds: Replay-window tolerance. Default 5s.

    Returns:
        The verified payload dict.

    Raises:
        GatewaySignatureError on any verification failure.
    """
    ctx = (context_b64 or "").strip()
    sig = (signature_hex or "").strip()
    if not ctx or not sig:
        raise GatewaySignatureError("context or signature header missing")

    if auth_path is not None:
        ap = auth_path.strip()
        if ap and ap != _GATEWAY_V1_PATH:
            raise GatewaySignatureError(f"auth path not gateway-v1 (got {ap!r})")

    # 1. Timing-safe HMAC-SHA256 over the base64url context string (ascii).
    try:
        expected = hmac.new(
            shared_secret.encode("utf-8"),
            ctx.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
    except Exception as exc:  # noqa: BLE001 — surface as a verify failure, never crash
        raise GatewaySignatureError(f"HMAC computation failed: {exc}") from exc

    if not hmac.compare_digest(expected.lower(), sig.lower()):
        raise GatewaySignatureError("signature mismatch — context may be tampered")

    # 2. Decode + parse payload.
    try:
        raw = _b64url_decode(ctx)
        payload: Any = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise GatewaySignatureError(f"payload decode failed: {exc}") from exc

    if not isinstance(payload, dict):
        raise GatewaySignatureError("payload is not a JSON object")

    # 3. Issuer.
    if payload.get("iss") != _EXPECTED_ISSUER:
        raise GatewaySignatureError(
            f"unexpected issuer {payload.get('iss')!r} (expected {_EXPECTED_ISSUER!r})"
        )

    # 4. Audience — opt-in per service.
    expected_aud = _expected_audience()
    if expected_aud is not None:
        aud = payload.get("aud")
        if isinstance(aud, list):
            if expected_aud not in aud:
                raise GatewaySignatureError(
                    f"audience {aud!r} does not include {expected_aud!r}"
                )
        elif aud != expected_aud:
            raise GatewaySignatureError(
                f"unexpected audience {aud!r} (expected {expected_aud!r})"
            )
    else:
        # OBSERVABILITY — AX5-00036 (gateway Cognito audience bypass).
        #
        # The gateway signs a PER-ROUTE audience into every context it mints
        # (``_audience_for_path`` -> ``sign_context(audience=...)`` in
        # ``Adaptix-Gateway/backend/app/middleware/cognito_auth.py``). For a
        # Cognito token the gateway then SKIPS its own audience enforcement,
        # because a Cognito JWT carries ``aud=<client_id>`` and never a service
        # audience — so gateway-side enforcement is impossible by construction
        # and this consumer-side check is the ONLY place the signed audience can
        # actually be verified.
        #
        # That makes an unset ``ADAPTIX_GATEWAY_EXPECTED_AUDIENCE`` a SILENT
        # hole: the audience is signed but checked at neither end, so a context
        # minted for one service is replayable against another. Silence is the
        # real problem — the gap looks identical to a correctly-pinned service
        # in logs. Warn once per process so the services still missing the
        # variable can be enumerated from CloudWatch, which is the precondition
        # for installing it fleet-wide and then removing the gateway bypass.
        #
        # Deliberately WARN and not raise: rejecting here would 401 every
        # service that has not yet had the variable installed, which is the
        # outage this sequencing exists to avoid.
        global _warned_audience_unpinned
        if not _warned_audience_unpinned and payload.get("aud"):
            logger.warning(
                "gateway context carries a signed audience %r but %s is not "
                "configured, so the audience is NOT verified; a context minted "
                "for another service would be accepted here. Set %s to this "
                "service's audience to close cross-service replay.",
                payload.get("aud"),
                GATEWAY_EXPECTED_AUDIENCE_ENV,
                GATEWAY_EXPECTED_AUDIENCE_ENV,
            )
            _warned_audience_unpinned = True

    # 5. Replay window.
    exp = payload.get("exp")
    iat = payload.get("iat")
    if exp is None or iat is None:
        raise GatewaySignatureError("context missing exp or iat claim")
    try:
        exp_i = int(exp)
        iat_i = int(iat)
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

    # 6. Required identity claims.
    for claim in ("user_id", "tenant_id"):
        if not payload.get(claim):
            raise GatewaySignatureError(f"context missing required claim: {claim!r}")

    return payload


__all__ = [
    "GATEWAY_CLOCK_SKEW_SECONDS",
    "GATEWAY_EXPECTED_AUDIENCE_ENV",
    "GATEWAY_SHARED_SECRET_ENV",
    "GatewaySignatureError",
    "gateway_shared_secret",
    "has_gateway_signature",
    "verify_gateway_signature",
]
