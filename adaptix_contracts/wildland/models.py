"""Pydantic v2 models for the Adaptix Wildland federal sync service (Play P10).

Every model on the Wildland boundary carries ``tenant_id`` and
``correlation_id`` — ``tenant_id`` because a wildland assignment or
resource order belongs to one Adaptix agency, and ``correlation_id`` so
a Signal Bus event, an API call, and the federal-system sync record for
the same work can be joined post-hoc.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from adaptix_contracts.wildland.enums import (
    Ics209Section,
    IrocResourceType,
    WfdssPhase,
)


class WildlandAssignment(BaseModel):
    """An Adaptix resource's assignment to a wildland incident.

    The pair ``(tenant_id, assignment_id)`` is the canonical identity.
    ``irwin_incident_id`` links the assignment to the IRWIN incident
    identity record when one exists; it is optional because an
    assignment may be created before IRWIN sync completes.
    """

    tenant_id: str
    correlation_id: str

    assignment_id: str
    resource_id: str
    resource_type: IrocResourceType

    irwin_incident_id: str | None = None
    incident_name: str | None = None

    agency_id: str
    requesting_unit_id: str | None = None

    ordered_at: datetime
    mobilized_at: datetime | None = None
    demobilized_at: datetime | None = None

    status_reason: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)


class WildlandDeployment(BaseModel):
    """A point-in-time deployment/location record for a wildland assignment.

    Kept distinct from :class:`WildlandAssignment` because a single
    assignment produces many deployment updates (relocations, staging
    changes) over its lifetime and the assignment record itself should
    not grow unbounded.
    """

    tenant_id: str
    correlation_id: str

    deployment_id: str
    assignment_id: str

    reported_at: datetime
    location_description: str | None = None
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)

    division: str | None = None
    branch: str | None = None
    staging_area: str | None = None

    reported_by: str | None = None
    notes: str | None = None


class IrocResourceOrder(BaseModel):
    """An IROC resource order tracked on the Adaptix side of the sync.

    ``iroc_order_number`` is the federal system's own identifier and is
    optional until IROC assigns one; ``request_status`` is left as a
    free-text field owned by the sync worker rather than an enum because
    IROC's own status vocabulary is wider than Adaptix needs to model
    structurally.
    """

    tenant_id: str
    correlation_id: str

    order_id: str
    iroc_order_number: str | None = None

    resource_type: IrocResourceType
    resource_type_detail: str | None = None

    requesting_agency_id: str
    incident_name: str | None = None
    irwin_incident_id: str | None = None

    quantity_requested: int = Field(default=1, ge=1)
    quantity_filled: int = Field(default=0, ge=0)

    request_status: str | None = None
    ordered_at: datetime
    needed_by: datetime | None = None
    filled_at: datetime | None = None

    assignment_ids: list[str] = Field(default_factory=list)
    last_synced_at: datetime | None = None
    sync_error: str | None = None


class WfdssDecision(BaseModel):
    """A WFDSS strategic decision record synced into Adaptix.

    ``decision_document`` is an opaque structured blob (the WFDSS
    decision content) — consumers MUST NOT parse it beyond the fields
    Adaptix explicitly promotes onto this model; the shape is owned by
    WFDSS and may change without notice.
    """

    tenant_id: str
    correlation_id: str

    decision_id: str
    wfdss_analysis_id: str | None = None
    irwin_incident_id: str | None = None

    incident_name: str | None = None
    phase: WfdssPhase = WfdssPhase.DRAFT

    published_at: datetime | None = None
    revised_at: datetime | None = None
    published_by: str | None = None

    strategic_objectives: list[str] = Field(default_factory=list)
    decision_document: dict[str, Any] = Field(default_factory=dict)

    last_synced_at: datetime | None = None
    sync_error: str | None = None


class Ics209Report(BaseModel):
    """An ICS-209 Incident Status Summary report tracked in Adaptix.

    ``sections`` maps section name to the section's structured content
    so a partially-filed report (only some sections complete) is
    representable without a mandatory-field explosion across the model.
    """

    tenant_id: str
    correlation_id: str

    report_id: str
    irwin_incident_id: str | None = None
    incident_name: str

    report_number: int = Field(default=1, ge=1)
    operational_period_start: datetime
    operational_period_end: datetime | None = None

    sections: dict[Ics209Section, dict[str, Any]] = Field(default_factory=dict)

    prepared_by: str | None = None
    approved_by: str | None = None
    submitted_at: datetime | None = None

    last_synced_at: datetime | None = None
    sync_error: str | None = None


__all__ = [
    "Ics209Report",
    "IrocResourceOrder",
    "WfdssDecision",
    "WildlandAssignment",
    "WildlandDeployment",
]
