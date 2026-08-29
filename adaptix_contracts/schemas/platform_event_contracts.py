"""Canonical platform-level event bus contracts.

Defines the AdaptixEventType enum and AdaptixPlatformEvent envelope used
by all Adaptix services when publishing to the shared event bus. Individual
domain events (CadCaseCreatedEvent, ClaimCreatedEvent, etc.) remain in their
own domain contract files; this module provides the top-level routing layer.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Event Type Registry
# ---------------------------------------------------------------------------


class AdaptixEventType(str, Enum):
    """Canonical event type identifiers for the Adaptix platform event bus.

    Naming convention: ``<domain>.<noun>.<past-verb>``
    """

    # Agency / Tenant lifecycle
    AGENCY_ACTIVATED = "agency.activated"
    AGENCY_SUSPENDED = "agency.suspended"

    # Payments
    PAYMENT_RECEIVED = "payment.received"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_REFUNDED = "payment.refunded"

    # EPCR / Charts
    CHART_SUBMITTED = "chart.submitted"
    CHART_APPROVED = "chart.approved"
    CHART_REJECTED = "chart.rejected"
    CHART_SIGNED = "chart.signed"

    # Dispatch
    DISPATCH_CREATED = "dispatch.created"
    DISPATCH_STATUS_UPDATED = "dispatch.status_updated"
    DISPATCH_CLOSED = "dispatch.closed"

    # Crew
    CREW_ASSIGNED = "crew.assigned"
    CREW_SHIFT_STARTED = "crew.shift_started"
    CREW_SHIFT_ENDED = "crew.shift_ended"

    # Support
    SUPPORT_TICKET_CREATED = "support_ticket.created"
    SUPPORT_TICKET_RESOLVED = "support_ticket.resolved"

    # Users
    USER_ACTIVATED = "user.activated"
    USER_DEACTIVATED = "user.deactivated"
    USER_INVITED = "user.invited"

    # Interoperability
    INTEROP_DATA_RECEIVED = "interop.data_received"
    INTEROP_EXPORT_COMPLETED = "interop.export_completed"

    # Social / Media (Founder OS)
    SOCIAL_POST_PUBLISHED = "social.post_published"
    VIDEO_RENDER_COMPLETED = "video.render_completed"

    # Narcotics (DEA compliance)
    NARCOTIC_ADMINISTERED = "narcotic.administered"
    NARCOTIC_DISCREPANCY_DETECTED = "narcotic.discrepancy_detected"

    # Billing
    CLAIM_CREATED = "claim.created"
    CLAIM_SUBMITTED = "claim.submitted"
    CLAIM_PAID = "claim.paid"
    CLAIM_DENIED = "claim.denied"

    # Search
    SEARCH_INDEX_UPDATED = "search.index_updated"


# ---------------------------------------------------------------------------
# Canonical Event Envelope
# ---------------------------------------------------------------------------


class AdaptixPlatformEvent(BaseModel):
    """Canonical event envelope for all Adaptix platform events.

    All services MUST wrap their domain payloads in this envelope when
    publishing to the shared event bus. The ``payload`` field carries
    the serialized domain event dict without embedded PHI values.
    """

    event_type: AdaptixEventType
    event_id: str = Field(..., description="UUID; unique per event emission")
    tenant_id: Optional[str] = Field(
        default=None,
        description="None only for platform-wide events (e.g. agency.activated)",
    )
    payload: dict[str, Any] = Field(
        ..., description="Serialized domain event payload. No raw PHI."
    )
    published_at: datetime
    source_service: str = Field(
        ...,
        description=(
            "Short service identifier: 'core', 'cad', 'billing', 'epcr', etc."
        ),
    )
    schema_version: str = Field(
        default="1.0",
        description="Schema version of the payload dict for forward-compatibility.",
    )


# ---------------------------------------------------------------------------
# WebSocket / Pulse Envelope
# ---------------------------------------------------------------------------


class PulseMessageType(str, Enum):
    """Message types for the /ws/pulse WebSocket channel."""

    DISPATCH_UPDATE = "dispatch_update"
    UNIT_GPS_PING = "unit_gps_ping"
    ALERT = "alert"
    HEARTBEAT = "heartbeat"
    METRIC_SNAPSHOT = "metric_snapshot"


class PulseMessage(BaseModel):
    """Envelope for messages pushed over the /ws/pulse WebSocket."""

    message_type: PulseMessageType
    tenant_id: Optional[str] = None
    payload: dict[str, Any]
    sent_at: datetime
