"""AX5-00037 / AX5-00038 — audience checking that runs for every service.

Before this, the audience block ran ONLY when
``ADAPTIX_GATEWAY_EXPECTED_AUDIENCE`` was set. The audited Terraform showed the
variable configured for five workloads (forms, geo, reference-data, facilities,
vision) against 60 routed workload rows without it, so on the overwhelming
majority of services the gateway signed an audience that nobody read: a context
with no audience, a bogus audience, and the correct audience all verified
identically and logged identically.

Two layers now apply unconditionally — presence and registry membership — and
are safe to apply unconditionally because every legitimate Adaptix producer
already satisfies them. The exact per-service pin remains the only layer that
can stop A-to-B replay, and it is asserted separately here so its scope is not
overstated.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import pytest

from adaptix_contracts.gateway_signature import (
    GATEWAY_EXPECTED_AUDIENCE_ENV,
    GatewaySignatureError,
    verify_gateway_signature,
)
from adaptix_contracts.service_audiences import KNOWN_SERVICE_AUDIENCES

_SECRET = "unit-test-hmac-material-not-a-real-value"


def _sign(**overrides: object) -> tuple[str, str]:
    """Mint a byte-compatible signed context with the given payload overrides."""
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
def _unpinned(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run every test as an UNPINNED service — the majority of the fleet."""
    monkeypatch.delenv(GATEWAY_EXPECTED_AUDIENCE_ENV, raising=False)


# ---------------------------------------------------------------------------
# Layer 1 — presence, enforced for every service
# ---------------------------------------------------------------------------


def test_unpinned_service_rejects_a_context_with_no_audience() -> None:
    """ "No audience" must not be readable as "any audience"."""
    ctx, sig = _sign(aud=None)
    with pytest.raises(GatewaySignatureError, match="missing required claim"):
        verify_gateway_signature(
            context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
        )


def test_unpinned_service_rejects_an_empty_audience_string() -> None:
    """An empty string is absence wearing the right type."""
    ctx, sig = _sign(aud="")
    with pytest.raises(GatewaySignatureError, match="missing required claim"):
        verify_gateway_signature(
            context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
        )


# ---------------------------------------------------------------------------
# Layer 2 — registry membership, enforced for every service
# ---------------------------------------------------------------------------


def test_unpinned_service_rejects_an_audience_that_names_no_live_service() -> None:
    """A context addressed to something that is not an Adaptix service is not a
    context any Adaptix producer emits."""
    ctx, sig = _sign(aud="attacker-controlled-value")
    with pytest.raises(
        GatewaySignatureError, match="does not name a live Adaptix service"
    ):
        verify_gateway_signature(
            context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
        )


def test_unpinned_service_rejects_a_list_of_unknown_audiences() -> None:
    """The list shape must not become the way around the membership check."""
    ctx, sig = _sign(aud=["nope", "also-nope"])
    with pytest.raises(
        GatewaySignatureError, match="does not name a live Adaptix service"
    ):
        verify_gateway_signature(
            context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
        )


def test_unpinned_service_still_accepts_a_real_gateway_context() -> None:
    """Non-breaking: an unpinned service keeps accepting real traffic.

    This is the assertion that makes the two layers above deployable to ~47
    services at once — they reject only shapes no producer emits.
    """
    ctx, sig = _sign(aud="adaptix-core")
    payload = verify_gateway_signature(
        context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
    )
    assert payload["aud"] == "adaptix-core"


@pytest.mark.parametrize("audience", sorted(KNOWN_SERVICE_AUDIENCES))
def test_every_registered_service_audience_verifies(audience: str) -> None:
    """Every audience the gateway is allowed to sign must verify everywhere.

    The gateway refuses to route a prefix whose audience is not in this set, so
    this is the exact set of values that can arrive in production. If membership
    checking ever diverges from the registry, this fails for the specific
    audience that would 401 in production rather than for "some" audience.
    """
    ctx, sig = _sign(aud=audience)
    payload = verify_gateway_signature(
        context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
    )
    assert payload["aud"] == audience


# ---------------------------------------------------------------------------
# Layer 3 — the exact pin, and its configuration
# ---------------------------------------------------------------------------


def test_pin_stops_cross_service_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only the exact pin can tell service A's context from service B's.

    Both contexts below pass layers 1 and 2 — the audience is present and names
    a live service — so this is the layer that has to be installed per service
    for cross-service replay to actually close.
    """
    monkeypatch.setenv(GATEWAY_EXPECTED_AUDIENCE_ENV, "adaptix-billing")
    ctx, sig = _sign(aud="adaptix-core")
    with pytest.raises(GatewaySignatureError, match="unexpected audience"):
        verify_gateway_signature(
            context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
        )


def test_a_misconfigured_pin_fails_loudly_not_silently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A typo in the pin is indistinguishable from an attack at the request layer.

    ``ADAPTIX_GATEWAY_EXPECTED_AUDIENCE=adaptix-labour`` (British spelling) fails
    every real request with "unexpected audience" — a 401 storm that reads
    exactly like forged traffic. Validating the CONFIGURED value against the
    registry names the actual problem instead.
    """
    monkeypatch.setenv(GATEWAY_EXPECTED_AUDIENCE_ENV, "adaptix-labour")
    ctx, sig = _sign(aud="adaptix-labor")
    with pytest.raises(GatewaySignatureError, match="does not name a live"):
        verify_gateway_signature(
            context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
        )


def test_a_correct_pin_still_accepts_its_own_audience(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The five already-pinned workloads keep working."""
    monkeypatch.setenv(GATEWAY_EXPECTED_AUDIENCE_ENV, "adaptix-vision")
    ctx, sig = _sign(aud="adaptix-vision")
    payload = verify_gateway_signature(
        context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
    )
    assert payload["aud"] == "adaptix-vision"


def test_pinned_list_membership_still_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    """RFC 7519 list-form aud keeps working under the pin."""
    monkeypatch.setenv(GATEWAY_EXPECTED_AUDIENCE_ENV, "adaptix-core")
    ctx, sig = _sign(aud=["adaptix-core", "adaptix-billing"])
    payload = verify_gateway_signature(
        context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
    )
    assert payload["aud"] == ["adaptix-core", "adaptix-billing"]
