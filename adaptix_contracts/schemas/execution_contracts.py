"""Execution engine contracts for the Adaptix platform.

These schemas preserve the historical contract surface used by Core's
execution-engine integration tests and any older internal tooling that still
imports ``adaptix_contracts.schemas.execution_contracts``.

The canonical HTTP route layer in Core now uses inline request/response
schemas, but the domain model remains useful for compatibility, testability,
and future shared execution workflows.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ExecutionStatus(str, Enum):
    """Lifecycle states for an execution run."""

    PENDING = "pending"
    QUEUED = "queued"
    APPROVED = "approved"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class ApprovalStatus(str, Enum):
    """Approval-decision states recorded for a pending execution."""

    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class RiskLevel(str, Enum):
    """Execution risk classification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ExecutionTarget(BaseModel):
    """Concrete target for a DAG node."""

    domain: str = Field(min_length=1, max_length=100)
    repo_id: str = Field(min_length=1, max_length=255)
    service: str = Field(min_length=1, max_length=255)
    endpoint: str = Field(min_length=1, max_length=500)


class DAGNode(BaseModel):
    """Single executable node in an execution DAG."""

    node_id: str = Field(min_length=1, max_length=255)
    target: ExecutionTarget
    payload: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    timeout_ms: int = Field(default=5000, ge=1000)
    critical_path: bool = Field(default=False)


class ExecutionDAG(BaseModel):
    """Complete directed acyclic graph for an execution request."""

    dag_id: str = Field(min_length=1, max_length=255)
    nodes: list[DAGNode] = Field(default_factory=list)
    entry_nodes: list[str] = Field(default_factory=list)


class ExecutionCreateRequest(BaseModel):
    """Historical contract for creating an execution run."""

    dag: ExecutionDAG
    description: str = Field(min_length=1, max_length=1000)
    requires_approval: bool = Field(default=True)
    environment: str = Field(
        default="staging", pattern="^(staging|production|sandbox)$"
    )
    tags: list[str] = Field(default_factory=list)
    idempotency_key: str | None = Field(default=None, max_length=255)


class NodeExecutionResult(BaseModel):
    """Normalized per-node execution result payload."""

    node_id: str = Field(min_length=1, max_length=255)
    status: str = Field(min_length=1, max_length=50)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    output: dict[str, Any] | None = None
    error: str | None = None


class ApprovalRequest(BaseModel):
    """Approve/reject decision payload for a pending execution."""

    execution_id: UUID
    approved: bool
    comments: str | None = Field(default=None, max_length=2000)


class ExecutionAuditEntry(BaseModel):
    """Immutable execution-audit projection."""

    audit_id: UUID
    execution_id: UUID
    timestamp: datetime
    user_id: str
    action: str
    details: dict[str, Any] = Field(default_factory=dict)


class ExecutionRunResponse(BaseModel):
    """Compatibility response model for execution-run reads."""

    execution_id: UUID
    dag_id: str
    status: ExecutionStatus
    description: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_duration_ms: int | None = Field(default=None, ge=0)
    node_results: list[NodeExecutionResult] = Field(default_factory=list)
    approval_required: bool
    approval_status: ApprovalStatus | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    risk_level: RiskLevel | None = None
    environment: str
    tags: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Regulated action classes and the autonomy ladder (shared platform primitive M)
# ---------------------------------------------------------------------------
#
# Extends this module rather than creating a competing agent-execution universe:
# the DAG, approval and risk structures above already model "an execution ran and
# somebody approved it". What was missing is *how much authority an automated
# actor holds* and *how consequential the action is* — the two axes that decide
# whether an execution may proceed without a person.


class AutonomyLevel(str, Enum):
    """How much authority an automated actor holds for one execution.

    * ``L0`` — observe. Read and report; no output that anything acts on.
    * ``L1`` — draft. Produce content a person will edit and own.
    * ``L2`` — propose. Produce a concrete action a person must approve.
    * ``L3`` — execute reversible actions without prior approval.
    * ``L4`` — execute protected actions, and only where explicit tenant policy
      plus a recorded approval allow it.

    The ladder is per execution, not per agent: the same agent may hold ``L3``
    for scheduling and ``L0`` for controlled substances.
    """

    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"


class RegulatedActionClass(str, Enum):
    """How consequential an action is, and therefore what it takes to run it.

    * ``NONE`` — no domain effect at all (a read, a health check).
    * ``ADVISORY`` — produces a recommendation; a person still acts.
    * ``REVERSIBLE`` — changes state that can be cleanly undone.
    * ``PROTECTED`` — changes a protected record (a locked chart, a submitted
      claim, a custody event). Requires an ``expected_state_version`` so it
      cannot silently overwrite a concurrent change.
    * ``IRREVERSIBLE`` — cannot be undone once done: money moves, a controlled
      substance is destroyed, a message leaves the platform, a record is
      permanently filed. Never autonomous by default at any autonomy level.
    """

    NONE = "none"
    ADVISORY = "advisory"
    REVERSIBLE = "reversible"
    PROTECTED = "protected"
    IRREVERSIBLE = "irreversible"


