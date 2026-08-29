"""Canonical Gateway identity-signature protocol.

Every producer and verifier of Adaptix Gateway identity proof MUST use this
package. Local HMAC copies in domain services are forbidden: they drift.

Two on-the-wire schemes exist. Both live here so they cannot diverge.

1. Modern signed context (gateway-v1 HMAC / gateway-v2 Ed25519)
   Headers: ``X-Adaptix-Auth-Context`` + ``X-Adaptix-Auth-Signature``
   Implementation: :mod:`adaptix_contracts.gateway_signing` (sign) and
   :mod:`adaptix_contracts.gateway_signature` (verify). Re-exported below.

2. Legacy identity HMAC (ALB-direct services that still read the old headers)
   Headers: ``X-Adaptix-Gateway-Timestamp`` + ``X-Adaptix-Gateway-Signature``
   Canonical payload: ``"{timestamp}.{user_id}.{tenant_id}.{email}"``
   HMAC-SHA256 hex digest, 300s timestamp tolerance.
   Implementation: :func:`sign_legacy_identity` / :func:`verify_legacy_identity`.

Consumers (Office Ally, Payments modern path, other ALB-direct services) verify
the same contract the Gateway signs. Do not reimplement timestamp tolerance,
payload construction, or the HMAC algorithm in a service tree.
"""

from __future__ import annotations

import hashlib
import hmac
import time

from adaptix_contracts.gateway_signature import (
    GATEWAY_CLOCK_SKEW_SECONDS,
    GATEWAY_EXPECTED_AUDIENCE_ENV,
    GATEWAY_SHARED_SECRET_ENV,
    GatewaySignatureError,
    GatewayVerifierConfigurationError,
    has_gateway_signature,
    verify_gateway_signature,
)
from adaptix_contracts.gateway_signing import (
    HEADER_AUTH_CONTEXT,
    HEADER_AUTH_KEY_ID,
    HEADER_AUTH_PATH,
    HEADER_AUTH_SIGNATURE,
    GatewayClaims,
    build_gateway_signed_headers,
    sign_claims_hmac,
    sign_gateway_context,
)

HEADER_LEGACY_TIMESTAMP = "X-Adaptix-Gateway-Timestamp"
HEADER_LEGACY_SIGNATURE = "X-Adaptix-Gateway-Signature"

# Matches Adaptix-Gateway ``sign_legacy_gateway_headers`` and the historical
# Office Ally / Crew verifiers. Changing this value is a fleet-wide break.
LEGACY_TIMESTAMP_TOLERANCE_SECONDS = 300


class GatewayIdentityError(ValueError):
    """Base failure for the Gateway identity-signature protocol."""

    code: str = "gateway_identity_error"


class GatewayIdentityMissing(GatewayIdentityError):
    """Timestamp or signature header is absent."""

    code = "missing_gateway_signature"


class GatewayIdentityInvalidTimestamp(GatewayIdentityError):
    """Timestamp is not an integer unix epoch."""

    code = "invalid_gateway_timestamp"


class GatewayIdentityExpired(GatewayIdentityError):
    """Timestamp is outside the accepted replay window."""

    code = "gateway_signature_expired"


class GatewayIdentityMismatch(GatewayIdentityError):
    """HMAC did not match the canonical payload."""

    code = "invalid_gateway_signature"


class GatewayIdentitySecretMissing(GatewayIdentityError):
    """Shared secret is required to sign or verify and is not configured."""

    code = "gateway_verification_unavailable"


def _require_secret(shared_secret: str | None) -> str:
    secret = (shared_secret or "").strip()
    if not secret:
        raise GatewayIdentitySecretMissing(
            "ADAPTIX_GATEWAY_SHARED_SECRET is empty; cannot sign or verify identity"
        )
    return secret


def canonical_legacy_payload(
    *,
    timestamp: str,
    user_id: str,
    tenant_id: str,
    email: str,
) -> bytes:
    """Return the exact bytes the Gateway HMAC covers.

    Values are used as signed — no stripping — because a signature over one
    string does not authorise acting on a different one.
    """
    return f"{timestamp}.{user_id}.{tenant_id}.{email}".encode("utf-8")


