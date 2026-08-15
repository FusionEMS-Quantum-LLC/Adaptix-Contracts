"""Contract tests for ``EpcrChartHospitalHandoffEvent``."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from adaptix_contracts.events.registry import (
    ALL_EVENTS,
    EPCR_CHART_HOSPITAL_HANDOFF,
    is_registered,
)
from adaptix_contracts.schemas import (
    EpcrBillingPatientDemographics,
    EpcrChartHospitalHandoffEvent,
)


def _minimal_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "chart_id": "chart-001",
        "tenant_id": "tenant-001",
        "handoff_id": "handoff-001",
        "call_number": "CALL-001",
        "hospital_id": "hospital-001",
        "handoff_status": "transmitted",
        "created_at": datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc).isoformat(),
    }
    payload.update(overrides)
    return payload


def test_minimal_valid_payload_round_trips() -> None:
    event = EpcrChartHospitalHandoffEvent.model_validate(_minimal_payload())
    assert event.event_type == "epcr.chart.hospital_handoff"
    assert event.handoff_status == "transmitted"
    assert event.is_test is False


@pytest.mark.parametrize(
    "required",
    ["chart_id", "tenant_id", "handoff_id", "hospital_id", "handoff_status", "created_at"],
)
def test_required_fields_are_enforced(required: str) -> None:
    payload = _minimal_payload()
    del payload[required]
    with pytest.raises(ValidationError, match=required):
        EpcrChartHospitalHandoffEvent.model_validate(payload)


def test_optional_fields_survive_serialization_round_trip() -> None:
    event = EpcrChartHospitalHandoffEvent.model_validate(
        _minimal_payload(
            hospital_name="North Valley Regional",
            incident_id="incident-001",
            unit_id="unit-12",
            bed_assignment="ED-14",
            receiving_facility="North Valley Regional",
            receiving_clinician_name="Taylor RN",
            receiving_role_title="Charge Nurse",
            transfer_of_care_time="2026-08-14T12:10:00+00:00",
            hl7_message_id="hl7-msg-001",
            chief_complaint="Chest pain",
            primary_impression="Acute coronary syndrome",
            handoff_summary="Crew transferred care to ED charge nurse.",
            patient_demographics={
                "first_name": "Alex",
                "last_name": "Morgan",
                "date_of_birth": "1978-01-15",
            },
            transmitted_at="2026-08-14T12:02:00+00:00",
            acknowledged_at="2026-08-14T12:12:00+00:00",
            is_test=True,
        )
    )
    restored = EpcrChartHospitalHandoffEvent.model_validate(event.model_dump())
    assert restored.hospital_name == "North Valley Regional"
    assert restored.transfer_of_care_time is not None
    assert restored.patient_demographics == EpcrBillingPatientDemographics(
        first_name="Alex",
        last_name="Morgan",
        date_of_birth="1978-01-15",
    )
    assert restored.is_test is True


def test_registry_entry_is_versioned_and_registered() -> None:
    assert EPCR_CHART_HOSPITAL_HANDOFF == "epcr.chart.hospital_handoff"
    assert ALL_EVENTS[EPCR_CHART_HOSPITAL_HANDOFF] == {
        "version": "1.0",
        "source_service": "epcr",
    }
    assert is_registered(EPCR_CHART_HOSPITAL_HANDOFF) is True
