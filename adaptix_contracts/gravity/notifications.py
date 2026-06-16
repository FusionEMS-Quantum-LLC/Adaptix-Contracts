"""
GRAVITY NOTIFICATIONS CONTRACTS
ADAPTIX_PLATFORM_GRAVITY_COMPLETION_LOCK

Authoritative contracts for the unified notification system.
All modules route user-visible action feedback through this system.
"""

from __future__ import annotations
from datetime import datetime

from pydantic import BaseModel
from .modules import GravityNotificationSeverity, GravityNotificationState


class NotificationCreateRequest(BaseModel):
    tenant_id: str
    title: str
    message: str | None = None
    severity: GravityNotificationSeverity
    module: str
    source_record_id: str | None = None
    source_record_type: str | None = None
    action_url: str | None = None


class NotificationResponse(BaseModel):
    id: str
    tenant_id: str
    title: str
    message: str | None = None
    severity: GravityNotificationSeverity
    state: GravityNotificationState
    module: str
    source_record_id: str | None = None
    source_record_type: str | None = None
    action_url: str | None = None
    created_at: datetime
    read_at: datetime | None = None
    resolved_at: datetime | None = None
    snoozed_until: datetime | None = None
    escalated_at: datetime | None = None
    audit_event_id: str | None = None


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    unread_count: int


class NotificationSnoozeRequest(BaseModel):
    snoozed_until: datetime


class NotificationActionResponse(BaseModel):
    notification: NotificationResponse
    audit_event_id: str
