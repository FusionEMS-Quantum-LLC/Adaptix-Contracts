"""Contract tests for the regulated autonomy ladder (shared platform primitive M)."""

from __future__ import annotations

from adaptix_contracts.schemas.execution_contracts import (
    AutonomyLevel,
    RegulatedActionClass,
    RegulatedExecutionContext,
    autonomy_at_least,
    requires_expected_state_version,
    requires_human_approval,
)
import pytest
from pydantic import ValidationError


class TestAutonomyOrdering:
    def test_a_level_meets_itself(self) -> None:
        assert autonomy_at_least(AutonomyLevel.L3, AutonomyLevel.L3)

    def test_a_higher_level_meets_a_lower_requirement(self) -> None:
        assert autonomy_at_least(AutonomyLevel.L4, AutonomyLevel.L1)

    def test_a_lower_level_does_not_meet_a_higher_requirement(self) -> None:
        assert not autonomy_at_least(AutonomyLevel.L2, AutonomyLevel.L3)

    def test_unknown_level_fails_closed(self) -> None:
        assert not autonomy_at_least("L9", AutonomyLevel.L0)
        assert not autonomy_at_least(AutonomyLevel.L4, "L9")


class TestApprovalRules:
    def test_irreversible_always_needs_a_person(self) -> None:
        """Money leaving and a vial destroyed are not undone by a rollback."""

        for level in AutonomyLevel:
            assert requires_human_approval(level, RegulatedActionClass.IRREVERSIBLE)

    def test_protected_needs_l4(self) -> None:
        assert requires_human_approval(AutonomyLevel.L3, RegulatedActionClass.PROTECTED)
        assert not requires_human_approval(
            AutonomyLevel.L4, RegulatedActionClass.PROTECTED
        )

    def test_reversible_needs_l3(self) -> None:
        assert requires_human_approval(
            AutonomyLevel.L2, RegulatedActionClass.REVERSIBLE
        )
        assert not requires_human_approval(
            AutonomyLevel.L3, RegulatedActionClass.REVERSIBLE
        )

    def test_advisory_needs_l2(self) -> None:
        assert requires_human_approval(AutonomyLevel.L1, RegulatedActionClass.ADVISORY)
        assert not requires_human_approval(
            AutonomyLevel.L2, RegulatedActionClass.ADVISORY
        )

    def test_a_read_needs_nothing(self) -> None:
        assert not requires_human_approval(AutonomyLevel.L0, RegulatedActionClass.NONE)

    def test_l0_may_not_execute_anything_consequential(self) -> None:
        for action_class in (
            RegulatedActionClass.ADVISORY,
            RegulatedActionClass.REVERSIBLE,
            RegulatedActionClass.PROTECTED,
            RegulatedActionClass.IRREVERSIBLE,
        ):
            assert requires_human_approval(AutonomyLevel.L0, action_class)

    def test_unknown_action_class_fails_closed(self) -> None:
        assert requires_human_approval(AutonomyLevel.L4, "delete_everything")

    def test_unknown_autonomy_level_fails_closed(self) -> None:
        assert requires_human_approval("L99", RegulatedActionClass.REVERSIBLE)

    def test_every_action_class_is_classified(self) -> None:
        for action_class in RegulatedActionClass:
            assert isinstance(
                requires_human_approval(AutonomyLevel.L4, action_class), bool
            )


class TestStateVersionRequirement:
    @pytest.mark.parametrize(
        "action_class",
        [RegulatedActionClass.PROTECTED, RegulatedActionClass.IRREVERSIBLE],
    )
    def test_protected_writes_require_a_version(
        self, action_class: RegulatedActionClass
    ) -> None:
        assert requires_expected_state_version(action_class)

    @pytest.mark.parametrize(
        "action_class",
        [
            RegulatedActionClass.NONE,
            RegulatedActionClass.ADVISORY,
            RegulatedActionClass.REVERSIBLE,
        ],
    )
    def test_other_classes_do_not(self, action_class: RegulatedActionClass) -> None:
        assert not requires_expected_state_version(action_class)

    def test_unknown_class_fails_closed(self) -> None:
        assert requires_expected_state_version("mystery_action")


class TestRegulatedExecutionContext:
    def test_a_read_at_l0_is_cleared(self) -> None:
        context = RegulatedExecutionContext(
            autonomy_level=AutonomyLevel.L0,
            regulated_action_class=RegulatedActionClass.NONE,
            human_approval_required=False,
        )
        assert context.is_cleared_to_execute()

    def test_a_reversible_action_at_l3_is_cleared(self) -> None:
        context = RegulatedExecutionContext(
            autonomy_level=AutonomyLevel.L3,
            regulated_action_class=RegulatedActionClass.REVERSIBLE,
            human_approval_required=False,
        )
        assert context.is_cleared_to_execute()

    def test_understating_the_approval_requirement_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="requires human approval"):
            RegulatedExecutionContext(
                autonomy_level=AutonomyLevel.L2,
                regulated_action_class=RegulatedActionClass.REVERSIBLE,
                human_approval_required=False,
            )

    def test_protected_action_without_a_version_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="requires expected_state_version"):
            RegulatedExecutionContext(
                autonomy_level=AutonomyLevel.L4,
                regulated_action_class=RegulatedActionClass.PROTECTED,
                human_approval_required=False,
            )

    def test_protected_action_at_l4_with_a_version_is_cleared(self) -> None:
        context = RegulatedExecutionContext(
            autonomy_level=AutonomyLevel.L4,
            regulated_action_class=RegulatedActionClass.PROTECTED,
            human_approval_required=False,
            expected_state_version=7,
        )
        assert context.is_cleared_to_execute()

    def test_irreversible_action_is_not_cleared_without_a_receipt(self) -> None:
        """An approval requirement with nobody's approval attached blocks."""

        context = RegulatedExecutionContext(
            autonomy_level=AutonomyLevel.L4,
            regulated_action_class=RegulatedActionClass.IRREVERSIBLE,
            human_approval_required=True,
            expected_state_version=3,
        )
        assert not context.is_cleared_to_execute()

    def test_irreversible_action_with_a_receipt_is_cleared(self) -> None:
        context = RegulatedExecutionContext(
            autonomy_level=AutonomyLevel.L4,
            regulated_action_class=RegulatedActionClass.IRREVERSIBLE,
            human_approval_required=True,
            approval_receipt_id="rcpt-1",
            expected_state_version=3,
        )
        assert context.is_cleared_to_execute()

    def test_a_receipt_without_an_approval_requirement_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="human_approval_required is False"):
            RegulatedExecutionContext(
                autonomy_level=AutonomyLevel.L3,
                regulated_action_class=RegulatedActionClass.REVERSIBLE,
                human_approval_required=False,
                approval_receipt_id="rcpt-1",
            )

    def test_negative_state_version_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            RegulatedExecutionContext(
                autonomy_level=AutonomyLevel.L4,
                regulated_action_class=RegulatedActionClass.PROTECTED,
                human_approval_required=False,
                expected_state_version=-1,
            )


def test_historical_execution_surface_is_preserved() -> None:
    """The autonomy ladder extends this module; it must not displace it."""

    from adaptix_contracts.schemas import execution_contracts

    for name in (
        "ExecutionStatus",
        "ApprovalStatus",
        "RiskLevel",
        "ExecutionTarget",
        "DAGNode",
        "ExecutionDAG",
        "ExecutionCreateRequest",
        "NodeExecutionResult",
        "ApprovalRequest",
        "ExecutionAuditEntry",
        "ExecutionRunResponse",
    ):
        assert hasattr(execution_contracts, name)
        assert name in execution_contracts.__all__
