"""Adaptix Scheduling — Event Definitions."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SchedulingEvent(BaseModel):
    """Base scheduling event envelope."""

    event_type: str
    tenant_id: UUID
    actor_id: UUID
    record_id: UUID
    record_type: str
    schedule_id: UUID | None = None
    shift_id: UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None
    audit_event_id: UUID | None = None
    occurred_at: datetime


# ---------------------------------------------------------------------------
# Shift Events
# ---------------------------------------------------------------------------

SCHEDULE_SHIFT_CREATED = "schedule.shift.created"
SCHEDULE_SHIFT_UPDATED = "schedule.shift.updated"
SCHEDULE_SHIFT_CANCELLED = "schedule.shift.cancelled"
SCHEDULE_SHIFT_ASSIGNED = "schedule.shift.assigned"
SCHEDULE_SHIFT_UNASSIGNED = "schedule.shift.unassigned"

# Swap Events
SCHEDULE_SHIFT_SWAP_REQUESTED = "schedule.shift.swap.requested"
SCHEDULE_SHIFT_SWAP_APPROVED = "schedule.shift.swap.approved"
SCHEDULE_SHIFT_SWAP_DENIED = "schedule.shift.swap.denied"

# Time-Off Events
SCHEDULE_TIMEOFF_REQUESTED = "schedule.timeoff.requested"
SCHEDULE_TIMEOFF_APPROVED = "schedule.timeoff.approved"
SCHEDULE_TIMEOFF_DENIED = "schedule.timeoff.denied"

# Overtime Events
SCHEDULE_OVERTIME_OFFERED = "schedule.overtime.offered"
SCHEDULE_OVERTIME_ACCEPTED = "schedule.overtime.accepted"
SCHEDULE_OVERTIME_DECLINED = "schedule.overtime.declined"

# Holdover Events
SCHEDULE_HOLDOVER_CREATED = "schedule.holdover.created"
SCHEDULE_HOLDOVER_APPROVED = "schedule.holdover.approved"

# Staffing / Coverage Events
SCHEDULE_STAFFING_SHORTAGE_DETECTED = "schedule.staffing.shortage.detected"
SCHEDULE_COVERAGE_VIOLATION_DETECTED = "schedule.coverage.violation.detected"
SCHEDULE_RANK_COVERAGE_VIOLATION_DETECTED = "schedule.rank.coverage.violation.detected"
SCHEDULE_BEAT_COVERAGE_VIOLATION_DETECTED = "schedule.beat.coverage.violation.detected"
SCHEDULE_ZONE_COVERAGE_VIOLATION_DETECTED = "schedule.zone.coverage.violation.detected"

# Conflict Events
SCHEDULE_COURT_CONFLICT_DETECTED = "schedule.court.conflict.detected"
SCHEDULE_TRAINING_CONFLICT_DETECTED = "schedule.training.conflict.detected"

# AI Events
SCHEDULE_AI_ASSESSMENT_CREATED = "schedule.ai.assessment.created"

# CAD / MDT Sync Events
SCHEDULE_CAD_AVAILABILITY_UPDATED = "schedule.cad.availability.updated"
SCHEDULE_MDT_AVAILABILITY_UPDATED = "schedule.mdt.availability.updated"

# Audit
SCHEDULE_AUDIT_EVENT_CREATED = "schedule.audit.event.created"

ALL_SCHEDULING_EVENTS = [
    SCHEDULE_SHIFT_CREATED,
    SCHEDULE_SHIFT_UPDATED,
    SCHEDULE_SHIFT_CANCELLED,
    SCHEDULE_SHIFT_ASSIGNED,
    SCHEDULE_SHIFT_UNASSIGNED,
    SCHEDULE_SHIFT_SWAP_REQUESTED,
    SCHEDULE_SHIFT_SWAP_APPROVED,
    SCHEDULE_SHIFT_SWAP_DENIED,
    SCHEDULE_TIMEOFF_REQUESTED,
    SCHEDULE_TIMEOFF_APPROVED,
    SCHEDULE_TIMEOFF_DENIED,
    SCHEDULE_OVERTIME_OFFERED,
    SCHEDULE_OVERTIME_ACCEPTED,
    SCHEDULE_OVERTIME_DECLINED,
    SCHEDULE_HOLDOVER_CREATED,
    SCHEDULE_HOLDOVER_APPROVED,
    SCHEDULE_STAFFING_SHORTAGE_DETECTED,
    SCHEDULE_COVERAGE_VIOLATION_DETECTED,
    SCHEDULE_RANK_COVERAGE_VIOLATION_DETECTED,
    SCHEDULE_BEAT_COVERAGE_VIOLATION_DETECTED,
    SCHEDULE_ZONE_COVERAGE_VIOLATION_DETECTED,
    SCHEDULE_COURT_CONFLICT_DETECTED,
    SCHEDULE_TRAINING_CONFLICT_DETECTED,
    SCHEDULE_AI_ASSESSMENT_CREATED,
    SCHEDULE_CAD_AVAILABILITY_UPDATED,
    SCHEDULE_MDT_AVAILABILITY_UPDATED,
    SCHEDULE_AUDIT_EVENT_CREATED,
]
