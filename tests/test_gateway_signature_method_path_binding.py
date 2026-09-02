"""Ledger item 1, gap 1: signed ``method``/``path`` binding.

The signed context previously carried no binding to the HTTP request it was
minted for, so a context minted for one route verified identically when
presented against a different route of the same audience/tenant/user (e.g. a
context signed alongside ``GET /patients/{id}`` also verified against
``DELETE /patients/{id}``). ``verify_gateway_signature`` now compares the
payload's ``method``/``path`` claims — when the payload carries them — against
the caller-supplied ``request_method``/``request_path``, gated by
``ADAPTIX_GATEWAY_SIGNATURE_REQUIRE_PATH`` for the absent-claims case only.

These tests exercise the verifier in isolation (hand-built payloads), since
the producer side (Adaptix-Gateway) ships in a separate repository/PR.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from uuid import uuid4

import pytest

from adaptix_contracts.gateway_signature import (
    GATEWAY_SIGNATURE_REQUIRE_PATH_ENV,
    GATEWAY_SHARED_SECRET_ENV,
    GATEWAY_TRUST_MODE_ENV,
    GatewaySignatureError,
    GatewayVerifierConfigurationError,
    verify_gateway_signature,
)

_SECRET = "unit-test-hmac-material-not-a-real-value"


def _sign(**overrides: object) -> tuple[str, str]:
    """Mint a byte-compatible signed gateway-v1 context with payload overrides."""
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
    payload = {k: v for k, v in payload.items() if v is not None}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ctx = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    sig = hmac.new(
        _SECRET.encode("utf-8"), ctx.encode("ascii"), hashlib.sha256
    ).hexdigest()
    return ctx, sig


@pytest.fixture(autouse=True)
def _hmac_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default posture: a service verifying gateway-v1 by HMAC, flag off."""
    monkeypatch.setenv(GATEWAY_SHARED_SECRET_ENV, _SECRET)
    monkeypatch.delenv(GATEWAY_TRUST_MODE_ENV, raising=False)
    monkeypatch.delenv(GATEWAY_SIGNATURE_REQUIRE_PATH_ENV, raising=False)


# ---------------------------------------------------------------------------
# Compat mode: flag OFF (default)
# ---------------------------------------------------------------------------


class TestCompatModeFlagOff:
    def test_payload_without_binding_is_accepted(self) -> None:
        """Pre-rollout producers signing no method/path must not be rejected."""
        ctx, sig = _sign()
        # Must not raise, even though we pass the actual request to compare.
        payload = verify_gateway_signature(
            context_b64=ctx,
            signature_hex=sig,
            shared_secret=_SECRET,
            request_method="GET",
            request_path="/api/v1/patients/123",
        )
        assert "method" not in payload

    def test_payload_with_binding_but_no_request_supplied_is_accepted(self) -> None:
        """A caller not yet wired to pass request_method/path is unaffected."""
        ctx, sig = _sign(method="GET", path="/api/v1/patients/123")
        payload = verify_gateway_signature(
            context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
        )
        assert payload["method"] == "GET"

    def test_matching_binding_is_accepted(self) -> None:
        ctx, sig = _sign(method="POST", path="/api/v1/claims")
        verify_gateway_signature(
            context_b64=ctx,
            signature_hex=sig,
            shared_secret=_SECRET,
            request_method="POST",
            request_path="/api/v1/claims",
        )  # must not raise

    def test_method_mismatch_is_rejected_even_with_flag_off(self) -> None:
        """A claim the payload DOES make is always checked, flag or not."""
        ctx, sig = _sign(method="GET", path="/api/v1/patients/123")
        with pytest.raises(GatewaySignatureError, match="method"):
            verify_gateway_signature(
                context_b64=ctx,
                signature_hex=sig,
                shared_secret=_SECRET,
                request_method="DELETE",
                request_path="/api/v1/patients/123",
            )

    def test_path_mismatch_is_rejected_even_with_flag_off(self) -> None:
        ctx, sig = _sign(method="GET", path="/api/v1/patients/123")
        with pytest.raises(GatewaySignatureError, match="path"):
            verify_gateway_signature(
                context_b64=ctx,
                signature_hex=sig,
                shared_secret=_SECRET,
                request_method="GET",
                request_path="/api/v1/patients/456",
            )

    def test_method_comparison_is_case_insensitive(self) -> None:
        ctx, sig = _sign(method="GET", path="/api/v1/patients/123")
        verify_gateway_signature(
            context_b64=ctx,
            signature_hex=sig,
            shared_secret=_SECRET,
            request_method="get",
            request_path="/api/v1/patients/123",
        )  # must not raise

    def test_request_path_query_string_is_stripped_before_comparison(self) -> None:
        """The producer never signs a query string; the verifier must not
        require the caller to strip one either."""
        ctx, sig = _sign(method="GET", path="/api/v1/patients")
        verify_gateway_signature(
            context_b64=ctx,
            signature_hex=sig,
            shared_secret=_SECRET,
            request_method="GET",
            request_path="/api/v1/patients?limit=50&cursor=abc",
        )  # must not raise

    def test_trailing_slash_on_the_request_path_is_not_a_mismatch(self) -> None:
        """Codacy flagged the normalizer as sensitive to a trailing slash --
        a producer and consumer that format the same logical path slightly
        differently (redirect_slashes, mounted routers) must not
        false-negative against each other over a cosmetic difference."""
        ctx, sig = _sign(method="GET", path="/api/v1/patients")
        verify_gateway_signature(
            context_b64=ctx,
            signature_hex=sig,
            shared_secret=_SECRET,
            request_method="GET",
            request_path="/api/v1/patients/",
        )  # must not raise

    def test_trailing_slash_on_the_signed_path_is_not_a_mismatch(self) -> None:
        """Same normalization applies symmetrically to the signed claim."""
        ctx, sig = _sign(method="GET", path="/api/v1/patients/")
        verify_gateway_signature(
            context_b64=ctx,
            signature_hex=sig,
            shared_secret=_SECRET,
            request_method="GET",
            request_path="/api/v1/patients",
        )  # must not raise

    def test_root_path_normalizes_to_slash_not_empty_string(self) -> None:
        """The rstrip-based normalizer must not turn "/" into "" -- an empty
        normalized path would compare unequal to itself in a way that looks
        like a mismatch, or worse, unequal paths could both collapse to "".
        """
        ctx, sig = _sign(method="GET", path="/")
        verify_gateway_signature(
            context_b64=ctx,
            signature_hex=sig,
            shared_secret=_SECRET,
            request_method="GET",
            request_path="/",
        )  # must not raise

    def test_trailing_slash_does_not_widen_acceptance_to_a_different_path(
        self,
    ) -> None:
        """A materially different path must still fail even with trailing
        slashes on either side -- normalization must never become a
        bypass."""
        ctx, sig = _sign(method="GET", path="/api/v1/patients/")
        with pytest.raises(GatewaySignatureError, match="path"):
            verify_gateway_signature(
                context_b64=ctx,
                signature_hex=sig,
                shared_secret=_SECRET,
                request_method="GET",
                request_path="/api/v1/claims/",
            )


