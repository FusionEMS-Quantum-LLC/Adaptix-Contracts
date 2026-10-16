"""Adaptix Scheduling — Law Enforcement Specific Models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class OfficerProfile(BaseModel):
    id: UUID
    tenant_id: UUID
    person_id: UUID
    badge_number: str
    rank: str
    squad_id: UUID | None = None
    district_id: UUID | None = None
    hire_date: datetime | None = None
    seniority_points: float = 0.0
    union_member: bool = False
    union_id: str | None = None
    active: bool = True
    created_at: datetime
    updated_at: datetime


class OfficerRank(BaseModel):
    id: UUID
    tenant_id: UUID
    rank_name: str
    rank_code: str
    rank_order: int  # lower = more senior
    supervisory: bool = False
    created_at: datetime
    updated_at: datetime


class OfficerBadge(BaseModel):
    id: UUID
    tenant_id: UUID
    person_id: UUID
    badge_number: str
    issued_at: datetime
    active: bool = True
    created_at: datetime
    updated_at: datetime


class OfficerSpecialty(BaseModel):
    id: UUID
    tenant_id: UUID
    person_id: UUID
    specialty: str  # K9, SWAT, SRO, Detective, Narcotics, etc.
    certified: bool = True
    certified_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class OfficerCertification(BaseModel):
    id: UUID
    tenant_id: UUID
    person_id: UUID
    certification_name: str
    certification_number: str | None = None
    issued_at: datetime
    expires_at: datetime | None = None
    active: bool = True
    created_at: datetime
    updated_at: datetime


class OfficerSeniority(BaseModel):
    id: UUID
    tenant_id: UUID
    person_id: UUID
    seniority_date: datetime
    seniority_points: float = 0.0
    bid_priority: int = 0
    created_at: datetime
    updated_at: datetime


class PatrolAssignment(BaseModel):
    id: UUID
    tenant_id: UUID
    shift_id: UUID
    person_id: UUID
    beat_id: UUID | None = None
    zone_id: UUID | None = None
    district_id: UUID | None = None
    squad_id: UUID | None = None
    vehicle_id: UUID | None = None
    assigned_by: UUID
    assigned_at: datetime
    created_at: datetime
    updated_at: datetime
    audit_event_id: UUID | None = None


class BeatAssignment(BaseModel):
    id: UUID
    tenant_id: UUID
    shift_id: UUID
    person_id: UUID
    beat_id: UUID
    beat_name: str
    assigned_by: UUID
    assigned_at: datetime
    created_at: datetime
    updated_at: datetime
    audit_event_id: UUID | None = None


class ZoneAssignment(BaseModel):
    id: UUID
    tenant_id: UUID
    shift_id: UUID
    person_id: UUID
    zone_id: UUID
    zone_name: str
    assigned_by: UUID
    assigned_at: datetime
    created_at: datetime
    updated_at: datetime
    audit_event_id: UUID | None = None


class DistrictAssignment(BaseModel):
    id: UUID
    tenant_id: UUID
    shift_id: UUID
    person_id: UUID
    district_id: UUID
    district_name: str
    assigned_by: UUID
    assigned_at: datetime
    created_at: datetime
    updated_at: datetime
    audit_event_id: UUID | None = None


class CourtConflict(BaseModel):
    id: UUID
    tenant_id: UUID
    person_id: UUID
    shift_id: UUID
    court_appearance_id: UUID
    conflict_type: str = "overlap"
    detected_at: datetime
    resolved: bool = False
    resolved_by: UUID | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    audit_event_id: UUID | None = None


class DetailAssignment(BaseModel):
    id: UUID
    tenant_id: UUID
    event_id: UUID
    person_id: UUID
    detail_type: str  # special_event, security, traffic, etc.
    role: str
    shift_id: UUID | None = None
    assigned_by: UUID
    assigned_at: datetime
    created_at: datetime
    updated_at: datetime
    audit_event_id: UUID | None = None


class K9Assignment(BaseModel):
    id: UUID
    tenant_id: UUID
    shift_id: UUID
    handler_id: UUID
    k9_unit_id: UUID
    k9_name: str
    assigned_by: UUID
    assigned_at: datetime
    created_at: datetime
    updated_at: datetime
    audit_event_id: UUID | None = None


class SWATAssignment(BaseModel):
    id: UUID
    tenant_id: UUID
    shift_id: UUID
    person_id: UUID
    swat_role: str  # entry, sniper, negotiator, commander, etc.
    callout_id: UUID | None = None
    assigned_by: UUID
    assigned_at: datetime
    created_at: datetime
    updated_at: datetime
    audit_event_id: UUID | None = None


class SchoolResourceAssignment(BaseModel):
    id: UUID
    tenant_id: UUID
    shift_id: UUID
    person_id: UUID
    school_name: str
    school_id: UUID | None = None
    assigned_by: UUID
    assigned_at: datetime
    created_at: datetime
    updated_at: datetime
    audit_event_id: UUID | None = None


class CorrectionsPostAssignment(BaseModel):
    id: UUID
    tenant_id: UUID
    shift_id: UUID
    person_id: UUID
    post_name: str
    post_id: UUID | None = None
    facility_id: UUID | None = None
    post_type: str  # housing, control, transport, perimeter, etc.
    assigned_by: UUID
    assigned_at: datetime
    created_at: datetime
    updated_at: datetime
    audit_event_id: UUID | None = None
