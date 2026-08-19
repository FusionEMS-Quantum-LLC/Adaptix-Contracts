"""Shared continuity contracts for collaborative workspace sync across Adaptix domains."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class AttachmentSyncState(str, Enum):
    STAGED = "staged"
    UPLOADING = "uploading"
    SYNCED = "synced"
    FAILED = "failed"
    CONFLICT = "conflict"
    DELETED = "deleted"


class DraftStatus(str, Enum):
    DRAFT = "draft"
    SYNCED = "synced"
    CONFLICTED = "conflicted"


class ResumeState(str, Enum):
    AVAILABLE = "available"
    FINALIZED = "finalized"
    LOCKED = "locked"


class SyncState(str, Enum):
    SYNCED = "synced"
    CONFLICTED = "conflicted"
    PENDING = "pending"


class LockState(str, Enum):
    """Truthful lock state for shared continuity workspaces."""

    HELD = "held"
    TAKEOVER_AVAILABLE = "takeover_available"
    UNLOCKED = "unlocked"


class ContinuityAuditAction(str, Enum):
    """Canonical audit actions emitted by continuity workflows."""

    LOCK_ACQUIRED = "lock_acquired"
    LOCK_RENEWED = "lock_renewed"
    LOCK_TAKEN_OVER = "lock_taken_over"
    LOCK_RELEASED = "lock_released"
    OPERATION_RECORDED = "operation_recorded"


class ClientDeviceIdentity(BaseModel):
    device_id: str
    device_type: str
    platform: str
    app_version: str | None = None
    session_token: str | None = None


class ContinuityLockSnapshot(BaseModel):
    """Current lock state for a shared mutable workspace."""

    state: LockState
    locked_by_user_id: str | None = None
    locked_by_device_id: str | None = None
    locked_at: datetime | None = None
    expires_at: datetime | None = None
    takeover_available: bool = False


class OperationEnvelope(BaseModel):
    """Canonical device-originated write envelope for continuity replay."""

    operation_id: str
    operation_type: str
    domain: str
    object_type: str
    object_id: str
    base_sync_version: int = Field(ge=0)
    payload: dict[str, Any] = Field(default_factory=dict)
    device: ClientDeviceIdentity
    client_created_at: datetime | None = None
    client_sequence: int | None = Field(default=None, ge=0)


class ContinuityAuditEvent(BaseModel):
    """Structured audit payload for continuity activity."""

    workspace: dict[str, Any]
    action: ContinuityAuditAction
    status: str
    actor_user_id: str | None = None
    device: ClientDeviceIdentity | None = None
    sync_version: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime


class WorkspaceIdentity(BaseModel):
    """Typed workspace identity for authoritative continuity responses."""

    tenant_id: str
    domain: str
    object_type: str
    object_id: str
    workspace_id: str


class AttachmentSyncStatus(BaseModel):
    attachment_id: str
    file_name: str
    mime_type: str | None = None
    size_bytes: int | None = None
    storage_key: str | None = None
    checksum_sha256: str | None = None
    sync_state: AttachmentSyncState
    updated_at: datetime


class ResumeStateResponse(BaseModel):
    workspace: WorkspaceIdentity
    resume_state: ResumeState
    draft_status: DraftStatus
    sync_state: SyncState
    sync_version: int
    last_saved_at: datetime | None = None
    last_saved_by_user_id: str | None = None
    workflow_step: str | None = None
    validation_errors: list[Any] = Field(default_factory=list)
    unresolved_warnings: list[Any] = Field(default_factory=list)
    attachments: list[AttachmentSyncStatus] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)


class ConflictResponse(BaseModel):
    tenant_id: str
    domain: str
    object_type: str
    object_id: str
    expected_sync_version: int
    actual_sync_version: int
    server_state: dict[str, Any]
    conflict_fields: list[str] = Field(default_factory=list)
    message: str = "Conflict detected: server state has been modified."


# ---------------------------------------------------------------------------
# Offline authority envelope (shared platform primitive J)
# ---------------------------------------------------------------------------
#
# The contracts above cover a shared workspace several devices edit while the
# platform is reachable. What follows covers the harder case: an apparatus that
# has lost the cloud entirely and must keep working — a crew still documenting a
# patient, still recording a controlled-substance administration, still changing
# unit status — and then reconnects and has to be reconciled without duplicating
# or silently overwriting anything.
#
# The rule that makes this safe is that offline authority is *granted, scoped and
# expiring*, not assumed. A device does not decide it may write while offline; it
# carries a grant that says which operations it may perform and until when.


class ContinuityMode(str, Enum):
    """Operating mode of the platform as one device experiences it.

    * ``NORMAL`` — everything reachable.
    * ``DEGRADED_PROVIDER`` — an external provider is unavailable; AdaptixCore
      itself is healthy. Domain work continues; provider-dependent steps queue.
    * ``DEGRADED_CLOUD`` — the platform is partially reachable. Reads may be
      stale; writes may be queued.
    * ``EDGE_AUTHORITY`` — the cloud is unreachable and the device is operating
      under an offline authority grant.
    * ``RECOVERY`` — reconnected; the operation journal is being uploaded.
    * ``RECONCILIATION`` — uploaded; conflicts are being classified and settled.

    ``DEGRADED_PROVIDER`` is deliberately distinct from ``DEGRADED_CLOUD``: a
    clearinghouse outage must never present to a crew as "the platform is down",
    and a platform outage must never be reported as a provider problem.
    """

    NORMAL = "normal"
    DEGRADED_PROVIDER = "degraded_provider"
    DEGRADED_CLOUD = "degraded_cloud"
    EDGE_AUTHORITY = "edge_authority"
    RECOVERY = "recovery"
    RECONCILIATION = "reconciliation"


#: Modes in which a device is not in normal communication with the platform and
#: its local state may diverge from canonical truth.
DIVERGENT_CONTINUITY_MODES: frozenset[ContinuityMode] = frozenset(
    {
        ContinuityMode.DEGRADED_CLOUD,
        ContinuityMode.EDGE_AUTHORITY,
        ContinuityMode.RECOVERY,
        ContinuityMode.RECONCILIATION,
    }
)


def may_diverge_from_canonical(mode: ContinuityMode | str) -> bool:
    """Return ``True`` when local state may not match the platform.

    Fails closed: an unrecognised mode is treated as divergent, so a consumer
    that meets a mode it does not understand reconciles rather than trusting
    what it holds.
    """

    try:
        resolved = ContinuityMode(mode)
    except ValueError:
        return True
    return resolved in DIVERGENT_CONTINUITY_MODES


class OfflineAuthorityGrant(BaseModel):
    """A time-boxed, scoped grant letting one device write while offline.

    ``allowed_operation_types`` is an allow-list, never a deny-list: an
    operation nobody explicitly granted is not permitted offline. That is what
    keeps an irreversible action — destroying a vial, submitting a claim — from
    happening on a disconnected tablet because nobody thought to forbid it.

    ``expires_at`` is required. An unexpiring offline grant is a device that can
    write forever against state it cannot see.
    """

    grant_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    device_id: str = Field(..., min_length=1)
    device_cert_id: str = Field(
        ..., min_length=1, description="Client certificate this grant is bound to"
    )
    user_id: str = Field(..., min_length=1)
    allowed_operation_types: list[str] = Field(
        ...,
        min_length=1,
        description="Allow-list of operation types permitted while offline",
    )
    issued_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def _grant_window_is_valid(self) -> OfflineAuthorityGrant:
        if self.expires_at <= self.issued_at:
            raise ValueError("expires_at must be after issued_at")
        return self

    def is_valid_at(self, when: datetime) -> bool:
        """Return ``True`` when the grant is live at ``when``."""

        return self.issued_at <= when < self.expires_at

    def permits(self, operation_type: str, *, when: datetime) -> bool:
        """Return ``True`` when this grant allows ``operation_type`` at ``when``.

        Both conditions must hold. An expired grant permits nothing, whatever it
        lists.
        """

        return self.is_valid_at(when) and operation_type in self.allowed_operation_types


class OfflineOperationEnvelope(BaseModel):
    """One write a device performed while operating under an offline grant.

    Distinct from :class:`OperationEnvelope` above, which is a workspace edit
    made against a reachable platform. This one is signed, bound to an authority
    grant, and replayed during ``RECOVERY``.

    ``base_state_version`` is the protected-record version the device believed it
    was changing — the same optimistic-concurrency version as
    ``adaptix_contracts.schemas.state_conflict_contracts``. On replay, a
    mismatch is a conflict for a person to settle, never an automatic merge.

    ``local_sequence`` orders one device's operations against each other. It is
    explicitly not a clock: device clocks drift, and ordering two devices'
    offline work by their own timestamps is how a later record overwrites an
    earlier one.
    """

    offline_operation_id: str = Field(..., min_length=1)
    device_id: str = Field(..., min_length=1)
    device_cert_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    authority_grant_id: str = Field(..., min_length=1)
    issued_at: datetime
    expires_at: datetime
    operation_type: str = Field(..., min_length=1)
    resource_type: str = Field(..., min_length=1)
    resource_id: str = Field(..., min_length=1)
    base_state_version: int = Field(..., ge=0)
    local_sequence: int = Field(
        ..., ge=0, description="Per-device monotonic order; not a timestamp"
    )
    payload_hash: str = Field(..., min_length=1)
    signature: str = Field(
        ..., min_length=1, description="Device signature over the operation"
    )

    @model_validator(mode="after")
    def _authority_window_is_valid(self) -> OfflineOperationEnvelope:
        if self.expires_at <= self.issued_at:
            raise ValueError("expires_at must be after issued_at")
        return self

    def is_within_authority(
        self, grant: OfflineAuthorityGrant, *, when: datetime
    ) -> bool:
        """Return ``True`` when ``grant`` actually authorised this operation.

        Checks every binding, not just the id: tenant, device, certificate,
        operation type, and the grant window. A replay that matches the grant id
        but not the certificate is a device presenting somebody else's authority.
        """

        return (
            grant.grant_id == self.authority_grant_id
            and grant.tenant_id == self.tenant_id
            and grant.device_id == self.device_id
            and grant.device_cert_id == self.device_cert_id
            and grant.permits(self.operation_type, when=when)
        )
