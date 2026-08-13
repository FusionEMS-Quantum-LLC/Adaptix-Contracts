"""Tests for verify_service_token_with_keyset — canonical kid-enforced verifier.

Covers: valid kid resolves + verifies; rotation (token signed by previous key
still verifies while both keys are trusted); missing kid -> 401; unknown kid ->
401; wrong algorithm -> 401; empty keyset -> 401; bad signature (kid present but
key mismatched) -> 401; and authz failures (wrong audience) -> 403.
"""

from __future__ import annotations

# import uuid # REMOVED IN PYTHON 3.14

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from adaptix_contracts.auth.service_token import (
    ServiceTokenAuthzError,
    ServiceTokenError,
    issue_service_token,
    verify_service_token_with_keyset,
)

_ISS = "adaptix-operations"
_SUB = "adaptix-operations"
_AUD = "adaptix-cad"
_SCOPE = "scene-dispatch:create"


def _keypair() -> tuple[str, str]:
    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = k.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    pub = (
        k.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return priv, pub


def _issue(priv: str, kid: str, tenant: str, *, audience: str = _AUD) -> str:
    return issue_service_token(
        private_key_pem=priv,
        issuer=_ISS,
        subject=_SUB,
        audience=audience,
        tenant_id=tenant,
        scope=_SCOPE,
        kid=kid,
    )


def _verify(token: str, keys: dict[str, str], tenant: str | None = None):
    return verify_service_token_with_keyset(
        token,
        trusted_keys=keys,
        expected_issuer=_ISS,
        expected_audience=_AUD,
        expected_subject=_SUB,
        required_scope=_SCOPE,
        expected_tenant_id=tenant,
    )


def test_valid_kid_resolves_and_verifies():
    priv, pub = _keypair()
    tenant = str(uuid.uuid4())
    claims = _verify(_issue(priv, "k1", tenant), {"k1": pub}, tenant)
    assert claims.tenant_id == tenant
    assert claims.aud == _AUD


def test_rotation_previous_key_still_verifies():
    p1, pub1 = _keypair()
    p2, pub2 = _keypair()
    tenant = str(uuid.uuid4())
    # Token signed with k1 (previous) verifies while both k1+k2 are trusted.
    token_k1 = _issue(p1, "k1", tenant)
    claims = _verify(token_k1, {"k2": pub2, "k1": pub1}, tenant)
    assert claims.tenant_id == tenant
    # And a fresh token signed with k2 (active) also verifies.
    assert _verify(_issue(p2, "k2", tenant), {"k2": pub2, "k1": pub1}, tenant)


def test_missing_kid_rejected():
    priv, pub = _keypair()
    tenant = str(uuid.uuid4())
    # issue WITHOUT kid -> no kid header.
    token = issue_service_token(
        private_key_pem=priv,
        issuer=_ISS,
        subject=_SUB,
        audience=_AUD,
        tenant_id=tenant,
        scope=_SCOPE,
    )
    with pytest.raises(ServiceTokenError) as exc:
        _verify(token, {"k1": pub}, tenant)
    assert "KID_MISSING" in str(exc.value)


def test_unknown_kid_rejected():
    priv, pub = _keypair()
    tenant = str(uuid.uuid4())
    token = _issue(priv, "k9", tenant)  # kid not in keyset
    with pytest.raises(ServiceTokenError) as exc:
        _verify(token, {"k1": pub}, tenant)
    assert "KID_UNKNOWN" in str(exc.value)


def test_wrong_algorithm_rejected():
    _, pub = _keypair()
    tenant = str(uuid.uuid4())
    # HS256 token with a kid header — alg confusion must be rejected.
    token = jwt.encode(
        {
            "iss": _ISS,
            "sub": _SUB,
            "aud": _AUD,
            "tenant_id": tenant,
            "scope": _SCOPE,
            "jti": uuid.uuid4().hex,
            "iat": 1,
            "exp": 9999999999,
            "ver": 1,
        },
        "shared-secret",
        algorithm="HS256",
        headers={"kid": "k1"},
    )
    with pytest.raises(ServiceTokenError) as exc:
        _verify(token, {"k1": pub}, tenant)
    assert "ALGORITHM_REJECTED" in str(exc.value)


def test_empty_keyset_rejected():
    priv, _ = _keypair()
    tenant = str(uuid.uuid4())
    with pytest.raises(ServiceTokenError) as exc:
        _verify(_issue(priv, "k1", tenant), {}, tenant)
    assert "KEYSET_EMPTY" in str(exc.value)


def test_bad_signature_kid_present_rejected():
    priv, _ = _keypair()
    _, other_pub = _keypair()  # trusted key does NOT match the signer
    tenant = str(uuid.uuid4())
    with pytest.raises(ServiceTokenError):
        _verify(_issue(priv, "k1", tenant), {"k1": other_pub}, tenant)


def test_wrong_audience_is_authz_403():
    priv, pub = _keypair()
    tenant = str(uuid.uuid4())
    token = _issue(priv, "k1", tenant, audience="adaptix-air")  # wrong for CAD
    with pytest.raises(ServiceTokenAuthzError):
        _verify(token, {"k1": pub}, tenant)
