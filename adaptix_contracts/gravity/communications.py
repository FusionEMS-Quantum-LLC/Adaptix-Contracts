"""
GRAVITY COMMUNICATIONS CONTRACTS
ADAPTIX_PLATFORM_GRAVITY_COMPLETION_LOCK
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum

from pydantic import BaseModel
from .modules import GravityAIRunPayload


class EmailThreadState(str, Enum):
    OPEN = "open"
    SNOOZED = "snoozed"
    ASSIGNED = "assigned"
    RESOLVED = "resolved"
    ARCHIVED = "archived"


class SMSThreadState(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    OPTED_OUT = "opted_out"
    BLOCKED = "blocked"


class CallState(str, Enum):
    COMPLETED = "completed"
    MISSED = "missed"
    VOICEMAIL = "voicemail"
    FAILED = "failed"
    IN_PROGRESS = "in_progress"


class EmailMessageResponse(BaseModel):
    id: str
    thread_id: str
    from_address: str
    from_name: str | None = None
    to_addresses: list[str]
    subject: str
    body_preview: str
    delivery_state: str
    sent_at: datetime | None = None
    received_at: datetime | None = None
    has_attachments: bool
    phi_warning: bool


class EmailThreadResponse(BaseModel):
    id: str
    tenant_id: str
    subject: str
    state: EmailThreadState
    priority: str
    assignee_id: str | None = None
    assignee_name: str | None = None
    participant_count: int
    message_count: int
    last_message_at: datetime
    snoozed_until: datetime | None = None
    messages: list[EmailMessageResponse] = []
    ai_suggestion: GravityAIRunPayload | None = None
    tags: list[str] = []
    phi_warning: bool = False
    created_at: datetime
    updated_at: datetime


class EmailThreadListItemResponse(BaseModel):
    id: str
    subject: str
    state: EmailThreadState
    priority: str
    assignee_name: str | None = None
    message_count: int
    last_message_at: datetime
    has_ai_suggestion: bool
    phi_warning: bool


class SendEmailRequest(BaseModel):
    thread_id: str | None = None
    to_addresses: list[str]
    subject: str
    body_html: str
    reply_to_message_id: str | None = None


class SMSMessageResponse(BaseModel):
    id: str
    thread_id: str
    direction: str
    body: str
    delivery_state: str
    sent_at: datetime
    phi_warning: bool


class SMSThreadResponse(BaseModel):
    id: str
    tenant_id: str
    phone_number: str
    contact_name: str | None = None
    state: SMSThreadState
    message_count: int
    last_message_at: datetime
    messages: list[SMSMessageResponse] = []
    patient_id: str | None = None
    patient_name: str | None = None
    opt_in_status: str
    created_at: datetime
    updated_at: datetime


class SendSMSRequest(BaseModel):
    thread_id: str | None = None
    phone_number: str
    body: str


class PhoneCallResponse(BaseModel):
    id: str
    tenant_id: str
    phone_number: str
    contact_name: str | None = None
    direction: str
    state: CallState
    disposition: str | None = None
    duration_seconds: int | None = None
    patient_id: str | None = None
    patient_name: str | None = None
    notes: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    created_at: datetime


class DispositionCallRequest(BaseModel):
    disposition: str
    notes: str | None = None


class CommunicationActionResponse(BaseModel):
    audit_event_id: str
