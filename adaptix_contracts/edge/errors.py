"""Service-specific error types for the Adaptix Edge apparatus compute node service.

Two layers are provided so callers can pick the right primitive:

* :class:`EdgeError` and its subclasses are Python exceptions raised
  inside the Edge service and its clients; they carry structured
  context (``node_id``, ``deployment_id``, etc.) and know how to render
  themselves into the shared Adaptix HTTP error envelope.
* :class:`EdgeErrorEnvelope` extends
  :class:`~adaptix_contracts.errors.envelope.AdaptixErrorEnvelope` so
  the wire format is exactly the platform envelope — the ``error_code``
  field is widened to accept :class:`EdgeErrorCode`, and edge-specific
  factory classmethods produce well-typed envelopes without callers
  hand-building the dict.

Nothing here catches or silences errors — it only names them. Callers
still decide when to raise, when to convert to an envelope, and when to
propagate to the operational backbone.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field

from adaptix_contracts.errors.envelope import (
    AdaptixErrorCode,
    AdaptixErrorEnvelopeBase,
    AdaptixTraceContext,
)


class EdgeErrorCode(str, Enum):
    """Edge-specific error codes.

    Kept distinct from :class:`AdaptixErrorCode` (rather than trying to
    extend it — Python does not allow enum extension in a way that keeps
    ``isinstance`` sensible) and merged at the envelope boundary through
    :class:`EdgeErrorEnvelope.error_code`. When an edge-specific code
    truly overlaps a platform-wide one, prefer the platform code and do
    not add a duplicate here.
    """

    EDGE_NODE_NOT_FOUND = "edge.node.not_found"
    EDGE_NODE_NOT_REGISTERED = "edge.node.not_registered"
    EDGE_NODE_DECOMMISSIONED = "edge.node.decommissioned"
    EDGE_NODE_OFFLINE = "edge.node.offline"
    EDGE_NODE_DEGRADED = "edge.node.degraded"

    EDGE_IMAGE_NOT_FOUND = "edge.image.not_found"
    EDGE_IMAGE_SIGNATURE_INVALID = "edge.image.signature_invalid"
    EDGE_IMAGE_DIGEST_MISMATCH = "edge.image.digest_mismatch"
    EDGE_IMAGE_HARDWARE_INCOMPATIBLE = "edge.image.hardware_incompatible"

    EDGE_DEPLOYMENT_NOT_FOUND = "edge.deployment.not_found"
    EDGE_DEPLOYMENT_FAILED = "edge.deployment.failed"
    EDGE_DEPLOYMENT_ALREADY_ACTIVE = "edge.deployment.already_active"
    EDGE_DEPLOYMENT_SUPERSEDED = "edge.deployment.superseded"

    EDGE_UPLINK_UNAVAILABLE = "edge.uplink.unavailable"
    EDGE_UPLINK_DEGRADED = "edge.uplink.degraded"

    EDGE_CRDT_CONFLICT = "edge.crdt.conflict"
    EDGE_CRDT_CHECKPOINT_STALE = "edge.crdt.checkpoint_stale"
    EDGE_CRDT_DATASET_UNKNOWN = "edge.crdt.dataset_unknown"

    EDGE_REGISTRATION_REJECTED = "edge.registration.rejected"
    EDGE_TENANT_MISMATCH = "edge.tenant.mismatch"


class EdgeError(Exception):
    """Base exception for the Edge service.

    Subclasses set :attr:`code` to an :class:`EdgeErrorCode`; callers
    catch :class:`EdgeError` when they want to handle any Edge fault
    generically, or a specific subclass when they can act on it.

    :meth:`to_envelope` renders the exception into the shared HTTP error
    envelope; nothing in the exception itself decides HTTP status.
    """

    code: EdgeErrorCode = EdgeErrorCode.EDGE_NODE_NOT_FOUND

    def __init__(
        self,
        message: str,
        *,
        code: EdgeErrorCode | None = None,
        tenant_id: str | None = None,
        node_id: str | None = None,
        deployment_id: str | None = None,
        image_id: str | None = None,
        detail: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code
        self.message = message
        self.detail = detail
        self.tenant_id = tenant_id
        self.node_id = node_id
        self.deployment_id = deployment_id
        self.image_id = image_id
        self.context: dict[str, Any] = dict(context or {})

    def to_envelope(
        self,
        *,
        trace: AdaptixTraceContext | None = None,
    ) -> "EdgeErrorEnvelope":
        """Render this exception as an :class:`EdgeErrorEnvelope`.

        No stack trace or raw exception text is emitted — only the
        structured fields the caller supplied when constructing the
        exception.
        """

        effective_trace = trace
        if effective_trace is None and self.tenant_id is not None:
            effective_trace = AdaptixTraceContext(tenant_id=self.tenant_id)

        return EdgeErrorEnvelope(
            error_code=self.code,
            message=self.message,
            detail=self.detail,
            trace=effective_trace,
            edge_context=self._edge_context(),
        )

    def _edge_context(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.tenant_id is not None:
            payload["tenant_id"] = self.tenant_id
        if self.node_id is not None:
            payload["node_id"] = self.node_id
        if self.deployment_id is not None:
            payload["deployment_id"] = self.deployment_id
        if self.image_id is not None:
            payload["image_id"] = self.image_id
        payload.update(self.context)
        return payload


class EdgeNodeNotFoundError(EdgeError):
    """Raised when an Edge node id does not resolve for the caller's tenant."""

    code = EdgeErrorCode.EDGE_NODE_NOT_FOUND


