"""The shared verifier caps signed-context lifetime, like Core's own verifier.

`_verify_replay_window` bounded only "expired" and "issued in the future"
against the current clock. It never bounded `exp - iat`, so a context minted
with `exp = iat + 10 years` verified and was accepted — and under this
platform's threat model the shared HMAC secret is held by every service that
verifies gateway-v1 contexts, any of which could therefore mint itself a
forever-valid identity (is_founder included). Replay protection the token's own
author can opt out of is not replay protection.

`core_app.auth.gateway_context` fixed exactly this in Core's hand-rolled
verifier with `_MAX_CONTEXT_LIFETIME_SECONDS = 300`; the shared package — the
canonical consumer-side verifier for ~52 domain services — never got it. These
tests pin the ceiling here at the same value, under both the HMAC and DUAL
trust modes (the default posture until gateway-v2 keys are distributed), and
confirm a normal 60s context is untouched.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import pytest

from adaptix_contracts.gateway_signature import (
    GATEWAY_SHARED_SECRET_ENV,
    GATEWAY_TRUST_MODE_ENV,
    TRUST_MODE_DUAL,
    TRUST_MODE_HMAC,
    GatewaySignatureError,
    verify_gateway_signature,
)

_SECRET = "unit-test-hmac-material-not-a-real-value"
_TEN_YEARS = 10 * 365 * 86400


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
    """Default posture: a service verifying gateway-v1 by HMAC."""
    monkeypatch.setenv(GATEWAY_SHARED_SECRET_ENV, _SECRET)
    monkeypatch.delenv(GATEWAY_TRUST_MODE_ENV, raising=False)


@pytest.mark.parametrize("mode", [TRUST_MODE_HMAC, TRUST_MODE_DUAL])
def test_long_lived_context_is_rejected(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    """A decade-long context is refused under every symmetric-verifying mode."""
    monkeypatch.setenv(GATEWAY_TRUST_MODE_ENV, mode)
    now = int(time.time())
    ctx, sig = _sign(iat=now, exp=now + _TEN_YEARS)
    with pytest.raises(GatewaySignatureError, match="lifetime .* exceeds the maximum"):
        verify_gateway_signature(
            context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
        )


def test_context_at_the_ceiling_is_accepted() -> None:
    """exp - iat exactly 300s is allowed; 301s is not — the boundary is real."""
    now = int(time.time())
    ok_ctx, ok_sig = _sign(iat=now, exp=now + 300)
    # Must not raise.
    verify_gateway_signature(
        context_b64=ok_ctx, signature_hex=ok_sig, shared_secret=_SECRET
    )

    over_ctx, over_sig = _sign(iat=now, exp=now + 301)
    with pytest.raises(GatewaySignatureError, match="lifetime 301s exceeds"):
        verify_gateway_signature(
            context_b64=over_ctx, signature_hex=over_sig, shared_secret=_SECRET
        )


def test_exp_before_iat_is_rejected() -> None:
    """A window whose exp precedes iat is malformed and refused."""
    now = int(time.time())
    ctx, sig = _sign(iat=now, exp=now - 10)
    with pytest.raises(GatewaySignatureError, match="exp precedes iat"):
        verify_gateway_signature(
            context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
        )


def test_normal_sixty_second_context_still_verifies() -> None:
    """The producer's real 60s contexts are untouched — no legitimate traffic
    is broken by the ceiling."""
    ctx, sig = _sign()  # default exp = iat + 60
    # Must not raise.
    verify_gateway_signature(context_b64=ctx, signature_hex=sig, shared_secret=_SECRET)
