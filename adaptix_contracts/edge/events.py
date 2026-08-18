"""Signal Bus event contracts for the Adaptix Edge apparatus compute node service.

Two things live in this module:

* the canonical event-type STRINGS an Edge producer stamps on the
  :class:`adaptix_contracts.event_contracts.EventSchema` envelope
  (``EDGE_REGISTERED`` and friends, plus the :data:`EDGE_EVENTS` set), and
* the typed Pydantic PAYLOAD contracts a consumer can validate against
  (``EdgeRegisteredEvent`` and friends).

Both are exported so a producer can import the string, a consumer can
import the payload contract, and a test can check membership in
:data:`EDGE_EVENTS`.

Registration in the central ``adaptix_contracts.events.registry``
allow-list is intentionally NOT done here. That registry requires a live
producer file:line citation (see
``tests/test_event_producer_registry_drift.py``); Play P23's Adaptix Edge
Service does not yet publish these events in production, so registering
them centrally would either fail the drift guard or need a fabricated
citation. When the live Edge producer lands, its shipping session must
add the citations and the ``EDGE_SERVICE`` slug to
``adaptix_contracts.schemas.service_registry`` in the same change.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from pydantic import BaseModel, Field

from adaptix_contracts.edge.enums import (
    EdgeDeploymentStatus,
    EdgeNodeStatus,
    LinkQuality,
    UplinkChannel,
)
from adaptix_contracts.edge.models import (
    BondedLinkChannelStatus,
    CrdtSyncCheckpoint,
    EdgeModelDeployment,
    EdgeNode,
)

EDGE_REGISTERED: Final[str] = "edge.registered"
EDGE_HEARTBEAT: Final[str] = "edge.heartbeat"
EDGE_MODEL_DEPLOYED: Final[str] = "edge.model.deployed"
EDGE_CRDT_SYNCED: Final[str] = "edge.crdt.synced"
EDGE_UPLINK_STATUS: Final[str] = "edge.uplink.status"

EDGE_EVENTS: Final[frozenset[str]] = frozenset(
    {
        EDGE_REGISTERED,
        EDGE_HEARTBEAT,
        EDGE_MODEL_DEPLOYED,
        EDGE_CRDT_SYNCED,
        EDGE_UPLINK_STATUS,
    }
)


class _EdgeEventBase(BaseModel):
    """Base envelope shape shared by every Edge Signal Bus event payload.

    Mirrors the ``tenant_id`` / ``correlation_id`` / ``occurred_at``
    fields the Adaptix envelope uses across other domains (see e.g.
    :class:`adaptix_contracts.schemas.fire_contracts.FireIncidentCreatedEvent`),
    so an Edge event round-trips through the Signal Bus without a
    per-domain shim. ``event_type`` is a literal on each subclass — that
    keeps the string a producer stamps and the contract a consumer
    validates against in one place.
    """

    tenant_id: str
    correlation_id: str
    occurred_at: datetime


class EdgeRegisteredEvent(_EdgeEventBase):
    """Published when an Edge node completes first-time registration.

    Carries the full :class:`EdgeNode` snapshot so downstream consumers
    (fleet, inventory, observability) do not have to make a follow-up
    read against Edge-Service just to render the new node.
    """

    event_type: str = EDGE_REGISTERED
    node: EdgeNode


class EdgeHeartbeatEvent(_EdgeEventBase):
    """Published on each Edge node heartbeat that changes reported state.

    Not a fixed-cadence event — the Edge worker filters steady-state
    heartbeats out and only emits when ``status``, primary uplink, or
    aggregate quality changes.
    """

    event_type: str = EDGE_HEARTBEAT

    node_id: str
    status: EdgeNodeStatus
    primary_uplink: UplinkChannel | None = None
    aggregate_quality: LinkQuality = LinkQuality.DOWN
    agent_version: str | None = None
    uptime_seconds: int | None = Field(default=None, ge=0)
    status_reason: str | None = None


class EdgeModelDeployedEvent(_EdgeEventBase):
    """Published when an Edge model deployment reaches a terminal state.

    ``deployment`` carries the full state at the terminal transition so
    the receiver can decide whether to promote, alert, or rollback
    without a follow-up read.
    """

    event_type: str = EDGE_MODEL_DEPLOYED

    deployment: EdgeModelDeployment
    previous_status: EdgeDeploymentStatus | None = None


class EdgeCrdtSyncedEvent(_EdgeEventBase):
    """Published when an Edge CRDT dataset finishes a sync round.

    Emitted per (node, dataset) so a consumer scoped to one dataset (for
    example the ePCR draft reconciler) can subscribe narrowly without
    seeing unrelated Edge sync traffic.
    """

    event_type: str = EDGE_CRDT_SYNCED

    checkpoint: CrdtSyncCheckpoint
    dataset: str


class EdgeUplinkStatusEvent(_EdgeEventBase):
    """Published when an Edge node's bonded uplink state changes.

    Change-driven, not cadence-driven — see
    :class:`adaptix_contracts.edge.models.BondedLinkStatus`.
    """

    event_type: str = EDGE_UPLINK_STATUS

    node_id: str
    aggregate_quality: LinkQuality
    primary_channel: UplinkChannel | None = None
    channels: list[BondedLinkChannelStatus] = Field(default_factory=list)
    on_scene: bool = False
    reason: str | None = None


__all__ = [
    "EDGE_CRDT_SYNCED",
    "EDGE_EVENTS",
    "EDGE_HEARTBEAT",
    "EDGE_MODEL_DEPLOYED",
    "EDGE_REGISTERED",
    "EDGE_UPLINK_STATUS",
    "EdgeCrdtSyncedEvent",
    "EdgeHeartbeatEvent",
    "EdgeModelDeployedEvent",
    "EdgeRegisteredEvent",
    "EdgeUplinkStatusEvent",
]
