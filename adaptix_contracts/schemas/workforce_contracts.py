"""Workforce/scheduling contracts shared across Adaptix services.

DEPRECATED DOMAIN SURFACE
-------------------------
``adaptix_contracts.scheduling.models`` is the single source of truth for the
shift / assignment / availability / time-off domain per
SCHEDULING_ARCHITECTURE_LOCK.md section 3.3. The canonical models are re-exported
from this module so downstream code can migrate its *imports* to the canonical
names without changing its import path first.

The legacy ``Workforce*Contract`` models and the legacy ``ShiftStatus`` /
``AvailabilityType`` / ``TimeOffStatus`` / ``FatigueLevel`` enums below are
RETAINED, not deleted. Replacing them with the canonical models is a
major-version change under DEPRECATION_POLICY.md ("Major releases are required
for removing fields, renaming fields, changing field meaning, narrowing accepted
values, or deleting enum members"), because the shapes and enum value sets are
not interchangeable. See ``DEPRECATED_MODEL_REPLACEMENTS`` /
``DEPRECATED_ENUM_REPLACEMENTS`` below and the blocker recorded in CHANGELOG.md
for the exact incompatibilities.
"""

from __future__ import annotations

import enum
from datetime import datetime, date, time
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

# Canonical scheduling domain models — re-exported so callers can adopt the
# single-truth names from this legacy module path. Additive: nothing below is
# shadowed or replaced.
from adaptix_contracts.scheduling.models import (  # noqa: F401
    AssignmentStatus as CanonicalAssignmentStatus,
    AvailabilityWindow,
    RiskLevel,
    ShiftAssignment,
    ShiftInstance,
    ShiftStatus as CanonicalShiftStatus,
    TimeOffRequest,
    TimeOffStatus as CanonicalTimeOffStatus,
)

#: Legacy model -> canonical replacement in ``adaptix_contracts.scheduling.models``.
#: Machine-readable so drift tests can assert every deprecated name has a live target.
DEPRECATED_MODEL_REPLACEMENTS: dict[str, str] = {
    "WorkforceShiftContract": "adaptix_contracts.scheduling.models.ShiftInstance",
    "WorkforceShiftAssignmentContract": (
        "adaptix_contracts.scheduling.models.ShiftAssignment"
    ),
    "WorkforceAvailabilityContract": (
        "adaptix_contracts.scheduling.models.AvailabilityWindow"
    ),
    "WorkforceTimeOffContract": "adaptix_contracts.scheduling.models.TimeOffRequest",
    "WorkforceFatigueEventContract": "adaptix_contracts.scheduling.ai.FatigueRiskScore",
}

#: Legacy enum -> canonical replacement. NOTE: these replacements are NOT
#: value-compatible; see the per-entry deltas below.
DEPRECATED_ENUM_REPLACEMENTS: dict[str, str] = {
    "ShiftStatus": "adaptix_contracts.scheduling.models.ShiftStatus",
    "TimeOffStatus": "adaptix_contracts.scheduling.models.TimeOffStatus",
    "FatigueLevel": "adaptix_contracts.scheduling.models.RiskLevel",
}


class ShiftStatus(str, enum.Enum):
    """DEPRECATED — use ``adaptix_contracts.scheduling.models.ShiftStatus``.

    NOT value-compatible. This enum: draft/published/in_progress/completed/
    cancelled. Canonical: open/assigned/cancelled/completed. Swapping the two
    drops "draft", "published" and "in_progress" and adds "open"/"assigned",
    which is a major-version change under DEPRECATION_POLICY.md.
    """

    DRAFT = "draft"
    PUBLISHED = "published"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AvailabilityType(str, enum.Enum):
    """RETAINED — no canonical equivalent.

    ``adaptix_contracts.scheduling.models.AvailabilityWindow`` models availability
    as a boolean ``available`` flag over an absolute datetime window and has no
    preferred/on-call distinction, so this enum has nothing to collapse onto.
    """

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    PREFERRED = "preferred"
    ON_CALL = "on_call"


class TimeOffStatus(str, enum.Enum):
    """DEPRECATED — use ``adaptix_contracts.scheduling.models.TimeOffStatus``.

    Value-compatible: both are pending/approved/denied/cancelled. Retained only
    because deleting the name would break the import path in a minor release.
    """

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    CANCELLED = "cancelled"


