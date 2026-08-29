"""
Adaptix Event Envelope Contract
=================================
All events published across Adaptix services MUST use this envelope.
Every event must include tenant, actor, correlation, timestamp, idempotency, and version metadata.
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field
import uuid
from datetime import datetime, timezone


class AdaptixEventEnvelope(BaseModel):
    """
    Canonical event envelope for ALL Adaptix domain events.

    Rules:
    - event_id must be unique per event instance
    - idempotency_key must be stable for retry scenarios
    - tenant_id must always be set for tenant-scoped events
    - event_version must be incremented on breaking payload changes
    """

    event_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique event instance ID",
    )
    event_type: str = Field(..., description="Canonical event type name from registry")
    event_version: str = Field(default="1.0", description="Payload schema version")
    tenant_id: str = Field(
        ..., description="Tenant scope — required for all tenant events"
    )
    actor_id: str | None = Field(
        default=None, description="User or service that caused this event"
    )
    source_service: str = Field(..., description="Service that published this event")
    correlation_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Correlation ID for tracing across services",
    )
    causation_id: str | None = Field(
        default=None, description="ID of the event or request that caused this event"
    )
    idempotency_key: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Stable key for idempotent processing — set explicitly for retries",
    )
    occurred_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp when event occurred",
    )
    payload_schema: str = Field(
        default="adaptix/v1", description="Schema namespace for payload validation"
    )
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Event-specific payload data"
    )
    metadata: Optional[dict[str, Any]] = Field(
        default=None,
        description="Optional additional metadata (routing hints, flags, etc.)",
    )

    @classmethod
    def create(
        cls,
        event_type: str,
        tenant_id: str,
        source_service: str,
        payload: dict[str, Any],
        actor_id: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        idempotency_key: str | None = None,
        event_version: str = "1.0",
    ) -> "AdaptixEventEnvelope":
        """Factory method for creating a properly formed event."""
        return cls(
            event_type=event_type,
            event_version=event_version,
            tenant_id=tenant_id,
            actor_id=actor_id,
            source_service=source_service,
            correlation_id=correlation_id or str(uuid.uuid4()),
            causation_id=causation_id,
            idempotency_key=idempotency_key or str(uuid.uuid4()),
            payload=payload,
        )