class EdgeNodeStateError(EdgeError):
    """Raised when an Edge node is not in a state that permits the operation.

    ``code`` is left assignable by the caller (offline / degraded /
    decommissioned) — the state is fault-specific.
    """

    code = EdgeErrorCode.EDGE_NODE_OFFLINE


class EdgeImageError(EdgeError):
    """Raised for image lookup, signature, digest, or compatibility faults."""

    code = EdgeErrorCode.EDGE_IMAGE_NOT_FOUND


class EdgeDeploymentError(EdgeError):
    """Raised when an Edge model deployment cannot proceed as requested."""

    code = EdgeErrorCode.EDGE_DEPLOYMENT_FAILED


class EdgeUplinkError(EdgeError):
    """Raised when an Edge node's uplink cannot serve the requested operation."""

    code = EdgeErrorCode.EDGE_UPLINK_UNAVAILABLE


class EdgeCrdtConflictError(EdgeError):
    """Raised when a CRDT sync round produces an unresolvable conflict."""

    code = EdgeErrorCode.EDGE_CRDT_CONFLICT


class EdgeRegistrationRejectedError(EdgeError):
    """Raised when an Edge node's registration attempt is refused."""

    code = EdgeErrorCode.EDGE_REGISTRATION_REJECTED


class EdgeTenantMismatchError(EdgeError):
    """Raised when a caller's tenant does not match the target Edge node.

    Distinct from :class:`EdgeNodeNotFoundError` because a mismatch is a
    tenancy fault (the caller has an authenticated identity in another
    tenant) whereas ``not found`` covers unknown-id lookups within the
    caller's own tenant. Callers MUST NOT downgrade this to a 404 — the
    distinction is required for cross-tenant audit.
    """

    code = EdgeErrorCode.EDGE_TENANT_MISMATCH


