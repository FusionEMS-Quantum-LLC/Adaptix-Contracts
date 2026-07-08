"""Facility registry contracts shared across Adaptix services.

Canonical facility record, aliases, external-system mappings (CMS/NEMSIS/
state identifiers), and contacts for the AdaptixCore Facility shared service.
These are the authoritative facility-registry shapes; the transport-domain
``FacilityResponse`` remains a distinct read model for the transport service.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FacilityType(str, Enum):
    """Classification of a healthcare facility."""

    HOSPITAL = "hospital"
    SNF = "snf"
    CLINIC = "clinic"
    DIALYSIS = "dialysis"
    OTHER = "other"


class FacilityStatus(str, Enum):
    """Lifecycle state of a facility registry record."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING_VERIFICATION = "pending_verification"
    MERGED = "merged"
    CLOSED = "closed"


# ---------------------------------------------------------------------------
# Sub-records
# ---------------------------------------------------------------------------


class FacilityContact(BaseModel):
    """A point of contact at a facility."""

    name: Optional[str] = Field(None, max_length=200)
    role: Optional[str] = Field(None, max_length=120)
    phone: Optional[str] = Field(None, max_length=32)
    fax: Optional[str] = Field(None, max_length=32)
    email: Optional[str] = Field(None, max_length=320)


class FacilityAlias(BaseModel):
    """An alternate name a facility is known by."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    facility_id: UUID
    alias: str = Field(..., min_length=1, max_length=255)
    source: Optional[str] = Field(
        None, max_length=64, description="Origin of the alias, e.g. nemsis, state."
    )
    created_at: datetime


class FacilityMapping(BaseModel):
    """External-system identifiers for a facility."""

    facility_id: UUID
    cms_certification_number: Optional[str] = Field(
        None, max_length=32, description="CMS CCN."
    )
    npi: Optional[str] = Field(None, max_length=10, description="10-digit NPI.")
    nemsis_facility_id: Optional[str] = Field(None, max_length=64)
    state_facility_id: Optional[str] = Field(None, max_length=64)
    state: Optional[str] = Field(None, min_length=2, max_length=2)
    external_system: Optional[str] = Field(None, max_length=64)
    external_id: Optional[str] = Field(None, max_length=128)


# ---------------------------------------------------------------------------
# Facility Record
# ---------------------------------------------------------------------------


class FacilityRecord(BaseModel):
    """Canonical facility registry record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: Optional[UUID] = Field(
        None, description="None for platform-shared facilities."
    )
    name: str = Field(..., min_length=1, max_length=255)
    facility_type: FacilityType
    status: FacilityStatus = FacilityStatus.ACTIVE
    address_line1: Optional[str] = Field(None, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=120)
    state: Optional[str] = Field(None, min_length=2, max_length=2)
    postal_code: Optional[str] = Field(None, max_length=16)
    country: str = Field("US", min_length=2, max_length=2)
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    phone: Optional[str] = Field(None, max_length=32)
    contacts: list[FacilityContact] = Field(default_factory=list)
    mapping: Optional[FacilityMapping] = None
    aliases: list[FacilityAlias] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
