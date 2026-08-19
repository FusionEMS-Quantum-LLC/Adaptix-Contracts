"""Adaptix Family-Bridge — Signal Bus event contracts.

Play P24. Every event rides on
:class:`adaptix_contracts.events.envelope.AdaptixEventEnvelope` so tenant
scope, correlation, idempotency, and payload versioning survive across
service boundaries the same way every other Adaptix domain event does.

The four canonical events named in Play P24:

* ``bridge.thread.opened``   — a thread was opened after consent.
* ``bridge.sms.sent``        — an SMS left the Telephony gateway on a thread.
* ``bridge.status.updated``  — the thread moved to a new stage.
* ``bridge.thread.closed``   — the thread reached CLOSED.

PHI rule: payloads below never carry patient name, complaint text, vitals,
or the raw portal token. ``complaint_class`` is a coarse tone bucket only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from adaptix_contracts.events.envelope import AdaptixEventEnvelope
from adaptix_contracts.family_bridge.enums import (
    ConsentSource,
    SmsDeliveryStatus,
    ThreadCloseReason,
    ThreadStage,
)

# ---------------------------------------------------------------------------
# Event name constants
# ---------------------------------------------------------------------------

BRIDGE_THREAD_OPENED: Final[str] = "bridge.thread.opened"
BRIDGE_SMS_SENT: Final[str] = "bridge.sms.sent"
BRIDGE_STATUS_UPDATED: Final[str] = "bridge.status.updated"
BRIDGE_THREAD_CLOSED: Final[str] = "bridge.thread.closed"

FAMILY_BRIDGE_EVENTS: frozenset[str] = frozenset(
    {
        BRIDGE_THREAD_OPENED,
        BRIDGE_SMS_SENT,
        BRIDGE_STATUS_UPDATED,
        BRIDGE_THREAD_CLOSED,
    }
)

FAMILY_BRIDGE_SOURCE_SERVICE: Final[str] = "communications"
"""Service registry slug for the Communications-Service that publishes these events."""


# ---------------------------------------------------------------------------
# Payload models (ride inside AdaptixEventEnvelope.payload)
# ---------------------------------------------------------------------------


class _FamilyBridgeEventPayload(BaseModel):
    """Base for every Family-Bridge event payload."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    tenant_id: str = Field(..., description="Tenant scope.")
    correlation_id: str | None = Field(
        default=None,
        description="Correlation id for tracing (mirrors envelope.correlation_id).",
    )
    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the domain event occurred (may pre-date publish).",
    )
    thread_id: UUID


class BridgeThreadOpenedPayload(_FamilyBridgeEventPayload):
    """Payload for ``bridge.thread.opened``."""

    patient_id: str
    chart_id: str
    incident_id: str | None = None
    nok_contact_id: UUID
    consent_id: UUID
    consent_source: ConsentSource
    complaint_class: str | None = None
    destination_facility_id: str | None = None
    eta_at: datetime | None = None
    opened_by_actor_id: str | None = None


class BridgeSmsSentPayload(_FamilyBridgeEventPayload):
    """Payload for ``bridge.sms.sent``.

    Never carries the message body — only the fact that a message left the
    gateway, its delivery status, and the provider message id for
    reconciliation with Telnyx delivery receipts.
    """

    stage_at_send: ThreadStage
    provider: str = Field(default="telnyx")
    provider_message_id: str | None = None
    delivery_status: SmsDeliveryStatus = SmsDeliveryStatus.QUEUED
    to_phone_last4: str | None = Field(
        default=None,
        min_length=4,
        max_length=4,
        description="Last 4 digits only — for reconciliation, never full number.",
    )
    template_key: str | None = Field(
        default=None,
        description="Which Cortex-drafted wording template was used.",
    )


class BridgeStatusUpdatedPayload(_FamilyBridgeEventPayload):
    """Payload for ``bridge.status.updated``."""

    from_stage: ThreadStage | None = None
    to_stage: ThreadStage
    source_event_type: str | None = Field(
        default=None,
        description="Upstream event that caused this transition.",
    )
    source_event_id: str | None = None
    destination_facility_id: str | None = None
    eta_at: datetime | None = None
    sms_triggered: bool = False


