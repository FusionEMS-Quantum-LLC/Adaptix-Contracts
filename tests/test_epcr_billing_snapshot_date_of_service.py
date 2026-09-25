"""Date of service on the ePCR billing snapshot (5.26.0, BILL-PRE-001).

Billing stamped every ePCR-sourced claim with the chart FINALIZATION date
because the snapshot carried no date of service. These fields carry the
encounter instant (NEMSIS eTimes) and its agency-local calendar date, and
older payloads without them must still validate.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from adaptix_contracts.schemas import EpcrBillingSnapshot, EpcrChartFinalizedEvent


def _event(snapshot: dict | None) -> dict:
    payload: dict = {
        "chart_id": "c-1",
        "tenant_id": "t-1",
        "call_number": "CALL-1",
        "finalized_at": "2026-03-02T02:30:00+00:00",
    }
    if snapshot is not None:
        payload["billing_snapshot"] = snapshot
    return payload


def test_snapshot_carries_local_date_of_service_distinct_from_finalized_at() -> None:
    event = EpcrChartFinalizedEvent.model_validate(
        _event(
            {
                "date_of_service": "2026-03-01",
                "encounter_occurred_at": "2026-03-01T20:30:00-06:00",
            }
        )
    )
    snap = event.billing_snapshot
    assert snap is not None
    assert snap.date_of_service == date(2026, 3, 1)
    assert snap.encounter_occurred_at == datetime(
        2026, 3, 2, 2, 30, tzinfo=timezone.utc
    )
    assert snap.encounter_occurred_at.utcoffset() == timedelta(hours=-6)
    assert event.finalized_at.date() == date(2026, 3, 2)


def test_round_trip_preserves_both_fields() -> None:
    snap = EpcrBillingSnapshot(
        date_of_service=date(2026, 3, 1),
        encounter_occurred_at=datetime(2026, 3, 2, 2, 30, tzinfo=timezone.utc),
    )
    dumped = snap.model_dump(mode="json")
    assert dumped["date_of_service"] == "2026-03-01"
    assert dumped["encounter_occurred_at"].startswith("2026-03-02T02:30:00")
    assert EpcrBillingSnapshot.model_validate(dumped) == snap


def test_older_snapshot_without_fields_still_validates_as_none() -> None:
    event = EpcrChartFinalizedEvent.model_validate(
        _event({"chart_status": "finalized", "ready_for_billing": True})
    )
    assert event.billing_snapshot is not None
    assert event.billing_snapshot.date_of_service is None
    assert event.billing_snapshot.encounter_occurred_at is None


def test_legacy_event_without_snapshot_still_validates() -> None:
    event = EpcrChartFinalizedEvent.model_validate(_event(None))
    assert event.billing_snapshot is None


def test_naive_encounter_instant_is_rejected() -> None:
    with pytest.raises(ValidationError):
        EpcrBillingSnapshot.model_validate(
            {"encounter_occurred_at": "2026-03-01T20:30:00"}
        )
