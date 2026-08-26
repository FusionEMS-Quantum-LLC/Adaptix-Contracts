"""THE central safety proof for the platform S2S token primitive.

adaptix_contracts.auth.platform_token exists as a SEPARATE module (rather
than making ServiceTokenClaims.tenant_id optional) specifically so that
tenant safety is a shape guarantee, not a value some verifier has to
remember to check. This file proves that guarantee holds in both
directions, using the REAL public functions a service actually calls (not
an inspection of source code):

  1. A platform token (minted by issue_platform_service_token) MUST be
     rejected by the existing tenant-scoped verifiers
     (verify_service_token / verify_service_token_with_keyset).

  2. A tenant token (minted by issue_service_token) MUST be rejected by the
     new platform verifiers (verify_platform_service_token /
     verify_platform_service_token_with_keyset).

Both directions use matching iss/sub/aud/scope and, where a keyset is
involved, the SAME signing key and kid on both sides -- so the only thing
that differs between the two tokens is their actual shape (tenant_id vs.
token_use). If either of these tests fails, the central invariant this
module was built to guarantee does not hold and the module must not ship.
"""

from __future__ import annotations

import uuid

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import ValidationError

from adaptix_contracts.auth.platform_token import (
    TOKEN_USE,
    PlatformServiceTokenAuthzError,
    PlatformServiceTokenClaims,
    PlatformServiceTokenError,
    issue_platform_service_token,
    verify_platform_service_token,
    verify_platform_service_token_with_keyset,
)
from adaptix_contracts.auth.service_token import (
    ServiceTokenAuthzError,
    ServiceTokenClaims,
    ServiceTokenError,
    issue_service_token,
    verify_service_token,
    verify_service_token_with_keyset,
)

_ISS = "adaptix-core"
_SUB = "adaptix-core"
_AUD = "adaptix-calendar"
_SCOPE = "mail:send-marketing"


