"""NFPA 1620 Pre-Incident Planning — Pydantic v2 models.

Play P07. Shared contract surface for the Preplan service, the
AdaptixCore UI, dispatch/CAD context enrichment, and mobile field
reference on apparatus.

Every tenant-scoped model carries ``tenant_id`` and ``correlation_id`` so
tenant isolation and cross-service tracing survive marshalling into
events and audit records.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from adaptix_contracts.preplan.enums import HazardClass, KnoxKeyStatus, OccupancyType


class _PreplanBase(BaseModel):
    """Base model for every Preplan contract.

    Enforces tenant scope and correlation on every payload that crosses a
    service or event boundary. ``model_config`` uses Pydantic v2's
    ``populate_by_name`` so downstream consumers may deserialize either
    the canonical snake_case names or common camelCase aliases already
    used by the UI donors.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=False,
        extra="forbid",
        str_strip_whitespace=True,
    )

    tenant_id: str = Field(
        ...,
        description=(
            "Tenant scope — resolved server-side from trusted auth context. "
            "Never accept a client-supplied tenant_id as authorization truth."
        ),
    )
    correlation_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Correlation ID for tracing across services and events.",
    )


# ---------------------------------------------------------------------------
# Occupancy — the target building/site a preplan is written for
# ---------------------------------------------------------------------------


class Occupancy(_PreplanBase):
    """A building or site that is the subject of pre-incident planning.

    One occupancy may have more than one ``Preplan`` over time (a plan is
    revised, superseded, or re-surveyed), so occupancy identity is kept
    separate from the plan content itself.
    """

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., min_length=1, max_length=300)
    occupancy_type: OccupancyType

    address_line_1: str = Field(..., min_length=1, max_length=300)
    address_line_2: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=150)
    state: str | None = Field(default=None, max_length=50)
    postal_code: str | None = Field(default=None, max_length=20)
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)

    parcel_number: str | None = Field(default=None, max_length=100)
    jurisdiction: str | None = Field(default=None, max_length=150)
    first_due_unit_ids: list[str] = Field(default_factory=list)
    mutual_aid_unit_ids: list[str] = Field(default_factory=list)

    stories_above_grade: int | None = Field(default=None, ge=0, le=200)
    stories_below_grade: int | None = Field(default=None, ge=0, le=20)
    gross_square_footage: int | None = Field(default=None, ge=0)
    construction_type: str | None = Field(default=None, max_length=100)
    sprinklered: bool | None = None
    fire_alarm_monitored: bool | None = None

    contact_name: str | None = Field(default=None, max_length=200)
    contact_phone: str | None = Field(default=None, max_length=50)
    contact_email: str | None = Field(default=None, max_length=254)
    after_hours_contact_phone: str | None = Field(default=None, max_length=50)

    active: bool = True

    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Preplan — the versioned NFPA 1620 plan document itself
# ---------------------------------------------------------------------------


class UtilityShutoff(BaseModel):
    """A utility shutoff location captured on a preplan.

    Kept as a first-class list entry (rather than free text) so a mobile
    field-reference view can render shutoff locations as discrete map
    pins/checklist items during a response.
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    utility_type: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="e.g. 'electrical_main', 'gas_main', 'water_main', 'sprinkler_riser'.",
    )
    location_description: str = Field(..., min_length=1, max_length=1000)
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    requires_special_tool: bool = False
    notes: str | None = Field(default=None, max_length=2000)


class KnoxBox(BaseModel):
    """A Knox Box / rapid-entry key device recorded on a preplan."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    status: KnoxKeyStatus = KnoxKeyStatus.NOT_APPLICABLE
    location_description: str | None = Field(default=None, max_length=1000)
    box_serial_number: str | None = Field(default=None, max_length=100)
    installed_on: date | None = None
    last_verified_on: date | None = None
    last_verified_by: str | None = None
    notes: str | None = Field(default=None, max_length=2000)


