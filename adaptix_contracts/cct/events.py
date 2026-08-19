"""Critical Care Transport (CCT) — Signal Bus event contracts (Play P05).

Every event rides on :class:`adaptix_contracts.events.envelope.AdaptixEventEnvelope`
so tenant scope, correlation, idempotency, and payload versioning survive
across service boundaries the same way every other Adaptix domain event
does. Payload models below sit inside ``envelope.payload`` and are
validated by consumers using :meth:`AdaptixEventEnvelope.create`.

Event names follow the platform ``<domain>.<entity>.<action>`` convention
used in ``adaptix_contracts.crr.events`` and ``adaptix_contracts.mih.events``.

NOTE: These event name constants are exported for producer/consumer typing
convenience. Registering them as live Signal Bus topics in
``adaptix_contracts.events.registry`` requires a live producer citation from
the cct-Service repo and is intentionally NOT done here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from adaptix_contracts.cct.enums import CctType, CredentialLevel
from adaptix_contracts.events.envelope import AdaptixEventEnvelope

# ---------------------------------------------------------------------------
# Event name constants
# ---------------------------------------------------------------------------

CCT_MISSION_REQUESTED: Final[str] = "cct.mission.requested"
CCT_CREW_ASSIGNED: Final[str] = "cct.crew.assigned"
CCT_HANDOFF_COMPLETED: Final[str] = "cct.handoff.completed"
CCT_MISSION_COMPLETED: Final[str] = "cct.mission.completed"

CCT_EVENTS: frozenset[str] = frozenset(
    {
        CCT_MISSION_REQUESTED,
        CCT_CREW_ASSIGNED,
        CCT_HANDOFF_COMPLETED,
        CCT_MISSION_COMPLETED,
    }
)

CCT_SOURCE_SERVICE: Final[str] = "cct"
"""Service registry slug for the CCT service that publishes these events."""


# ---------------------------------------------------------------------------
# Payload models (ride inside AdaptixEventEnvelope.payload)
# ---------------------------------------------------------------------------


class _CctEventPayload(BaseModel):
    """Base for every CCT event payload.

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


class CctMissionRequestedPayload(_CctEventPayload):
    """Payload for ``cct.mission.requested``."""

    mission_id: UUID
    cct_type: CctType
    required_credential_level: CredentialLevel
    sending_facility_name: str
    sending_facility_id: str | None = None
    receiving_facility_name: str
    receiving_facility_id: str | None = None
    patient_id: str | None = None
    requested_at: datetime
    camts_reportable: bool = True


class CctCrewAssignedPayload(_CctEventPayload):
    """Payload for ``cct.crew.assigned``."""

    mission_id: UUID
    cct_type: CctType
    assigned_crew_user_ids: list[str] = Field(default_factory=list)
    assigned_crew_credential_levels: dict[str, CredentialLevel] = Field(default_factory=dict)
    loadout_id: str | None = None
    assigned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CctHandoffCompletedPayload(_CctEventPayload):
    """Payload for ``cct.handoff.completed``."""

    mission_id: UUID
    handoff_id: UUID
    sending_facility_report_at: datetime | None = None
    receiving_facility_accepted_at: datetime | None = None
    patient_condition_at_handoff: str | None = None
    equipment_returned: bool = False
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CctMissionCompletedPayload(_CctEventPayload):
    """Payload for ``cct.mission.completed``."""

    mission_id: UUID
    cct_type: CctType
    status: str = Field(default="completed")
    linked_epcr_chart_id: str | None = None
    linked_cad_incident_id: str | None = None
    camts_reportable: bool = True
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Envelope factories — one per canonical event
# ---------------------------------------------------------------------------


def _envelope(
    event_type: str,
    payload_model: _CctEventPayload,
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


def build_cct_mission_requested_event(
    payload: CctMissionRequestedPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    source_service: str = CCT_SOURCE_SERVICE,
) -> AdaptixEventEnvelope:
    """Build a Signal-Bus-ready envelope for ``cct.mission.requested``.

    ``idempotency_key`` SHOULD be the mission id when a service wants
    "request this mission exactly once" semantics on retries.
    """

    return _envelope(
        CCT_MISSION_REQUESTED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=idempotency_key or f"cct.mission.requested:{payload.mission_id}",
        source_service=source_service,
    )


def build_cct_crew_assigned_event(
    payload: CctCrewAssignedPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    source_service: str = CCT_SOURCE_SERVICE,
) -> AdaptixEventEnvelope:
    """Build a Signal-Bus-ready envelope for ``cct.crew.assigned``."""

    return _envelope(
        CCT_CREW_ASSIGNED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=(idempotency_key or f"cct.crew.assigned:{payload.mission_id}"),
        source_service=source_service,
    )


def build_cct_handoff_completed_event(
    payload: CctHandoffCompletedPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    source_service: str = CCT_SOURCE_SERVICE,
) -> AdaptixEventEnvelope:
    """Build a Signal-Bus-ready envelope for ``cct.handoff.completed``."""

    return _envelope(
        CCT_HANDOFF_COMPLETED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=(idempotency_key or f"cct.handoff.completed:{payload.handoff_id}"),
        source_service=source_service,
    )


def build_cct_mission_completed_event(
    payload: CctMissionCompletedPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    source_service: str = CCT_SOURCE_SERVICE,
) -> AdaptixEventEnvelope:
    """Build a Signal-Bus-ready envelope for ``cct.mission.completed``."""

    return _envelope(
        CCT_MISSION_COMPLETED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=(idempotency_key or f"cct.mission.completed:{payload.mission_id}"),
        source_service=source_service,
    )


__all__ = [
    "CCT_CREW_ASSIGNED",
    "CCT_EVENTS",
    "CCT_HANDOFF_COMPLETED",
    "CCT_MISSION_COMPLETED",
    "CCT_MISSION_REQUESTED",
    "CCT_SOURCE_SERVICE",
    "CctCrewAssignedPayload",
    "CctHandoffCompletedPayload",
    "CctMissionCompletedPayload",
    "CctMissionRequestedPayload",
    "build_cct_crew_assigned_event",
    "build_cct_handoff_completed_event",
    "build_cct_mission_completed_event",
    "build_cct_mission_requested_event",
]
