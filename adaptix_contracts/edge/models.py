"""Pydantic v2 models for the Adaptix Edge apparatus compute node service (Play P23).

Every model on the Edge boundary carries ``tenant_id`` and
``correlation_id`` — ``tenant_id`` because Edge nodes are tenant-scoped
compute (an apparatus belongs to one agency), and ``correlation_id`` so a
Signal Bus event, an API call, and the CRDT sync record for the same
work can be joined post-hoc.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from adaptix_contracts.edge.enums import (
    EdgeDeploymentStatus,
    EdgeHardware,
    EdgeNodeStatus,
    LinkQuality,
    UplinkChannel,
)


class EdgeNode(BaseModel):
    """A registered Adaptix Edge compute node on a single apparatus.

    The pair ``(tenant_id, node_id)`` is the canonical identity — the
    same physical hardware moved to a different agency re-registers with
    a new ``node_id``.
    """

    tenant_id: str
    correlation_id: str

    node_id: str
    hostname: str
    hardware: EdgeHardware
    hardware_details: dict[str, Any] = Field(default_factory=dict)

    agency_id: str
    apparatus_id: str | None = None
    station_id: str | None = None

    firmware_version: str
    agent_version: str
    kernel_version: str | None = None

    status: EdgeNodeStatus = EdgeNodeStatus.PROVISIONING
    supported_uplinks: list[UplinkChannel] = Field(default_factory=list)

    registered_at: datetime
    last_heartbeat_at: datetime | None = None
    last_status_reason: str | None = None

    labels: dict[str, str] = Field(default_factory=dict)


class EdgeImage(BaseModel):
    """A signed container/model image published for deployment to Edge nodes.

    Images are tenant-scoped in the contract because agencies may pin
    to different validated versions; a platform-wide image is still
    represented per-tenant when it is offered to that tenant.
    ``signature_authority`` defaults to ``"trustsign"`` — TrustSign is
    the sole Adaptix signature authority (DocuSeal retired 2026-08-18).
    """

    tenant_id: str
    correlation_id: str

    image_id: str
    name: str
    version: str
    digest: str
    size_bytes: int = Field(ge=0)

    hardware_targets: list[EdgeHardware] = Field(default_factory=list)
    signature_authority: str = "trustsign"
    signature_reference: str | None = None

    published_at: datetime
    published_by: str | None = None

    notes: str | None = None


class EdgeModelDeployment(BaseModel):
    """A model/image deployment onto one specific Edge node.

    ``model_id`` and ``model_version`` name the logical model contract;
    ``image_id`` names the concrete signed artifact that carries it. Both
    are kept so a rollback from image B to image A of the same model
    still shows in the deployment history.
    """

    tenant_id: str
    correlation_id: str

    deployment_id: str
    node_id: str

    model_id: str
    model_version: str
    image_id: str

    status: EdgeDeploymentStatus = EdgeDeploymentStatus.PENDING
    progress_pct: float = Field(default=0.0, ge=0.0, le=100.0)

    requested_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    supersedes_deployment_id: str | None = None
    failure_reason: str | None = None

    checksum_verified: bool = False
    signature_verified: bool = False


class CrdtSyncCheckpoint(BaseModel):
    """A CRDT sync checkpoint for one dataset on one Edge node.

    Edge nodes reconcile locally-authored records (ePCR drafts, fleet
    telemetry, etc.) with the platform through CRDT sync; a checkpoint
    records the merged state so a later disconnect/reconnect cycle can
    resume from a known point instead of replaying the entire history.

    ``vector_clock`` is a small opaque map (node/actor -> counter) that
    identifies the causal position of this checkpoint; consumers MUST NOT
    parse it beyond equality/subset comparisons — the shape is owned by
    the Edge sync worker and may add fields.
    """

    tenant_id: str
    correlation_id: str

    checkpoint_id: str
    node_id: str
    dataset: str

    vector_clock: dict[str, int] = Field(default_factory=dict)
    merged_record_count: int = Field(default=0, ge=0)
    pending_local_ops: int = Field(default=0, ge=0)
    pending_remote_ops: int = Field(default=0, ge=0)
    conflict_count: int = Field(default=0, ge=0)

    last_synced_at: datetime
    next_expected_sync_at: datetime | None = None

    remote_epoch: str | None = None


class BondedLinkChannelStatus(BaseModel):
    """Per-channel status inside a :class:`BondedLinkStatus` snapshot.

    Kept in this module (not enums) because it carries per-channel
    telemetry (latency, throughput bucket) that a bare enum cannot
    express.
    """

    channel: UplinkChannel
    quality: LinkQuality
    connected: bool
    latency_ms: int | None = Field(default=None, ge=0)
    downstream_kbps: int | None = Field(default=None, ge=0)
    upstream_kbps: int | None = Field(default=None, ge=0)
    packet_loss_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    carrier: str | None = None


class BondedLinkStatus(BaseModel):
    """A point-in-time snapshot of one Edge node's bonded WAN state.

    Emitted on state change (channel up/down, primary swap, aggregate
    quality bucket change) rather than on a fixed cadence, to avoid
    flooding the Signal Bus with steady-state noise.
    """

    tenant_id: str
    correlation_id: str

    node_id: str
    measured_at: datetime

    channels: list[BondedLinkChannelStatus] = Field(default_factory=list)
    primary_channel: UplinkChannel | None = None
    aggregate_quality: LinkQuality = LinkQuality.DOWN
    aggregate_downstream_kbps: int | None = Field(default=None, ge=0)
    aggregate_upstream_kbps: int | None = Field(default=None, ge=0)

    on_scene: bool = False
    reason: str | None = None


__all__ = [
    "BondedLinkChannelStatus",
    "BondedLinkStatus",
    "CrdtSyncCheckpoint",
    "EdgeImage",
    "EdgeModelDeployment",
    "EdgeNode",
]
