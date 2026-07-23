"""Labor domain contracts for cross-domain communication.

Defines contracts for the Adaptix Labor Service: workforce lifecycle,
shift scheduling, assignment decisions, open-shift marketplace,
leave/trade requests, fatigue scoring, compliance enforcement,
compensation resolution, and payroll export events.

SCOPE CORRECTION (SCHEDULING_ARCHITECTURE_LOCK.md section 3.3)
-------------------------------------------------------------
This module is NO LONGER the authoritative source for the shift / assignment /
trade / leave domain. ``adaptix_contracts.scheduling.models`` is the single
source of truth. The canonical models are re-exported below so downstream code
can adopt the canonical names from this module path.

The genuinely payroll-only surface — ``PayrollExportStatus``,
``LaborPayrollExportSubmittedEvent`` and ``LaborExternalSyncCompletedEvent`` —
is KEPT here and is not part of the scheduling consolidation.

The legacy ``Labor*Contract`` models and the ``ShiftStatus`` / ``AssignmentStatus``
/ ``TradeStatus`` / ``LeaveStatus`` enums below are RETAINED, not deleted:
replacing them is a major-version change under DEPRECATION_POLICY.md because the
shapes and enum value sets are not interchangeable. See
``DEPRECATED_MODEL_REPLACEMENTS`` / ``DEPRECATED_ENUM_REPLACEMENTS`` and the
per-class notes for the exact incompatibilities.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel

# Canonical scheduling domain models — re-exported so callers can adopt the
# single-truth names from this legacy module path. Additive: nothing below is
# shadowed or replaced.
from adaptix_contracts.scheduling.models import (  # noqa: F401
    AssignmentStatus as CanonicalAssignmentStatus,
    RiskLevel,
    ShiftAssignment,
    ShiftInstance,
    ShiftStatus as CanonicalShiftStatus,
    ShiftSwapRequest,
    SwapStatus as CanonicalSwapStatus,
    TimeOffRequest,
    TimeOffStatus as CanonicalTimeOffStatus,
)

#: Legacy model -> canonical replacement in ``adaptix_contracts.scheduling.models``.
DEPRECATED_MODEL_REPLACEMENTS: dict[str, str] = {
    "LaborShiftContract": "adaptix_contracts.scheduling.models.ShiftInstance",
    "LaborAssignmentContract": "adaptix_contracts.scheduling.models.ShiftAssignment",
}

#: Legacy enum -> canonical replacement. NOT value-compatible; see per-enum notes.
DEPRECATED_ENUM_REPLACEMENTS: dict[str, str] = {
    "ShiftStatus": "adaptix_contracts.scheduling.models.ShiftStatus",
    "AssignmentStatus": "adaptix_contracts.scheduling.models.AssignmentStatus",
    "TradeStatus": "adaptix_contracts.scheduling.models.SwapStatus",
    "LeaveStatus": "adaptix_contracts.scheduling.models.TimeOffStatus",
}

#: Payroll-only surface that deliberately STAYS in the labor domain.
PAYROLL_ONLY_SURFACE: tuple[str, ...] = (
    "PayrollExportStatus",
    "LaborPayrollExportSubmittedEvent",
    "LaborExternalSyncCompletedEvent",
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EmploymentStatus(str, Enum):
    """Lifecycle status of a labor employee."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ON_LEAVE = "on_leave"
    TERMINATED = "terminated"
    REHIRED = "rehired"


class LaborDomain(str, Enum):
    """Operational domain for a labor entity."""

    EMS = "ems"
    FIRE = "fire"
    LAW = "law"
    HEMS = "hems"
    MULTI = "multi"


