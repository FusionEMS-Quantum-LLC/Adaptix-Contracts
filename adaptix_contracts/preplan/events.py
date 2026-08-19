"""NFPA 1620 Pre-Incident Planning — Signal Bus event contracts.

Play P07. Every event rides on :class:`adaptix_contracts.events.envelope.AdaptixEventEnvelope`
so tenant scope, correlation, idempotency, and payload versioning survive
across service boundaries the same way every other Adaptix domain event
does. Payload models below sit inside ``envelope.payload`` and are
validated by consumers using :meth:`AdaptixEventEnvelope.create`.

The canonical event names for the Preplan service:

* ``preplan.occupancy.registered``  — an occupancy is added to the
                                       preplanning inventory.
* ``preplan.published``             — a preplan revision is approved and
                                       becomes the active version.
* ``preplan.hazard.recorded``       — a hazard is added/updated on a plan.
* ``preplan.floor_plan.added``      — a floor plan diagram is attached to
                                       a preplan revision.
* ``preplan.readiness_changed``     — a plan's ``ready_for_response``
                                       derived flag flips (e.g. Knox Box
                                       goes missing/inoperable), so
                                       dispatch/CAD context enrichment and
                                       mobile field reference can react.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from adaptix_contracts.events.envelope import AdaptixEventEnvelope
from adaptix_contracts.preplan.enums import HazardClass, KnoxKeyStatus, OccupancyType

# ---------------------------------------------------------------------------
# Event name constants
# ---------------------------------------------------------------------------

PREPLAN_OCCUPANCY_REGISTERED: Final[str] = "preplan.occupancy.registered"
PREPLAN_PUBLISHED: Final[str] = "preplan.published"
PREPLAN_HAZARD_RECORDED: Final[str] = "preplan.hazard.recorded"
PREPLAN_FLOOR_PLAN_ADDED: Final[str] = "preplan.floor_plan.added"
PREPLAN_READINESS_CHANGED: Final[str] = "preplan.readiness_changed"

PREPLAN_EVENTS: frozenset[str] = frozenset(
    {
        PREPLAN_OCCUPANCY_REGISTERED,
        PREPLAN_PUBLISHED,
        PREPLAN_HAZARD_RECORDED,
        PREPLAN_FLOOR_PLAN_ADDED,
        PREPLAN_READINESS_CHANGED,
    }
)

PREPLAN_SOURCE_SERVICE: Final[str] = "preplan"
"""Service registry slug for the Preplan service that publishes these events."""


# ---------------------------------------------------------------------------
# Payload models (ride inside AdaptixEventEnvelope.payload)
# ---------------------------------------------------------------------------


class _PreplanEventPayload(BaseModel):
    """Base for every Preplan event payload.

    ``tenant_id`` is redundant with :attr:`AdaptixEventEnvelope.tenant_id`
    but is kept on the payload so a consumer that stores raw payloads
    (e.g. Reality projections, CAD context enrichment, analytics
    warehouse) still has tenant scope in a single row without re-joining
    envelope columns.
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


class PreplanOccupancyRegisteredPayload(_PreplanEventPayload):
    """Payload for ``preplan.occupancy.registered``."""

    occupancy_id: UUID
    name: str
    occupancy_type: OccupancyType
    jurisdiction: str | None = None
    first_due_unit_ids: list[str] = Field(default_factory=list)


class PreplanPublishedPayload(_PreplanEventPayload):
    """Payload for ``preplan.published``."""

    preplan_id: UUID
    occupancy_id: UUID
    version: int
    ready_for_response: bool = False
    approved_by: str | None = None
    approved_at: datetime | None = None
    superseded_preplan_id: UUID | None = None


class PreplanHazardRecordedPayload(_PreplanEventPayload):
    """Payload for ``preplan.hazard.recorded``."""

    hazard_id: UUID
    preplan_id: UUID
    occupancy_id: UUID
    hazard_class: HazardClass
    active: bool = True


