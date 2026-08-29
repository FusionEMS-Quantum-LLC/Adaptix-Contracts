"""Real-time communication (RTC) contracts shared across Adaptix services.

Canonical session, participant-token, and room-status shapes for the
AdaptixCore RTC shared service (real-time audio/video/data rooms).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RTCRoomStatus(str, Enum):
    """Lifecycle state of an RTC room/session."""

    PENDING = "pending"
    ACTIVE = "active"
    CLOSED = "closed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Session & Token
# ---------------------------------------------------------------------------


class RTCSession(BaseModel):
    """A real-time communication room/session."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    room_name: str = Field(..., min_length=1, max_length=200)
    status: RTCRoomStatus = RTCRoomStatus.PENDING
    correlation_id: Optional[str] = None
    created_by: Optional[UUID] = None
    max_participants: Optional[int] = Field(default=None, ge=1)
    reference_type: Optional[str] = Field(default=None, max_length=120)
    reference_id: Optional[str] = Field(default=None, max_length=255)
    created_at: datetime
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


class RTCParticipantToken(BaseModel):
    """An access token authorizing a participant to join an RTC room."""

    tenant_id: UUID
    session_id: UUID
    room_name: str = Field(..., min_length=1, max_length=200)
    participant_identity: str = Field(..., min_length=1, max_length=200)
    participant_name: Optional[str] = Field(default=None, max_length=200)
    token: str = Field(..., min_length=1)
    url: Optional[str] = Field(default=None, max_length=2000)
    can_publish: bool = True
    can_subscribe: bool = True
    expires_at: Optional[datetime] = None
