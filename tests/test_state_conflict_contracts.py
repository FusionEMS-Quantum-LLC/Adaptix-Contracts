"""Contract tests for protected-state conflicts (shared platform primitive G)."""

from __future__ import annotations

from datetime import datetime, timezone

from adaptix_contracts import schemas
from adaptix_contracts.schemas.state_conflict_contracts import (
    ProtectedStateKind,
    ProtectedStateWrite,
    StateConflict,
    has_state_conflict,
    next_state_version,
)
import pytest
from pydantic import ValidationError

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)


def _conflict(**overrides: object) -> StateConflict:
    payload: dict[str, object] = {
        "tenant_id": "tenant-a",
        "resource_type": "epcr_chart",
        "resource_id": "chart-1",
        "protected_state": ProtectedStateKind.CHART_LOCKED,
        "expected_state_version": 4,
        "current_state_version": 5,
        "detected_at": NOW,
        "correlation_id": "corr-1",
    }
    payload.update(overrides)
    return StateConflict(**payload)  # type: ignore[arg-type]


class TestConflictDetection:
    def test_matching_versions_are_not_a_conflict(self) -> None:
        assert not has_state_conflict(4, 4)

    def test_a_newer_current_version_is_a_conflict(self) -> None:
        assert has_state_conflict(4, 5)

    def test_a_version_that_went_backwards_is_also_a_conflict(self) -> None:
        """A restored or rewritten record is at least as dangerous as a lost update."""

        assert has_state_conflict(5, 4)


class TestVersionAdvance:
    def test_version_advances_by_exactly_one(self) -> None:
        assert next_state_version(4) == 5

    def test_zero_is_a_valid_starting_version(self) -> None:
        assert next_state_version(0) == 1

    def test_negative_version_is_refused(self) -> None:
        with pytest.raises(ValueError, match="must not be negative"):
            next_state_version(-1)


class TestProtectedStateWrite:
    def test_expected_version_has_no_default(self) -> None:
        """A default would silently give the caller last-write-wins."""

        assert ProtectedStateWrite.model_fields["expected_state_version"].is_required()

    def test_a_conditional_write_round_trips(self) -> None:
        write = ProtectedStateWrite(
            tenant_id="tenant-a",
            resource_type="claim",
            resource_id="claim-1",
            protected_state=ProtectedStateKind.CLAIM_SUBMITTED,
            expected_state_version=2,
            actor_id="user-1",
            correlation_id="corr-1",
        )
        assert write.idempotency_key is None

    def test_unknown_field_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ProtectedStateWrite(
                tenant_id="tenant-a",
                resource_type="claim",
                resource_id="claim-1",
                protected_state=ProtectedStateKind.CLAIM_SUBMITTED,
                expected_state_version=2,
                actor_id="user-1",
                correlation_id="corr-1",
                force=True,
            )


class TestStateConflictResponse:
    def test_a_real_conflict_round_trips(self) -> None:
        conflict = _conflict(conflicting_fields=["status"])
        assert conflict.current_state_version == 5
        assert conflict.message

    def test_equal_versions_may_not_be_reported_as_a_conflict(self) -> None:
        with pytest.raises(ValidationError, match="not a conflict"):
            _conflict(current_state_version=4)

    def test_server_state_defaults_to_empty(self) -> None:
        """This response crosses to the client and into logs."""

        assert _conflict().server_state == {}

    def test_unknown_field_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _conflict(full_record={"everything": "here"})


def test_protected_state_kinds_cover_the_platform_list() -> None:
    assert {member.value for member in ProtectedStateKind} == {
        "chart.locked",
        "claim.submitted",
        "payment.posted",
        "vial.destroyed",
        "signature.completed",
        "credential.revoked",
        "protocol.effective",
        "rule_pack.effective",
    }


def test_continuity_conflict_remains_a_separate_contract() -> None:
    """Workspace sync conflicts may merge; protected-record conflicts may not."""

    from adaptix_contracts.schemas.continuity_contracts import ConflictResponse

    assert "expected_sync_version" in ConflictResponse.model_fields
    assert "expected_state_version" in StateConflict.model_fields
    assert "expected_sync_version" not in StateConflict.model_fields


def test_surface_is_exported_from_the_package_root() -> None:
    for name in ("ProtectedStateKind", "ProtectedStateWrite", "StateConflict"):
        assert name in schemas.__all__
        assert hasattr(schemas, name)