def _keypair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    pub = (
        key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return priv, pub


# --------------------------------------------------------------------------
# Direction 1: a platform token must not satisfy a tenant-scoped verifier.
# --------------------------------------------------------------------------


def test_platform_token_rejected_by_verify_service_token():
    priv, pub = _keypair()
    platform_token = issue_platform_service_token(
        private_key_pem=priv,
        issuer=_ISS,
        audience=_AUD,
        subject=_SUB,
        scope=_SCOPE,
    )

    with pytest.raises(ServiceTokenAuthzError, match="tenant"):
        verify_service_token(
            platform_token,
            public_key_pem=pub,
            expected_issuer=_ISS,
            expected_audience=_AUD,
            expected_subject=_SUB,
            required_scope=_SCOPE,
        )


def test_platform_token_rejected_by_verify_service_token_with_keyset():
    """Same proof through the REAL production entry point services call."""
    priv, pub = _keypair()
    platform_token = issue_platform_service_token(
        private_key_pem=priv,
        issuer=_ISS,
        audience=_AUD,
        subject=_SUB,
        scope=_SCOPE,
        kid="k1",
    )

    with pytest.raises(ServiceTokenAuthzError, match="tenant"):
        verify_service_token_with_keyset(
            platform_token,
            trusted_keys={"k1": pub},
            expected_issuer=_ISS,
            expected_audience=_AUD,
            expected_subject=_SUB,
            required_scope=_SCOPE,
        )


def test_platform_token_rejected_by_verify_service_token_even_with_matching_tenant_expectation():
    """Even a verifier that also happens to pass expected_tenant_id (the
    request-body tenant a real caller would supply) still refuses -- the
    token has no tenant claim to compare against at all, so there is no
    value of expected_tenant_id that could make this pass."""
    priv, pub = _keypair()
    platform_token = issue_platform_service_token(
        private_key_pem=priv,
        issuer=_ISS,
        audience=_AUD,
        subject=_SUB,
        scope=_SCOPE,
    )

    with pytest.raises(ServiceTokenAuthzError, match="tenant"):
        verify_service_token(
            platform_token,
            public_key_pem=pub,
            expected_issuer=_ISS,
            expected_audience=_AUD,
            expected_subject=_SUB,
            required_scope=_SCOPE,
            expected_tenant_id=str(uuid.uuid4()),
        )


def test_service_token_claims_model_requires_tenant_id_structurally():
    """Direct proof of the rationale's second, independent gate: even
    bypassing verify_service_token's own explicit tenant-presence check and
    constructing ServiceTokenClaims directly from a platform-shaped payload
    fails Pydantic validation -- tenant_id is `str = Field(...)`, required,
    on the model itself."""
    now = 1_000_000
    platform_shaped_raw = {
        "token_use": TOKEN_USE,
        "iss": _ISS,
        "aud": _AUD,
        "sub": _SUB,
        "scope": _SCOPE,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "nbf": now,
        "exp": now + 120,
        "ver": 1,
        # no tenant_id
    }
    with pytest.raises(ValidationError):
        ServiceTokenClaims(**platform_shaped_raw)


# --------------------------------------------------------------------------
# Direction 2: a tenant token must not satisfy the platform verifier.
# --------------------------------------------------------------------------


def test_tenant_token_rejected_by_verify_platform_service_token():
    priv, pub = _keypair()
    tenant_token = issue_service_token(
        private_key_pem=priv,
        issuer=_ISS,
        audience=_AUD,
        subject=_SUB,
        tenant_id=str(uuid.uuid4()),
        scope=_SCOPE,
    )

    with pytest.raises(PlatformServiceTokenError, match="not a platform service token"):
        verify_platform_service_token(
            tenant_token,
            public_key_pem=pub,
            expected_issuer=_ISS,
            expected_audience=_AUD,
            expected_subject=_SUB,
            required_scope=_SCOPE,
        )


def test_tenant_token_rejected_by_verify_platform_service_token_with_keyset():
    """Same proof through the REAL production entry point services call."""
    priv, pub = _keypair()
    tenant_token = issue_service_token(
        private_key_pem=priv,
        issuer=_ISS,
        audience=_AUD,
        subject=_SUB,
        tenant_id=str(uuid.uuid4()),
        scope=_SCOPE,
        kid="k1",
    )

    with pytest.raises(PlatformServiceTokenError, match="not a platform service token"):
        verify_platform_service_token_with_keyset(
            tenant_token,
            trusted_keys={"k1": pub},
            expected_issuer=_ISS,
            expected_audience=_AUD,
            expected_subject=_SUB,
            required_scope=_SCOPE,
        )


def test_platform_claims_model_requires_token_use_structurally():
    """Mirror of test_service_token_claims_model_requires_tenant_id_structurally:
    constructing PlatformServiceTokenClaims directly from a tenant-shaped
    payload (has tenant_id, no token_use) fails Pydantic validation too --
    token_use is a required Literal on the model itself, not merely a
    runtime string comparison someone could forget to call."""
    now = 1_000_000
    tenant_shaped_raw = {
        "iss": _ISS,
        "aud": _AUD,
        "sub": _SUB,
        "tenant_id": str(uuid.uuid4()),
        "scope": _SCOPE,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "nbf": now,
        "exp": now + 120,
        "ver": 1,
        # no token_use
    }
    with pytest.raises(ValidationError):
        PlatformServiceTokenClaims(**tenant_shaped_raw)


# --------------------------------------------------------------------------
# Round out the boundary: neither exception type is a subclass of the other,
# so a call site that catches one family can never accidentally swallow the
# other's failure.
# --------------------------------------------------------------------------


def test_error_hierarchies_are_fully_independent():
    assert not issubclass(PlatformServiceTokenError, ServiceTokenError)
    assert not issubclass(ServiceTokenError, PlatformServiceTokenError)
    assert not issubclass(PlatformServiceTokenAuthzError, ServiceTokenAuthzError)
    assert not issubclass(ServiceTokenAuthzError, PlatformServiceTokenAuthzError)
