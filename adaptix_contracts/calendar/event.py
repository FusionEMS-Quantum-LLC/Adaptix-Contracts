"""Focused TransportLink and Workforce calendar event contracts."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AdaptixCalendarProduct(str, Enum):
    """Calendar product scopes allowed by the reduced implementation."""

    TRANSPORTLINK = "transportlink"
    WORKFORCE = "workforce"


class AdaptixCalendarEventStatus(str, Enum):
    """Lifecycle states shared by TransportLink and Workforce calendars."""

    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    LOCKED = "locked"


class AdaptixCalendarEvent(BaseModel):
    """Tenant-scoped event kernel contract for TransportLink and Workforce."""

    id: str
    tenant_id: str = Field(alias="tenantId")
    product: AdaptixCalendarProduct
    event_type: str = Field(alias="eventType", min_length=1)
    source_id: str = Field(alias="sourceId", min_length=1)
    source_type: str = Field(alias="sourceType", min_length=1)
    title: str = Field(min_length=1)
    start_at: datetime = Field(alias="startAt")
    end_at: datetime = Field(alias="endAt")
    timezone: str = Field(min_length=1)
    resource_ids: list[str] = Field(default_factory=list, alias="resourceIds")
    status: AdaptixCalendarEventStatus
    locked: bool = False
    version: int = Field(ge=1)
    actor_id: str | None = Field(default=None, alias="actorId")
    correlation_id: str | None = Field(default=None, alias="correlationId")
    idempotency_key: str | None = Field(default=None, alias="idempotencyKey")
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "populate_by_name": True,
        "validate_by_name": True,
        "validate_by_alias": True,
        "extra": "forbid",
    }
