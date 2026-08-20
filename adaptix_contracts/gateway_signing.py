"""Gateway signed-auth-context PRODUCER.

This is the *producer* (sign) counterpart to
``adaptix_contracts.gateway_signature`` (the verify side).

Two schemes, one entry point
----------------------------
:func:`build_gateway_signed_headers` emits **gateway-v2 (Ed25519)** headers when
this process holds gateway signing material
(``ADAPTIX_GATEWAY_SIGNING_PRIVATE_KEY`` + ``..._SIGNING_KEY_ID``) and falls
back to the **legacy gateway-v1 (HMAC)** contract only when it does not and a
shared secret is available. The selection is by CONFIGURATION, never by
argument, so a call site cannot accidentally choose the weaker scheme once its
task definition has been migrated.

Who may sign (D-053)
--------------------
Under the corrected trust model **only the gateway holds the private key**. A
domain service that finds itself able to sign gateway-v2 has been misprovisioned
— that is the defect this migration removes, reintroduced.

The legacy HMAC path exists because of a real historical gap: service-to-service
calls that do not transit the gateway (e.g. Billing -> AI) forwarded raw,
unsigned identity headers, and ``build_gateway_signed_headers`` let them stamp
the same HMAC context the gateway would. That pattern is exactly what D-053
condemns — every such caller holds the fleet secret — and it is replaced by
dedicated service identities (see D-051's scene-dispatch contract and the Core
workload-identity mint, D-054). Until each caller is migrated, the HMAC fallback
keeps it authenticating; afterwards the fallback dies with the shared secret.

Byte-compatibility
------------------
The v1 path is byte-for-byte the historical scheme::

  context_b64   = base64url(json.dumps(payload, separators=(",",":"),
                            sort_keys=True)).rstrip("=")
  signature_hex = hex(HMAC-SHA256(shared_secret.utf-8, context_b64.ascii))

The v2 path signs the SAME serialized context bytes::

  signature_b64 = base64url(Ed25519-sign(private_key, context_b64.ascii))

Headers::

  X-Adaptix-Auth-Context   : context_b64
  X-Adaptix-Auth-Signature : signature (hex for v1, base64url for v2)
  X-Adaptix-Auth-Path      : "gateway-v1" | "gateway-v2"
  X-Adaptix-Auth-Key-Id    : v2 only — kid of the signing key

Round-trip tests (sign here -> verify in ``gateway_signature``) fail the build
on any drift in either scheme.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from typing import Any

from adaptix_contracts.gateway_keys import (
    asymmetric_signing_configured,
    b64url_encode,
    load_signing_key,
)
from adaptix_contracts.gateway_signature import (
    GATEWAY_SHARED_SECRET_ENV,
    GatewaySignatureError,
)

# These MUST match ``gateway_signature._EXPECTED_ISSUER`` and the path
# constants there. They are asserted by the round-trip tests, which fail
# loudly on any drift.
_GATEWAY_ISS = "adaptix-gateway"
_GATEWAY_V1_PATH = "gateway-v1"
_GATEWAY_V2_PATH = "gateway-v2"

# Header NAMES the producer stamps and downstream verifiers read (the verifier's
# module docstring is the source of truth). HTTP header matching is
# case-insensitive; the canonical mixed-case forms are used here.
HEADER_AUTH_CONTEXT = "X-Adaptix-Auth-Context"
HEADER_AUTH_SIGNATURE = "X-Adaptix-Auth-Signature"
HEADER_AUTH_PATH = "X-Adaptix-Auth-Path"
HEADER_AUTH_KEY_ID = "X-Adaptix-Auth-Key-Id"

# Default context lifetime. Small on purpose — the context is a per-request
# bearer of identity and the verifier applies only a 5s clock-skew tolerance on
# top of ``exp``. 60s comfortably covers in-VPC request latency without leaving
# a wide replay window.
_DEFAULT_TTL_SECONDS = 60


def _build_context_b64(
    *,
    user_id: str,
    tenant_id: str,
    aud: str,
    sub: str | None,
    agency_id: str | None,
    email: str | None,
    roles: list[str] | None,
    scopes: list[str] | None,
    jti: str | None,
    ttl_seconds: int,
    now: int | None,
) -> str:
    """Serialize the canonical context payload to unpadded base64url.

    Shared by both schemes so the payload bytes are identical regardless of how
    they are signed — the signature is the only difference between v1 and v2.
    """
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
    return (
        base64.urlsafe_b64encode(serialized.encode("utf-8")).decode("ascii").rstrip("=")
    )


def sign_gateway_context_asymmetric(
    *,
    user_id: str,
    tenant_id: str,
    aud: str,
    sub: str | None = None,
    agency_id: str | None = None,
    email: str | None = None,
    roles: list[str] | None = None,
    scopes: list[str] | None = None,
    jti: str | None = "",
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    now: int | None = None,
) -> tuple[str, str, str]:
    """Mint an Ed25519-signed gateway-v2 context. Gateway-side only.

    Args:
        user_id / tenant_id / aud: Required identity and destination. See
            :func:`sign_gateway_context` for semantics.
        jti: Anti-replay id, REQUIRED on gateway-v2 (the verifier rejects a v2
            context without one). The default sentinel ``""`` means "generate a
            UUID for me"; pass ``None`` explicitly only in tests that exercise
            the verifier's rejection.
        ttl_seconds / now: Lifetime and issue-time override (tests).

    Returns:
        ``(context_b64, signature_b64, kid)``.

    Raises:
        GatewaySignatureError: on missing required fields.
        GatewayKeyError: when this process holds no signing material — i.e. it
            is not the gateway. Domain services must not call this.
    """
    effective_jti = str(uuid.uuid4()) if jti == "" else jti
    kid, private_key = load_signing_key()
    context_b64 = _build_context_b64(
        user_id=user_id,
        tenant_id=tenant_id,
        aud=aud,
        sub=sub,
        agency_id=agency_id,
        email=email,
        roles=roles,
        scopes=scopes,
        jti=effective_jti,
        ttl_seconds=ttl_seconds,
        now=now,
    )
    signature = private_key.sign(context_b64.encode("ascii"))
    return context_b64, b64url_encode(signature), kid


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
    """Mint a LEGACY HMAC gateway-v1 ``(context_b64, signature_hex)`` pair.

    Deprecated by D-053: every caller of this function necessarily holds the
    fleet-wide symmetric secret, which is the defect. Retained byte-for-byte for
    the migration window; new code paths must not adopt it.

    Args:
        shared_secret: ``ADAPTIX_GATEWAY_SHARED_SECRET`` value. Never logged.
        user_id: Verified user id being forwarded. Required (the verifier
            rejects a context missing it).
        tenant_id: Verified tenant id being forwarded. Required.
        aud: The TARGET service's audience string (e.g. ``"adaptix-ai"``).
            Required — signing a context without a target audience would
            recreate the cross-service replay hole the audience pin closes.
        sub, agency_id, email, roles, scopes, jti: Optional forwarded claims.
        ttl_seconds: Context lifetime; ``exp = iat + ttl_seconds``. Must be > 0.
        now: Override issue time in epoch seconds (for tests).

    Returns:
        ``(context_b64, signature_hex)``.

    Raises:
        GatewaySignatureError: if a required argument is empty/invalid.
    """
    secret = (shared_secret or "").strip()
    if not secret:
        raise GatewaySignatureError("shared_secret is empty — cannot sign a context")

    context_b64 = _build_context_b64(
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
    signature_hex = hmac.new(
        secret.encode("utf-8"),
        context_b64.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return context_b64, signature_hex


def build_gateway_signed_headers(
    *,
    user_id: str,
    tenant_id: str,
    aud: str,
    shared_secret: str | None = None,
    sub: str | None = None,
    agency_id: str | None = None,
    email: str | None = None,
    roles: list[str] | None = None,
    scopes: list[str] | None = None,
    jti: str | None = None,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    now: int | None = None,
) -> dict[str, str]:
    """Return signed-auth headers ready to attach to an outbound request.

    Scheme selection is by configuration:

    * Signing material configured (``asymmetric_signing_configured()``) →
      **gateway-v2** headers, including ``X-Adaptix-Auth-Key-Id``. The
      ``shared_secret`` argument is ignored.
    * Otherwise → legacy **gateway-v1** HMAC headers, using ``shared_secret``
      or, when omitted, ``ADAPTIX_GATEWAY_SHARED_SECRET`` from the environment.

    ``shared_secret`` moved from required-positional to optional keyword when
    v2 landed; existing v1 callers that pass it keep working unchanged.

    Raises:
        GatewaySignatureError: on missing required identity fields, or when
            neither signing scheme is configured.
    """
    if asymmetric_signing_configured():
        context_b64, signature_b64, kid = sign_gateway_context_asymmetric(
            user_id=user_id,
            tenant_id=tenant_id,
            aud=aud,
            sub=sub,
            agency_id=agency_id,
            email=email,
            roles=roles,
            scopes=scopes,
            jti=jti if jti is not None else "",
            ttl_seconds=ttl_seconds,
            now=now,
        )
        return {
            HEADER_AUTH_CONTEXT: context_b64,
            HEADER_AUTH_SIGNATURE: signature_b64,
            HEADER_AUTH_PATH: _GATEWAY_V2_PATH,
            HEADER_AUTH_KEY_ID: kid,
        }

    secret = (shared_secret or "").strip() or os.environ.get(
        GATEWAY_SHARED_SECRET_ENV, ""
    ).strip()
    if not secret:
        raise GatewaySignatureError(
            "no signing scheme configured: neither gateway signing material "
            f"nor {GATEWAY_SHARED_SECRET_ENV} is available"
        )
    context_b64, signature_hex = sign_gateway_context(
        shared_secret=secret,
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
    """Return the env-var NAME a legacy caller reads its shared secret from.

    Re-exported from the verify module so producers and consumers name the same
    variable without duplicating the literal.
    """
    return GATEWAY_SHARED_SECRET_ENV


__all__ = [
    "HEADER_AUTH_CONTEXT",
    "HEADER_AUTH_KEY_ID",
    "HEADER_AUTH_PATH",
    "HEADER_AUTH_SIGNATURE",
    "build_gateway_signed_headers",
    "gateway_secret_env_name",
    "sign_gateway_context",
    "sign_gateway_context_asymmetric",
]