#: Minimum autonomy level at which an action class may execute without a person
#: approving that specific execution. ``IRREVERSIBLE`` is deliberately absent:
#: no autonomy level clears it, so it always falls through to "approval
#: required".
_MINIMUM_AUTONOMY_FOR_AUTONOMOUS_EXECUTION: dict[
    RegulatedActionClass, AutonomyLevel
] = {
    RegulatedActionClass.NONE: AutonomyLevel.L0,
    RegulatedActionClass.ADVISORY: AutonomyLevel.L2,
    RegulatedActionClass.REVERSIBLE: AutonomyLevel.L3,
    RegulatedActionClass.PROTECTED: AutonomyLevel.L4,
}

#: Action classes that write to a protected record and therefore must carry the
#: optimistic-concurrency version they expect to be changing.
_ACTION_CLASSES_REQUIRING_STATE_VERSION: frozenset[RegulatedActionClass] = frozenset(
    {
        RegulatedActionClass.PROTECTED,
        RegulatedActionClass.IRREVERSIBLE,
    }
)

_AUTONOMY_ORDER: tuple[AutonomyLevel, ...] = (
    AutonomyLevel.L0,
    AutonomyLevel.L1,
    AutonomyLevel.L2,
    AutonomyLevel.L3,
    AutonomyLevel.L4,
)


def autonomy_at_least(
    granted: AutonomyLevel | str, required: AutonomyLevel | str
) -> bool:
    """Return ``True`` when ``granted`` is at or above ``required``.

    Fails closed: an unrecognised level on either side returns ``False``.
    """

    try:
        granted_level = AutonomyLevel(granted)
        required_level = AutonomyLevel(required)
    except ValueError:
        return False
    return _AUTONOMY_ORDER.index(granted_level) >= _AUTONOMY_ORDER.index(required_level)


def requires_human_approval(
    autonomy_level: AutonomyLevel | str,
    regulated_action_class: RegulatedActionClass | str,
) -> bool:
    """Return ``True`` when this execution needs a person to approve it.

    ``IRREVERSIBLE`` always returns ``True``, at every autonomy level including
    ``L4``. Money leaving, a vial being destroyed, and a message reaching a
    member of the public are not recoverable by rollback, so no ladder position
    clears them.

    Fails closed on anything unrecognised: an action class or level this
    contract does not know requires approval.
    """

    try:
        action_class = RegulatedActionClass(regulated_action_class)
    except ValueError:
        return True
    if action_class is RegulatedActionClass.IRREVERSIBLE:
        return True
    minimum = _MINIMUM_AUTONOMY_FOR_AUTONOMOUS_EXECUTION[action_class]
    return not autonomy_at_least(autonomy_level, minimum)


def requires_expected_state_version(
    regulated_action_class: RegulatedActionClass | str,
) -> bool:
    """Return ``True`` when the execution must carry an expected state version.

    Fails closed: an unrecognised class requires one.
    """

    try:
        action_class = RegulatedActionClass(regulated_action_class)
    except ValueError:
        return True
    return action_class in _ACTION_CLASSES_REQUIRING_STATE_VERSION


class RegulatedExecutionContext(BaseModel):
    """The authority under which one execution is allowed to run.

    Attached to an execution request by the policy layer, never by the actor
    requesting the work. ``approval_receipt_id`` points at a
    ``HumanConfirmationReceipt``
    (``adaptix_contracts.schemas.human_confirmation_contracts``).

    The model enforces the three rules that make the ladder mean something:

    * an execution that needs approval must carry ``human_approval_required``;
    * if it needs approval, either an approval receipt is present or the
      execution is not cleared to run (:meth:`is_cleared_to_execute`);
    * a protected or irreversible action must carry ``expected_state_version``.
    """

    autonomy_level: AutonomyLevel
    regulated_action_class: RegulatedActionClass
    human_approval_required: bool
    approval_receipt_id: str | None = None
    expected_state_version: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _authority_is_internally_consistent(self) -> RegulatedExecutionContext:
        needs_approval = requires_human_approval(
            self.autonomy_level, self.regulated_action_class
        )
        if needs_approval and not self.human_approval_required:
            raise ValueError(
                f"{self.regulated_action_class.value} at autonomy "
                f"{self.autonomy_level.value} requires human approval; "
                "human_approval_required must be True"
            )
        if (
            requires_expected_state_version(self.regulated_action_class)
            and self.expected_state_version is None
        ):
            raise ValueError(
                f"{self.regulated_action_class.value} writes a protected record and "
                "requires expected_state_version"
            )
        if self.approval_receipt_id is not None and not self.human_approval_required:
            raise ValueError(
                "approval_receipt_id is set but human_approval_required is False"
            )
        return self

    def is_cleared_to_execute(self) -> bool:
        """Return ``True`` only when this execution may actually proceed.

        An execution that requires approval and has no recorded approval receipt
        is not cleared, however the request was constructed.
        """

        if self.human_approval_required:
            return bool(self.approval_receipt_id)
        return not requires_human_approval(
            self.autonomy_level, self.regulated_action_class
        )


__all__ = [
    "ApprovalRequest",
    "ApprovalStatus",
    "AutonomyLevel",
    "DAGNode",
    "ExecutionAuditEntry",
    "ExecutionCreateRequest",
    "ExecutionDAG",
    "ExecutionRunResponse",
    "ExecutionStatus",
    "ExecutionTarget",
    "NodeExecutionResult",
    "RegulatedActionClass",
    "RegulatedExecutionContext",
    "RiskLevel",
    "autonomy_at_least",
    "requires_expected_state_version",
    "requires_human_approval",
]
