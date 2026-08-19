"""Adaptix TEFCA QHIN Sub-Participant — Signal Bus event contracts.

Play P26. Every event rides on :class:`adaptix_contracts.events.envelope.AdaptixEventEnvelope`
so tenant scope, correlation, idempotency, and payload versioning survive
across service boundaries the same way every other Adaptix domain event
does. Payload models below sit inside ``envelope.payload`` and are
validated by consumers using :meth:`AdaptixEventEnvelope.create`.

Canonical event names:

* ``qhin.transaction.started``    — a QHIN exchange transaction begins.
* ``qhin.transaction.completed``  — a QHIN exchange transaction reaches a
                                     terminal status (completed or failed).
* ``qhin.bundle.received``        — an inbound FHIR bundle is resolved for
                                     a patient via a QHIN query.
* ``qhin.bundle.published``       — an outbound FHIR bundle is transmitted
                                     to a QHIN.
* ``qhin.acknowledgment.received`` — a QHIN acknowledges a transaction.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from adaptix_contracts.events.envelope import AdaptixEventEnvelope
from adaptix_contracts.qhin.enums import FhirVersion, Qhin, QhinPurpose

# ---------------------------------------------------------------------------
# Event name constants
# ---------------------------------------------------------------------------

QHIN_TRANSACTION_STARTED: Final[str] = "qhin.transaction.started"
QHIN_TRANSACTION_COMPLETED: Final[str] = "qhin.transaction.completed"
QHIN_BUNDLE_RECEIVED: Final[str] = "qhin.bundle.received"
QHIN_BUNDLE_PUBLISHED: Final[str] = "qhin.bundle.published"
QHIN_ACKNOWLEDGMENT_RECEIVED: Final[str] = "qhin.acknowledgment.received"

QHIN_EVENTS: frozenset[str] = frozenset(
    {
        QHIN_TRANSACTION_STARTED,
        QHIN_TRANSACTION_COMPLETED,
        QHIN_BUNDLE_RECEIVED,
        QHIN_BUNDLE_PUBLISHED,
        QHIN_ACKNOWLEDGMENT_RECEIVED,
    }
)

QHIN_SOURCE_SERVICE: Final[str] = "qhin"
"""Service registry slug for the QHIN-Service that publishes these events."""


# ---------------------------------------------------------------------------
# Payload models (ride inside AdaptixEventEnvelope.payload)
# ---------------------------------------------------------------------------


class _QhinEventPayload(BaseModel):
    """Base for every QHIN event payload.

    ``tenant_id`` is redundant with :attr:`AdaptixEventEnvelope.tenant_id`
    but is kept on the payload so a consumer that stores raw payloads (e.g.
    Reality projections, analytics warehouse) still has tenant scope in a
    single row without re-joining envelope columns.
    """

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


class QhinTransactionStartedPayload(_QhinEventPayload):
    """Payload for ``qhin.transaction.started``."""

    transaction_id: UUID
    credential_id: UUID
    qhin: Qhin
    fhir_version: FhirVersion = FhirVersion.R4
    purpose: QhinPurpose
    patient_id: str | None = None
    direction: str
    interaction: str


class QhinTransactionCompletedPayload(_QhinEventPayload):
    """Payload for ``qhin.transaction.completed``."""

    transaction_id: UUID
    credential_id: UUID
    qhin: Qhin
    purpose: QhinPurpose
    patient_id: str | None = None
    direction: str
    interaction: str
    status: str
    http_status: int | None = None
    error_detail: str | None = None
    retry_count: int = Field(default=0, ge=0)


class QhinBundleReceivedPayload(_QhinEventPayload):
    """Payload for ``qhin.bundle.received``."""

    bundle_id: UUID
    transaction_id: UUID
    qhin: Qhin
    fhir_version: FhirVersion = FhirVersion.R4
    patient_id: str
    resource_types: list[str] = Field(default_factory=list)
    resource_count: int = Field(default=0, ge=0)


class QhinBundlePublishedPayload(_QhinEventPayload):
    """Payload for ``qhin.bundle.published``."""

    bundle_id: UUID
    transaction_id: UUID
    qhin: Qhin
    fhir_version: FhirVersion = FhirVersion.R4
    patient_id: str
    purpose: QhinPurpose
    resource_types: list[str] = Field(default_factory=list)
    resource_count: int = Field(default=0, ge=0)
    sent_at: datetime | None = None


class QhinAcknowledgmentReceivedPayload(_QhinEventPayload):
    """Payload for ``qhin.acknowledgment.received``."""

    acknowledgment_id: UUID
    transaction_id: UUID
    qhin: Qhin
    accepted: bool
    ack_code: str | None = None
    message: str | None = None


# ---------------------------------------------------------------------------
# Envelope factories — one per canonical event
# ---------------------------------------------------------------------------


def _envelope(
    event_type: str,
    payload_model: _QhinEventPayload,
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


def build_qhin_transaction_started_event(
    payload: QhinTransactionStartedPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    source_service: str = QHIN_SOURCE_SERVICE,
) -> AdaptixEventEnvelope:
    """Build a Signal-Bus-ready envelope for ``qhin.transaction.started``."""

    return _envelope(
        QHIN_TRANSACTION_STARTED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=(
            idempotency_key or f"qhin.transaction.started:{payload.transaction_id}"
        ),
        source_service=source_service,
    )


def build_qhin_transaction_completed_event(
    payload: QhinTransactionCompletedPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    source_service: str = QHIN_SOURCE_SERVICE,
) -> AdaptixEventEnvelope:
    """Build a Signal-Bus-ready envelope for ``qhin.transaction.completed``."""

    return _envelope(
        QHIN_TRANSACTION_COMPLETED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=(
            idempotency_key or f"qhin.transaction.completed:{payload.transaction_id}"
        ),
        source_service=source_service,
    )


def build_qhin_bundle_received_event(
    payload: QhinBundleReceivedPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    source_service: str = QHIN_SOURCE_SERVICE,
) -> AdaptixEventEnvelope:
    """Build a Signal-Bus-ready envelope for ``qhin.bundle.received``."""

    return _envelope(
        QHIN_BUNDLE_RECEIVED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=(
            idempotency_key or f"qhin.bundle.received:{payload.bundle_id}"
        ),
        source_service=source_service,
    )


def build_qhin_bundle_published_event(
    payload: QhinBundlePublishedPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    source_service: str = QHIN_SOURCE_SERVICE,
) -> AdaptixEventEnvelope:
    """Build a Signal-Bus-ready envelope for ``qhin.bundle.published``."""

    return _envelope(
        QHIN_BUNDLE_PUBLISHED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=(
            idempotency_key or f"qhin.bundle.published:{payload.bundle_id}"
        ),
        source_service=source_service,
    )


def build_qhin_acknowledgment_received_event(
    payload: QhinAcknowledgmentReceivedPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    source_service: str = QHIN_SOURCE_SERVICE,
) -> AdaptixEventEnvelope:
    """Build a Signal-Bus-ready envelope for ``qhin.acknowledgment.received``."""

    return _envelope(
        QHIN_ACKNOWLEDGMENT_RECEIVED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=(
            idempotency_key
            or f"qhin.acknowledgment.received:{payload.acknowledgment_id}"
        ),
        source_service=source_service,
    )


__all__ = [
    "QHIN_ACKNOWLEDGMENT_RECEIVED",
    "QHIN_BUNDLE_PUBLISHED",
    "QHIN_BUNDLE_RECEIVED",
    "QHIN_EVENTS",
    "QHIN_SOURCE_SERVICE",
    "QHIN_TRANSACTION_COMPLETED",
    "QHIN_TRANSACTION_STARTED",
    "QhinAcknowledgmentReceivedPayload",
    "QhinBundlePublishedPayload",
    "QhinBundleReceivedPayload",
    "QhinTransactionCompletedPayload",
    "QhinTransactionStartedPayload",
    "build_qhin_acknowledgment_received_event",
    "build_qhin_bundle_published_event",
    "build_qhin_bundle_received_event",
    "build_qhin_transaction_completed_event",
    "build_qhin_transaction_started_event",
]
