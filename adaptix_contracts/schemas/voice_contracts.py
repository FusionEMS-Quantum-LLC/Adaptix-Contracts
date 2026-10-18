"""Voice domain cross-domain contracts."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class VoiceRoomCreatedEvent(BaseModel):
    """Published when a voice room is created for an incident."""

    event_type: str = "voice.room.created"

    room_id: UUID
    tenant_id: UUID
    incident_id: UUID
    case_id: UUID | None = None
    room_name: str
    created_at: datetime


class VoiceRoomClosedEvent(BaseModel):
    """Published when a voice room is closed."""

    event_type: str = "voice.room.closed"

    room_id: UUID
    tenant_id: UUID
    incident_id: UUID
    closed_at: datetime
    participant_count: int
