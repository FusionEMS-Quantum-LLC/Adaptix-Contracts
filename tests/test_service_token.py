"""Tests for the canonical Adaptix service-to-service identity token.

Covers the full issue/verify contract and the required auth truth table:
valid; missing/invalid-signature/expired/not-yet-valid/untrusted-issuer/unknown-
version -> 401 (ServiceTokenError); wrong-audience/wrong-subject/missing-scope/
missing-tenant/tenant-mismatch -> 403 (ServiceTokenAuthzError).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from adaptix_contracts.auth.service_token import (
    SERVICE_TOKEN_VERSION,
    ServiceTokenAuthzError,
    ServiceTokenClaims,
    ServiceTokenError,
    issue_service_token,
    verify_service_token,
)

_ISS = "adaptix-operations"
_SUB = "adaptix-operations"
_AUD = "adaptix-cad"
_SCOPE = "scene-dispatch:create"
_TENANT = str(uuid.uuid4())


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


@pytest.fixture(scope="module")
def keys() -> tuple[str, str]:
    return _keypair()


def _issue(priv: str, **over) -> str:
    kw = dict(
        private_key_pem=priv,
        issuer=_ISS,
        audience=_AUD,
        subject=_SUB,
        tenant_id=_TENANT,
        scope=_SCOPE,
        scene_request_id=str(uuid.uuid4()),
        correlation_id="corr-1",
        actor_sub=str(uuid.uuid4()),
    )
    kw.update(over)
    return issue_service_token(**kw)


def _verify(token: str, pub: str, **over) -> ServiceTokenClaims:
    kw = dict(
        public_key_pem=pub,
        expected_issuer=_ISS,
        expected_audience=_AUD,
        expected_subject=_SUB,
        required_scope=_SCOPE,
    )
    kw.update(over)
    return verify_service_token(token, **kw)


def test_valid_roundtrip(keys):
    priv, pub = keys
    claims = _verify(_issue(priv), pub, expected_tenant_id=_TENANT)
    assert claims.tenant_id == _TENANT
    assert claims.aud == _AUD
    assert claims.sub == _SUB
    assert claims.scope == _SCOPE
    assert claims.ver == SERVICE_TOKEN_VERSION
    assert claims.jti and claims.scene_request_id and claims.correlation_id


def test_missing_token_401(keys):
    _, pub = keys
    with pytest.raises(ServiceTokenError):
        _verify("", pub)


def test_invalid_signature_401(keys):
    priv, _ = keys
    _, other_pub = _keypair()  # different key => signature will not verify
    with pytest.raises(ServiceTokenError):
        _verify(_issue(priv), other_pub)


def test_expired_401(keys):
    priv, pub = keys
    past = datetime.now(UTC) - timedelta(minutes=10)
    token = _issue(priv, ttl_seconds=1, now=past)
    with pytest.raises(ServiceTokenError):
        _verify(token, pub)


def test_not_yet_valid_401(keys):
    priv, pub = keys
    future = datetime.now(UTC) + timedelta(minutes=10)
    # nbf is set to iat; issuing "now=future" makes nbf far in the future.
    token = _issue(priv, now=future)
    with pytest.raises(ServiceTokenError):
        _verify(token, pub)


def test_untrusted_issuer_401(keys):
    priv, pub = keys
    token = _issue(priv, issuer="evil-issuer")
    with pytest.raises(ServiceTokenError):
        _verify(token, pub)


def test_unsupported_version_401(keys):
    priv, pub = keys
    # Hand-craft a structurally valid token with a bad version claim.
    now = int(datetime.now(UTC).timestamp())
    payload = {
        "iss": _ISS,
        "aud": _AUD,
        "sub": _SUB,
        "tenant_id": _TENANT,
        "scope": _SCOPE,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "nbf": now,
        "exp": now + 120,
        "ver": 999,
    }
    token = jwt.encode(payload, priv, algorithm="RS256")
    with pytest.raises(ServiceTokenError):
        _verify(token, pub)


def test_wrong_audience_403(keys):
    priv, pub = keys
    token = _issue(priv, audience="adaptix-air")
    with pytest.raises(ServiceTokenAuthzError):
        _verify(token, pub)  # verifier expects adaptix-cad


def test_wrong_subject_403(keys):
    priv, pub = keys
    token = _issue(priv, subject="adaptix-somethingelse")
    with pytest.raises(ServiceTokenAuthzError):
        _verify(token, pub)


def test_missing_scope_403(keys):
    priv, pub = keys
    token = _issue(priv, scope="scene-dispatch:read")
    with pytest.raises(ServiceTokenAuthzError):
        _verify(token, pub)  # verifier requires scene-dispatch:create


def test_missing_tenant_claim_403(keys):
    priv, pub = keys
    now = int(datetime.now(UTC).timestamp())
    payload = {
        "iss": _ISS,
        "aud": _AUD,
        "sub": _SUB,
        "scope": _SCOPE,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "nbf": now,
        "exp": now + 120,
        "ver": SERVICE_TOKEN_VERSION,  # no tenant_id
    }
    token = jwt.encode(payload, priv, algorithm="RS256")
    with pytest.raises(ServiceTokenAuthzError):
        _verify(token, pub)


def test_tenant_body_mismatch_403(keys):
    priv, pub = keys
    token = _issue(priv, tenant_id=_TENANT)
    with pytest.raises(ServiceTokenAuthzError):
        _verify(token, pub, expected_tenant_id=str(uuid.uuid4()))


def test_issue_requires_identity_inputs(keys):
    priv, _ = keys
    with pytest.raises(ServiceTokenError):
        issue_service_token(
            private_key_pem=priv,
            issuer=_ISS,
            audience=_AUD,
            subject=_SUB,
            tenant_id="",
            scope=_SCOPE,
        )
