"""Round-trip tests for the gateway signed-auth PRODUCER.

Every test signs with ``gateway_signing`` and verifies with the real
``gateway_signature.verify_gateway_signature``. This pins the producer to the
verifier byte-for-byte: if either side's canonical serialization, HMAC
construction, issuer, or required-claim set drifts, these tests fail.
"""

from __future__ import annotations

import time

import pytest

from adaptix_contracts.gateway_signature import (
    GATEWAY_EXPECTED_AUDIENCE_ENV,
    GatewaySignatureError,
    verify_gateway_signature,
)
from adaptix_contracts.gateway_signing import (
    HEADER_AUTH_CONTEXT,
    HEADER_AUTH_PATH,
    HEADER_AUTH_SIGNATURE,
    build_gateway_signed_headers,
    sign_gateway_context,
)

SECRET = "unit-test-gateway-shared-secret-32-bytes-plus"


def test_sign_then_verify_roundtrip() -> None:
    ctx, sig = sign_gateway_context(
        shared_secret=SECRET, user_id="user-1", tenant_id="tenant-1", aud="adaptix-ai"
    )
    payload = verify_gateway_signature(
        context_b64=ctx, signature_hex=sig, shared_secret=SECRET
    )
    assert payload["iss"] == "adaptix-gateway"
    assert payload["user_id"] == "user-1"
    assert payload["tenant_id"] == "tenant-1"
    assert payload["aud"] == "adaptix-ai"


def test_optional_claims_roundtrip() -> None:
    ctx, sig = sign_gateway_context(
        shared_secret=SECRET,
        user_id="u",
        tenant_id="t",
        aud="adaptix-ai",
        sub="sub-9",
        agency_id="agency-3",
        email="biller@example.com",
        roles=["founder", "billing"],
        scopes=["read", "write"],
        jti="jti-abc",
    )
    p = verify_gateway_signature(
        context_b64=ctx, signature_hex=sig, shared_secret=SECRET
    )
    assert p["sub"] == "sub-9"
    assert p["agency_id"] == "agency-3"
    assert p["email"] == "biller@example.com"
    assert p["roles"] == ["founder", "billing"]
    assert p["scopes"] == ["read", "write"]
    assert p["jti"] == "jti-abc"


def test_headers_helper_roundtrip() -> None:
    headers = build_gateway_signed_headers(
        shared_secret=SECRET, user_id="u", tenant_id="t", aud="adaptix-ai"
    )
    assert set(headers) == {
        HEADER_AUTH_CONTEXT,
        HEADER_AUTH_SIGNATURE,
        HEADER_AUTH_PATH,
    }
    assert headers[HEADER_AUTH_PATH] == "gateway-v1"
    p = verify_gateway_signature(
        context_b64=headers[HEADER_AUTH_CONTEXT],
        signature_hex=headers[HEADER_AUTH_SIGNATURE],
        shared_secret=SECRET,
        auth_path=headers[HEADER_AUTH_PATH],
    )
    assert p["user_id"] == "u"


def test_wrong_secret_is_rejected() -> None:
    ctx, sig = sign_gateway_context(
        shared_secret=SECRET, user_id="u", tenant_id="t", aud="adaptix-ai"
    )
    with pytest.raises(GatewaySignatureError):
        verify_gateway_signature(
            context_b64=ctx, signature_hex=sig, shared_secret="a-different-secret"
        )


def test_tampered_context_is_rejected() -> None:
    ctx, sig = sign_gateway_context(
        shared_secret=SECRET, user_id="u", tenant_id="t", aud="adaptix-ai"
    )
    tampered = ("B" if ctx[0] != "B" else "C") + ctx[1:]
    with pytest.raises(GatewaySignatureError):
        verify_gateway_signature(
            context_b64=tampered, signature_hex=sig, shared_secret=SECRET
        )


def test_expired_context_is_rejected() -> None:
    long_ago = int(time.time()) - 3600
    ctx, sig = sign_gateway_context(
        shared_secret=SECRET,
        user_id="u",
        tenant_id="t",
        aud="adaptix-ai",
        ttl_seconds=1,
        now=long_ago,
    )
    with pytest.raises(GatewaySignatureError):
        verify_gateway_signature(
            context_b64=ctx, signature_hex=sig, shared_secret=SECRET
        )


def test_audience_pin_accepts_match_and_rejects_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx, sig = sign_gateway_context(
        shared_secret=SECRET, user_id="u", tenant_id="t", aud="adaptix-ai"
    )
    monkeypatch.setenv(GATEWAY_EXPECTED_AUDIENCE_ENV, "adaptix-ai")
    p = verify_gateway_signature(
        context_b64=ctx, signature_hex=sig, shared_secret=SECRET
    )
    assert p["aud"] == "adaptix-ai"

    monkeypatch.setenv(GATEWAY_EXPECTED_AUDIENCE_ENV, "adaptix-core")
    with pytest.raises(GatewaySignatureError):
        verify_gateway_signature(
            context_b64=ctx, signature_hex=sig, shared_secret=SECRET
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"shared_secret": "", "user_id": "u", "tenant_id": "t", "aud": "adaptix-ai"},
        {"shared_secret": SECRET, "user_id": "", "tenant_id": "t", "aud": "adaptix-ai"},
        {"shared_secret": SECRET, "user_id": "u", "tenant_id": "", "aud": "adaptix-ai"},
        {"shared_secret": SECRET, "user_id": "u", "tenant_id": "t", "aud": ""},
    ],
)
def test_missing_required_inputs_raise(kwargs: dict[str, str]) -> None:
    with pytest.raises(GatewaySignatureError):
        sign_gateway_context(**kwargs)


def test_non_positive_ttl_raises() -> None:
    with pytest.raises(GatewaySignatureError):
        sign_gateway_context(
            shared_secret=SECRET,
            user_id="u",
            tenant_id="t",
            aud="adaptix-ai",
            ttl_seconds=0,
        )