class ShiftStatus(str, Enum):
    """DEPRECATED — use ``adaptix_contracts.scheduling.models.ShiftStatus``.

    NOT value-compatible. This enum: draft/published/locked/open/in_progress/
    completed/cancelled. Canonical: open/assigned/cancelled/completed. Collapsing
    would delete "draft", "published", "locked" and "in_progress".
    """

    DRAFT = "draft"
    PUBLISHED = "published"
    LOCKED = "locked"
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AssignmentStatus(str, Enum):
    """DEPRECATED — use ``adaptix_contracts.scheduling.models.AssignmentStatus``.

    NOT value-compatible. This enum adds "overridden", which the canonical enum
    (pending/confirmed/cancelled) does not define. Collapsing would reject every
    persisted or in-flight assignment carrying status="overridden".
    """

    PENDING = "pending"
    CONFIRMED = "confirmed"
    OVERRIDDEN = "overridden"
    CANCELLED = "cancelled"


class TradeStatus(str, Enum):
    """DEPRECATED — canonical target is
    ``adaptix_contracts.scheduling.models.SwapStatus``.

    NOT value-compatible. This enum: proposed/accepted/denied/cancelled/completed.
    SwapStatus: requested/approved/denied/cancelled. Only "denied" and "cancelled"
    overlap; "proposed", "accepted" and "completed" have no canonical equivalent.
    """

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    DENIED = "denied"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class LeaveStatus(str, Enum):
    """DEPRECATED — use ``adaptix_contracts.scheduling.models.TimeOffStatus``.

    Value-compatible: both are pending/approved/denied/cancelled. Retained only
    because deleting the name would break the import path in a minor release.
    """

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    CANCELLED = "cancelled"


