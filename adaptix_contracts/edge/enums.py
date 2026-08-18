"""Enums for the Adaptix Edge apparatus compute node service (Play P23).

Edge nodes are the compute devices that run on-apparatus (in-truck) for
Adaptix crews: AWS Snowcones, NVIDIA Jetson Orin NX modules, Lenovo SE30
edge servers, and other qualified hardware. Uplinks describe how each node
reaches the platform when the apparatus is out of the station.
"""

from __future__ import annotations

from enum import StrEnum


class EdgeHardware(StrEnum):
    """Qualified compute hardware families for an Adaptix Edge node.

    ``other`` covers hardware Josh has approved for a specific pilot that
    does not yet warrant its own SKU-level enum member; a node stamped
    ``other`` must still carry a truthful ``hardware_details`` blob on the
    :class:`~adaptix_contracts.edge.models.EdgeNode` contract so the
    platform can tell one ``other`` node from another.
    """

    SNOWCONE = "snowcone"
    JETSON_ORIN_NX = "jetson_orin_nx"
    LENOVO_SE30 = "lenovo_se30"
    OTHER = "other"


class UplinkChannel(StrEnum):
    """Physical uplink channels an Edge node can bond for platform reach.

    A single Edge node typically bonds multiple channels through
    :class:`~adaptix_contracts.edge.models.BondedLinkStatus`; the members
    here name the individual channels, not the bonded aggregate.
    ``ethernet`` is the wired station-return channel used when the
    apparatus is docked; the other four are the wireless WAN channels used
    on scene.
    """

    STARLINK = "starlink"
    FIRSTNET = "firstnet"
    VERIZON_LTE = "verizon_lte"
    ATT_LTE = "att_lte"
    ETHERNET = "ethernet"


class EdgeNodeStatus(StrEnum):
    """Lifecycle status of a registered Edge node.

    ``provisioning`` covers first-boot before the initial heartbeat.
    ``online`` and ``offline`` are heartbeat-driven; ``degraded`` is set
    by the platform when a node is reachable but failing health checks
    (e.g. bonded link below the tenant's minimum aggregate quality, or a
    model deployment failure that has not yet cleared).
    ``decommissioned`` is terminal — a node returning from that state
    must re-register.
    """

    PROVISIONING = "provisioning"
    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    DECOMMISSIONED = "decommissioned"


class EdgeDeploymentStatus(StrEnum):
    """Lifecycle status of a model deployment onto an Edge node."""

    PENDING = "pending"
    DOWNLOADING = "downloading"
    INSTALLING = "installing"
    ACTIVE = "active"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    SUPERSEDED = "superseded"


class LinkQuality(StrEnum):
    """Coarse-grained bonded-link quality bucket.

    Deliberately coarse so it is safe to include in heartbeat and uplink
    events at high frequency without leaking fine-grained location or
    subscriber-specific carrier telemetry.
    """

    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    DOWN = "down"


__all__ = [
    "EdgeDeploymentStatus",
    "EdgeHardware",
    "EdgeNodeStatus",
    "LinkQuality",
    "UplinkChannel",
]
