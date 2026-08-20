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
from dataclasses import dataclass
from typing import Any

from adaptix_contracts.gateway_keys import (
    b64url_encode,
    has_signing_material,
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


@dataclass(frozen=True)
class GatewayClaims:
    """The identity a signed context forwards, independent of signing scheme.

    ``user_id``, ``tenant_id`` and ``aud`` are required (the verifier rejects a
    context missing any of them — and a context without a target audience would
    recreate the cross-service replay hole the audience pin closes). Everything
    else is an optional forwarded claim.
    """

    user_id: str
    tenant_id: str
    aud: str
    sub: str | None = None
    agency_id: str | None = None
    email: str | None = None
    roles: list[str] | None = None
    scopes: list[str] | None = None
    jti: str | None = None
    ttl_seconds: int = _DEFAULT_TTL_SECONDS
    now: int | None = None

    def validated(self) -> GatewayClaims:
        """Return ``self`` after checking required fields.

        Raises:
            GatewaySignatureError: on a missing required field or bad TTL.
        """
        if not (self.user_id or "").strip():
            raise GatewaySignatureError("user_id is required to sign a context")
        if not (self.tenant_id or "").strip():
            raise GatewaySignatureError("tenant_id is required to sign a context")
        if not (self.aud or "").strip():
            raise GatewaySignatureError("aud (target service audience) is required")
        if self.ttl_seconds <= 0:
            raise GatewaySignatureError("ttl_seconds must be a positive integer")
        return self

    def payload(self) -> dict[str, Any]:
        """Return the canonical context payload for these claims."""
        issued = int(time.time()) if self.now is None else int(self.now)
        payload: dict[str, Any] = {
            "iss": _GATEWAY_ISS,
            "aud": self.aud,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "iat": issued,
            "exp": issued + int(self.ttl_seconds),
        }
        optional: dict[str, Any] = {
            "sub": self.sub,
            "agency_id": self.agency_id,
            "email": self.email,
            "jti": self.jti,
        }
        payload.update({k: v for k, v in optional.items() if v is not None})
        if self.roles is not None:
            payload["roles"] = list(self.roles)
        if self.scopes is not None:
            payload["scopes"] = list(self.scopes)
        return payload

    def context_b64(self) -> str:
        """Serialize the payload to the unpadded-base64url context string.

        Shared by both schemes so the payload bytes are identical regardless of
        how they are signed — the signature is the only v1/v2 difference.
        """
        serialized = json.dumps(
            self.validated().payload(), separators=(",", ":"), sort_keys=True
        )
        return (
            base64.urlsafe_b64encode(serialized.encode("utf-8"))
            .decode("ascii")
            .rstrip("=")
        )


def sign_claims_asymmetric(claims: GatewayClaims) -> tuple[str, str, str]:
    """Mint an Ed25519-signed gateway-v2 context. Gateway-side only.

    A ``claims.jti`` of ``None`` is replaced with a fresh UUID: ``jti`` is the
    anti-replay handle and is REQUIRED on gateway-v2 by the verifier.

    Returns:
        ``(context_b64, signature_b64, kid)``.

    Raises:
        GatewaySignatureError: on missing required fields.
        GatewayKeyError: when this process holds no signing material — i.e. it
            is not the gateway. Domain services must not call this.
    """
    if claims.jti is None:
        claims = GatewayClaims(**{**claims.__dict__, "jti": str(uuid.uuid4())})
    kid, private_key = load_signing_key()
    context_b64 = claims.context_b64()
    signature = private_key.sign(context_b64.encode("ascii"))
    return context_b64, b64url_encode(signature), kid


def sign_claims_hmac(claims: GatewayClaims, *, shared_secret: str) -> tuple[str, str]:
    """Mint a LEGACY HMAC gateway-v1 ``(context_b64, signature_hex)`` pair.

    Deprecated by D-053: every caller of this function necessarily holds the
    fleet-wide symmetric secret, which is the defect. Retained byte-for-byte for
    the migration window; new code paths must not adopt it.

    Raises:
        GatewaySignatureError: on an empty secret or missing required claims.
    """
    secret = (shared_secret or "").strip()
    if not secret:
        raise GatewaySignatureError("shared_secret is empty — cannot sign a context")
    context_b64 = claims.context_b64()
    signature_hex = hmac.new(
        secret.encode("utf-8"),
        context_b64.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return context_b64, signature_hex


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
    """Legacy kwargs wrapper over :func:`sign_claims_hmac`.

    Kept with its historical signature so existing v1 call sites are unchanged;
    new code should build a :class:`GatewayClaims` and use the claims-based
    functions.
    """  # pylint: disable=too-many-arguments
    claims = GatewayClaims(
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
    return sign_claims_hmac(claims, shared_secret=shared_secret)


def _v2_headers(claims: GatewayClaims) -> dict[str, str]:
    """Return gateway-v2 headers for ``claims``."""
    context_b64, signature_b64, kid = sign_claims_asymmetric(claims)
    return {
        HEADER_AUTH_CONTEXT: context_b64,
        HEADER_AUTH_SIGNATURE: signature_b64,
        HEADER_AUTH_PATH: _GATEWAY_V2_PATH,
        HEADER_AUTH_KEY_ID: kid,
    }


def _v1_headers(claims: GatewayClaims, shared_secret: str | None) -> dict[str, str]:
    """Return legacy gateway-v1 headers for ``claims``.

    Raises:
        GatewaySignatureError: when no shared secret is available either as an
            argument or in the environment.
    """
    secret = (shared_secret or "").strip() or os.environ.get(
        GATEWAY_SHARED_SECRET_ENV, ""
    ).strip()
    if not secret:
        raise GatewaySignatureError(
            "no signing scheme configured: neither gateway signing material "
            f"nor {GATEWAY_SHARED_SECRET_ENV} is available"
        )
    context_b64, signature_hex = sign_claims_hmac(claims, shared_secret=secret)
    return {
        HEADER_AUTH_CONTEXT: context_b64,
        HEADER_AUTH_SIGNATURE: signature_hex,
        HEADER_AUTH_PATH: _GATEWAY_V1_PATH,
    }


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

    * Signing material configured (``has_signing_material()``) →
      **gateway-v2** headers, including ``X-Adaptix-Auth-Key-Id``. The
      ``shared_secret`` argument is ignored.
    * Otherwise → legacy **gateway-v1** HMAC headers, using ``shared_secret``
      or, when omitted, ``ADAPTIX_GATEWAY_SHARED_SECRET`` from the environment.

    ``shared_secret`` moved from required to optional keyword when v2 landed;
    existing v1 callers that pass it keep working unchanged.

    Raises:
        GatewaySignatureError: on missing required identity fields, or when
            neither signing scheme is configured.
    """  # pylint: disable=too-many-arguments
    claims = GatewayClaims(
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
    if has_signing_material():
        return _v2_headers(claims)
    return _v1_headers(claims, shared_secret)


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
    "GatewayClaims",
    "build_gateway_signed_headers",
    "gateway_secret_env_name",
    "sign_claims_asymmetric",
    "sign_claims_hmac",
    "sign_gateway_context",
]