class BridgeThreadClosedPayload(_FamilyBridgeEventPayload):
    """Payload for ``bridge.thread.closed``."""

    final_stage: ThreadStage = ThreadStage.CLOSED
    close_reason: ThreadCloseReason
    closed_by_actor_id: str | None = None
    total_sms_sent: int = Field(default=0, ge=0)
    total_portal_views: int = Field(default=0, ge=0)


# ---------------------------------------------------------------------------
# Envelope factories — one per canonical event
# ---------------------------------------------------------------------------


def _envelope(
    event_type: str,
    payload_model: _FamilyBridgeEventPayload,
    *,
    actor_id: str | None,
    causation_id: str | None,
    idempotency_key: str | None,
    source_service: str,
) -> AdaptixEventEnvelope:
    payload_dict: dict[str, Any] = payload_model.model_dump(mode="json")
    return AdaptixEventEnvelope.create(
        event_type=event_type,
        tenant_id=payload_model.tenant_id,
        source_service=source_service,
        payload=payload_dict,
        actor_id=actor_id,
        correlation_id=payload_model.correlation_id,
        causation_id=causation_id,
        idempotency_key=idempotency_key,
    )


def build_bridge_thread_opened_event(
    payload: BridgeThreadOpenedPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    source_service: str = FAMILY_BRIDGE_SOURCE_SERVICE,
) -> AdaptixEventEnvelope:
    """Build a Signal-Bus-ready envelope for ``bridge.thread.opened``.

    Idempotency defaults to the thread id so a retried open never produces
    a second thread.
    """

    return _envelope(
        BRIDGE_THREAD_OPENED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=idempotency_key or f"bridge.thread.opened:{payload.thread_id}",
        source_service=source_service,
    )


def build_bridge_sms_sent_event(
    payload: BridgeSmsSentPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    source_service: str = FAMILY_BRIDGE_SOURCE_SERVICE,
) -> AdaptixEventEnvelope:
    """Build a Signal-Bus-ready envelope for ``bridge.sms.sent``.

    Idempotency defaults to the provider message id when present (exactly
    once per Telnyx message), else thread id + stage.
    """

    key = idempotency_key or (
        f"bridge.sms.sent:{payload.provider_message_id}"
        if payload.provider_message_id
        else f"bridge.sms.sent:{payload.thread_id}:{payload.stage_at_send.value}"
    )
    return _envelope(
        BRIDGE_SMS_SENT,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=key,
        source_service=source_service,
    )


def build_bridge_status_updated_event(
    payload: BridgeStatusUpdatedPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    source_service: str = FAMILY_BRIDGE_SOURCE_SERVICE,
) -> AdaptixEventEnvelope:
    """Build a Signal-Bus-ready envelope for ``bridge.status.updated``.

    Idempotency defaults to thread id + target stage — the stage machine
    only moves forward, so a retry to the same stage is a no-op.
    """

    return _envelope(
        BRIDGE_STATUS_UPDATED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=(
            idempotency_key
            or f"bridge.status.updated:{payload.thread_id}:{payload.to_stage.value}"
        ),
        source_service=source_service,
    )


def build_bridge_thread_closed_event(
    payload: BridgeThreadClosedPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    source_service: str = FAMILY_BRIDGE_SOURCE_SERVICE,
) -> AdaptixEventEnvelope:
    """Build a Signal-Bus-ready envelope for ``bridge.thread.closed``."""

    return _envelope(
        BRIDGE_THREAD_CLOSED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=idempotency_key or f"bridge.thread.closed:{payload.thread_id}",
        source_service=source_service,
    )


__all__ = [
    "BRIDGE_SMS_SENT",
    "BRIDGE_STATUS_UPDATED",
    "BRIDGE_THREAD_CLOSED",
    "BRIDGE_THREAD_OPENED",
    "FAMILY_BRIDGE_EVENTS",
    "FAMILY_BRIDGE_SOURCE_SERVICE",
    "BridgeSmsSentPayload",
    "BridgeStatusUpdatedPayload",
    "BridgeThreadClosedPayload",
    "BridgeThreadOpenedPayload",
    "build_bridge_sms_sent_event",
    "build_bridge_status_updated_event",
    "build_bridge_thread_closed_event",
    "build_bridge_thread_opened_event",
]