# ---------------------------------------------------------------------------
# Enforcement mode: ADAPTIX_GATEWAY_SIGNATURE_REQUIRE_PATH=true
# ---------------------------------------------------------------------------


class TestRequirePathBindingEnabled:
    @pytest.fixture(autouse=True)
    def _enable_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(GATEWAY_SIGNATURE_REQUIRE_PATH_ENV, "true")

    def test_payload_without_binding_fails_closed(self) -> None:
        """A pre-upgrade producer's context is refused once this service
        declares it requires the binding — the fail-closed half of the
        rollout contract."""
        ctx, sig = _sign()
        with pytest.raises(GatewaySignatureError, match="carries no method/path"):
            verify_gateway_signature(
                context_b64=ctx,
                signature_hex=sig,
                shared_secret=_SECRET,
                request_method="GET",
                request_path="/api/v1/patients/123",
            )

    def test_binding_present_but_caller_omits_actual_request_fails_closed(self) -> None:
        """Flipping the flag before wiring the local call site must not
        silently disable the check it was meant to enforce."""
        ctx, sig = _sign(method="GET", path="/api/v1/patients/123")
        with pytest.raises(GatewayVerifierConfigurationError, match="not given"):
            verify_gateway_signature(
                context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
            )

    def test_matching_binding_still_verifies(self) -> None:
        ctx, sig = _sign(method="PUT", path="/api/v1/patients/123")
        verify_gateway_signature(
            context_b64=ctx,
            signature_hex=sig,
            shared_secret=_SECRET,
            request_method="PUT",
            request_path="/api/v1/patients/123",
        )  # must not raise

    def test_mismatched_binding_is_rejected(self) -> None:
        ctx, sig = _sign(method="PUT", path="/api/v1/patients/123")
        with pytest.raises(GatewaySignatureError):
            verify_gateway_signature(
                context_b64=ctx,
                signature_hex=sig,
                shared_secret=_SECRET,
                request_method="PUT",
                request_path="/api/v1/patients/999",
            )

    @pytest.mark.parametrize("raw", ["1", "true", "True", "YES", "on"])
    def test_truthy_spellings_all_enforce(
        self, monkeypatch: pytest.MonkeyPatch, raw: str
    ) -> None:
        monkeypatch.setenv(GATEWAY_SIGNATURE_REQUIRE_PATH_ENV, raw)
        ctx, sig = _sign()
        with pytest.raises(GatewaySignatureError, match="carries no method/path"):
            verify_gateway_signature(
                context_b64=ctx,
                signature_hex=sig,
                shared_secret=_SECRET,
                request_method="GET",
                request_path="/x",
            )

    @pytest.mark.parametrize("raw", ["", "0", "false", "off", "no"])
    def test_falsy_spellings_all_stay_compat(
        self, monkeypatch: pytest.MonkeyPatch, raw: str
    ) -> None:
        monkeypatch.setenv(GATEWAY_SIGNATURE_REQUIRE_PATH_ENV, raw)
        ctx, sig = _sign()
        verify_gateway_signature(
            context_b64=ctx,
            signature_hex=sig,
            shared_secret=_SECRET,
            request_method="GET",
            request_path="/x",
        )  # must not raise
