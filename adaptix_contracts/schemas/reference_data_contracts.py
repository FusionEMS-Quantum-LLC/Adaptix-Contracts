"""Reference-data contracts shared across Adaptix services.

Canonical code-list container and item shapes for the AdaptixCore Reference
Data shared service (lookups, enumerated code sets, and controlled vocabularies).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Canonical Reference Enums
#
# These are the authoritative reference-data value sets. Domain modules that
# historically declared their own copies are documented below; those copies
# are intentionally NOT removed or repointed here (that requires a founder /
# billing decision because their member sets genuinely diverge — see PayerType).
# ---------------------------------------------------------------------------


class PayerType(str, Enum):
    """Canonical payer classification (reference-data superset).

    FIELD-IDENTITY NOTE — real divergence, versioned not unified:
      * ``billing_contracts.PayerType`` = MEDICARE, MEDICAID, COMMERCIAL,
        SELF_PAY, OTHER
      * ``intake_contracts.PayerType`` = MEDICARE, MEDICAID, TRICARE,
        COMMERCIAL, SELF_PAY, WORKERS_COMP
    They disagree (billing has OTHER; intake has TRICARE + WORKERS_COMP). This
    canonical enum is the union superset and is the authoritative reference-data
    catalog value. The two domain enums are left unchanged for backward
    compatibility; choosing one authoritative set for billing/intake to import
    is a founder/billing decision and is NOT made here.
    """

    MEDICARE = "medicare"
    MEDICAID = "medicaid"
    TRICARE = "tricare"
    COMMERCIAL = "commercial"
    WORKERS_COMP = "workers_comp"
    SELF_PAY = "self_pay"
    OTHER = "other"


class ServiceLevel(str, Enum):
    """Canonical transport service level.

    Sourced from the Core ``service_levels`` value list
    (``["BLS", "ALS", "SPECIALTY", "CCT", "AIR_MEDICAL"]``).
    """

    BLS = "bls"
    ALS = "als"
    SPECIALTY = "specialty"
    CCT = "cct"
    AIR_MEDICAL = "air_medical"


class StateCode(str, Enum):
    """USPS two-letter code for US states, DC, and territories."""

    AL = "AL"
    AK = "AK"
    AZ = "AZ"
    AR = "AR"
    CA = "CA"
    CO = "CO"
    CT = "CT"
    DE = "DE"
    FL = "FL"
    GA = "GA"
    HI = "HI"
    ID = "ID"
    IL = "IL"
    IN = "IN"
    IA = "IA"
    KS = "KS"
    KY = "KY"
    LA = "LA"
    ME = "ME"
    MD = "MD"
    MA = "MA"
    MI = "MI"
    MN = "MN"
    MS = "MS"
    MO = "MO"
    MT = "MT"
    NE = "NE"
    NV = "NV"
    NH = "NH"
    NJ = "NJ"
    NM = "NM"
    NY = "NY"
    NC = "NC"
    ND = "ND"
    OH = "OH"
    OK = "OK"
    OR = "OR"
    PA = "PA"
    RI = "RI"
    SC = "SC"
    SD = "SD"
    TN = "TN"
    TX = "TX"
    UT = "UT"
    VT = "VT"
    VA = "VA"
    WA = "WA"
    WV = "WV"
    WI = "WI"
    WY = "WY"
    DC = "DC"
    PR = "PR"
    VI = "VI"
    GU = "GU"
    AS = "AS"
    MP = "MP"


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------


class ReferenceDataItem(BaseModel):
    """A single entry within a reference-data list."""

    code: str = Field(..., min_length=1, max_length=160)
    label: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, max_length=2000)
    parent_code: Optional[str] = Field(default=None, max_length=160)
    sort_order: int = Field(default=0, ge=0)
    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------


class ReferenceDataList(BaseModel):
    """A named, versioned set of reference-data items."""

    model_config = ConfigDict(from_attributes=True)

    list_key: str = Field(..., min_length=1, max_length=160)
    name: str = Field(..., min_length=1, max_length=255)
    tenant_id: Optional[UUID] = Field(
        default=None, description="None for platform-shared reference lists."
    )
    description: Optional[str] = Field(default=None, max_length=2000)
    version: int = Field(default=1, ge=1)
    items: list[ReferenceDataItem] = Field(default_factory=list)
    updated_at: datetime


# ---------------------------------------------------------------------------
# CRUD / Query / Publish Request-Response DTOs
# ---------------------------------------------------------------------------


class ReferenceDataListCreateRequest(BaseModel):
    """Request to create a new reference-data list (as a draft version)."""

    list_key: str = Field(..., min_length=1, max_length=160)
    name: str = Field(..., min_length=1, max_length=255)
    tenant_id: Optional[UUID] = Field(
        default=None, description="None creates a platform-shared list (founder-only)."
    )
    description: Optional[str] = Field(default=None, max_length=2000)
    items: list[ReferenceDataItem] = Field(default_factory=list)


class ReferenceDataListUpdateRequest(BaseModel):
    """Partial update of a reference-data list's metadata and/or items."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    items: Optional[list[ReferenceDataItem]] = Field(
        default=None, description="When provided, replaces the full item set."
    )


class ReferenceDataItemUpsertRequest(BaseModel):
    """Add or update a single item within a list."""

    code: str = Field(..., min_length=1, max_length=160)
    label: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, max_length=2000)
    parent_code: Optional[str] = Field(default=None, max_length=160)
    sort_order: int = Field(default=0, ge=0)
    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReferenceDataQuery(BaseModel):
    """Query parameters for listing reference-data lists."""

    list_key: Optional[str] = Field(default=None, max_length=160)
    tenant_id: Optional[UUID] = None
    include_platform_shared: bool = True
    include_inactive_items: bool = False
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class ReferenceDataListResponse(BaseModel):
    """Paginated set of reference-data lists."""

    lists: list[ReferenceDataList] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class ReferenceDataPublishRequest(BaseModel):
    """Request to publish (version-bump) a reference-data list."""

    list_key: str = Field(..., min_length=1, max_length=160)
    tenant_id: Optional[UUID] = None


class ReferenceDataPublishResponse(BaseModel):
    """Result of publishing a reference-data list."""

    list_key: str
    tenant_id: Optional[UUID] = None
    version: int = Field(..., ge=1)
    published_at: datetime


# ---------------------------------------------------------------------------
# reference_data.* Events
# ---------------------------------------------------------------------------


class ReferenceDataListPublishedEvent(BaseModel):
    """Published when a reference-data list version is published."""

    event_type: str = "reference_data.list.published"

    list_key: str
    tenant_id: Optional[UUID] = None
    version: int = Field(..., ge=1)
    published_at: datetime


class ReferenceDataListUpdatedEvent(BaseModel):
    """Published when a reference-data list's items or metadata change."""

    event_type: str = "reference_data.list.updated"

    list_key: str
    tenant_id: Optional[UUID] = None
    version: int = Field(..., ge=1)
    updated_at: datetime