class Hazard(_PreplanBase):
    """A hazard recorded against a preplan.

    Modeled as its own tenant-scoped entity (rather than an embedded list
    on ``Preplan``) so a hazard can be updated, superseded, or referenced
    by dispatch/CAD context enrichment independently of a full plan
    revision.
    """

    id: UUID = Field(default_factory=uuid4)
    preplan_id: UUID
    occupancy_id: UUID

    hazard_class: HazardClass
    description: str = Field(..., min_length=1, max_length=4000)
    location_description: str | None = Field(default=None, max_length=1000)
    quantity: str | None = Field(
        default=None,
        max_length=200,
        description="Free-form quantity/measure (e.g. '2,000 gal AST').",
    )
    nfpa_704_rating: str | None = Field(
        default=None,
        max_length=20,
        description="NFPA 704 diamond rating string, e.g. '3-1-0-OX'.",
    )
    sds_reference: str | None = Field(
        default=None,
        max_length=500,
        description="Safety Data Sheet reference/link, if applicable.",
    )
    mitigation_notes: str | None = Field(default=None, max_length=4000)

    active: bool = True

    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FloorPlan(_PreplanBase):
    """A floor/level plan diagram bound to a preplan revision.

    Stores a reference to the rendered artifact (image/PDF/vector) rather
    than the artifact bytes themselves — artifact storage/versioning is
    owned by the object-storage service, this contract only tracks the
    metadata a preplan revision needs to resolve the correct artifact.
    """

    id: UUID = Field(default_factory=uuid4)
    preplan_id: UUID
    occupancy_id: UUID

    level_label: str = Field(
        ..., min_length=1, max_length=100, description="e.g. 'Ground Floor', 'B1', 'Roof'."
    )
    level_order: int = Field(
        default=0, description="Sort order for stacking levels; 0 = grade/ground."
    )
    artifact_object_key: str = Field(
        ..., min_length=1, max_length=1000, description="Object-storage key for the diagram."
    )
    artifact_content_type: str | None = Field(default=None, max_length=150)
    egress_points: list[str] = Field(default_factory=list)
    stairwell_labels: list[str] = Field(default_factory=list)
    standpipe_locations: list[str] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=2000)

    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Preplan(_PreplanBase):
    """A versioned NFPA 1620 pre-incident plan for an occupancy.

    ``version`` increments on every published revision so a Reality
    projection of what a plan looked like at a given response stays
    verifiable after the plan is updated. ``ready_for_response`` is a
    derived-by-service flag (not client-set truth) that should require a
    Knox Box status other than ``MISSING``/``INOPERABLE``/``LOCKED_OUT``
    when the occupancy has one, plus at least one current ``FloorPlan``.
    """

    id: UUID = Field(default_factory=uuid4)
    occupancy_id: UUID

    version: int = Field(default=1, ge=1)
    active: bool = True
    superseded_by_id: UUID | None = None

    summary: str | None = Field(default=None, max_length=8000)
    tactical_considerations: str | None = Field(default=None, max_length=8000)
    staffing_recommendation: str | None = Field(default=None, max_length=2000)
    water_supply_notes: str | None = Field(default=None, max_length=4000)
    apparatus_access_notes: str | None = Field(default=None, max_length=4000)

    knox_box: KnoxBox | None = None
    utility_shutoffs: list[UtilityShutoff] = Field(default_factory=list)

    ready_for_response: bool = Field(
        default=False,
        description="Derived by the Preplan service; not client-set authorization truth.",
    )

    survey_completed_on: date | None = None
    survey_completed_by: str | None = None
    review_due_on: date | None = None
    approved_by: str | None = Field(
        default=None,
        description="User id of the officer/inspector who approved this revision.",
    )
    approved_at: datetime | None = None

    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Program-specific plan fields not modelled above.",
    )


__all__ = [
    "FloorPlan",
    "Hazard",
    "KnoxBox",
    "Occupancy",
    "Preplan",
    "UtilityShutoff",
]
