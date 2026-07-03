"""Unit tests for workforce contract schemas.

Exercises valid construction, enum integrity, validation-failure paths for
required/constrained fields, and JSON round-trip stability for the Pydantic
contract schemas in adaptix_contracts.workforce.models.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import BaseModel, ValidationError

from adaptix_contracts.workforce.models import (
    FatigueAssessment,
    FatigueRiskLevel,
    ReturnToDutyRecord,
    StaffProfile,
    StaffRestriction,
    StaffStatus,
    WorkforceAvailability,
)

_NOW = datetime(2026, 7, 3, 12, 0, 0, tzinfo=timezone.utc)


def _assert_json_round_trip(model: BaseModel) -> None:
    """A model must survive dump -> validate and JSON dump -> validate."""

    cls = type(model)
    assert cls.model_validate(model.model_dump()) == model
    assert cls.model_validate_json(model.model_dump_json()) == model


# --------------------------------------------------------------------------- #
# enums
# --------------------------------------------------------------------------- #


def test_fatigue_risk_level_enum_values() -> None:
    assert {level.value for level in FatigueRiskLevel} == {
        "low",
        "moderate",
        "high",
        "critical",
    }


def test_staff_status_enum_values() -> None:
    expected = {"active", "on_leave", "restricted", "return_to_duty", "inactive"}
    actual = {status.value for status in StaffStatus}
    assert actual == expected
    assert len(actual) == len(list(StaffStatus))


# --------------------------------------------------------------------------- #
# StaffProfile
# --------------------------------------------------------------------------- #


def test_staff_profile_valid_and_status_default() -> None:
    profile = StaffProfile(
        staff_id="staff-1",
        tenant_id="tenant-1",
        name="Alex Medic",
        role="paramedic",
        created_at=_NOW,
        updated_at=_NOW,
    )

    assert profile.status is StaffStatus.ACTIVE
    assert profile.certifications == []
    assert profile.unit_assignment is None
    _assert_json_round_trip(profile)


def test_staff_profile_accepts_explicit_status_and_certs() -> None:
    profile = StaffProfile(
        staff_id="staff-1",
        tenant_id="tenant-1",
        name="Alex Medic",
        role="paramedic",
        certifications=["NREMT-P", "ACLS"],
        status=StaffStatus.ON_LEAVE,
        created_at=_NOW,
        updated_at=_NOW,
    )

    assert profile.status is StaffStatus.ON_LEAVE
    assert profile.certifications == ["NREMT-P", "ACLS"]
    _assert_json_round_trip(profile)


def test_staff_profile_missing_required_field_fails() -> None:
    with pytest.raises(ValidationError) as exc_info:
        StaffProfile(
            staff_id="staff-1",
            tenant_id="tenant-1",
            name="Alex Medic",
            role="paramedic",
            created_at=_NOW,
        )  # type: ignore[call-arg]

    assert "updated_at" in str(exc_info.value)


def test_staff_profile_rejects_invalid_status() -> None:
    with pytest.raises(ValidationError):
        StaffProfile(
            staff_id="staff-1",
            tenant_id="tenant-1",
            name="Alex Medic",
            role="paramedic",
            status="unknown_status",
            created_at=_NOW,
            updated_at=_NOW,
        )


# --------------------------------------------------------------------------- #
# FatigueAssessment
# --------------------------------------------------------------------------- #


def test_fatigue_assessment_valid_and_safety_defaults() -> None:
    assessment = FatigueAssessment(
        assessment_id="fa-1",
        staff_id="staff-1",
        tenant_id="tenant-1",
        risk_level=FatigueRiskLevel.HIGH,
        hours_worked_last_24h=16.0,
        hours_worked_last_7d=70.5,
        consecutive_shifts=4,
        assessed_at=_NOW,
    )

    assert assessment.risk_level is FatigueRiskLevel.HIGH
    assert assessment.risk_factors == []
    assert assessment.recommendation is None
    # Human-review-required is the safety default; AI-generated defaults off.
    assert assessment.human_review_required is True
    assert assessment.supervisor_review_flag is False
    assert assessment.ai_generated is False
    _assert_json_round_trip(assessment)


def test_fatigue_assessment_rejects_invalid_risk_level() -> None:
    with pytest.raises(ValidationError):
        FatigueAssessment(
            assessment_id="fa-1",
            staff_id="staff-1",
            tenant_id="tenant-1",
            risk_level="extreme",
            hours_worked_last_24h=16.0,
            hours_worked_last_7d=70.5,
            consecutive_shifts=4,
            assessed_at=_NOW,
        )


def test_fatigue_assessment_rejects_non_numeric_hours() -> None:
    with pytest.raises(ValidationError) as exc_info:
        FatigueAssessment(
            assessment_id="fa-1",
            staff_id="staff-1",
            tenant_id="tenant-1",
            risk_level=FatigueRiskLevel.LOW,
            hours_worked_last_24h="a-lot",  # type: ignore[arg-type]
            hours_worked_last_7d=70.5,
            consecutive_shifts=4,
            assessed_at=_NOW,
        )

    assert "hours_worked_last_24h" in str(exc_info.value)


def test_fatigue_assessment_rejects_non_integer_consecutive_shifts() -> None:
    with pytest.raises(ValidationError):
        FatigueAssessment(
            assessment_id="fa-1",
            staff_id="staff-1",
            tenant_id="tenant-1",
            risk_level=FatigueRiskLevel.LOW,
            hours_worked_last_24h=8.0,
            hours_worked_last_7d=40.0,
            consecutive_shifts="three",  # type: ignore[arg-type]
            assessed_at=_NOW,
        )


# --------------------------------------------------------------------------- #
# StaffRestriction
# --------------------------------------------------------------------------- #


def test_staff_restriction_valid_and_defaults() -> None:
    restriction = StaffRestriction(
        restriction_id="rest-1",
        staff_id="staff-1",
        tenant_id="tenant-1",
        actor_id="actor-1",
        reason="fatigue",
        restriction_type="no_driving",
        start_datetime=_NOW,
        created_at=_NOW,
    )

    assert restriction.end_datetime is None
    assert restriction.supervisor_id is None
    assert restriction.audit_event_emitted is True
    _assert_json_round_trip(restriction)


def test_staff_restriction_missing_reason_fails() -> None:
    with pytest.raises(ValidationError) as exc_info:
        StaffRestriction(
            restriction_id="rest-1",
            staff_id="staff-1",
            tenant_id="tenant-1",
            actor_id="actor-1",
            restriction_type="no_driving",
            start_datetime=_NOW,
            created_at=_NOW,
        )  # type: ignore[call-arg]

    assert "reason" in str(exc_info.value)


# --------------------------------------------------------------------------- #
# ReturnToDutyRecord
# --------------------------------------------------------------------------- #


def test_return_to_duty_record_valid_and_defaults() -> None:
    record = ReturnToDutyRecord(
        record_id="rtd-1",
        staff_id="staff-1",
        tenant_id="tenant-1",
        actor_id="actor-1",
        cleared_by="supervisor-1",
        return_datetime=_NOW,
        created_at=_NOW,
    )

    assert record.clearance_notes is None
    assert record.audit_event_emitted is True
    _assert_json_round_trip(record)


def test_return_to_duty_record_missing_cleared_by_fails() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ReturnToDutyRecord(
            record_id="rtd-1",
            staff_id="staff-1",
            tenant_id="tenant-1",
            actor_id="actor-1",
            return_datetime=_NOW,
            created_at=_NOW,
        )  # type: ignore[call-arg]

    assert "cleared_by" in str(exc_info.value)


# --------------------------------------------------------------------------- #
# WorkforceAvailability
# --------------------------------------------------------------------------- #


def test_workforce_availability_valid_and_linkage_defaults() -> None:
    availability = WorkforceAvailability(
        tenant_id="tenant-1",
        date="2026-07-03",
        shift_type="day",
        available_staff=["staff-1"],
        restricted_staff=["staff-2"],
    )

    assert availability.available_staff == ["staff-1"]
    assert availability.unavailable_staff == []
    assert availability.coverage_adequate is True
    assert availability.cad_linkage_active is True
    assert availability.crewlink_linkage_active is True
    _assert_json_round_trip(availability)


def test_workforce_availability_missing_shift_type_fails() -> None:
    with pytest.raises(ValidationError) as exc_info:
        WorkforceAvailability(
            tenant_id="tenant-1",
            date="2026-07-03",
        )  # type: ignore[call-arg]

    assert "shift_type" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
