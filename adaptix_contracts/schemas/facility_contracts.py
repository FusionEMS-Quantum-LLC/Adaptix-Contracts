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

    name: Optional[str] = Field(default=None, max_length=200)
    role: Optional[str] = Field(default=None, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=32)
    fax: Optional[str] = Field(default=None, max_length=32)
    email: Optional[str] = Field(default=None, max_length=320)


class FacilityAlias(BaseModel):
    """An alternate name a facility is known by."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    facility_id: UUID
    alias: str = Field(..., min_length=1, max_length=255)
    source: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Origin of the alias, e.g. nemsis, state.",
    )
    created_at: datetime


class FacilityMapping(BaseModel):
    """External-system identifiers for a facility."""

    facility_id: UUID
    cms_certification_number: Optional[str] = Field(
        default=None, max_length=32, description="CMS CCN."
    )
    npi: Optional[str] = Field(default=None, max_length=10, description="10-digit NPI.")
    nemsis_facility_id: Optional[str] = Field(default=None, max_length=64)
    state_facility_id: Optional[str] = Field(default=None, max_length=64)
    state: Optional[str] = Field(default=None, min_length=2, max_length=2)
    external_system: Optional[str] = Field(default=None, max_length=64)
    external_id: Optional[str] = Field(default=None, max_length=128)


class FacilityCapability(BaseModel):
    """A clinical/operational capability a facility offers.

    Examples: ``trauma_level_1``, ``cardiac_cath``, ``stroke_center``,
    ``dialysis``, ``bariatric``, ``pediatric_ed``.
    """

    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=160)
    category: Optional[str] = Field(default=None, max_length=64)
    is_available: bool = True
    detail: Optional[str] = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# Facility Record
# ---------------------------------------------------------------------------


class FacilityRecord(BaseModel):
    """Canonical facility registry record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: Optional[UUID] = Field(
        default=None, description="None for platform-shared facilities."
    )
    name: str = Field(..., min_length=1, max_length=255)
    facility_type: FacilityType
    status: FacilityStatus = FacilityStatus.ACTIVE
    address_line1: Optional[str] = Field(default=None, max_length=255)
    address_line2: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=120)
    state: Optional[str] = Field(default=None, min_length=2, max_length=2)
    postal_code: Optional[str] = Field(default=None, max_length=16)
    country: str = Field(default="US", min_length=2, max_length=2)
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    phone: Optional[str] = Field(default=None, max_length=32)
    contacts: list[FacilityContact] = Field(default_factory=list)
    capabilities: list[FacilityCapability] = Field(default_factory=list)
    mapping: Optional[FacilityMapping] = None
    aliases: list[FacilityAlias] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Directory Search
# ---------------------------------------------------------------------------


class FacilitySearchRequest(BaseModel):
    """Query parameters for the facility directory."""

    tenant_id: Optional[UUID] = Field(
        default=None, description="None searches only platform-shared facilities."
    )
    query: Optional[str] = Field(
        default=None, max_length=255, description="Free-text name/alias match."
    )
    facility_type: Optional[FacilityType] = None
    state: Optional[str] = Field(default=None, min_length=2, max_length=2)
    near_latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    near_longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    radius_miles: Optional[float] = Field(default=None, ge=0.0)
    include_inactive: bool = False
    include_platform_shared: bool = True
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class FacilitySearchResponse(BaseModel):
    """Paginated set of facility records."""

    facilities: list[FacilityRecord] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


# ---------------------------------------------------------------------------
# Create / Update Requests
# ---------------------------------------------------------------------------


class FacilityCreateRequest(BaseModel):
    """Request to register a new facility."""

    tenant_id: Optional[UUID] = Field(
        default=None,
        description="None registers a platform-shared facility (founder-only).",
    )
    name: str = Field(..., min_length=1, max_length=255)
    facility_type: FacilityType
    status: FacilityStatus = FacilityStatus.ACTIVE
    address_line1: Optional[str] = Field(default=None, max_length=255)
    address_line2: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=120)
    state: Optional[str] = Field(default=None, min_length=2, max_length=2)
    postal_code: Optional[str] = Field(default=None, max_length=16)
    country: str = Field(default="US", min_length=2, max_length=2)
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    phone: Optional[str] = Field(default=None, max_length=32)
    contacts: list[FacilityContact] = Field(default_factory=list)
    capabilities: list[FacilityCapability] = Field(default_factory=list)
    mapping: Optional[FacilityMapping] = None


class FacilityUpdateRequest(BaseModel):
    """Partial update of a facility record."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    facility_type: Optional[FacilityType] = None
    status: Optional[FacilityStatus] = None
    address_line1: Optional[str] = Field(default=None, max_length=255)
    address_line2: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=120)
    state: Optional[str] = Field(default=None, min_length=2, max_length=2)
    postal_code: Optional[str] = Field(default=None, max_length=16)
    country: Optional[str] = Field(default=None, min_length=2, max_length=2)
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    phone: Optional[str] = Field(default=None, max_length=32)
    contacts: Optional[list[FacilityContact]] = None
    capabilities: Optional[list[FacilityCapability]] = None


class FacilityAliasCreateRequest(BaseModel):
    """Request to add an alternate name to a facility."""

    alias: str = Field(..., min_length=1, max_length=255)
    source: Optional[str] = Field(default=None, max_length=64)


class FacilityMappingUpsertRequest(BaseModel):
    """Request to set external-system identifiers for a facility."""

    cms_certification_number: Optional[str] = Field(default=None, max_length=32)
    npi: Optional[str] = Field(default=None, max_length=10)
    nemsis_facility_id: Optional[str] = Field(default=None, max_length=64)
    state_facility_id: Optional[str] = Field(default=None, max_length=64)
    state: Optional[str] = Field(default=None, min_length=2, max_length=2)
    external_system: Optional[str] = Field(default=None, max_length=64)
    external_id: Optional[str] = Field(default=None, max_length=128)


# ---------------------------------------------------------------------------
# CMS / NPI Directory Sync
# ---------------------------------------------------------------------------


class CmsNpiSyncRequest(BaseModel):
    """Request to resolve/sync a facility against the CMS NPPES registry."""

    npi: Optional[str] = Field(default=None, min_length=10, max_length=10)
    cms_certification_number: Optional[str] = Field(default=None, max_length=32)
    name: Optional[str] = Field(default=None, max_length=255)
    state: Optional[str] = Field(default=None, min_length=2, max_length=2)


class CmsNpiSyncResult(BaseModel):
    """Result of a CMS/NPI directory lookup."""

    matched: bool
    facility_id: Optional[UUID] = None
    npi: Optional[str] = Field(default=None, max_length=10)
    name: Optional[str] = Field(default=None, max_length=255)
    source: str = Field(default="nppes", max_length=64)


# ---------------------------------------------------------------------------
# facility.* Events
# ---------------------------------------------------------------------------


class FacilityRegisteredEvent(BaseModel):
    """Published when a new facility is registered."""

    event_type: str = "facility.registered"

    facility_id: UUID
    tenant_id: Optional[UUID] = None
    facility_type: FacilityType
    registered_at: datetime


class FacilityUpdatedEvent(BaseModel):
    """Published when a facility record changes."""

    event_type: str = "facility.updated"

    facility_id: UUID
    tenant_id: Optional[UUID] = None
    updated_at: datetime


class FacilityMergedEvent(BaseModel):
    """Published when one facility is merged into another (dedup)."""

    event_type: str = "facility.merged"

    source_facility_id: UUID
    target_facility_id: UUID
    tenant_id: Optional[UUID] = None
    merged_at: datetime
