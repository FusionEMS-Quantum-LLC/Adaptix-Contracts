"""Gateway signed-auth-context PRODUCER for in-VPC service-to-service calls.

This is the *producer* (sign) counterpart to
``adaptix_contracts.gateway_signature`` (the verify side). It exists to close a
concrete gap: the shared package could only VERIFY a gateway signature, never
MINT one. Every Adaptix service-to-service call that does NOT transit the
gateway — e.g. ``Adaptix-Billing-Service`` -> ``Adaptix-AI-Service``
(``/api/v1/ai/billing-intelligence/...``), ``Adaptix-CAD-Service`` ->
``/api/v1/ai/invoke`` — therefore forwarded RAW, UNSIGNED identity headers
(``X-User-Id`` / ``X-Tenant-Id``). As a result no downstream service could set
``ADAPTIX_GATEWAY_HMAC_ENFORCE=true`` without 401-ing those legitimate callers.

A caller that already holds ``ADAPTIX_GATEWAY_SHARED_SECRET`` (every service does
— it is injected from Secrets Manager via the task definition) uses
``build_gateway_signed_headers`` to stamp the SAME HMAC-signed context the
gateway would, forwarding the identity it already verified. Once every direct
caller of a service signs, that service can safely enforce.

Byte-compatible with the verifier
----------------------------------
The scheme is the exact inverse of
``adaptix_contracts.gateway_signature.verify_gateway_signature``:

  context_b64   = base64url(json.dumps(payload, separators=(",",":"),
                            sort_keys=True)).rstrip("=")
  signature_hex = hex(HMAC-SHA256(shared_secret.utf-8, context_b64.ascii))

  X-Adaptix-Auth-Context   : context_b64
  X-Adaptix-Auth-Signature : signature_hex
  X-Adaptix-Auth-Path      : "gateway-v1"

Payload claims: iss="adaptix-gateway", aud=<target service audience>, user_id,
tenant_id, iat, exp (int, replay window), and optional sub, agency_id, email,
roles, scopes, jti. ``iss`` / ``user_id`` / ``tenant_id`` / ``iat`` / ``exp``
are required by the verifier; the round-trip tests assert acceptance so any
drift in the verifier's constants fails the build.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from adaptix_contracts.gateway_signature import (
    GATEWAY_SHARED_SECRET_ENV,
    GatewaySignatureError,
)

# These MUST match ``gateway_signature._EXPECTED_ISSUER`` and
# ``gateway_signature._GATEWAY_V1_PATH``. They are asserted by the round-trip
# tests (sign here -> verify there), which fail loudly on any drift.
_GATEWAY_ISS = "adaptix-gateway"
_GATEWAY_V1_PATH = "gateway-v1"

# Header NAMES the gateway stamps and downstream verifiers read (the verifier's
# module docstring is the source of truth). HTTP header matching is
# case-insensitive; the canonical mixed-case forms are used here.
HEADER_AUTH_CONTEXT = "X-Adaptix-Auth-Context"
HEADER_AUTH_SIGNATURE = "X-Adaptix-Auth-Signature"
HEADER_AUTH_PATH = "X-Adaptix-Auth-Path"

# Default context lifetime. Small on purpose — the context is a per-request
# bearer of identity and the verifier applies only a 5s clock-skew tolerance on
# top of ``exp``. 60s comfortably covers in-VPC request latency without leaving
# a wide replay window.
_DEFAULT_TTL_SECONDS = 60


def sign_gateway_context(
    *,
    shared_secret: str,
    user_id: str,
    tenant_id: str,
    aud: str,
    sub: str | None = None,
    agency_id: str | None = None,
    email: str | None = None,
    roles: list[str] | None = None,
    scopes: list[str] | None = None,
    jti: str | None = None,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    now: int | None = None,
) -> tuple[str, str]:
    """Mint ``(context_b64, signature_hex)`` that ``verify_gateway_signature``
    on the receiving service accepts. Exact inverse of the verifier.

    Args:
        shared_secret: ``ADAPTIX_GATEWAY_SHARED_SECRET`` value. Never logged.
        user_id: Verified user id being forwarded. Required (the verifier
            rejects a context missing it).
        tenant_id: Verified tenant id being forwarded. Required.
        aud: The TARGET service's audience string (e.g. ``"adaptix-ai"``) so the
            receiver can pin it via ``ADAPTIX_GATEWAY_EXPECTED_AUDIENCE``.
            Required — signing a context without a target audience would
            recreate the cross-service replay hole the audience pin closes.
        sub, agency_id, email, roles, scopes, jti: Optional forwarded claims.
        ttl_seconds: Context lifetime; ``exp = iat + ttl_seconds``. Must be > 0.
        now: Override issue time in epoch seconds (for tests). Defaults to
            ``int(time.time())``.

    Returns:
        ``(context_b64, signature_hex)`` — the ``X-Adaptix-Auth-Context`` and
        ``X-Adaptix-Auth-Signature`` header values.

    Raises:
        GatewaySignatureError: if ``shared_secret``, ``user_id``, ``tenant_id``
            or ``aud`` is empty, or ``ttl_seconds`` <= 0.
    """
    secret = (shared_secret or "").strip()
    if not secret:
        raise GatewaySignatureError("shared_secret is empty — cannot sign a context")
    if not (user_id or "").strip():
        raise GatewaySignatureError("user_id is required to sign a context")
    if not (tenant_id or "").strip():
        raise GatewaySignatureError("tenant_id is required to sign a context")
    if not (aud or "").strip():
        raise GatewaySignatureError("aud (target service audience) is required")
    if ttl_seconds <= 0:
        raise GatewaySignatureError("ttl_seconds must be a positive integer")

    issued = int(time.time()) if now is None else int(now)
    payload: dict[str, Any] = {
        "iss": _GATEWAY_ISS,
        "aud": aud,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "iat": issued,
        "exp": issued + int(ttl_seconds),
    }
    if sub is not None:
        payload["sub"] = sub
    if agency_id is not None:
        payload["agency_id"] = agency_id
    if email is not None:
        payload["email"] = email
    if roles is not None:
        payload["roles"] = list(roles)
    if scopes is not None:
        payload["scopes"] = list(scopes)
    if jti is not None:
        payload["jti"] = jti

    serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    context_b64 = (
        base64.urlsafe_b64encode(serialized.encode("utf-8")).decode("ascii").rstrip("=")
    )
    signature_hex = hmac.new(
        secret.encode("utf-8"),
        context_b64.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return context_b64, signature_hex


def build_gateway_signed_headers(
    *,
    shared_secret: str,
    user_id: str,
    tenant_id: str,
    aud: str,
    sub: str | None = None,
    agency_id: str | None = None,
    email: str | None = None,
    roles: list[str] | None = None,
    scopes: list[str] | None = None,
    jti: str | None = None,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    now: int | None = None,
) -> dict[str, str]:
    """Return the three signed-auth headers ready to attach to an outbound
    in-VPC request. Thin convenience over :func:`sign_gateway_context`; see it
    for argument semantics.
    """
    context_b64, signature_hex = sign_gateway_context(
        shared_secret=shared_secret,
        user_id=user_id,
        tenant_id=tenant_id,
        aud=aud,
        sub=sub,
        agency_id=agency_id,
        email=email,
        roles=roles,
        scopes=scopes,
        jti=jti,
        ttl_seconds=ttl_seconds,
        now=now,
    )
    return {
        HEADER_AUTH_CONTEXT: context_b64,
        HEADER_AUTH_SIGNATURE: signature_hex,
        HEADER_AUTH_PATH: _GATEWAY_V1_PATH,
    }


def gateway_secret_env_name() -> str:
    """Return the env-var NAME a caller reads its shared secret from.

    Re-exported from the verify module so producers and consumers name the same
    variable without duplicating the literal.
    """
    return GATEWAY_SHARED_SECRET_ENV


__all__ = [
    "HEADER_AUTH_CONTEXT",
    "HEADER_AUTH_PATH",
    "HEADER_AUTH_SIGNATURE",
    "build_gateway_signed_headers",
    "gateway_secret_env_name",
    "sign_gateway_context",
]
