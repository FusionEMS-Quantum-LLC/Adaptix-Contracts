"""Adaptix Scheduling — Fire Specific Models."""

from __future__ import annotations

from datetime import datetime

from uuid import UUID

from pydantic import BaseModel, Field


class FireStationAssignment(BaseModel):
    id: UUID
    tenant_id: UUID
    shift_id: UUID
    person_id: UUID
    station_id: UUID
    station_name: str
    role: str  # officer, driver, firefighter, emt, paramedic
    assigned_by: UUID
    assigned_at: datetime
    created_at: datetime
    updated_at: datetime
    audit_event_id: UUID | None = None


class ApparatusAssignment(BaseModel):
    id: UUID
    tenant_id: UUID
    shift_id: UUID
    apparatus_id: UUID
    apparatus_unit: str
    apparatus_type: str  # engine, ladder, medic, rescue, tanker
    station_id: UUID
    crew: list[UUID] = Field(default_factory=list)
    driver_id: UUID | None = None
    officer_id: UUID | None = None
    minimum_crew: int = 3
    assigned_by: UUID
    assigned_at: datetime
    created_at: datetime
    updated_at: datetime
    audit_event_id: UUID | None = None


class FireMinimumStaffingRule(BaseModel):
    id: UUID
    tenant_id: UUID
    station_id: UUID
    apparatus_id: UUID | None = None
    apparatus_type: str | None = None
    minimum_crew: int
    required_officer: bool = True
    required_driver: bool = True
    required_firefighters: int = 1
    active: bool = True
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class FireRoleCoverageRule(BaseModel):
    id: UUID
    tenant_id: UUID
    station_id: UUID
    role: str  # officer, driver, firefighter
    minimum_per_shift: int
    active: bool = True
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class FireSpecialtyCoverage(BaseModel):
    id: UUID
    tenant_id: UUID
    station_id: UUID
    specialty: str  # hazmat, technical_rescue, swift_water, etc.
    minimum_per_shift: int
    active: bool = True
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class VolunteerAvailability(BaseModel):
    id: UUID
    tenant_id: UUID
    person_id: UUID
    station_id: UUID | None = None
    available_from: datetime
    available_to: datetime
    available: bool = True
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class CallbackRoster(BaseModel):
    id: UUID
    tenant_id: UUID
    station_id: UUID
    shift_id: UUID
    shortage_reason: str
    callback_candidates: list[UUID] = Field(default_factory=list)
    notified_at: datetime | None = None
    filled: bool = False
    filled_by: UUID | None = None
    filled_at: datetime | None = None
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    audit_event_id: UUID | None = None


class MutualAidStaffingRequest(BaseModel):
    id: UUID
    tenant_id: UUID
    requesting_agency_id: UUID
    providing_agency_id: UUID | None = None
    event_id: UUID | None = None
    shift_id: UUID | None = None
    requested_roles: list[str] = Field(default_factory=list)
    requested_count: int
    status: str = "pending"  # pending, accepted, declined, fulfilled
    requested_at: datetime
    responded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    audit_event_id: UUID | None = None
