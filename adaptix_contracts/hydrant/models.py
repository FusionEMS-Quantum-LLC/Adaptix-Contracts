"""Adaptix Hydrant Registry — Pydantic v2 models.

Play P07. Shared contract surface for the Hydrant-Service, the AdaptixCore
UI, pre-plan / dispatch consumers, and downstream analytics that need fire
flow (PSI) history for a hydrant.

Every tenant-scoped model carries ``tenant_id`` and ``correlation_id`` so
tenant isolation and cross-service tracing survive marshalling into events
and audit records.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from adaptix_contracts.hydrant.enums import HydrantColor, HydrantStatus, TestType


class _HydrantBase(BaseModel):
    """Base model for every Hydrant contract.

    Enforces tenant scope and correlation on every payload that crosses a
    service or event boundary. ``model_config`` uses Pydantic v2's
    ``populate_by_name`` so downstream consumers may deserialize either the
    canonical snake_case names or common camelCase aliases already used by
    the UI donors.
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
# Hydrant — the physical asset
# ---------------------------------------------------------------------------


class Hydrant(_HydrantBase):
    """A registered fire hydrant asset.

    ``asset_tag`` is the agency's own field-marked identifier (paint tag /
    GIS asset number); it is distinct from ``id``, the platform UUID.
    """

    id: UUID = Field(default_factory=uuid4)
    asset_tag: str = Field(..., min_length=1, max_length=100)

    status: HydrantStatus = HydrantStatus.IN_SERVICE
    color: HydrantColor | None = None

    address_line_1: str | None = Field(default=None, max_length=200)
    address_line_2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=2)
    postal_code: str | None = Field(default=None, max_length=20)
    cross_street: str | None = Field(default=None, max_length=200)

    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)

    manufacturer: str | None = Field(default=None, max_length=200)
    model: str | None = Field(default=None, max_length=200)
    installed_on: date | None = None

    main_size_inches: Decimal | None = Field(default=None, ge=Decimal("0"))
    number_of_outlets: int | None = Field(default=None, ge=0, le=10)

    owning_utility: str | None = Field(default=None, max_length=200)
    hydrant_district: str | None = Field(default=None, max_length=200)
    response_district: str | None = Field(default=None, max_length=200)

    out_of_service_reason: str | None = Field(default=None, max_length=2000)
    out_of_service_at: datetime | None = None

    last_flow_gpm: int | None = Field(default=None, ge=0)
    last_static_psi: int | None = Field(default=None, ge=0)
    last_residual_psi: int | None = Field(default=None, ge=0)
    last_tested_at: datetime | None = None

    notes: str | None = Field(default=None, max_length=4000)

    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# HydrantTest — a single fire-flow / PSI test event
# ---------------------------------------------------------------------------


class HydrantTest(_HydrantBase):
    """A single test event recorded against a hydrant.

    This is the PSI history record: every flow test, static pressure test,
    or residual pressure test produces one ``HydrantTest`` row, so a
    hydrant's PSI trend over time can be reconstructed from
    ``hydrant_id``-scoped queries without mutating the hydrant's rollup
    fields (``last_flow_gpm`` etc. on :class:`Hydrant` are a convenience
    snapshot, not the source of truth for history).
    """

    id: UUID = Field(default_factory=uuid4)
    hydrant_id: UUID

    test_type: TestType
    tested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    static_pressure_psi: int | None = Field(default=None, ge=0, le=500)
    residual_pressure_psi: int | None = Field(default=None, ge=0, le=500)
    pitot_pressure_psi: int | None = Field(default=None, ge=0, le=500)
    flow_gpm: int | None = Field(default=None, ge=0)

    calculated_flow_at_20_psi_gpm: int | None = Field(
        default=None,
        ge=0,
        description="Fire flow available at 20 PSI residual, per NFPA 291 formula.",
    )

    pass_fail: bool | None = Field(
        default=None,
        description="Whether the test met the agency's minimum acceptable criteria.",
    )
    resulting_color: HydrantColor | None = Field(
        default=None,
        description="NFPA 291 color class this test result places the hydrant in.",
    )

    tested_by: str | None = Field(default=None, max_length=200)
    apparatus_used: str | None = Field(default=None, max_length=200)
    weather_conditions: str | None = Field(default=None, max_length=500)

    deficiencies_found: list[str] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=4000)

    linked_maintenance_id: UUID | None = None

    created_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# HydrantMaintenance — repair / service work performed on a hydrant
# ---------------------------------------------------------------------------


class HydrantMaintenance(_HydrantBase):
    """A maintenance or repair action performed on a hydrant."""

    id: UUID = Field(default_factory=uuid4)
    hydrant_id: UUID

    description: str = Field(..., min_length=1, max_length=4000)
    work_order_number: str | None = Field(default=None, max_length=100)

    performed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    performed_by: str | None = Field(default=None, max_length=200)
    contractor_name: str | None = Field(default=None, max_length=200)

    status_before: HydrantStatus | None = None
    status_after: HydrantStatus | None = None

    parts_replaced: list[str] = Field(default_factory=list)
    cost: Decimal | None = Field(default=None, ge=Decimal("0"))

    follow_up_required: bool = False
    follow_up_due_on: date | None = None

    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Agency-specific maintenance fields not modelled above.",
    )

    notes: str | None = Field(default=None, max_length=4000)

    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


__all__ = [
    "Hydrant",
    "HydrantMaintenance",
    "HydrantTest",
]
