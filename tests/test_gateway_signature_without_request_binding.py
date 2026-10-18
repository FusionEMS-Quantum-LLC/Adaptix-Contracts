"""Contracts #397: the verifier names say whether the route is bound.

``verify_gateway_signature`` checks the signed ``method``/``path`` claims only
when its caller passes the inbound request's method and path, and its name
does not say so (AssetOps #163). It is deprecated with no runtime warning;
``verify_gateway_signature_without_request_binding`` is the explicit name for
callers that no route can reach. These tests pin that the new name behaves as
the documented no-request arm, and that the deprecated name is unchanged
during the overlap.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import warnings
from uuid import uuid4

import pytest

from adaptix_contracts import gateway_identity, gateway_signature
from adaptix_contracts.gateway_signature import (
    GATEWAY_SHARED_SECRET_ENV,
    GATEWAY_SIGNATURE_REQUIRE_PATH_ENV,
    GATEWAY_TRUST_MODE_ENV,
    GatewaySignatureError,
    GatewayVerifierConfigurationError,
    verify_gateway_signature,
    verify_gateway_signature_without_request_binding,
)

_SECRET = "unit-test-hmac-material-not-a-real-value"


def _sign(**overrides: object) -> tuple[str, str]:
    now = int(time.time())
    payload: dict[str, object] = {
        "iss": "adaptix-gateway",
        "aud": "adaptix-core",
        "user_id": "11111111-1111-1111-1111-111111111111",
        "tenant_id": "22222222-2222-2222-2222-222222222222",
        "iat": now,
        "exp": now + 60,
        "jti": str(uuid4()),
    }
    payload.update(overrides)
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ctx = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    sig = hmac.new(
        _SECRET.encode("utf-8"), ctx.encode("ascii"), hashlib.sha256
    ).hexdigest()
    return ctx, sig


@pytest.fixture(autouse=True)
def _hmac_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(GATEWAY_SHARED_SECRET_ENV, _SECRET)
    monkeypatch.delenv(GATEWAY_TRUST_MODE_ENV, raising=False)
    monkeypatch.delenv(GATEWAY_SIGNATURE_REQUIRE_PATH_ENV, raising=False)
    gateway_signature.reset_gateway_replay_cache_for_tests()


def test_accepts_a_valid_context() -> None:
    ctx, sig = _sign()
    payload = verify_gateway_signature_without_request_binding(
        context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
    )
    assert payload["user_id"] == "11111111-1111-1111-1111-111111111111"


def test_rejects_a_bad_signature() -> None:
    ctx, _ = _sign()
    with pytest.raises(GatewaySignatureError):
        verify_gateway_signature_without_request_binding(
            context_b64=ctx, signature_hex="0" * 64, shared_secret=_SECRET
        )


def test_still_records_replay() -> None:
    ctx, sig = _sign()
    verify_gateway_signature_without_request_binding(
        context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
    )
    with pytest.raises(GatewaySignatureError):
        verify_gateway_signature_without_request_binding(
            context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
        )


def test_bound_context_is_accepted_when_flag_is_off() -> None:
    """Flag off: nothing to compare against, same as the documented arm."""
    ctx, sig = _sign(method="GET", path="/api/v1/patients/123")
    payload = verify_gateway_signature_without_request_binding(
        context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
    )
    assert payload["path"] == "/api/v1/patients/123"


def test_bound_context_fails_closed_under_require_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A service that requires the binding cannot verify a bound context here."""
    monkeypatch.setenv(GATEWAY_SIGNATURE_REQUIRE_PATH_ENV, "true")
    ctx, sig = _sign(method="GET", path="/api/v1/patients/123")
    with pytest.raises(GatewayVerifierConfigurationError):
        verify_gateway_signature_without_request_binding(
            context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
        )


def test_has_no_request_method_or_path_parameters() -> None:
    """The name promises no binding; it must not accept request fields."""
    ctx, sig = _sign()
    with pytest.raises(TypeError):
        verify_gateway_signature_without_request_binding(  # type: ignore[call-arg]
            context_b64=ctx,
            signature_hex=sig,
            shared_secret=_SECRET,
            request_method="GET",
        )


def test_deprecated_name_still_binds_when_given_the_request() -> None:
    ctx, sig = _sign(method="GET", path="/api/v1/work-orders/")
    with pytest.raises(GatewaySignatureError):
        verify_gateway_signature(
            context_b64=ctx,
            signature_hex=sig,
            shared_secret=_SECRET,
            request_method="GET",
            request_path="/api/v1/vendors/",
        )


def test_deprecated_name_emits_no_runtime_warning() -> None:
    """Consumers run with ``-W error``; the deprecation is docs plus the check."""
    ctx, sig = _sign()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        verify_gateway_signature(
            context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
        )


def test_new_names_are_exported() -> None:
    for module in (gateway_signature, gateway_identity):
        assert "verify_gateway_signature_without_request_binding" in module.__all__
        assert "verify_gateway_signature_for_request" in module.__all__
    assert (
        gateway_identity.verify_gateway_signature_without_request_binding
        is verify_gateway_signature_without_request_binding
    )
