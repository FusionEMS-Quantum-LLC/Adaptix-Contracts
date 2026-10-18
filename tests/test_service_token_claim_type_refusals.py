"""A wrongly typed or unsupported claim is a clean 401 that never echoes it (#376).

``verify_service_token`` checks presence and the authorization rules
explicitly, then builds ``ServiceTokenClaims``. A validly signed token whose
claim has the wrong type (a numeric ``tenant_id``) passed every explicit check
and failed only in that build, escaping as ``pydantic.ValidationError``: not a
``ServiceTokenError``, so a caller catching the documented errors answered 500,
and one returning ``str(exc)`` echoed the claim value. The version refusal also
quoted the token's ``ver``.

These tests pin the contract: both cases raise ``ServiceTokenError`` (401),
through the low-level verifier and the keyset entry point services call, and
the refusal text names the claim and rule but contains no claim value.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from adaptix_contracts.auth.service_token import (
    SERVICE_TOKEN_VERSION,
    ServiceTokenError,
    verify_service_token,
    verify_service_token_with_keyset,
)

_ISS = "adaptix-operations"
_SUB = "adaptix-operations"
_AUD = "adaptix-cad"
_SCOPE = "scene-dispatch:create"
_TENANT = str(uuid.uuid4())
# Distinctive values: if any reaches the refusal text, the assertion finds it.
_NUMERIC_TENANT = 77317731
_UNKNOWN_VER = 90419041


@pytest.fixture(scope="module")
def keys() -> tuple[str, str]:
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


def _payload(**over: Any) -> dict[str, Any]:
    now = int(datetime.now(UTC).timestamp())
    payload: dict[str, Any] = {
        "iss": _ISS,
        "aud": _AUD,
        "sub": _SUB,
        "tenant_id": _TENANT,
        "scope": _SCOPE,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "nbf": now,
        "exp": now + 120,
        "ver": SERVICE_TOKEN_VERSION,
    }
    payload.update(over)
    return payload


def _sign(priv: str, payload: dict[str, Any], kid: str | None = None) -> str:
    headers = {"kid": kid} if kid else None
    return jwt.encode(payload, priv, algorithm="RS256", headers=headers)


def _verify(token: str, pub: str) -> object:
    return verify_service_token(
        token,
        public_key_pem=pub,
        expected_issuer=_ISS,
        expected_audience=_AUD,
        expected_subject=_SUB,
        required_scope=_SCOPE,
    )


def _verify_keyset(token: str, pub: str) -> object:
    return verify_service_token_with_keyset(
        token,
        trusted_keys={"k1": pub},
        expected_issuer=_ISS,
        expected_audience=_AUD,
        expected_subject=_SUB,
        required_scope=_SCOPE,
    )


def test_numeric_tenant_id_is_401_naming_claim_not_value(keys):
    priv, pub = keys
    token = _sign(priv, _payload(tenant_id=_NUMERIC_TENANT))
    # pydantic.ValidationError is not a ServiceTokenError: a regression would
    # propagate uncaught and fail here.
    with pytest.raises(ServiceTokenError) as exc:
        _verify(token, pub)
    text = str(exc.value)
    assert text == "invalid service token claims: tenant_id: string_type"
    assert str(_NUMERIC_TENANT) not in text


def test_numeric_tenant_id_is_401_through_keyset_entry_point(keys):
    priv, pub = keys
    token = _sign(priv, _payload(tenant_id=_NUMERIC_TENANT), kid="k1")
    with pytest.raises(ServiceTokenError) as exc:
        _verify_keyset(token, pub)
    assert "tenant_id" in str(exc.value)
    assert str(_NUMERIC_TENANT) not in str(exc.value)


def test_several_wrongly_typed_claims_are_all_named_without_values(keys):
    priv, pub = keys
    token = _sign(
        priv,
        _payload(
            correlation_id=["corr-secret-value"],
            scene_request_id={"leak": "scene-secret-value"},
        ),
    )
    with pytest.raises(ServiceTokenError) as exc:
        _verify(token, pub)
    text = str(exc.value)
    assert "correlation_id: string_type" in text
    assert "scene_request_id: string_type" in text
    assert "secret-value" not in text
    assert "leak" not in text


def test_unknown_ver_is_401_without_quoting_it(keys):
    priv, pub = keys
    token = _sign(priv, _payload(ver=_UNKNOWN_VER))
    with pytest.raises(ServiceTokenError) as exc:
        _verify(token, pub)
    assert str(exc.value) == "unsupported service token version"
    assert str(_UNKNOWN_VER) not in str(exc.value)


def test_text_ver_is_401_without_quoting_it(keys):
    priv, pub = keys
    token = _sign(priv, _payload(ver="v1-injected-text"), kid="k1")
    with pytest.raises(ServiceTokenError) as exc:
        _verify_keyset(token, pub)
    assert "injected" not in str(exc.value)


def test_well_typed_token_still_verifies(keys):
    priv, pub = keys
    claims = _verify(_sign(priv, _payload()), pub)
    assert getattr(claims, "tenant_id") == _TENANT
