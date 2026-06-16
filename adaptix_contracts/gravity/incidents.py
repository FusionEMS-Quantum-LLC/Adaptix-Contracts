"""
GRAVITY INCIDENTS CONTRACTS
ADAPTIX_PLATFORM_GRAVITY_COMPLETION_LOCK
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum

from pydantic import BaseModel
from .modules import GravityAIRunPayload


class IncidentState(str, Enum):
    ACTIVE = "active"
    ESCALATED = "escalated"
    DE_ESCALATED = "de_escalated"
    CLOSED = "closed"
    REOPENED = "reopened"


class IncidentPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IncidentResourceResponse(BaseModel):
    id: str
    incident_id: str
    resource_type: str
    resource_id: str
    resource_label: str
    assigned_at: datetime
    released_at: datetime | None = None


class IncidentTimelineEventResponse(BaseModel):
    id: str
    incident_id: str
    timestamp: datetime
    event_type: str
    description: str
    actor_id: str | None = None
    actor_name: str | None = None
    severity: str | None = None


class IncidentLinkResponse(BaseModel):
    id: str
    incident_id: str
    linked_type: str
    linked_id: str
    linked_label: str | None = None


class IncidentResponse(BaseModel):
    id: str
    tenant_id: str
    record_id: str
    title: str
    description: str | None = None
    state: IncidentState
    priority: IncidentPriority
    patient_count: int = 0
    scene_address: str | None = None
    scene_lat: float | None = None
    scene_lng: float | None = None
    cad_call_id: str | None = None
    resources: list[IncidentResourceResponse] = []
    links: list[IncidentLinkResponse] = []
    timeline: list[IncidentTimelineEventResponse] = []
    ai_summary: GravityAIRunPayload | None = None
    command_notes: str | None = None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    actor_id: str
    version: int


class IncidentListItemResponse(BaseModel):
    id: str
    title: str
    state: IncidentState
    priority: IncidentPriority
    patient_count: int
    scene_address: str | None = None
    resource_count: int
    created_at: datetime
    updated_at: datetime


class CreateIncidentRequest(BaseModel):
    title: str
    description: str | None = None
    priority: IncidentPriority
    scene_address: str | None = None
    patient_count: int = 0


class UpdateIncidentRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: IncidentPriority | None = None
    command_notes: str | None = None
    version: int


class EscalateIncidentRequest(BaseModel):
    reason: str


class CloseIncidentRequest(BaseModel):
    resolution_note: str | None = None


class AssignResourceRequest(BaseModel):
    resource_type: str
    resource_id: str
    resource_label: str


class IncidentActionResponse(BaseModel):
    incident: IncidentResponse
    audit_event_id: str
