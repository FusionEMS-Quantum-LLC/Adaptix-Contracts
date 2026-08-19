"""Adaptix Hydrant Registry — Signal Bus event contracts.

Play P07. Every event rides on :class:`adaptix_contracts.events.envelope.AdaptixEventEnvelope`
so tenant scope, correlation, idempotency, and payload versioning survive
across service boundaries the same way every other Adaptix domain event
does. Payload models below sit inside ``envelope.payload`` and are
validated by consumers using :meth:`AdaptixEventEnvelope.create`.

Canonical event names:

* ``hydrant.registered``       — a hydrant asset is added to the registry.
* ``hydrant.status_changed``   — a hydrant's operational status changes.
* ``hydrant.tested``           — a flow/pressure/inspection test is recorded
                                  (this is the PSI-history event).
* ``hydrant.maintenance_logged`` — a repair/maintenance action is recorded.

These event names are NOT registered in
``adaptix_contracts/events/registry.py`` — that registration requires a
live producer citation from the Hydrant-Service repository and is out of
scope for this contracts-only change.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from adaptix_contracts.events.envelope import AdaptixEventEnvelope
from adaptix_contracts.hydrant.enums import HydrantColor, HydrantStatus, TestType

# ---------------------------------------------------------------------------
# Event name constants
# ---------------------------------------------------------------------------

HYDRANT_REGISTERED: Final[str] = "hydrant.registered"
HYDRANT_STATUS_CHANGED: Final[str] = "hydrant.status_changed"
HYDRANT_TESTED: Final[str] = "hydrant.tested"
HYDRANT_MAINTENANCE_LOGGED: Final[str] = "hydrant.maintenance_logged"

HYDRANT_EVENTS: frozenset[str] = frozenset(
    {
        HYDRANT_REGISTERED,
        HYDRANT_STATUS_CHANGED,
        HYDRANT_TESTED,
        HYDRANT_MAINTENANCE_LOGGED,
    }
)

HYDRANT_SOURCE_SERVICE: Final[str] = "hydrant"
"""Service registry slug for the Hydrant-Service that publishes these events."""


# ---------------------------------------------------------------------------
# Payload models (ride inside AdaptixEventEnvelope.payload)
# ---------------------------------------------------------------------------


class _HydrantEventPayload(BaseModel):
    """Base for every Hydrant event payload.

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


class HydrantRegisteredPayload(_HydrantEventPayload):
    """Payload for ``hydrant.registered``."""

    hydrant_id: UUID
    asset_tag: str
    status: HydrantStatus = HydrantStatus.IN_SERVICE
    color: HydrantColor | None = None
    latitude: float | None = None
    longitude: float | None = None
    hydrant_district: str | None = None
    response_district: str | None = None


class HydrantStatusChangedPayload(_HydrantEventPayload):
    """Payload for ``hydrant.status_changed``."""

    hydrant_id: UUID
    previous_status: HydrantStatus
    new_status: HydrantStatus
    out_of_service_reason: str | None = None
    changed_by: str | None = None


class HydrantTestedPayload(_HydrantEventPayload):
    """Payload for ``hydrant.tested`` — the PSI-history event."""

    hydrant_test_id: UUID
    hydrant_id: UUID
    test_type: TestType
    tested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    static_pressure_psi: int | None = None
    residual_pressure_psi: int | None = None
    pitot_pressure_psi: int | None = None
    flow_gpm: int | None = None
    calculated_flow_at_20_psi_gpm: int | None = None
    pass_fail: bool | None = None
    resulting_color: HydrantColor | None = None
    tested_by: str | None = None
    deficiencies_found: list[str] = Field(default_factory=list)


class HydrantMaintenanceLoggedPayload(_HydrantEventPayload):
    """Payload for ``hydrant.maintenance_logged``."""

    hydrant_maintenance_id: UUID
    hydrant_id: UUID
    description: str
    performed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    performed_by: str | None = None
    status_before: HydrantStatus | None = None
    status_after: HydrantStatus | None = None
    follow_up_required: bool = False


# ---------------------------------------------------------------------------
# Envelope factories — one per canonical event
# ---------------------------------------------------------------------------


def _envelope(
    event_type: str,
    payload_model: _HydrantEventPayload,
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


def build_hydrant_registered_event(
    payload: HydrantRegisteredPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    source_service: str = HYDRANT_SOURCE_SERVICE,
) -> AdaptixEventEnvelope:
    """Build a Signal-Bus-ready envelope for ``hydrant.registered``."""

    return _envelope(
        HYDRANT_REGISTERED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=(idempotency_key or f"hydrant.registered:{payload.hydrant_id}"),
        source_service=source_service,
    )


def build_hydrant_status_changed_event(
    payload: HydrantStatusChangedPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    source_service: str = HYDRANT_SOURCE_SERVICE,
) -> AdaptixEventEnvelope:
    """Build a Signal-Bus-ready envelope for ``hydrant.status_changed``."""

    return _envelope(
        HYDRANT_STATUS_CHANGED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=idempotency_key,
        source_service=source_service,
    )


def build_hydrant_tested_event(
    payload: HydrantTestedPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    source_service: str = HYDRANT_SOURCE_SERVICE,
) -> AdaptixEventEnvelope:
    """Build a Signal-Bus-ready envelope for ``hydrant.tested``.

    ``idempotency_key`` SHOULD be the hydrant test id so a retried
    publish does not duplicate a PSI-history record downstream.
    """

    return _envelope(
        HYDRANT_TESTED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=(idempotency_key or f"hydrant.tested:{payload.hydrant_test_id}"),
        source_service=source_service,
    )


def build_hydrant_maintenance_logged_event(
    payload: HydrantMaintenanceLoggedPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    source_service: str = HYDRANT_SOURCE_SERVICE,
) -> AdaptixEventEnvelope:
    """Build a Signal-Bus-ready envelope for ``hydrant.maintenance_logged``."""

    return _envelope(
        HYDRANT_MAINTENANCE_LOGGED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=(
            idempotency_key or f"hydrant.maintenance_logged:{payload.hydrant_maintenance_id}"
        ),
        source_service=source_service,
    )


__all__ = [
    "HYDRANT_EVENTS",
    "HYDRANT_MAINTENANCE_LOGGED",
    "HYDRANT_REGISTERED",
    "HYDRANT_SOURCE_SERVICE",
    "HYDRANT_STATUS_CHANGED",
    "HYDRANT_TESTED",
    "HydrantMaintenanceLoggedPayload",
    "HydrantRegisteredPayload",
    "HydrantStatusChangedPayload",
    "HydrantTestedPayload",
    "build_hydrant_maintenance_logged_event",
    "build_hydrant_registered_event",
    "build_hydrant_status_changed_event",
    "build_hydrant_tested_event",
]
