"""Notification service contracts shared across Adaptix services.

Canonical DTOs, enums, and delivery/preference/template types for the
AdaptixCore Notification shared service.

The canonical send request, ``NotificationRequest``, is defined in
``communications_contracts`` and re-used here (not redefined) to preserve a
single authoritative shape across the platform. This module adds the typed
channel/status enums and the delivery-status, preference, and template
contracts that the Notification service owns.
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


class NotificationChannel(str, Enum):
    """Delivery channel for a notification."""

    PUSH = "push"
    EMAIL = "email"
    SMS = "sms"
    IN_APP = "in_app"


class NotificationStatus(str, Enum):
    """Lifecycle state of a single notification delivery."""

    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Delivery Status
# ---------------------------------------------------------------------------


class NotificationDeliveryStatus(BaseModel):
    """Current delivery state of a dispatched notification."""

    model_config = ConfigDict(from_attributes=True)

    notification_id: UUID
    tenant_id: UUID
    recipient_id: UUID
    channel: NotificationChannel
    status: NotificationStatus
    correlation_id: Optional[str] = None
    template_key: Optional[str] = None
    attempts: int = Field(0, ge=0)
    provider_message_id: Optional[str] = None
    error_reason: Optional[str] = None
    queued_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    updated_at: datetime


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------


class NotificationPreference(BaseModel):
    """Per-user opt-in/opt-out preference for a channel and category."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    user_id: UUID
    channel: NotificationChannel
    category: str = Field(..., min_length=1, max_length=100)
    enabled: bool = True
    updated_at: datetime


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


class NotificationTemplate(BaseModel):
    """Reusable, per-channel notification template."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    key: str = Field(..., min_length=1, max_length=160)
    channel: NotificationChannel
    subject_template: Optional[str] = Field(None, max_length=500)
    body_template: str = Field(..., min_length=1)
    locale: str = Field("en-US", max_length=16)
    description: Optional[str] = Field(None, max_length=1000)
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Send Request (canonical, typed)
#
# FIELD-IDENTITY NOTE: ``communications_contracts.NotificationRequest`` is the
# real dispatcher's request and uses str-typed ``tenant_id``/``recipient_id``/
# ``channel`` with a single ``body``. It is preserved as-is. This
# ``NotificationSendRequest`` is the canonical, strongly-typed send shape for
# the consolidated Notification service (UUID ids, ``NotificationChannel`` enum,
# category + template + idempotency). The two shapes are intentionally NOT
# merged — they are versioned side by side until the dispatcher migrates.
# ---------------------------------------------------------------------------


class NotificationSendRequest(BaseModel):
    """Typed request to send a notification via the Notification service."""

    tenant_id: UUID
    recipient_id: UUID
    channel: NotificationChannel
    category: str = Field(..., min_length=1, max_length=100)
    subject: Optional[str] = Field(None, max_length=500)
    body: str = Field(..., min_length=1)
    template_key: Optional[str] = Field(None, max_length=160)
    correlation_id: Optional[str] = None
    idempotency_key: Optional[str] = Field(
        None,
        max_length=255,
        description="Dedup key; a retry with the same key must not double-send.",
    )
    reference_type: Optional[str] = Field(None, max_length=64)
    reference_id: Optional[str] = Field(None, max_length=255)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Preference Set (per-user, per-category, per-channel booleans)
#
# FIELD-IDENTITY NOTE: ``NotificationPreference`` above models a single
# (channel, category) opt-in row. ``NotificationPreferenceSet`` models the
# Core notification_preferences shape — one row per category carrying a boolean
# per channel plus quiet hours + timezone. Both are retained; consumers pick
# the shape that matches their storage. They are NOT unified.
# ---------------------------------------------------------------------------


class NotificationPreferenceSet(BaseModel):
    """Per-user, per-category notification preferences across all channels."""

    model_config = ConfigDict(from_attributes=True)

    tenant_id: UUID
    user_id: UUID
    category: str = Field(..., min_length=1, max_length=100)
    email_enabled: bool = True
    sms_enabled: bool = False
    in_app_enabled: bool = True
    push_enabled: bool = False
    quiet_hours_start: Optional[str] = Field(
        None, max_length=5, description="Local start time HH:MM, 24-hour."
    )
    quiet_hours_end: Optional[str] = Field(
        None, max_length=5, description="Local end time HH:MM, 24-hour."
    )
    timezone: str = Field("UTC", max_length=64)
    updated_at: datetime


# ---------------------------------------------------------------------------
# notification.* Events
#
# The delivered/failed lifecycle events already exist in
# ``communications_contracts`` under the ``communications.notification.*``
# namespace (the dispatcher owns them). These add the queued/sent/read
# lifecycle points the Notification service emits under ``notification.*``.
# ---------------------------------------------------------------------------


class NotificationQueuedEvent(BaseModel):
    """Published when a notification is accepted and queued for delivery."""

    event_type: str = "notification.queued"

    notification_id: UUID
    tenant_id: UUID
    recipient_id: UUID
    channel: NotificationChannel
    category: str
    correlation_id: Optional[str] = None
    queued_at: datetime


class NotificationSentEvent(BaseModel):
    """Published when a notification is handed to the delivery provider."""

    event_type: str = "notification.sent"

    notification_id: UUID
    tenant_id: UUID
    recipient_id: UUID
    channel: NotificationChannel
    provider_message_id: Optional[str] = None
    sent_at: datetime


class NotificationReadEvent(BaseModel):
    """Published when a recipient reads an in-app notification."""

    event_type: str = "notification.read"

    notification_id: UUID
    tenant_id: UUID
    recipient_id: UUID
    read_at: datetime
