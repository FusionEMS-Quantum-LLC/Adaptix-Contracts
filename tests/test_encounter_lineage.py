"""Contract tests for EncounterLineage, the compliance fact vocabulary, and
the optional ``lineage`` field on ``EpcrBillingSnapshot`` (5.27.0)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from adaptix_contracts.cad.models import LevelOfCare
from adaptix_contracts.lineage import (
    ComplianceFactResult,
    ComplianceFactStatus,
    EncounterLineage,
)
from adaptix_contracts.schemas.epcr_contracts import (
    EpcrBillingCrewMember,
    EpcrBillingSnapshot,
)

STARTED = datetime(2026, 9, 24, 23, 40, tzinfo=timezone.utc)
COMPLETED = STARTED + timedelta(minutes=55)


def _full_lineage() -> EncounterLineage:
    return EncounterLineage(
        tenant_id="tenant-1",
        dispatch_id="dispatch-1",
        transport_request_id="treq-1",
        trip_id="trip-1",
        epcr_id="chart-1",
        encounter_id="enc-1",
        unit_id="unit-1",
        vehicle_id="vehicle-1",
        crew_member_ids=["crew-b", "crew-a"],
        patient_id="patient-1",
        payer_id="payer-1",
        service_started_at=STARTED,
        service_completed_at=COMPLETED,
        date_of_service=date(2026, 9, 24),
        requested_level_of_care=LevelOfCare.ALS,
        dispatched_level_of_care=LevelOfCare.ALS,
        documented_level_of_care=LevelOfCare.BLS,
        billed_level_of_care=LevelOfCare.BLS,
    )


def test_full_lineage_constructs() -> None:
    lineage = _full_lineage()
    assert lineage.vehicle_id == "vehicle-1"
    assert lineage.crew_member_ids == ["crew-b", "crew-a"]
    assert lineage.documented_level_of_care is LevelOfCare.BLS


def test_minimal_lineage_needs_only_tenant() -> None:
    lineage = EncounterLineage(tenant_id="tenant-1")
    assert lineage.dispatch_id is None
    assert lineage.vehicle_id is None
    assert lineage.crew_member_ids == []
    assert lineage.billed_level_of_care is None


def test_tenant_is_required_and_non_empty() -> None:
    with pytest.raises(ValidationError):
        EncounterLineage()  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        EncounterLineage(tenant_id="")


def test_empty_identifier_rejected() -> None:
    with pytest.raises(ValidationError):
        EncounterLineage(tenant_id="tenant-1", vehicle_id="")
    with pytest.raises(ValidationError):
        EncounterLineage(tenant_id="tenant-1", crew_member_ids=["crew-a", ""])


def test_unknown_fields_are_ignored_for_forward_compatibility() -> None:
    """A newer producer's extra field must not break an older consumer, and is never kept."""
    lineage = EncounterLineage.model_validate(
        {"tenant_id": "tenant-1", "vehicle_name": "Medic 7"}
    )
    assert lineage.tenant_id == "tenant-1"
    assert "vehicle_name" not in lineage.model_dump()
    snapshot_field = EncounterLineage.model_validate(
        {"tenant_id": "t", "future_field": 1}
    ).model_dump()
    assert "future_field" not in snapshot_field


@pytest.mark.parametrize("field", ["service_started_at", "service_completed_at"])
def test_naive_datetime_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        EncounterLineage(tenant_id="tenant-1", **{field: datetime(2026, 9, 24, 23, 40)})


def test_completed_before_started_rejected() -> None:
    with pytest.raises(ValidationError, match="must not precede"):
        EncounterLineage(
            tenant_id="tenant-1",
            service_started_at=COMPLETED,
            service_completed_at=STARTED,
        )


def test_completed_equal_to_started_allowed() -> None:
    lineage = EncounterLineage(
        tenant_id="tenant-1", service_started_at=STARTED, service_completed_at=STARTED
    )
    assert lineage.service_completed_at == lineage.service_started_at


