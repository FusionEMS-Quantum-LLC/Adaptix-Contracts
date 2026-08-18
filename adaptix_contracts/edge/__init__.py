"""Adaptix Edge apparatus compute node contracts (Play P23).

Public surface for the Adaptix Edge Service. Nothing in this package
runs Edge behaviour — it defines the models, enums, events, and error
types that Adaptix services and clients share when talking about Edge
nodes, deployments, CRDT sync, and bonded uplinks.

Import from the subpackage root, not the leaf modules::

    from adaptix_contracts.edge import EdgeNode, EDGE_HEARTBEAT
"""

from adaptix_contracts.edge.enums import (
    EdgeDeploymentStatus,
    EdgeHardware,
    EdgeNodeStatus,
    LinkQuality,
    UplinkChannel,
)
from adaptix_contracts.edge.errors import (
    EdgeCrdtConflictError,
    EdgeDeploymentError,
    EdgeError,
    EdgeErrorCode,
    EdgeErrorEnvelope,
    EdgeImageError,
    EdgeNodeNotFoundError,
    EdgeNodeStateError,
    EdgeRegistrationRejectedError,
    EdgeTenantMismatchError,
    EdgeUplinkError,
)
from adaptix_contracts.edge.events import (
    EDGE_CRDT_SYNCED,
    EDGE_EVENTS,
    EDGE_HEARTBEAT,
    EDGE_MODEL_DEPLOYED,
    EDGE_REGISTERED,
    EDGE_UPLINK_STATUS,
    EdgeCrdtSyncedEvent,
    EdgeHeartbeatEvent,
    EdgeModelDeployedEvent,
    EdgeRegisteredEvent,
    EdgeUplinkStatusEvent,
)
from adaptix_contracts.edge.models import (
    BondedLinkChannelStatus,
    BondedLinkStatus,
    CrdtSyncCheckpoint,
    EdgeImage,
    EdgeModelDeployment,
    EdgeNode,
)

__all__ = [
    "BondedLinkChannelStatus",
    "BondedLinkStatus",
    "CrdtSyncCheckpoint",
    "EDGE_CRDT_SYNCED",
    "EDGE_EVENTS",
    "EDGE_HEARTBEAT",
    "EDGE_MODEL_DEPLOYED",
    "EDGE_REGISTERED",
    "EDGE_UPLINK_STATUS",
    "EdgeCrdtConflictError",
    "EdgeCrdtSyncedEvent",
    "EdgeDeploymentError",
    "EdgeDeploymentStatus",
    "EdgeError",
    "EdgeErrorCode",
    "EdgeErrorEnvelope",
    "EdgeHardware",
    "EdgeHeartbeatEvent",
    "EdgeImage",
    "EdgeImageError",
    "EdgeModelDeployedEvent",
    "EdgeModelDeployment",
    "EdgeNode",
    "EdgeNodeNotFoundError",
    "EdgeNodeStateError",
    "EdgeNodeStatus",
    "EdgeRegisteredEvent",
    "EdgeRegistrationRejectedError",
    "EdgeTenantMismatchError",
    "EdgeUplinkError",
    "EdgeUplinkStatusEvent",
    "LinkQuality",
    "UplinkChannel",
]