class ClaimStatus(str, Enum):
    """Status of an open-shift claim."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class CommandPosture(str, Enum):
    """Operational posture governing scheduling decisions."""

    NORMAL = "normal"
    SURGE = "surge"
    DISASTER = "disaster"
    COST_CONTROL = "cost_control"
    MUTUAL_AID = "mutual_aid"
    COMPLIANCE_FIRST = "compliance_first"


class PayrollExportStatus(str, Enum):
    """Status of a payroll export run.

    KEPT — genuinely payroll-only. Not part of the scheduling consolidation.
    """

    DRAFT = "draft"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    LOCKED = "locked"


class PolicyStatus(str, Enum):
    """Lifecycle status of a labor policy version."""

    DRAFT = "draft"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"


# ---------------------------------------------------------------------------
# Read contracts
# ---------------------------------------------------------------------------


class LaborShiftContract(BaseModel):
    """DEPRECATED — use ``adaptix_contracts.scheduling.models.ShiftInstance``.

    NOT shape-compatible: identifiers are ``str`` here and ``UUID`` in the
    canonical model; ``start_time``/``end_time`` are "HH:MM" strings here and
    ``datetime`` there; ``shift_date`` is ``date`` here and ``datetime`` there;
    ``domain``/``minimum_staffing``/``is_locked`` have no canonical counterpart.
    """

    shift_id: str
    tenant_id: str
    domain: LaborDomain
    status: ShiftStatus
    shift_date: date
    start_time: str
    end_time: str
    station_id: Optional[str] = None
    unit_id: Optional[str] = None
    minimum_staffing: int
    is_locked: bool
    created_at: datetime


class LaborAssignmentContract(BaseModel):
    """DEPRECATED — use ``adaptix_contracts.scheduling.models.ShiftAssignment``.

    NOT shape-compatible: identifiers are ``str`` here and ``UUID`` in the
    canonical model; ``employee_id`` maps to ``person_id``; ``slot_id`` and
    ``override_reason`` have no canonical counterpart; the canonical model
    requires ``person_name``, ``created_at`` and ``updated_at``.
    """

    assignment_id: str
    tenant_id: str
    shift_id: str
    slot_id: str
    employee_id: str
    status: AssignmentStatus
    override_reason: Optional[str] = None
    assigned_by: str
    assigned_at: datetime


class LaborEmployeeReadinessContract(BaseModel):
    """RETAINED — no canonical equivalent exists.

    ``adaptix_contracts.scheduling.models`` defines no employee-readiness model,
    so there is nothing to re-point this contract at. Left in place pending the
    Readiness Twin work (SCHEDULING_ARCHITECTURE_LOCK.md phase 3).
    """

    employee_id: str
    tenant_id: str
    unit_id: Optional[str] = None
    readiness_score: float
    cert_valid: bool
    rest_valid: bool
    pairing_valid: bool
    coverage_valid: bool
    no_ot_risk: bool
    evaluated_at: datetime


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


class LaborShiftPublishedEvent(BaseModel):
    """Published when a shift transitions from draft to published."""

    event_type: str = "labor.shift.published"

    shift_id: str
    tenant_id: str
    domain: LaborDomain
    shift_date: date
    start_time: str
    end_time: str
    station_id: Optional[str] = None
    unit_id: Optional[str] = None
    published_by: str
    occurred_at: datetime


class LaborShiftLockedEvent(BaseModel):
    """Published when a shift is locked and no longer editable."""

    event_type: str = "labor.shift.locked"

    shift_id: str
    tenant_id: str
    locked_by: str
    occurred_at: datetime


class LaborAssignmentCommittedEvent(BaseModel):
    """Published when an employee is assigned to a shift slot."""

    event_type: str = "labor.assignment.committed"

    assignment_id: str
    shift_id: str
    slot_id: str
    tenant_id: str
    employee_id: str
    command_posture: CommandPosture
    override_occurred: bool
    override_reason: Optional[str] = None
    assigned_by: str
    total_distortion_score: Optional[float] = None
    occurred_at: datetime


class LaborOpenShiftClaimSubmittedEvent(BaseModel):
    """Published when an employee submits a claim on an open shift."""

    event_type: str = "labor.open_shift.claim_submitted"

    claim_id: str
    open_shift_id: str
    tenant_id: str
    employee_id: str
    fatigue_score_at_claim: Optional[float] = None
    ot_impact_hours: Optional[float] = None
    occurred_at: datetime


class LaborShiftTradeProposedEvent(BaseModel):
    """Published when a shift trade is proposed between two employees."""

    event_type: str = "labor.shift_trade.proposed"

    trade_id: str
    tenant_id: str
    requesting_employee_id: str
    receiving_employee_id: str
    shift_id_offered: str
    shift_id_requested: str
    supervisor_approval_required: bool
    occurred_at: datetime


class LaborLeaveRequestSubmittedEvent(BaseModel):
    """Published when a leave request is submitted."""

    event_type: str = "labor.leave_request.submitted"

    leave_request_id: str
    tenant_id: str
    employee_id: str
    leave_type: str
    start_date: date
    end_date: date
    occurred_at: datetime


class LaborComplianceViolationCreatedEvent(BaseModel):
    """Published when a policy compliance violation is detected."""

    event_type: str = "labor.compliance.violation_created"

    violation_id: str
    tenant_id: str
    employee_id: str
    shift_id: Optional[str] = None
    rule_code: str
    severity: str
    detected_at: datetime
    occurred_at: datetime


class LaborFatigueRestrictionAppliedEvent(BaseModel):
    """Published when a fatigue block threshold is exceeded for an employee."""

    event_type: str = "labor.fatigue.restriction_applied"

    tenant_id: str
    employee_id: str
    fatigue_score: float
    consecutive_hours: float
    rolling_hours: float
    is_blocked: bool
    evaluated_at: datetime
    occurred_at: datetime


class LaborPayrollExportSubmittedEvent(BaseModel):
    """Published when a payroll export run is submitted to an external system.

    KEPT — genuinely payroll-only. Not part of the scheduling consolidation.
    """

    event_type: str = "labor.payroll_export.submitted"

    export_run_id: str
    tenant_id: str
    external_system: str
    pay_period_start: date
    pay_period_end: date
    item_count: int
    submitted_at: datetime
    occurred_at: datetime


class LaborExternalSyncCompletedEvent(BaseModel):
    """Published when an external system integration sync job completes.

    KEPT — genuinely payroll/integration-only. Not part of the scheduling
    consolidation.
    """

    event_type: str = "labor.external_sync.completed"

    sync_job_id: str
    tenant_id: str
    external_system: str
    sync_direction: str
    records_imported: int
    records_errored: int
    completed_at: datetime
    occurred_at: datetime
