"""ePCR test-record isolation flag on the cross-domain contracts.

``is_test`` lets a consumer (Billing, Patient-Identity, analytics) refuse to
create payer-facing or identity-facing artifacts from a non-production ePCR —
e.g. a Founder WARDS Lab record.

EPCR is the authoritative chokepoint and does not emit a finalize event for a
test chart at all. This flag exists so consumers can *additionally* defend
themselves rather than trusting upstream filtering.

The critical property pinned here is the DEFAULT: it must be ``False``, so that

* every existing producer and every already-persisted event stays valid, and
* an omitted value fails CLOSED toward production semantics — a real patient
  encounter can never be silently dropped from billing because a field was
  missing.

The unsafe direction would be defaulting to ``True``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from adaptix_contracts.schemas import EpcrChartFinalizedEvent

# EpcrBillingHandoffPayload is not re-exported from the schemas package; import
# it from its defining module the same way consumers do.
from adaptix_contracts.schemas.epcr_contracts import EpcrBillingHandoffPayload


def _finalized_event(**overrides) -> EpcrChartFinalizedEvent:
    payload = {
        "chart_id": "chart-1",
        "tenant_id": "tenant-1",
        "call_number": "CALL-1",
        "finalized_at": datetime.now(timezone.utc),
        "is_nemsis_compliant": True,
    }
    payload.update(overrides)
    return EpcrChartFinalizedEvent(**payload)


def _handoff(**overrides) -> EpcrBillingHandoffPayload:
    now = datetime.now(timezone.utc)
    payload = {
        "chart_id": "chart-1",
        "tenant_id": "tenant-1",
        "call_number": "CALL-1",
        "incident_type": "medical",
        "is_nemsis_compliant": True,
        "finalized_at": now,
        "created_at": now,
    }
    payload.update(overrides)
    return EpcrBillingHandoffPayload(**payload)


def test_finalized_event_defaults_to_production():
    """Omitting is_test must mean production (fail closed)."""
    assert _finalized_event().is_test is False


def test_billing_handoff_defaults_to_production():
    assert _handoff().is_test is False


def test_finalized_event_accepts_test_flag():
    assert _finalized_event(is_test=True).is_test is True


def test_billing_handoff_accepts_test_flag():
    assert _handoff(is_test=True).is_test is True


def test_flag_survives_serialization_round_trip():
    """A consumer reading a serialized event must still see is_test."""
    original = _finalized_event(is_test=True)
    restored = EpcrChartFinalizedEvent.model_validate(original.model_dump())
    assert restored.is_test is True


def test_legacy_payload_without_flag_is_still_valid():
    """Events persisted before this field existed must not fail validation."""
    legacy = {
        "chart_id": "chart-legacy",
        "tenant_id": "tenant-1",
        "call_number": "CALL-LEGACY",
        "finalized_at": datetime.now(timezone.utc).isoformat(),
        "is_nemsis_compliant": True,
    }
    event = EpcrChartFinalizedEvent.model_validate(legacy)
    assert event.is_test is False