def test_crew_member_ids_deduplicated_preserving_order() -> None:
    lineage = EncounterLineage(
        tenant_id="tenant-1",
        crew_member_ids=["crew-c", "crew-a", "crew-c", "crew-b", "crew-a"],
    )
    assert lineage.crew_member_ids == ["crew-c", "crew-a", "crew-b"]


def test_date_of_service_not_forced_to_utc_date_of_start() -> None:
    # 02:00Z on the 25th is 21:00 on the 24th in US Central time; the date of
    # service is agency-local (5.26.0), so the contract must not force the UTC date.
    lineage = EncounterLineage(
        tenant_id="tenant-1",
        service_started_at=datetime(2026, 9, 25, 2, 0, tzinfo=timezone.utc),
        date_of_service=date(2026, 9, 24),
    )
    assert lineage.date_of_service == date(2026, 9, 24)


def test_unknown_level_of_care_code_rejected() -> None:
    with pytest.raises(ValidationError):
        EncounterLineage(tenant_id="tenant-1", billed_level_of_care="PARAMEDIC_PLUS")


def test_snapshot_round_trips_with_lineage() -> None:
    snapshot = EpcrBillingSnapshot(
        attending_crew=[EpcrBillingCrewMember(crew_member_id="crew-a", level_code="P")],
        date_of_service=date(2026, 9, 24),
        lineage=_full_lineage(),
    )
    restored = EpcrBillingSnapshot.model_validate_json(snapshot.model_dump_json())
    assert restored == snapshot
    assert restored.lineage is not None
    assert restored.lineage.vehicle_id == "vehicle-1"
    assert restored.lineage.service_started_at == STARTED
    assert restored.attending_crew[0].crew_member_id == "crew-a"


def test_snapshot_round_trips_without_lineage() -> None:
    snapshot = EpcrBillingSnapshot(date_of_service=date(2026, 9, 24))
    restored = EpcrBillingSnapshot.model_validate_json(snapshot.model_dump_json())
    assert restored == snapshot
    assert restored.lineage is None


def test_old_payload_without_lineage_still_validates() -> None:
    payload = {
        "chart_status": "finalized",
        "level_of_service_code": "A0427",
        "attending_crew": [{"crew_member_id": "crew-a", "level_code": "P"}],
        "date_of_service": "2026-09-24",
        "missing_fields": [],
        "ready_for_billing": True,
    }
    snapshot = EpcrBillingSnapshot.model_validate(payload)
    assert snapshot.lineage is None
    assert snapshot.ready_for_billing is True


def test_snapshot_rejects_invalid_nested_lineage() -> None:
    with pytest.raises(ValidationError):
        EpcrBillingSnapshot.model_validate({"lineage": {"vehicle_id": "vehicle-1"}})


def test_compliance_fact_status_values() -> None:
    assert [status.value for status in ComplianceFactStatus] == [
        "VALID",
        "INVALID",
        "UNKNOWN",
    ]


def test_compliance_fact_result_constructs() -> None:
    result = ComplianceFactResult(
        status=ComplianceFactStatus.UNKNOWN,
        evaluated_at=COMPLETED,
        as_of=STARTED,
        source_system="fleet",
        reason="source unavailable",
    )
    restored = ComplianceFactResult.model_validate_json(result.model_dump_json())
    assert restored == result
    assert restored.source_record_id is None


@pytest.mark.parametrize("field", ["evaluated_at", "as_of"])
def test_compliance_fact_result_requires_aware_times(field: str) -> None:
    values = {
        "status": ComplianceFactStatus.VALID,
        "evaluated_at": COMPLETED,
        "as_of": STARTED,
        "source_system": "fleet",
    }
    values[field] = datetime(2026, 9, 24, 23, 40)
    with pytest.raises(ValidationError):
        ComplianceFactResult.model_validate(values)


def test_compliance_fact_result_requires_times_and_source() -> None:
    with pytest.raises(ValidationError):
        ComplianceFactResult.model_validate(
            {"status": "VALID", "source_system": "fleet"}
        )
    with pytest.raises(ValidationError):
        ComplianceFactResult.model_validate(
            {
                "status": "VALID",
                "evaluated_at": COMPLETED,
                "as_of": STARTED,
                "source_system": "",
            }
        )
