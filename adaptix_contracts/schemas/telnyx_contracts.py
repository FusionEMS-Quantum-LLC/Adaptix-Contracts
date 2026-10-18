"""Telnyx telephony contracts shared across Adaptix services."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TelnyxEventType(str, enum.Enum):
    CALL_INITIATED = "call.initiated"
    CALL_ANSWERED = "call.answered"
    CALL_HANGUP = "call.hangup"
    CALL_RECORDING_SAVED = "call.recording.saved"
    CALL_TRANSCRIPTION_COMPLETED = "call.transcription.completed"


class TelnyxCallDirection(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class TelnyxCallStatus(str, enum.Enum):
    INITIATED = "initiated"
    RINGING = "ringing"
    ANSWERED = "answered"
    COMPLETED = "completed"
    FAILED = "failed"
    MISSED = "missed"


class TelnyxCallCompletedEvent(BaseModel):
    call_id: str
    tenant_id: UUID
    direction: TelnyxCallDirection
    from_number: str
    to_number: str
    started_at: datetime
    ended_at: datetime
    duration_seconds: int
    status: TelnyxCallStatus
    recording_url: str | None = None


class TelnyxTranscriptContract(BaseModel):
    id: UUID
    tenant_id: UUID
    call_id: str
    transcript_text: str
    language: str = "en"
    confidence: float | None = None
    created_at: datetime


class TelnyxRecordingContract(BaseModel):
    id: UUID
    tenant_id: UUID
    call_id: str
    recording_url: str
    duration_seconds: int
    s3_key: str | None = None
    created_at: datetime


class TelnyxAISummaryContract(BaseModel):
    id: UUID
    tenant_id: UUID
    call_id: str
    summary: str
    action_items: list[str] = Field(default_factory=list)
    deadlines: list[str] = Field(default_factory=list)
    linked_claim_id: UUID | None = None
    ai_run_id: UUID
    created_at: datetime


class TelnyxWebhookEventContract(BaseModel):
    id: UUID
    provider: str = "telnyx"
    event_id: str
    event_type: str
    payload: dict[str, Any]
    processed: bool = False
    processed_at: datetime | None = None
    raw_hash: str | None = None
    created_at: datetime


class TelnyxCallCreatedEvent(BaseModel):
    call_id: str
    tenant_id: UUID
    direction: TelnyxCallDirection
    from_number: str
    to_number: str
    started_at: datetime


class TelnyxTranscriptionCompletedEvent(BaseModel):
    call_id: str
    tenant_id: UUID
    transcript_id: UUID
    created_at: datetime