def _legacy_hmac_hex(secret: str, payload: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _require_legacy_headers(timestamp: str, signature: str) -> None:
    if not timestamp or not signature:
        raise GatewayIdentityMissing("request did not come through the Adaptix gateway")


def _parse_legacy_timestamp(timestamp: str) -> int:
    try:
        return int(timestamp)
    except (TypeError, ValueError) as exc:
        raise GatewayIdentityInvalidTimestamp("timestamp is not an integer") from exc


def _assert_legacy_fresh(issued_at: int, clock_skew_seconds: int) -> None:
    if abs(time.time() - issued_at) > clock_skew_seconds:
        raise GatewayIdentityExpired("timestamp outside tolerance")


def _assert_legacy_hmac(secret: str, payload: bytes, signature: str) -> None:
    expected = _legacy_hmac_hex(secret, payload)
    if not hmac.compare_digest(expected, signature):
        raise GatewayIdentityMismatch("signature mismatch")


def sign_legacy_identity(
    *,
    user_id: str,
    tenant_id: str,
    email: str,
    shared_secret: str,
    now: int | None = None,
) -> tuple[str, str]:
    """Mint the legacy timestamp/signature pair the Gateway historically stamps.

    Returns:
        ``(timestamp, signature_hex)`` ready for the legacy headers.

    Raises:
        GatewayIdentitySecretMissing: when ``shared_secret`` is blank.
    """
    secret = _require_secret(shared_secret)
    timestamp = str(int(time.time()) if now is None else int(now))
    payload = canonical_legacy_payload(
        timestamp=timestamp,
        user_id=user_id,
        tenant_id=tenant_id,
        email=email,
    )
    return timestamp, _legacy_hmac_hex(secret, payload)


def verify_legacy_identity(
    *,
    tenant_id: str,
    user_id: str,
    email: str,
    timestamp: str,
    signature: str,
    shared_secret: str,
    clock_skew_seconds: int = LEGACY_TIMESTAMP_TOLERANCE_SECONDS,
) -> None:
    """Verify a legacy Gateway identity HMAC. Raises on any failure.

    Raises:
        GatewayIdentityMissing: timestamp or signature absent.
        GatewayIdentityInvalidTimestamp: timestamp is not an integer.
        GatewayIdentityExpired: timestamp outside ``clock_skew_seconds``.
        GatewayIdentityMismatch: HMAC does not match.
        GatewayIdentitySecretMissing: secret is blank.
    """
    secret = _require_secret(shared_secret)
    _require_legacy_headers(timestamp, signature)
    _assert_legacy_fresh(_parse_legacy_timestamp(timestamp), clock_skew_seconds)
    _assert_legacy_hmac(
        secret,
        canonical_legacy_payload(
            timestamp=timestamp,
            user_id=user_id,
            tenant_id=tenant_id,
            email=email,
        ),
        signature,
    )


# Back-compat aliases the correction named: sign() / verify() for the modern
# context scheme, plus the legacy pair above.
sign = sign_gateway_context
verify = verify_gateway_signature


__all__ = [
    "GATEWAY_CLOCK_SKEW_SECONDS",
    "GATEWAY_EXPECTED_AUDIENCE_ENV",
    "GATEWAY_SHARED_SECRET_ENV",
    "HEADER_AUTH_CONTEXT",
    "HEADER_AUTH_KEY_ID",
    "HEADER_AUTH_PATH",
    "HEADER_AUTH_SIGNATURE",
    "HEADER_LEGACY_SIGNATURE",
    "HEADER_LEGACY_TIMESTAMP",
    "LEGACY_TIMESTAMP_TOLERANCE_SECONDS",
    "GatewayClaims",
    "GatewayIdentityError",
    "GatewayIdentityExpired",
    "GatewayIdentityInvalidTimestamp",
    "GatewayIdentityMismatch",
    "GatewayIdentityMissing",
    "GatewayIdentitySecretMissing",
    "GatewaySignatureError",
    "GatewayVerifierConfigurationError",
    "build_gateway_signed_headers",
    "canonical_legacy_payload",
    "has_gateway_signature",
    "sign",
    "sign_claims_hmac",
    "sign_gateway_context",
    "sign_legacy_identity",
    "verify",
    "verify_gateway_signature",
    "verify_legacy_identity",
]
