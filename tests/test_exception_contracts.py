"""Contract tests for the universal exception inbox (shared platform primitive F)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from adaptix_contracts import schemas
from adaptix_contracts.schemas.exception_contracts import (
    ExceptionRecord,
    ExceptionSeverity,
    ExceptionStatus,
    is_open,
)
import pytest
from pydantic import ValidationError

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
LATER = NOW + timedelta(hours=2)


def _exception(**overrides: object) -> ExceptionRecord:
    payload: dict[str, object] = {
        "exception_id": "exc-1",
        "tenant_id": "tenant-a",
        "domain": "billing",
        "subject_type": "claim",
        "subject_id": "claim-1",
        "severity": ExceptionSeverity.HIGH,
        "reason_code": "payer_rejected_missing_modifier",
        "human_summary": "The payer rejected this claim for a missing modifier.",
        "created_at": NOW,
        "correlation_id": "corr-1",
    }
    payload.update(overrides)
    return ExceptionRecord(**payload)  # type: ignore[arg-type]


def _resolved(**overrides: object) -> ExceptionRecord:
    payload: dict[str, object] = {
        "status": ExceptionStatus.RESOLVED,
        "resolved_at": LATER,
        "resolved_by": "user-1",
        "resolution": "Added the modifier and resubmitted.",
    }
    payload.update(overrides)
    return _exception(**payload)


class TestOpenness:
    @pytest.mark.parametrize(
        "status",
        [
            ExceptionStatus.OPEN,
            ExceptionStatus.ASSIGNED,
            ExceptionStatus.IN_REVIEW,
            ExceptionStatus.WAITING_EXTERNAL,
            ExceptionStatus.ESCALATED,
        ],
    )
    def test_unfinished_statuses_stay_open(self, status: ExceptionStatus) -> None:
        assert is_open(status)

    @pytest.mark.parametrize(
        "status", [ExceptionStatus.RESOLVED, ExceptionStatus.WAIVED]
    )
    def test_terminal_statuses_are_closed(self, status: ExceptionStatus) -> None:
        assert not is_open(status)

    def test_waiting_external_is_still_open(self) -> None:
        """Blocked on a payer is not blocked on nobody."""

        assert is_open(ExceptionStatus.WAITING_EXTERNAL)

    def test_waived_is_closed_but_distinct_from_resolved(self) -> None:
        """Accepting a problem is not fixing it; the audit needs both numbers."""

        assert not is_open(ExceptionStatus.WAIVED)
        assert ExceptionStatus.WAIVED is not ExceptionStatus.RESOLVED

    def test_unknown_status_fails_open(self) -> None:
        """An exception nobody understands stays visible in the queue."""

        assert is_open("some_new_status")

    def test_every_status_is_classified(self) -> None:
        for status in ExceptionStatus:
            assert isinstance(is_open(status), bool)


class TestResolutionInvariants:
    def test_new_exception_defaults_to_open(self) -> None:
        record = _exception()
        assert record.status is ExceptionStatus.OPEN
        assert record.is_open()

    def test_resolved_requires_who_when_and_what(self) -> None:
        with pytest.raises(ValidationError, match="terminal but"):
            _exception(status=ExceptionStatus.RESOLVED)

    def test_resolved_with_full_detail_is_valid(self) -> None:
        assert not _resolved().is_open()

    def test_waived_requires_the_same_detail(self) -> None:
        with pytest.raises(ValidationError, match="terminal but"):
            _exception(status=ExceptionStatus.WAIVED, resolved_by="user-1")

    def test_open_exception_may_not_claim_a_resolution(self) -> None:
        with pytest.raises(ValidationError, match="not terminal but carries"):
            _exception(resolution="Looks fine to me.")

    def test_resolution_may_not_predate_creation(self) -> None:
        with pytest.raises(ValidationError, match="resolved_at precedes created_at"):
            _resolved(resolved_at=NOW - timedelta(hours=1))

    def test_unknown_field_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _exception(patient_mrn="never")


class TestOverdue:
    def test_an_exception_without_a_deadline_is_never_overdue(self) -> None:
        """A synthetic due date would turn every queue into false urgency."""

        assert not _exception().is_overdue(NOW + timedelta(days=365))

    def test_an_open_exception_past_its_deadline_is_overdue(self) -> None:
        record = _exception(due_at=LATER)
        assert record.is_overdue(LATER + timedelta(minutes=1))

    def test_an_open_exception_before_its_deadline_is_not_overdue(self) -> None:
        assert not _exception(due_at=LATER).is_overdue(NOW)

    def test_a_closed_exception_is_never_overdue(self) -> None:
        record = _resolved(due_at=LATER)
        assert not record.is_overdue(LATER + timedelta(days=30))


def test_severity_ladder_is_complete() -> None:
    assert {member.value for member in ExceptionSeverity} == {
        "info",
        "low",
        "medium",
        "high",
        "critical",
    }


def test_surface_is_exported_from_the_package_root() -> None:
    for name in (
        "ExceptionRecord",
        "ExceptionSeverity",
        "ExceptionStatus",
        "TERMINAL_EXCEPTION_STATUSES",
    ):
        assert name in schemas.__all__
        assert hasattr(schemas, name)
