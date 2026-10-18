"""Dispatch domain contract schemas for cross-domain communication.

Defines typed contracts for EMS dispatch unit status, GPS telemetry,
and dispatch lifecycle events consumed across the Adaptix platform.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DispatchStatus(str, Enum):
    """Lifecycle status of a dispatched EMS unit."""

    DISPATCHED = "dispatched"
    EN_ROUTE = "en-route"
    ON_SCENE = "on-scene"
    TRANSPORTING = "transporting"
    AT_HOSPITAL = "at-hospital"
    AVAILABLE = "available"
    CANCELLED = "cancelled"


class DispatchPriority(str, Enum):
    """Dispatch priority classification."""

    PRIORITY_1 = "priority_1"  # Life-threatening / lights-and-siren
    PRIORITY_2 = "priority_2"  # Urgent / non-life-threatening
    PRIORITY_3 = "priority_3"  # Routine / non-emergency


# ---------------------------------------------------------------------------
# Core Contracts
# ---------------------------------------------------------------------------


class DispatchGpsCoordinate(BaseModel):
    """GPS coordinate snapshot attached to a status update."""

    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)
    accuracy_meters: float | None = None
    captured_at: datetime


class DispatchContract(BaseModel):
    """Read-only dispatch contract for cross-domain consumption."""

    dispatch_id: str
    case_id: str
    unit_id: str
    tenant_id: str

    status: DispatchStatus
    priority: DispatchPriority

    pickup_address: str | None = None
    destination_facility: str | None = None

    crew_count: int | None = None
    vehicle_identifier: str | None = None

    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


class DispatchStatusUpdateEvent(BaseModel):
    """Event emitted when a dispatch unit status changes."""

    event_type: str = "dispatch.status_updated"

    dispatch_id: str
    unit_id: str
    tenant_id: str

    old_status: DispatchStatus | None = None
    new_status: DispatchStatus

    gps_lat: float | None = None
    gps_lon: float | None = None

    timestamp: datetime


class DispatchCreatedEvent(BaseModel):
    """Event emitted when a new dispatch is created."""

    event_type: str = "dispatch.created"

    dispatch_id: str
    case_id: str
    unit_id: str
    tenant_id: str

    priority: DispatchPriority
    pickup_address: str | None = None

    created_at: datetime


class DispatchClosedEvent(BaseModel):
    """Event emitted when a dispatch is closed (unit available or cancelled)."""

    event_type: str = "dispatch.closed"

    dispatch_id: str
    unit_id: str
    tenant_id: str

    final_status: DispatchStatus
    destination_facility: str | None = None

    closed_at: datetime


class DispatchUnitGpsPingEvent(BaseModel):
    """Periodic GPS heartbeat from a unit in an active dispatch."""

    event_type: str = "dispatch.unit.gps_ping"

    dispatch_id: str
    unit_id: str
    tenant_id: str

    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)
    speed_mph: float | None = None

    pinged_at: datetime
