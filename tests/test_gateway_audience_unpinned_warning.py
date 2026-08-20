"""Unpinned-audience observability (AX5-00036 downstream half).

The gateway signs a PER-ROUTE audience into every context it mints
(``_audience_for_path`` -> ``sign_context(audience=...)`` in
``Adaptix-Gateway/backend/app/middleware/cognito_auth.py``). For a Cognito token
the gateway then SKIPS its own audience enforcement, because a Cognito JWT
carries ``aud=<client_id>`` and never a service audience — gateway-side
enforcement is impossible by construction there.

That makes ``verify_gateway_signature`` the ONLY place the signed audience can
be checked, and it is a no-op when ``ADAPTIX_GATEWAY_EXPECTED_AUDIENCE`` is
unset. Unset therefore means the audience is enforced at neither end and a
context minted for one service is replayable against another — while looking
identical in logs to a correctly-pinned service.

These tests pin the warning that makes the gap enumerable, and prove it did not
turn into a rejection (which would 401 every service still missing the var).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from uuid import uuid4

import pytest

import adaptix_contracts.gateway_signature as gs
from adaptix_contracts.gateway_signature import (
    GatewaySignatureError,
    verify_gateway_signature,
)

_SECRET = "aud-test-shared-secret"  # noqa: S105 — test-only fixture, not a real secret


@pytest.fixture(autouse=True)
def _reset_warning_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """The guard is one-shot per process; reset it so each test is independent."""
    monkeypatch.delenv("ADAPTIX_GATEWAY_EXPECTED_AUDIENCE", raising=False)
    monkeypatch.setitem(gs._WARN_ONCE, "audience_unpinned", False)


def _sign(*, aud: object = "adaptix-core") -> tuple[str, str]:
    now = int(time.time())
    payload = {
        "sub": str(uuid4()),
        "user_id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "email": "user@adaptix.test",
        "roles": ["medic"],
        "scopes": [],
        "is_founder": False,
        "mfa_verified": False,
        "iss": "adaptix-gateway",
        "aud": aud,
        "iat": now,
        "exp": now + 60,
        "jti": str(uuid4()),
    }
    serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    ctx = base64.urlsafe_b64encode(serialized).rstrip(b"=").decode("ascii")
    sig = hmac.new(
        _SECRET.encode("utf-8"), ctx.encode("ascii"), hashlib.sha256
    ).hexdigest()
    return ctx, sig


def test_unpinned_audience_warns_once(caplog: pytest.LogCaptureFixture) -> None:
    """A signed aud with no expected audience configured must warn."""
    ctx, sig = _sign()
    with caplog.at_level("WARNING", logger="adaptix_contracts.gateway_signature"):
        verify_gateway_signature(
            context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
        )
    messages = [r.getMessage() for r in caplog.records]
    assert any(
        "ADAPTIX_GATEWAY_EXPECTED_AUDIENCE is not configured" in m for m in messages
    ), messages
    # The signed audience must be named so the operator knows what to pin to.
    assert any("adaptix-core" in m for m in messages), messages


def test_unpinned_audience_does_not_reject(caplog: pytest.LogCaptureFixture) -> None:
    """DENY-nothing: warning only. Rejecting would 401 every unpinned service."""
    ctx, sig = _sign()
    payload = verify_gateway_signature(
        context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
    )
    assert payload["aud"] == "adaptix-core"


def test_warning_is_one_shot_per_process(caplog: pytest.LogCaptureFixture) -> None:
    """The guard must prevent per-request log flooding."""
    with caplog.at_level("WARNING", logger="adaptix_contracts.gateway_signature"):
        for _ in range(3):
            ctx, sig = _sign()
            verify_gateway_signature(
                context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
            )
    warnings = [r for r in caplog.records if "EXPECTED_AUDIENCE" in r.getMessage()]
    assert len(warnings) == 1


def test_no_warning_when_audience_is_pinned(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A correctly-pinned service must stay quiet."""
    monkeypatch.setenv("ADAPTIX_GATEWAY_EXPECTED_AUDIENCE", "adaptix-core")
    ctx, sig = _sign()
    with caplog.at_level("WARNING", logger="adaptix_contracts.gateway_signature"):
        verify_gateway_signature(
            context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
        )
    assert not [r for r in caplog.records if "EXPECTED_AUDIENCE" in r.getMessage()]


def test_context_with_no_audience_is_rejected(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A context carrying no ``aud`` is REJECTED, so it can never be warned about.

    This test previously asserted that such a context verified silently, on the
    reasoning that "no signed aud means nothing to pin". That reasoning is what
    AX5-00037/AX5-00038 identified: "no audience" and "correct audience" then
    produced identical outcomes and identical logs. Every legitimate producer
    signs an audience — the gateway's ``_audience_for_path`` cannot return empty
    and ``build_gateway_signed_headers`` raises without one — so presence is now
    required for every service, pinned or not.

    The original property (no noisy warning) still holds, and now holds because
    the context never reaches the warning branch at all.
    """
    ctx, sig = _sign(aud=None)
    with caplog.at_level("WARNING", logger="adaptix_contracts.gateway_signature"):
        with pytest.raises(GatewaySignatureError, match="missing required claim"):
            verify_gateway_signature(
                context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
            )
    assert not [r for r in caplog.records if "EXPECTED_AUDIENCE" in r.getMessage()]


def test_pinned_audience_still_rejects_a_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DENY: the real enforcement path is untouched by the warning branch."""
    monkeypatch.setenv("ADAPTIX_GATEWAY_EXPECTED_AUDIENCE", "adaptix-billing")
    ctx, sig = _sign(aud="adaptix-core")
    with pytest.raises(GatewaySignatureError, match="unexpected audience"):
        verify_gateway_signature(
            context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
        )


def test_pinned_audience_accepts_list_membership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ALLOW: list-form aud membership still passes (no regression)."""
    monkeypatch.setenv("ADAPTIX_GATEWAY_EXPECTED_AUDIENCE", "adaptix-core")
    ctx, sig = _sign(aud=["adaptix-core", "adaptix-billing"])
    payload = verify_gateway_signature(
        context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
    )
    assert payload["aud"] == ["adaptix-core", "adaptix-billing"]
