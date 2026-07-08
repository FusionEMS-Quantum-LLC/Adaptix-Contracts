"""SignalCore event/signal contracts shared across Adaptix services.

Canonical event envelope, trigger definition, and delivery-status enum for the
AdaptixCore SignalCore shared service (the platform signal/event fan-out layer).

``source_entity_id`` is typed as ``str`` because SignalCore references entities
from any domain service whose identifier type varies (UUID, claim key, etc.),
matching the platform convention used by ``AuditEntry.entity_id``.
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


class EventDeliveryStatus(str, Enum):
    """Delivery state of a SignalCore event to a subscriber."""

    PENDING = "pending"
    DELIVERED = "delivered"
    ACKNOWLEDGED = "acknowledged"
    RETRYING = "retrying"
    FAILED = "failed"
    DEAD_LETTERED = "dead_lettered"


# ---------------------------------------------------------------------------
# Event Envelope
# ---------------------------------------------------------------------------


class SignalCoreEvent(BaseModel):
    """Canonical SignalCore event envelope emitted by a source service."""

    event_id: UUID
    tenant_id: UUID
    source_service: str = Field(..., min_length=1, max_length=64)
    source_entity_type: str = Field(..., min_length=1, max_length=120)
    source_entity_id: str = Field(..., min_length=1, max_length=255)
    event_type: str = Field(..., min_length=1, max_length=160)
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    schema_version: str = Field("1.0", max_length=16)
    occurred_at: datetime


# ---------------------------------------------------------------------------
# Trigger
# ---------------------------------------------------------------------------


class SignalCoreTrigger(BaseModel):
    """A rule that routes matching events to a downstream service action."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    event_type_pattern: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Exact or glob pattern matched against event_type.",
    )
    source_service: Optional[str] = Field(None, max_length=64)
    target_service: str = Field(..., min_length=1, max_length=64)
    target_action: str = Field(..., min_length=1, max_length=160)
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
