"""MDT (Mobile Data Terminal) contracts for Adaptix platform.

MDT provides field units with real-time CAD case display, unit status updates,
crew assignment display, incident notes, and map/route display.
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel


class UnitStatus(str, Enum):
    AVAILABLE = "available"
    EN_ROUTE = "en_route"
    ARRIVED = "arrived"
    TRANSPORTING = "transporting"
    AT_DESTINATION = "at_destination"
    CLEAR = "clear"
    OUT_OF_SERVICE = "out_of_service"
    STAGING = "staging"


class MDTUnitStatusUpdate(BaseModel):
    """Unit status update from MDT."""

    unit_id: str
    tenant_id: str
    actor_id: str
    case_id: str | None = None
    status: UnitStatus
    location_lat: float | None = None
    location_lon: float | None = None
    notes: str | None = None
    updated_at: datetime
    idempotency_key: str | None = None


class MDTCaseAssignment(BaseModel):
    """CAD case assignment displayed on MDT."""

    case_id: str
    tenant_id: str
    unit_id: str
    incident_type: str | None = None
    priority: str | None = None
    location: str | None = None
    chief_complaint: str | None = None
    dispatch_notes: str | None = None
    crew_members: list[str] = []
    assigned_at: datetime
    cad_sync_at: datetime | None = None


class MDTIncidentNote(BaseModel):
    """Incident note created from MDT."""

    note_id: str
    case_id: str
    unit_id: str
    tenant_id: str
    actor_id: str
    note_text: str
    created_at: datetime
    phi_safe: bool = True


class MDTRouteRequest(BaseModel):
    """Route/map request from MDT."""

    unit_id: str
    tenant_id: str
    origin_lat: float
    origin_lon: float
    destination_lat: float
    destination_lon: float
    provider_status: str = "credential_gated"


class MDTRouteResponse(BaseModel):
    """Route response for MDT display."""

    unit_id: str
    route_available: bool
    provider_status: str
    estimated_minutes: int | None = None
    distance_miles: float | None = None
    credential_gated: bool = False
    credential_gated_reason: str | None = None


class MDTOfflineState(BaseModel):
    """Offline state for Android MDT."""

    unit_id: str
    tenant_id: str
    last_sync_at: datetime | None = None
    pending_status_updates: int = 0
    pending_notes: int = 0
    offline_since: datetime | None = None
    sync_required: bool = False
