"""Adaptix Scheduling — EMS Specific Models."""

from __future__ import annotations

from datetime import datetime

from uuid import UUID

from pydantic import BaseModel, Field


class EMSUnitAssignment(BaseModel):
    id: UUID
    tenant_id: UUID
    shift_id: UUID
    unit_id: UUID
    unit_number: str
    unit_type: str  # ALS, BLS, MICU, fly_car
    station_id: UUID | None = None
    crew: list[UUID] = Field(default_factory=list)
    assigned_by: UUID
    assigned_at: datetime
    cad_unit_id: str | None = None
    cad_synced: bool = False
    cad_synced_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    audit_event_id: UUID | None = None


class EMSCrewPairing(BaseModel):
    id: UUID
    tenant_id: UUID
    shift_id: UUID
    unit_id: UUID
    paramedic_id: UUID | None = None
    emt_id: UUID | None = None
    als_covered: bool = False
    bls_covered: bool = False
    skill_mix_valid: bool = False
    pairing_validated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    audit_event_id: UUID | None = None


class ALSBLSCoverageRule(BaseModel):
    id: UUID
    tenant_id: UUID
    station_id: UUID | None = None
    minimum_als_units: int = 1
    minimum_bls_units: int = 0
    minimum_paramedics: int = 1
    active: bool = True
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class CredentialCoverageRule(BaseModel):
    id: UUID
    tenant_id: UUID
    credential_type: str  # paramedic, emt_basic, emt_advanced, etc.
    minimum_per_unit: int = 1
    block_on_expiry: bool = True
    active: bool = True
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class EMSStationCoverage(BaseModel):
    id: UUID
    tenant_id: UUID
    station_id: UUID
    shift_id: UUID
    units_assigned: int = 0
    als_units: int = 0
    bls_units: int = 0
    minimum_met: bool = False
    coverage_checked_at: datetime
    created_at: datetime
    updated_at: datetime


class EMSSkillMixValidation(BaseModel):
    id: UUID
    tenant_id: UUID
    shift_id: UUID
    unit_id: UUID
    validation_passed: bool
    issues: list[str] = Field(default_factory=list)
    validated_at: datetime
    created_at: datetime
    updated_at: datetime
    audit_event_id: UUID | None = None
