"""Telephony platform contracts shared across Adaptix services.

Provider-agnostic Call / Voicemail / Queue / UserPresence shapes and the
realtime telephony event-type constants that the Telephony-Service, Web-App,
and Founder-Service agree on. These are the shared cross-domain wire shapes for
the AdaptixCore telephony platform; provider-specific webhook payloads (e.g.
``telnyx_contracts``) remain separate and map INTO these platform contracts.

Identifier typing notes:
  * Domain entity ids (call/tenant/user/queue/voicemail) are ``UUID``.
  * ``destination_id`` is typed ``str`` because a routing destination may be a
    UUID (user/team/queue) or a non-UUID value (an external phone number),
    matching the platform convention used by ``SignalCoreEvent.source_entity_id``.
  * ``provider_call_id`` is the carrier's own call identifier (opaque string).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DestinationType(str, Enum):
    """Kind of routing destination a call can be directed to."""

    USER = "user"
    TEAM = "team"
    QUEUE = "queue"
    DEPARTMENT = "department"
    WORKSPACE = "workspace"
    CORTEX_AGENT = "cortex_agent"
    VOICEMAIL_BOX = "voicemail_box"
    EXTERNAL_NUMBER = "external_number"
    ON_CALL_POLICY = "on_call_policy"


class CallStatus(str, Enum):
    """Lifecycle state of a telephony call leg."""

    NEW = "new"
    RINGING = "ringing"
    AI_ACTIVE = "ai_active"
    QUEUED = "queued"
    OFFERED = "offered"
    ANSWERED = "answered"
    ON_HOLD = "on_hold"
    TRANSFERRING = "transferring"
    VOICEMAIL = "voicemail"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    FAILED = "failed"


class VoicemailStatus(str, Enum):
    """Lifecycle / review state of a voicemail message."""

    NEW = "new"
    UNREAD = "unread"
    LISTENED = "listened"
    IN_REVIEW = "in_review"
    ASSIGNED = "assigned"
    CALLBACK_REQUIRED = "callback_required"
    CALLBACK_COMPLETED = "callback_completed"
    ARCHIVED = "archived"
    DELETED = "deleted"
    FAILED_PROCESSING = "failed_processing"


class QueueStatus(str, Enum):
    """Operational state of a call queue."""

    OPEN = "open"
    CLOSED = "closed"
    PAUSED = "paused"
    DEGRADED = "degraded"


class TelephonyEventType(str, Enum):
    """Canonical realtime telephony event-type constants.

    Emitted on the platform realtime channel so Web-App and Founder-Service can
    react to live call / voicemail / queue / presence changes.
    """

    CALL_RINGING = "telephony.call.ringing"
    CALL_OFFERED = "telephony.call.offered"
    CALL_ANSWERED = "telephony.call.answered"
    CALL_HELD = "telephony.call.held"
    CALL_RESUMED = "telephony.call.resumed"
    CALL_TRANSFERRED = "telephony.call.transferred"
    CALL_COMPLETED = "telephony.call.completed"
    CALL_FAILED = "telephony.call.failed"
    VOICEMAIL_CREATED = "telephony.voicemail.created"
    VOICEMAIL_TRANSCRIBED = "telephony.voicemail.transcribed"
    VOICEMAIL_PROCESSING_FAILED = "telephony.voicemail.processing_failed"
    QUEUE_UPDATED = "telephony.queue.updated"
    PRESENCE_UPDATED = "telephony.presence.updated"


# ---------------------------------------------------------------------------
# Entity contracts
# ---------------------------------------------------------------------------


class Call(BaseModel):
    """Provider-agnostic telephony call record shared across services."""

    model_config = ConfigDict(from_attributes=True)

    call_id: UUID
    tenant_id: UUID
    provider: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Carrier provider key, e.g. 'telnyx'.",
    )
    provider_call_id: str = Field(
        ..., min_length=1, max_length=255, description="Carrier's own call identifier."
    )
    direction: str = Field(
        ..., min_length=1, max_length=16, description="'inbound' or 'outbound'."
    )
    from_number: str = Field(..., min_length=1, max_length=64)
    to_number: str = Field(..., min_length=1, max_length=64)
    destination_type: Optional[DestinationType] = None
    destination_id: Optional[str] = Field(
        None,
        max_length=255,
        description="UUID (user/team/queue/…) or non-UUID (external number) target.",
    )
    status: CallStatus
    started_at: Optional[datetime] = None
    answered_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = Field(None, ge=0)
    recording_status: Optional[str] = Field(None, max_length=32)
    transcription_status: Optional[str] = Field(None, max_length=32)
    assigned_user_id: Optional[UUID] = None
    assigned_queue_id: Optional[UUID] = None
    failure_code: Optional[str] = Field(None, max_length=64)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class Voicemail(BaseModel):
    """Provider-agnostic voicemail record shared across services."""

    model_config = ConfigDict(from_attributes=True)

    voicemail_id: UUID
    tenant_id: UUID
    call_id: Optional[UUID] = Field(
        None,
        description="Originating call, when the voicemail derives from a call leg.",
    )
    voicemail_box_id: UUID
    caller_number: str = Field(..., min_length=1, max_length=64)
    caller_contact_id: Optional[UUID] = None
    audio_object_key: Optional[str] = Field(
        None, max_length=1024, description="Object-storage key of the recorded audio."
    )
    duration_seconds: Optional[int] = Field(None, ge=0)
    transcript: Optional[str] = None
    summary: Optional[str] = None
    intent: Optional[str] = Field(None, max_length=255)
    urgency: Optional[str] = Field(None, max_length=32)
    status: VoicemailStatus
    assigned_user_id: Optional[UUID] = None
    callback_required: bool = False
    callback_completed_at: Optional[datetime] = None
    received_at: datetime
    listened_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None
    retention_until: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class Queue(BaseModel):
    """Call queue definition shared across services.

    ``routing_policy`` / ``business_hours_policy`` / ``overflow_policy`` are
    structured policy configurations owned by the telephony domain; they are
    carried here as open JSON objects so consumers agree on the field identity
    without the platform contract dictating the domain-internal policy shape.
    """

    model_config = ConfigDict(from_attributes=True)

    queue_id: UUID
    tenant_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=160)
    status: QueueStatus
    routing_policy: dict[str, Any] = Field(default_factory=dict)
    business_hours_policy: dict[str, Any] = Field(default_factory=dict)
    overflow_policy: dict[str, Any] = Field(default_factory=dict)
    voicemail_box_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class UserPresence(BaseModel):
    """Realtime telephony presence for a user shared across services."""

    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    tenant_id: UUID
    telephony_status: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="e.g. 'available', 'on_call', 'away', 'offline'.",
    )
    device_status: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="e.g. 'registered', 'unregistered'.",
    )
    last_seen_at: Optional[datetime] = None
    active_call_id: Optional[UUID] = None
    do_not_disturb: bool = False
