"""Adaptix Scheduling — Dispatch/911 Specific Models."""

from __future__ import annotations

from datetime import datetime

from uuid import UUID

from pydantic import BaseModel, Field


class DispatchConsoleAssignment(BaseModel):
    id: UUID
    tenant_id: UUID
    shift_id: UUID
    person_id: UUID
    console_id: UUID
    console_name: str
    role: str  # call_taker, dispatcher, supervisor
    radio_channels: list[str] = Field(default_factory=list)
    assigned_by: UUID
    assigned_at: datetime
    created_at: datetime
    updated_at: datetime
    audit_event_id: UUID | None = None


class CallTakerCoverageRule(BaseModel):
    id: UUID
    tenant_id: UUID
    minimum_call_takers: int
    time_window: str | None = None  # e.g. "peak", "overnight"
    active: bool = True
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class DispatcherCoverageRule(BaseModel):
    id: UUID
    tenant_id: UUID
    minimum_dispatchers: int
    agency_type: str | None = None  # law, fire, ems
    time_window: str | None = None
    active: bool = True
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class RadioChannelAssignment(BaseModel):
    id: UUID
    tenant_id: UUID
    shift_id: UUID
    person_id: UUID
    channel_id: str
    channel_name: str
    agency_type: str
    assigned_by: UUID
    assigned_at: datetime
    created_at: datetime
    updated_at: datetime
    audit_event_id: UUID | None = None


class DispatchSupervisorCoverage(BaseModel):
    id: UUID
    tenant_id: UUID
    shift_id: UUID
    supervisor_id: UUID
    minimum_supervisors: int = 1
    coverage_met: bool = False
    checked_at: datetime
    created_at: datetime
    updated_at: datetime


class MandatoryBreakCoverageRule(BaseModel):
    id: UUID
    tenant_id: UUID
    break_duration_minutes: int = 30
    minimum_coverage_during_break: int = 1
    active: bool = True
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class HighVolumeForecastWindow(BaseModel):
    id: UUID
    tenant_id: UUID
    forecast_date: datetime
    start_time: datetime
    end_time: datetime
    predicted_call_volume: int
    risk_level: str  # low, medium, high, critical
    recommended_staff: int
    source: str = "historical"  # historical, ai, manual
    created_at: datetime
    updated_at: datetime