class PreplanFloorPlanAddedPayload(_PreplanEventPayload):
    """Payload for ``preplan.floor_plan.added``."""

    floor_plan_id: UUID
    preplan_id: UUID
    occupancy_id: UUID
    level_label: str
    artifact_object_key: str


class PreplanReadinessChangedPayload(_PreplanEventPayload):
    """Payload for ``preplan.readiness_changed``."""

    preplan_id: UUID
    occupancy_id: UUID
    previous_ready_for_response: bool
    ready_for_response: bool
    knox_key_status: KnoxKeyStatus | None = None
    reason: str | None = None


# ---------------------------------------------------------------------------
# Envelope factories — one per canonical event
# ---------------------------------------------------------------------------


def _envelope(
    event_type: str,
    payload_model: _PreplanEventPayload,
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


def build_preplan_occupancy_registered_event(
    payload: PreplanOccupancyRegisteredPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    source_service: str = PREPLAN_SOURCE_SERVICE,
) -> AdaptixEventEnvelope:
    """Build a Signal-Bus-ready envelope for ``preplan.occupancy.registered``."""

    return _envelope(
        PREPLAN_OCCUPANCY_REGISTERED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=(
            idempotency_key or f"preplan.occupancy.registered:{payload.occupancy_id}"
        ),
        source_service=source_service,
    )


def build_preplan_published_event(
    payload: PreplanPublishedPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    source_service: str = PREPLAN_SOURCE_SERVICE,
) -> AdaptixEventEnvelope:
    """Build a Signal-Bus-ready envelope for ``preplan.published``.

    ``idempotency_key`` includes the version so republishing the same
    revision does not double-fire downstream dispatch/CAD context
    enrichment.
    """

    return _envelope(
        PREPLAN_PUBLISHED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=(
            idempotency_key
            or f"preplan.published:{payload.preplan_id}:{payload.version}"
        ),
        source_service=source_service,
    )


def build_preplan_hazard_recorded_event(
    payload: PreplanHazardRecordedPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    source_service: str = PREPLAN_SOURCE_SERVICE,
) -> AdaptixEventEnvelope:
    """Build a Signal-Bus-ready envelope for ``preplan.hazard.recorded``."""

    return _envelope(
        PREPLAN_HAZARD_RECORDED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=(
            idempotency_key or f"preplan.hazard.recorded:{payload.hazard_id}"
        ),
        source_service=source_service,
    )


def build_preplan_floor_plan_added_event(
    payload: PreplanFloorPlanAddedPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    source_service: str = PREPLAN_SOURCE_SERVICE,
) -> AdaptixEventEnvelope:
    """Build a Signal-Bus-ready envelope for ``preplan.floor_plan.added``."""

    return _envelope(
        PREPLAN_FLOOR_PLAN_ADDED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=(
            idempotency_key or f"preplan.floor_plan.added:{payload.floor_plan_id}"
        ),
        source_service=source_service,
    )


def build_preplan_readiness_changed_event(
    payload: PreplanReadinessChangedPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    source_service: str = PREPLAN_SOURCE_SERVICE,
) -> AdaptixEventEnvelope:
    """Build a Signal-Bus-ready envelope for ``preplan.readiness_changed``."""

    return _envelope(
        PREPLAN_READINESS_CHANGED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=idempotency_key,
        source_service=source_service,
    )


__all__ = [
    "PREPLAN_EVENTS",
    "PREPLAN_FLOOR_PLAN_ADDED",
    "PREPLAN_HAZARD_RECORDED",
    "PREPLAN_OCCUPANCY_REGISTERED",
    "PREPLAN_PUBLISHED",
    "PREPLAN_READINESS_CHANGED",
    "PREPLAN_SOURCE_SERVICE",
    "PreplanFloorPlanAddedPayload",
    "PreplanHazardRecordedPayload",
    "PreplanOccupancyRegisteredPayload",
    "PreplanPublishedPayload",
    "PreplanReadinessChangedPayload",
    "build_preplan_floor_plan_added_event",
    "build_preplan_hazard_recorded_event",
    "build_preplan_occupancy_registered_event",
    "build_preplan_published_event",
    "build_preplan_readiness_changed_event",
]
