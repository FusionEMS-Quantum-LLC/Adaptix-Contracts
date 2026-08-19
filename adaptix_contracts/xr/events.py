"""Adaptix AR/XR Remote Physician Overwatch + Training — Signal Bus event contracts.

Play P04. Every event rides on :class:`adaptix_contracts.events.envelope.AdaptixEventEnvelope`
so tenant scope, correlation, idempotency, and payload versioning survive
across service boundaries the same way every other Adaptix domain event
does. Payload models below sit inside ``envelope.payload`` and are
validated by consumers using :meth:`AdaptixEventEnvelope.create`.

The canonical event names for Play P04 are:

* ``xr.session.started``       — a session transitions to ACTIVE.
* ``xr.session.ended``         — a session transitions to a terminal status
                                  (ENDED, FAILED, ABANDONED).
* ``xr.annotation.created``    — a remote physician places a new annotation.
* ``xr.recording.completed``   — a recording manifest reaches AVAILABLE.

Registering these constants here does NOT register them as live producers
in ``adaptix_contracts/events/registry.py`` — that registration requires a
citation of the actual publishing call in the xr-Service repository and is
out of scope for this contracts-only change.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from adaptix_contracts.events.envelope import AdaptixEventEnvelope
from adaptix_contracts.xr.enums import (
    AnnotationType,
    RecordingStatus,
    SessionStatus,
    SessionType,
    XrDevice,
)

# ---------------------------------------------------------------------------
# Event name constants
# ---------------------------------------------------------------------------

XR_SESSION_STARTED: Final[str] = "xr.session.started"
XR_SESSION_ENDED: Final[str] = "xr.session.ended"
XR_ANNOTATION_CREATED: Final[str] = "xr.annotation.created"
XR_RECORDING_COMPLETED: Final[str] = "xr.recording.completed"

XR_EVENTS: frozenset[str] = frozenset(
    {
        XR_SESSION_STARTED,
        XR_SESSION_ENDED,
        XR_ANNOTATION_CREATED,
        XR_RECORDING_COMPLETED,
    }
)

XR_SOURCE_SERVICE: Final[str] = "xr"
"""Service registry slug for the XR service that publishes these events."""


# ---------------------------------------------------------------------------
# Payload models (ride inside AdaptixEventEnvelope.payload)
# ---------------------------------------------------------------------------


class _XrEventPayload(BaseModel):
    """Base for every XR event payload.

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


class XrSessionStartedPayload(_XrEventPayload):
    """Payload for ``xr.session.started``."""

    session_id: UUID
    session_type: SessionType
    device: XrDevice
    status: SessionStatus = SessionStatus.ACTIVE
    field_provider_id: str
    remote_physician_id: str | None = None
    patient_id: str | None = None
    training_scenario_id: UUID | None = None
    linked_epcr_chart_id: str | None = None
    linked_cad_incident_id: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class XrSessionEndedPayload(_XrEventPayload):
    """Payload for ``xr.session.ended``."""

    session_id: UUID
    session_type: SessionType
    status: SessionStatus
    field_provider_id: str
    remote_physician_id: str | None = None
    patient_id: str | None = None
    ended_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_reason: str | None = None
    duration_seconds: float | None = Field(default=None, ge=0)
    recording_manifest_id: UUID | None = None
    annotation_count: int = Field(default=0, ge=0)


class XrAnnotationCreatedPayload(_XrEventPayload):
    """Payload for ``xr.annotation.created``."""

    annotation_id: UUID
    session_id: UUID
    annotation_type: AnnotationType
    created_by: str
    session_timestamp_ms: int = Field(..., ge=0)


class XrRecordingCompletedPayload(_XrEventPayload):
    """Payload for ``xr.recording.completed``."""

    recording_manifest_id: UUID
    session_id: UUID
    status: RecordingStatus = RecordingStatus.AVAILABLE
    storage_uri: str | None = None
    duration_seconds: float | None = Field(default=None, ge=0)
    size_bytes: int | None = Field(default=None, ge=0)
    content_hash: str | None = None
    consent_on_file: bool = False


# ---------------------------------------------------------------------------
# Envelope factories — one per canonical event
# ---------------------------------------------------------------------------


def _envelope(
    event_type: str,
    payload_model: _XrEventPayload,
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


def build_xr_session_started_event(
    payload: XrSessionStartedPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    source_service: str = XR_SOURCE_SERVICE,
) -> AdaptixEventEnvelope:
    """Build a Signal-Bus-ready envelope for ``xr.session.started``."""

    return _envelope(
        XR_SESSION_STARTED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=idempotency_key or f"xr.session.started:{payload.session_id}",
        source_service=source_service,
    )


def build_xr_session_ended_event(
    payload: XrSessionEndedPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    source_service: str = XR_SOURCE_SERVICE,
) -> AdaptixEventEnvelope:
    """Build a Signal-Bus-ready envelope for ``xr.session.ended``."""

    return _envelope(
        XR_SESSION_ENDED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=idempotency_key or f"xr.session.ended:{payload.session_id}",
        source_service=source_service,
    )


def build_xr_annotation_created_event(
    payload: XrAnnotationCreatedPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    source_service: str = XR_SOURCE_SERVICE,
) -> AdaptixEventEnvelope:
    """Build a Signal-Bus-ready envelope for ``xr.annotation.created``."""

    return _envelope(
        XR_ANNOTATION_CREATED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=(
            idempotency_key or f"xr.annotation.created:{payload.annotation_id}"
        ),
        source_service=source_service,
    )


def build_xr_recording_completed_event(
    payload: XrRecordingCompletedPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    source_service: str = XR_SOURCE_SERVICE,
) -> AdaptixEventEnvelope:
    """Build a Signal-Bus-ready envelope for ``xr.recording.completed``."""

    return _envelope(
        XR_RECORDING_COMPLETED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=(
            idempotency_key or f"xr.recording.completed:{payload.recording_manifest_id}"
        ),
        source_service=source_service,
    )


__all__ = [
    "XR_ANNOTATION_CREATED",
    "XR_EVENTS",
    "XR_RECORDING_COMPLETED",
    "XR_SESSION_ENDED",
    "XR_SESSION_STARTED",
    "XR_SOURCE_SERVICE",
    "XrAnnotationCreatedPayload",
    "XrRecordingCompletedPayload",
    "XrSessionEndedPayload",
    "XrSessionStartedPayload",
    "build_xr_annotation_created_event",
    "build_xr_recording_completed_event",
    "build_xr_session_ended_event",
    "build_xr_session_started_event",
]
