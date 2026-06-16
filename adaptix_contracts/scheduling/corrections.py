"""Adaptix Scheduling — Corrections/Jail Specific Models."""

from __future__ import annotations

from datetime import datetime

from uuid import UUID

from pydantic import BaseModel, Field


class CorrectionsPost(BaseModel):
    id: UUID
    tenant_id: UUID
    facility_id: UUID
    post_name: str
    post_code: str
    post_type: str  # housing, control, transport, perimeter, booking, medical
    mandatory: bool = True
    minimum_staff: int = 1
    active: bool = True
    created_at: datetime
    updated_at: datetime


class CorrectionsShiftAssignment(BaseModel):
    id: UUID
    tenant_id: UUID
    shift_id: UUID
    person_id: UUID
    post_id: UUID
    post_name: str
    facility_id: UUID
    role: str  # officer, supervisor, transport
    assigned_by: UUID
    assigned_at: datetime
    created_at: datetime
    updated_at: datetime
    audit_event_id: UUID | None = None


class CorrectionsReliefCoverage(BaseModel):
    id: UUID
    tenant_id: UUID
    shift_id: UUID
    post_id: UUID
    relief_person_id: UUID
    primary_person_id: UUID
    relief_start: datetime
    relief_end: datetime
    reason: str
    assigned_by: UUID
    created_at: datetime
    updated_at: datetime
    audit_event_id: UUID | None = None


class CorrectionsTransportStaffing(BaseModel):
    id: UUID
    tenant_id: UUID
    shift_id: UUID
    transport_id: UUID
    officer_ids: list[UUID] = Field(default_factory=list)
    destination: str
    transport_type: str  # court, medical, transfer
    departure_time: datetime
    return_time: datetime | None = None
    assigned_by: UUID
    created_at: datetime
    updated_at: datetime
    audit_event_id: UUID | None = None


class CorrectionsPostCoverageRule(BaseModel):
    id: UUID
    tenant_id: UUID
    facility_id: UUID
    post_id: UUID
    minimum_staff: int = 1
    mandatory: bool = True
    active: bool = True
    created_by: UUID
    created_at: datetime
    updated_at: datetime
