"""Calendar and scheduling contracts for Adaptix platform."""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel


class ShiftType(str, Enum):
    DAY = "day"
    NIGHT = "night"
    SWING = "swing"
    ON_CALL = "on_call"
    OVERTIME = "overtime"


class ScheduleStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class ShiftAssignment(BaseModel):
    """Shift assignment contract."""

    shift_id: str
    tenant_id: str
    staff_id: str
    unit_id: str | None = None
    shift_type: ShiftType
    start_datetime: datetime
    end_datetime: datetime
    status: ScheduleStatus = ScheduleStatus.DRAFT
    role: str | None = None
    notes: str | None = None
    created_by: str
    created_at: datetime
    audit_trail: list[dict] = []


class ScheduleEntry(BaseModel):
    """Schedule entry for calendar view."""

    entry_id: str
    tenant_id: str
    title: str
    start_datetime: datetime
    end_datetime: datetime
    entry_type: str  # shift, training, meeting, on_call
    staff_ids: list[str] = []
    unit_ids: list[str] = []
    status: ScheduleStatus = ScheduleStatus.DRAFT
    cad_linked: bool = False
    crewlink_linked: bool = False
    fatigue_risk_flag: bool = False
    fatigue_risk_reason: str | None = None


class StaffingCoverage(BaseModel):
    """Staffing coverage assessment."""

    tenant_id: str
    date: str
    shift_type: ShiftType
    required_staff: int
    assigned_staff: int
    coverage_percentage: float
    gaps: list[str] = []
    at_risk: bool = False
    ai_recommendation: str | None = None
    human_review_required: bool = True


class CalendarExportRequest(BaseModel):
    """Calendar export request (iCal/Google)."""

    tenant_id: str
    actor_id: str
    staff_id: str | None = None
    unit_id: str | None = None
    start_date: str
    end_date: str
    format: str = "ical"  # ical, google
    provider_status: str = "credential_gated"
