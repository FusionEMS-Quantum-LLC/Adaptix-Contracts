"""Adaptix Community Paramedicine / MIH-CP — Signal Bus event contracts.

Play P31. Every event rides on :class:`adaptix_contracts.events.envelope.AdaptixEventEnvelope`
so tenant scope, correlation, idempotency, and payload versioning survive
across service boundaries the same way every other Adaptix domain event
does. Payload models below sit inside ``envelope.payload`` and are
validated by consumers using :meth:`AdaptixEventEnvelope.create`.

The four canonical event names Josh named in Play P31 are:

* ``mih.enrolled``            — a patient's enrollment reaches ENROLLED.
* ``mih.visit.scheduled``     — a visit is scheduled against an enrollment.
* ``mih.visit.completed``     — a visit's status becomes COMPLETED.
* ``mih.discharged``          — an enrollment transitions to DISCHARGED / a
                                terminal branch (declined, ineligible,
                                lost-to-followup, transferred).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from adaptix_contracts.events.envelope import AdaptixEventEnvelope
from adaptix_contracts.mih.enums import (
    EnrollmentStatus,
    MihOutcomeType,
    MihPayer,
    MihServiceType,
    MihVisitStatus,
)

# ---------------------------------------------------------------------------
# Event name constants
# ---------------------------------------------------------------------------

MIH_ENROLLED: Final[str] = "mih.enrolled"
MIH_VISIT_SCHEDULED: Final[str] = "mih.visit.scheduled"
MIH_VISIT_COMPLETED: Final[str] = "mih.visit.completed"
MIH_DISCHARGED: Final[str] = "mih.discharged"

MIH_EVENTS: frozenset[str] = frozenset(
    {
        MIH_ENROLLED,
        MIH_VISIT_SCHEDULED,
        MIH_VISIT_COMPLETED,
        MIH_DISCHARGED,
    }
)

MIH_SOURCE_SERVICE: Final[str] = "mih"
"""Service registry slug for the MIH-CP service that publishes these events."""


# ---------------------------------------------------------------------------
# Payload models (ride inside AdaptixEventEnvelope.payload)
# ---------------------------------------------------------------------------


class _MihEventPayload(BaseModel):
    """Base for every MIH event payload.

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


class MihEnrolledPayload(_MihEventPayload):
    """Payload for ``mih.enrolled``."""

    enrollment_id: UUID
    program_id: UUID
    patient_id: str
    payer: MihPayer
    status: EnrollmentStatus = EnrollmentStatus.ENROLLED
    assigned_paramedic_id: str | None = None
    assigned_care_coordinator_id: str | None = None
    referring_provider_npi: str | None = None
    linked_epcr_chart_ids: list[str] = Field(default_factory=list)
    linked_cad_incident_ids: list[str] = Field(default_factory=list)


class MihVisitScheduledPayload(_MihEventPayload):
    """Payload for ``mih.visit.scheduled``."""

    visit_id: UUID
    enrollment_id: UUID
    program_id: UUID
    service_plan_id: UUID | None = None
    service_types: list[MihServiceType] = Field(default_factory=list)
    scheduled_start_at: datetime
    scheduled_end_at: datetime | None = None
    telehealth: bool = False
    assigned_staff_ids: list[str] = Field(default_factory=list)
    primary_paramedic_id: str | None = None


class MihVisitCompletedPayload(_MihEventPayload):
    """Payload for ``mih.visit.completed``."""

    visit_id: UUID
    enrollment_id: UUID
    program_id: UUID
    service_plan_id: UUID | None = None
    status: MihVisitStatus = MihVisitStatus.COMPLETED
    service_types: list[MihServiceType] = Field(default_factory=list)
    interventions_delivered: list[MihServiceType] = Field(default_factory=list)
    actual_start_at: datetime | None = None
    actual_end_at: datetime | None = None
    billable: bool = True
    billing_snapshot_id: str | None = None
    linked_epcr_chart_id: str | None = None
    linked_cad_incident_id: str | None = None
    escalation_to_911: bool = False
    escalation_to_911_reason: str | None = None


class MihDischargedPayload(_MihEventPayload):
    """Payload for ``mih.discharged``."""

    enrollment_id: UUID
    program_id: UUID
    patient_id: str
    payer: MihPayer
    final_status: EnrollmentStatus
    outcome_id: UUID | None = None
    outcome_type: MihOutcomeType | None = None
    discharged_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    discharge_reason: str | None = None
    total_visit_count: int = Field(default=0, ge=0)
    total_billable_visit_count: int = Field(default=0, ge=0)


# ---------------------------------------------------------------------------
# Envelope factories — one per canonical event
# ---------------------------------------------------------------------------


def _envelope(
    event_type: str,
    payload_model: _MihEventPayload,
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


def build_mih_enrolled_event(
    payload: MihEnrolledPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    source_service: str = MIH_SOURCE_SERVICE,
) -> AdaptixEventEnvelope:
    """Build a Signal-Bus-ready envelope for ``mih.enrolled``.

    ``idempotency_key`` SHOULD be the enrollment id when a service wants
    "enroll this patient exactly once" semantics on retries.
    """

    return _envelope(
        MIH_ENROLLED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=idempotency_key or f"mih.enrolled:{payload.enrollment_id}",
        source_service=source_service,
    )


def build_mih_visit_scheduled_event(
    payload: MihVisitScheduledPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    source_service: str = MIH_SOURCE_SERVICE,
) -> AdaptixEventEnvelope:
    """Build a Signal-Bus-ready envelope for ``mih.visit.scheduled``."""

    return _envelope(
        MIH_VISIT_SCHEDULED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=(
            idempotency_key or f"mih.visit.scheduled:{payload.visit_id}"
        ),
        source_service=source_service,
    )


def build_mih_visit_completed_event(
    payload: MihVisitCompletedPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    source_service: str = MIH_SOURCE_SERVICE,
) -> AdaptixEventEnvelope:
    """Build a Signal-Bus-ready envelope for ``mih.visit.completed``."""

    return _envelope(
        MIH_VISIT_COMPLETED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=(
            idempotency_key or f"mih.visit.completed:{payload.visit_id}"
        ),
        source_service=source_service,
    )


def build_mih_discharged_event(
    payload: MihDischargedPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    source_service: str = MIH_SOURCE_SERVICE,
) -> AdaptixEventEnvelope:
    """Build a Signal-Bus-ready envelope for ``mih.discharged``."""

    return _envelope(
        MIH_DISCHARGED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=(
            idempotency_key or f"mih.discharged:{payload.enrollment_id}"
        ),
        source_service=source_service,
    )


__all__ = [
    "MIH_DISCHARGED",
    "MIH_ENROLLED",
    "MIH_EVENTS",
    "MIH_SOURCE_SERVICE",
    "MIH_VISIT_COMPLETED",
    "MIH_VISIT_SCHEDULED",
    "MihDischargedPayload",
    "MihEnrolledPayload",
    "MihVisitCompletedPayload",
    "MihVisitScheduledPayload",
    "build_mih_discharged_event",
    "build_mih_enrolled_event",
    "build_mih_visit_completed_event",
    "build_mih_visit_scheduled_event",
]
