"""Facility registry contracts shared across Adaptix services.

Canonical facility record, aliases, external-system mappings (CMS/NEMSIS/
state identifiers), and contacts for the AdaptixCore Facility shared service.
These are the authoritative facility-registry shapes; the transport-domain
``FacilityResponse`` remains a distinct read model for the transport service.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
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

    name: str | None = Field(default=None, max_length=200)
    role: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=32)
    fax: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=320)


class FacilityAlias(BaseModel):
    """An alternate name a facility is known by."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    facility_id: UUID
    alias: str = Field(..., min_length=1, max_length=255)
    source: str | None = Field(
        default=None,
        max_length=64,
        description="Origin of the alias, e.g. nemsis, state.",
    )
    created_at: datetime


class FacilityMapping(BaseModel):
    """External-system identifiers for a facility."""

    facility_id: UUID
    cms_certification_number: str | None = Field(
        default=None, max_length=32, description="CMS CCN."
    )
    npi: str | None = Field(default=None, max_length=10, description="10-digit NPI.")
    nemsis_facility_id: str | None = Field(default=None, max_length=64)
    state_facility_id: str | None = Field(default=None, max_length=64)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    external_system: str | None = Field(default=None, max_length=64)
    external_id: str | None = Field(default=None, max_length=128)


class FacilityCapability(BaseModel):
    """A clinical/operational capability a facility offers.

    Examples: ``trauma_level_1``, ``cardiac_cath``, ``stroke_center``,
    ``dialysis``, ``bariatric``, ``pediatric_ed``.
    """

    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=160)
    category: str | None = Field(default=None, max_length=64)
    is_available: bool = True
    detail: str | None = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# Facility Record
# ---------------------------------------------------------------------------


class FacilityRecord(BaseModel):
    """Canonical facility registry record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID | None = Field(
        default=None, description="None for platform-shared facilities."
    )
    name: str = Field(..., min_length=1, max_length=255)
    facility_type: FacilityType
    status: FacilityStatus = FacilityStatus.ACTIVE
    address_line1: str | None = Field(default=None, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    postal_code: str | None = Field(default=None, max_length=16)
    country: str = Field(default="US", min_length=2, max_length=2)
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    phone: str | None = Field(default=None, max_length=32)
    contacts: list[FacilityContact] = Field(default_factory=list)
    capabilities: list[FacilityCapability] = Field(default_factory=list)
    mapping: FacilityMapping | None = None
    aliases: list[FacilityAlias] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Directory Search
# ---------------------------------------------------------------------------


class FacilitySearchRequest(BaseModel):
    """Query parameters for the facility directory."""

    tenant_id: UUID | None = Field(
        default=None, description="None searches only platform-shared facilities."
    )
    query: str | None = Field(
        default=None, max_length=255, description="Free-text name/alias match."
    )
    facility_type: FacilityType | None = None
    state: str | None = Field(default=None, min_length=2, max_length=2)
    near_latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    near_longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    radius_miles: float | None = Field(default=None, ge=0.0)
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

    tenant_id: UUID | None = Field(
        default=None,
        description="None registers a platform-shared facility (founder-only).",
    )
    name: str = Field(..., min_length=1, max_length=255)
    facility_type: FacilityType
    status: FacilityStatus = FacilityStatus.ACTIVE
    address_line1: str | None = Field(default=None, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    postal_code: str | None = Field(default=None, max_length=16)
    country: str = Field(default="US", min_length=2, max_length=2)
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    phone: str | None = Field(default=None, max_length=32)
    contacts: list[FacilityContact] = Field(default_factory=list)
    capabilities: list[FacilityCapability] = Field(default_factory=list)
    mapping: FacilityMapping | None = None


class FacilityUpdateRequest(BaseModel):
    """Partial update of a facility record."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    facility_type: FacilityType | None = None
    status: FacilityStatus | None = None
    address_line1: str | None = Field(default=None, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    postal_code: str | None = Field(default=None, max_length=16)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    phone: str | None = Field(default=None, max_length=32)
    contacts: list[FacilityContact] | None = None
    capabilities: list[FacilityCapability] | None = None


class FacilityAliasCreateRequest(BaseModel):
    """Request to add an alternate name to a facility."""

    alias: str = Field(..., min_length=1, max_length=255)
    source: str | None = Field(default=None, max_length=64)


class FacilityMappingUpsertRequest(BaseModel):
    """Request to set external-system identifiers for a facility."""

    cms_certification_number: str | None = Field(default=None, max_length=32)
    npi: str | None = Field(default=None, max_length=10)
    nemsis_facility_id: str | None = Field(default=None, max_length=64)
    state_facility_id: str | None = Field(default=None, max_length=64)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    external_system: str | None = Field(default=None, max_length=64)
    external_id: str | None = Field(default=None, max_length=128)


# ---------------------------------------------------------------------------
# CMS / NPI Directory Sync
# ---------------------------------------------------------------------------


class CmsNpiSyncRequest(BaseModel):
    """Request to resolve/sync a facility against the CMS NPPES registry."""

    npi: str | None = Field(default=None, min_length=10, max_length=10)
    cms_certification_number: str | None = Field(default=None, max_length=32)
    name: str | None = Field(default=None, max_length=255)
    state: str | None = Field(default=None, min_length=2, max_length=2)


class CmsNpiSyncResult(BaseModel):
    """Result of a CMS/NPI directory lookup."""

    matched: bool
    facility_id: UUID | None = None
    npi: str | None = Field(default=None, max_length=10)
    name: str | None = Field(default=None, max_length=255)
    source: str = Field(default="nppes", max_length=64)


# ---------------------------------------------------------------------------
# facility.* Events
# ---------------------------------------------------------------------------


class FacilityRegisteredEvent(BaseModel):
    """Published when a new facility is registered."""

    event_type: str = "facility.registered"

    facility_id: UUID
    tenant_id: UUID | None = None
    facility_type: FacilityType
    registered_at: datetime


class FacilityUpdatedEvent(BaseModel):
    """Published when a facility record changes."""

    event_type: str = "facility.updated"

    facility_id: UUID
    tenant_id: UUID | None = None
    updated_at: datetime


class FacilityMergedEvent(BaseModel):
    """Published when one facility is merged into another (dedup)."""

    event_type: str = "facility.merged"

    source_facility_id: UUID
    target_facility_id: UUID
    tenant_id: UUID | None = None
    merged_at: datetime