class EdgeErrorEnvelope(AdaptixErrorEnvelopeBase):
    """Adaptix HTTP error envelope widened for Edge-specific codes.

    Declares ``error_code`` widened to accept
    :class:`EdgeErrorCode`) and adds ``edge_context`` for structured
    Edge-scoped fields (``node_id``, ``deployment_id`` …). The
    envelope shape, timestamp field, trace context, factory helpers and
    ``to_http_response`` behaviour are inherited unchanged from
    :class:`~adaptix_contracts.errors.envelope.AdaptixErrorEnvelopeBase`,
    which is the SIBLING base it shares with
    :class:`~adaptix_contracts.errors.envelope.AdaptixErrorEnvelope`.
    Widening a field on a subclass is a Liskov violation the type
    checker rejects; widening the platform envelope itself would make
    every service accept these codes. Siblings avoid both.
    """

    error_code: EdgeErrorCode | AdaptixErrorCode
    edge_context: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def node_not_found(
        cls,
        node_id: str,
        *,
        tenant_id: str | None = None,
        trace: AdaptixTraceContext | None = None,
    ) -> "EdgeErrorEnvelope":
        return cls(
            error_code=EdgeErrorCode.EDGE_NODE_NOT_FOUND,
            message=f"Edge node not found: {node_id}",
            trace=trace,
            edge_context={
                k: v
                for k, v in {"node_id": node_id, "tenant_id": tenant_id}.items()
                if v is not None
            },
        )

    @classmethod
    def image_signature_invalid(
        cls,
        image_id: str,
        *,
        detail: str | None = None,
        trace: AdaptixTraceContext | None = None,
    ) -> "EdgeErrorEnvelope":
        return cls(
            error_code=EdgeErrorCode.EDGE_IMAGE_SIGNATURE_INVALID,
            message=f"Edge image signature failed verification: {image_id}",
            detail=detail,
            trace=trace,
            edge_context={"image_id": image_id},
        )

    @classmethod
    def deployment_failed(
        cls,
        deployment_id: str,
        reason: str,
        *,
        node_id: str | None = None,
        trace: AdaptixTraceContext | None = None,
    ) -> "EdgeErrorEnvelope":
        return cls(
            error_code=EdgeErrorCode.EDGE_DEPLOYMENT_FAILED,
            message=f"Edge deployment {deployment_id} failed",
            detail=reason,
            trace=trace,
            edge_context={
                k: v
                for k, v in {
                    "deployment_id": deployment_id,
                    "node_id": node_id,
                }.items()
                if v is not None
            },
        )

    @classmethod
    def uplink_unavailable(
        cls,
        node_id: str,
        *,
        detail: str | None = None,
        trace: AdaptixTraceContext | None = None,
    ) -> "EdgeErrorEnvelope":
        return cls(
            error_code=EdgeErrorCode.EDGE_UPLINK_UNAVAILABLE,
            message=f"Edge node {node_id} has no working uplink",
            detail=detail,
            trace=trace,
            edge_context={"node_id": node_id},
        )

    @classmethod
    def crdt_conflict(
        cls,
        node_id: str,
        dataset: str,
        *,
        detail: str | None = None,
        trace: AdaptixTraceContext | None = None,
    ) -> "EdgeErrorEnvelope":
        return cls(
            error_code=EdgeErrorCode.EDGE_CRDT_CONFLICT,
            message=f"CRDT sync conflict on {dataset}@{node_id}",
            detail=detail,
            trace=trace,
            edge_context={"node_id": node_id, "dataset": dataset},
        )

    @classmethod
    def tenant_mismatch(
        cls,
        *,
        expected_tenant_id: str,
        actual_tenant_id: str,
        node_id: str | None = None,
        trace: AdaptixTraceContext | None = None,
    ) -> "EdgeErrorEnvelope":
        return cls(
            error_code=EdgeErrorCode.EDGE_TENANT_MISMATCH,
            message="Edge node belongs to a different tenant",
            trace=trace,
            edge_context={
                k: v
                for k, v in {
                    "expected_tenant_id": expected_tenant_id,
                    "actual_tenant_id": actual_tenant_id,
                    "node_id": node_id,
                }.items()
                if v is not None
            },
        )


__all__ = [
    "EdgeCrdtConflictError",
    "EdgeDeploymentError",
    "EdgeError",
    "EdgeErrorCode",
    "EdgeErrorEnvelope",
    "EdgeImageError",
    "EdgeNodeNotFoundError",
    "EdgeNodeStateError",
    "EdgeRegistrationRejectedError",
    "EdgeTenantMismatchError",
    "EdgeUplinkError",
]
