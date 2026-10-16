"""Billing transport readiness contract schemas for cross-domain communication.

Defines all typed contracts for the billing domain's transport readiness
evaluation: claim readiness gates, signed document verification, and
artifact attachment to active claims.

These contracts are consumed by billing (primary) and transportlink (secondary).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TransportReadinessGateStatus(str, Enum):
    """Pass/fail status for a single billing readiness gate."""

    PASSED = "passed"
    FAILED = "failed"
    NOT_EVALUATED = "not_evaluated"


class TransportReadinessRequest(BaseModel):
    """Contract for requesting a billing readiness evaluation for a transport."""

    transport_request_id: str
    tenant_id: str
    requester_user_id: str


class BillingReadinessGate(BaseModel):
    """A single billing readiness gate result."""

    gate: str
    status: TransportReadinessGateStatus
    detail: str | None = None


class TransportReadinessResponse(BaseModel):
    """Read contract for billing readiness state of a transport request.

    A transport claim is not ready for submission unless all gates pass.
    Missing or unsigned documents must be shown as blockers, never as passing.
    """

    transport_request_id: str
    tenant_id: str
    claim_ready: bool
    gates: list[BillingReadinessGate]
    blocking_count: int
    pcs_signed: bool
    aob_signed: bool
    authorization_resolved: bool
    level_of_care_documented: bool
    patient_info_complete: bool
    evaluated_at: datetime


class ClaimArtifactAttachRequest(BaseModel):
    """Contract for attaching a signed transport artifact to a billing claim."""

    transport_request_id: str
    claim_id: str
    artifact_type: str = Field(..., description="pcs, aob, consent, authorization")
    signed_artifact_id: str = Field(
        ..., description="ID of the TransportSignedArtifact record"
    )
    s3_key: str = Field(..., description="S3 key for the signed PDF")
    attached_by_user_id: str


class ClaimArtifactAttachResponse(BaseModel):
    """Response contract after a billing artifact is attached to a claim."""

    claim_artifact_link_id: str
    transport_request_id: str
    claim_id: str
    artifact_type: str
    attached_at: datetime
    readiness_re_evaluated: bool
    claim_ready_after_attach: bool


class BillingTransportLinkEvent(BaseModel):
    """Published when billing creates a readiness link to a transport request."""

    event_type: str = "billing.transport.linked"
    transport_request_id: str
    tenant_id: str
    claim_id: str | None = None
    linked_at: datetime


class ClaimReadinessResolvedEvent(BaseModel):
    """Published when all billing readiness gates pass for a transport claim."""

    event_type: str = "billing.transport.claim_ready"
    transport_request_id: str
    claim_id: str | None = None
    tenant_id: str
    resolved_at: datetime
