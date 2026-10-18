"""CAD domain contract schemas for cross-domain communication."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CadCaseCreatedEvent(BaseModel):
    """Published when a CAD case is created."""

    event_type: str = "cad.case.created"

    case_id: str
    tenant_id: str
    call_type: str
    priority: str

    pickup_address: str | None = None
    destination_facility: str | None = None

    created_at: datetime


class CadCaseStatusUpdatedEvent(BaseModel):
    """Published when a CAD case status changes."""

    event_type: str = "cad.case.status_updated"

    case_id: str
    tenant_id: str
    old_status: str
    new_status: str

    updated_at: datetime


class CadCaseContract(BaseModel):
    """Read-only CAD case contract for cross-domain consumption."""

    id: str
    tenant_id: str
    call_type: str
    status: str
    priority: str

    gravity_score: float | None = None
    pickup_address: str | None = None
    destination_facility: str | None = None

    created_at: datetime
    updated_at: datetime


class CadUnitAssignedEvent(BaseModel):
    """Published when a unit is assigned to a CAD case."""

    event_type: str = "cad.unit.assigned"

    case_id: str
    tenant_id: str
    unit_id: str

    assigned_at: datetime
