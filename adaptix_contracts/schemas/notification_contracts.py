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
from typing import Optional
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