class FatigueLevel(str, enum.Enum):
    """DEPRECATED — canonical target is
    ``adaptix_contracts.scheduling.models.RiskLevel``.

    NOT value-compatible. This enum: none/low/moderate/high/critical. RiskLevel:
    low/medium/high/critical. Collapsing them would delete the "none" and
    "moderate" members and would reject any persisted or in-flight payload
    carrying those values — a major-version change under DEPRECATION_POLICY.md.
    """

    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class WorkforceShiftContract(BaseModel):
    """DEPRECATED — use ``adaptix_contracts.scheduling.models.ShiftInstance``.

    NOT shape-compatible: ``ShiftInstance`` drops ``name`` and ``location`` and
    adds required ``schedule_id``, ``agency_type``, ``shift_date`` and
    ``created_by``.
    """

    id: UUID
    tenant_id: UUID
    name: str
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None
    minimum_staff: int = 1
    status: ShiftStatus = ShiftStatus.DRAFT
    created_at: datetime
    updated_at: Optional[datetime] = None


class WorkforceShiftAssignmentContract(BaseModel):
    """DEPRECATED — use ``adaptix_contracts.scheduling.models.ShiftAssignment``.

    NOT shape-compatible: canonical uses ``person_id`` (not ``user_id``), drops
    ``role``, types ``status`` as ``AssignmentStatus`` (not free ``str``), and
    adds required ``person_name``, ``assigned_by``, ``created_at``, ``updated_at``.
    """

    id: UUID
    tenant_id: UUID
    shift_id: UUID
    user_id: UUID
    role: Optional[str] = None
    status: str = "assigned"
    assigned_at: datetime


class WorkforceAvailabilityContract(BaseModel):
    """DEPRECATED — use ``adaptix_contracts.scheduling.models.AvailabilityWindow``.

    NOT shape-compatible: this contract models recurring availability
    (``day_of_week`` + ``time``-of-day) with an ``AvailabilityType``; the canonical
    model uses an absolute ``datetime`` window plus a boolean ``available`` flag.
    The recurring form cannot be expressed in the canonical model without loss.
    """

    id: UUID
    tenant_id: UUID
    user_id: UUID
    day_of_week: Optional[int] = None
    specific_date: Optional[date] = None
    start_time: time
    end_time: time
    availability_type: AvailabilityType
    created_at: datetime


class WorkforceTimeOffContract(BaseModel):
    """DEPRECATED — use ``adaptix_contracts.scheduling.models.TimeOffRequest``.

    NOT shape-compatible: canonical uses ``person_id`` (not ``user_id``) and
    ``datetime`` (not ``date``) bounds, and adds required ``created_by`` and
    ``updated_at``. The ``status`` enum values ARE compatible.
    """

    id: UUID
    tenant_id: UUID
    user_id: UUID
    start_date: date
    end_date: date
    reason: Optional[str] = None
    status: TimeOffStatus = TimeOffStatus.PENDING
    reviewed_by: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime


class WorkforceFatigueEventContract(BaseModel):
    """DEPRECATED — canonical target is
    ``adaptix_contracts.scheduling.ai.FatigueRiskScore``.

    Blocked on the ``FatigueLevel`` -> ``RiskLevel`` value-set incompatibility
    documented on ``FatigueLevel`` above.
    """

    id: UUID
    tenant_id: UUID
    user_id: UUID
    hours_worked_last_24: float
    hours_worked_last_48: float
    fatigue_level: FatigueLevel
    restriction_applied: bool = False
    restriction_reason: Optional[str] = None
    created_at: datetime


class WorkforceReadinessContract(BaseModel):
    tenant_id: UUID
    shift_id: Optional[UUID] = None
    total_required: int
    total_assigned: int
    total_available: int
    coverage_percentage: float
    fatigue_flagged_count: int = 0
    snapshot_at: datetime


class WorkforceShiftCreatedEvent(BaseModel):
    shift_id: UUID
    tenant_id: UUID
    start_time: datetime
    end_time: datetime
    status: ShiftStatus
    created_at: datetime


class WorkforceShiftAssignedEvent(BaseModel):
    shift_id: UUID
    user_id: UUID
    tenant_id: UUID
    assigned_at: datetime


class WorkforceFatigueAlertEvent(BaseModel):
    user_id: UUID
    tenant_id: UUID
    fatigue_level: FatigueLevel
    hours_worked_last_24: float
    created_at: datetime
