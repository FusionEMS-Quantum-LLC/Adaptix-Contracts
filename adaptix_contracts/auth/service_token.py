"""Canonical Adaptix service-to-service (S2S) identity token.

The shared ``INTERNAL_SERVICE_KEY`` proves only that *a* trusted process holds a
shared secret. It does not prove which service is calling, which tenant it is
acting for, which user initiated the request, or which operation is authorized —
and a valid-looking body ``tenant_id`` is not authorization evidence.

This module defines the ONE canonical, cryptographically-signed, short-lived,
tenant-bound service token used for Operations -> CAD / Air scene dispatch (and
future S2S calls). It extends the platform's existing asymmetric JWT pattern
(Core signs user JWTs with an RSA private key; services verify with the public
key) — it does NOT introduce a new broadly-shared HMAC secret.

Signing:  RS256 with an RSA private key held only by the issuer (Operations),
          via the approved secret/KMS mechanism. Verifiers (CAD/Air) hold only
          the public key. ``kid`` supports rotation (verifiers accept the active
          and previous key).

Claims (see ``ServiceTokenClaims``): iss, aud, sub, tenant_id, scope, jti, iat,
nbf, exp, actor_sub, correlation_id, scene_request_id, ver. No secrets and no
patient/clinical data belong in the token.

Verification maps to HTTP results (``ServiceTokenError`` -> 401 authentication,
``ServiceTokenAuthzError`` -> 403 authorization) so downstream services enforce:
missing/invalid/expired/unknown-key/untrusted-issuer -> 401; wrong audience /
wrong caller service / missing scope / missing-or-mismatched tenant -> 403.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pydantic import BaseModel, Field

# Current claims schema version. Verifiers reject unknown major versions.
SERVICE_TOKEN_VERSION = 1

# Default short lifetime — a service token is minted per dispatch, not reused.
DEFAULT_TTL_SECONDS = 120
# Clock-skew tolerance (matches the platform's 5s gateway-signature leeway).
LEEWAY_SECONDS = 5

_ALGORITHM = "RS256"


class ServiceTokenError(ValueError):
    """Authentication failure (map to HTTP 401).

    Raised for missing/invalid/expired/not-yet-valid tokens, unknown signing
    keys, and untrusted issuers — anything that means the token cannot be
    trusted as authentic.
    """


class ServiceTokenAuthzError(ValueError):
    """Authorization failure (map to HTTP 403).

    Raised when the token is authentic but not permitted: wrong audience, wrong
    caller service, missing scope, or missing/mismatched tenant.
    """


class ServiceTokenClaims(BaseModel):
    """Validated claims carried by a canonical Adaptix service token."""

    iss: str = Field(
        ..., description="Canonical Adaptix issuer service, e.g. adaptix-operations"
    )
    aud: str = Field(
        ..., description="Exact downstream audience, e.g. adaptix-cad / adaptix-air"
    )
    sub: str = Field(
        ..., description="Calling service identity, e.g. adaptix-operations"
    )
    tenant_id: str = Field(
        ..., description="Trusted tenant/workspace the call acts for"
    )
    scope: str = Field(..., description="Authorized action, e.g. scene-dispatch:create")
    jti: str = Field(
        ..., description="Unique token id (replay/idempotency correlation)"
    )
    iat: int = Field(..., description="Issued-at (epoch seconds)")
    exp: int = Field(..., description="Expiration (epoch seconds)")
    nbf: int | None = Field(default=None, description="Not-before (epoch seconds)")
    actor_sub: str | None = Field(
        default=None, description="Initiating user id (for audit)"
    )
    correlation_id: str | None = Field(
        default=None, description="Cross-service correlation id"
    )
    scene_request_id: str | None = Field(
        default=None, description="Bound source scene-request id"
    )
    ver: int = Field(default=SERVICE_TOKEN_VERSION, description="Claims schema version")


def issue_service_token(
    *,
    private_key_pem: str,
    issuer: str,
    audience: str,
    subject: str,
    tenant_id: str,
    scope: str,
    kid: str | None = None,
    actor_sub: str | None = None,
    correlation_id: str | None = None,
    scene_request_id: str | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    now: datetime | None = None,
) -> str:
    """Mint a signed (RS256) service token. ``private_key_pem`` never leaves the issuer.

    Raises:
        ServiceTokenError: required identity/tenant/scope inputs are missing.
    """
    for name, value in (
        ("issuer", issuer),
        ("audience", audience),
        ("subject", subject),
        ("tenant_id", tenant_id),
        ("scope", scope),
    ):
        if not value or not str(value).strip():
            raise ServiceTokenError(f"{name} is required to issue a service token")

    issued = now or datetime.now(UTC)
    iat = int(issued.timestamp())
    exp = int((issued + timedelta(seconds=max(1, ttl_seconds))).timestamp())
    payload: dict[str, Any] = {
        "iss": issuer,
        "aud": audience,
        "sub": subject,
        "tenant_id": tenant_id,
        "scope": scope,
        "jti": uuid.uuid4().hex,
        "iat": iat,
        "nbf": iat,
        "exp": exp,
        "ver": SERVICE_TOKEN_VERSION,
    }
    if actor_sub:
        payload["actor_sub"] = actor_sub
    if correlation_id:
        payload["correlation_id"] = correlation_id
    if scene_request_id:
        payload["scene_request_id"] = scene_request_id

    headers = {"kid": kid} if kid else None
    return jwt.encode(payload, private_key_pem, algorithm=_ALGORITHM, headers=headers)


def verify_service_token(
    token: str,
    *,
    public_key_pem: str,
    expected_issuer: str,
    expected_audience: str,
    expected_subject: str,
    required_scope: str,
    expected_tenant_id: str | None = None,
    leeway_seconds: int = LEEWAY_SECONDS,
) -> ServiceTokenClaims:
    """Verify a service token and return its validated claims.

    Enforces (in order): signature+exp+nbf+issuer (401 on failure), audience
    (403), caller subject (403), required scope (403), tenant presence and — when
    ``expected_tenant_id`` is supplied (e.g. the request-body tenant) — that the
    signed tenant matches it (403). The caller is still responsible for proving
    the *source scene request* belongs to the signed tenant.

    Raises:
        ServiceTokenError: authentication failure -> HTTP 401.
        ServiceTokenAuthzError: authorization failure -> HTTP 403.
    """
    if not token or not token.strip():
        raise ServiceTokenError("missing service token")

    try:
        raw: dict[str, Any] = jwt.decode(
            token,
            public_key_pem,
            algorithms=[_ALGORITHM],
            audience=expected_audience,
            issuer=expected_issuer,
            leeway=leeway_seconds,
            options={"require": ["exp", "iat", "aud", "iss", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise ServiceTokenError("service token expired") from exc
    except jwt.ImmatureSignatureError as exc:
        raise ServiceTokenError("service token not yet valid") from exc
    except jwt.InvalidAudienceError as exc:
        # Authentic-but-not-for-this-service -> authorization failure.
        raise ServiceTokenAuthzError("service token audience mismatch") from exc
    except jwt.InvalidIssuerError as exc:
        raise ServiceTokenError("service token issuer not trusted") from exc
    except jwt.InvalidTokenError as exc:
        # Bad signature, malformed, missing required claim, unknown key, etc.
        raise ServiceTokenError(f"invalid service token: {type(exc).__name__}") from exc

    ver = raw.get("ver")
    if ver != SERVICE_TOKEN_VERSION:
        raise ServiceTokenError(f"unsupported service token version: {ver!r}")

    if raw.get("sub") != expected_subject:
        raise ServiceTokenAuthzError("service token caller subject not authorized")

    if raw.get("scope") != required_scope:
        raise ServiceTokenAuthzError(
            f"service token missing required scope {required_scope!r}"
        )

    tenant_id = raw.get("tenant_id")
    if not tenant_id or not str(tenant_id).strip():
        raise ServiceTokenAuthzError("service token missing tenant claim")

    if expected_tenant_id is not None and tenant_id != expected_tenant_id:
        raise ServiceTokenAuthzError(
            "service token tenant does not match request tenant"
        )

    return ServiceTokenClaims(**raw)
