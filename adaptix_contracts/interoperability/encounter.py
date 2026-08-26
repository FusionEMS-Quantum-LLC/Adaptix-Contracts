"""Canonical encounter linkage contracts."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from .provenance import DataProvenance


class EncounterLinkStatus(str, Enum):
    SUGGESTED = "SUGGESTED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class PublicSafetyEncounter(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    canonical_resource_version: str = "1.0"
    global_encounter_id: str = Field(..., min_length=1)
    global_incident_id: str | None = None
    source_agency_id: str = Field(..., min_length=1)
    source_tenant_id: str | None = None
    source_service: str = Field(..., min_length=1)
    source_encounter_id: str = Field(..., min_length=1)
    patient_identity_ref: str | None = None
    status: EncounterLinkStatus = EncounterLinkStatus.CONFIRMED
    occurred_at: datetime | None = None
    provenance: list[DataProvenance] = Field(default_factory=list)


__all__ = ["EncounterLinkStatus", "PublicSafetyEncounter"]
