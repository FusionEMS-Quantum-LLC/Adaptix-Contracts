"""Canonical public-safety incident model.

This is not NEMSIS, NERIS, FHIR, or a vendor CAD schema. Source records remain
independent members of the incident graph and are never overwritten.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .provenance import DataProvenance


class IncidentIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    global_incident_id: str = Field(..., min_length=1)
    originating_agency_id: str = Field(..., min_length=1)
    primary_incident_number: str = Field(..., min_length=1)
    incident_type: str = Field(..., min_length=1)
    incident_status: str = Field(..., min_length=1)


class IncidentLocation(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    address: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)


class AgencyParticipation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    agency_id: str = Field(..., min_length=1)
    tenant_id: str | None = None
    role: str | None = None
    joined_at: datetime | None = None
    cleared_at: datetime | None = None


class UnitParticipation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    agency_id: str = Field(..., min_length=1)
    unit_id: str = Field(..., min_length=1)
    unit_type: str | None = None
    status: str | None = None
    assigned_at: datetime | None = None
    cleared_at: datetime | None = None


class SourceRecordReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    source_agency_id: str = Field(..., min_length=1)
    source_tenant_id: str | None = None
    source_service: str = Field(..., min_length=1)
    source_record_id: str = Field(..., min_length=1)
    source_record_version: str | None = None
    source_standard: str | None = None
    source_standard_version: str | None = None


class PublicSafetyIncident(BaseModel):
    """Versioned canonical incident spanning multiple agencies and source records."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    canonical_resource_version: str = Field(default="1.0", min_length=1)
    identity: IncidentIdentity
    location: IncidentLocation | None = None
    timestamps: dict[str, datetime] = Field(default_factory=dict)
    agency_participation: list[AgencyParticipation] = Field(default_factory=list)
    units: list[UnitParticipation] = Field(default_factory=list)
    personnel: list[dict[str, Any]] = Field(default_factory=list)
    dispatch: dict[str, Any] = Field(default_factory=dict)
    response: dict[str, Any] = Field(default_factory=dict)
    patient_encounters: list[str] = Field(default_factory=list)
    fire_activity: dict[str, Any] = Field(default_factory=dict)
    clinical_activity: dict[str, Any] = Field(default_factory=dict)
    transport: dict[str, Any] = Field(default_factory=dict)
    destination: dict[str, Any] = Field(default_factory=dict)
    communications: list[dict[str, Any]] = Field(default_factory=list)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    source_records: list[SourceRecordReference] = Field(default_factory=list)
    provenance: list[DataProvenance] = Field(default_factory=list)


__all__ = [
    "AgencyParticipation",
    "IncidentIdentity",
    "IncidentLocation",
    "PublicSafetyIncident",
    "SourceRecordReference",
    "UnitParticipation",
]
