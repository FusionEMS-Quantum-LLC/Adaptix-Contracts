"""Billing clearinghouse integration contracts.

Defines all typed request/response/event contracts for external clearinghouse
interactions: claim submission, acknowledgements, remittance ingestion,
and error handling.

This layer isolates external vendor behavior (Office Ally, Availity, etc.)
from the core billing domain.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

# Import shared enums from core billing contracts
from .billing_contracts import ClearinghouseProvider


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SubmissionStatus(str, Enum):
    """Submission lifecycle at clearinghouse."""

    QUEUED = "queued"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ERROR = "error"


class AckType(str, Enum):
    """Type of clearinghouse acknowledgement."""

    TA1 = "ta1"  # interchange acknowledgment
    ACK_999 = "999"  # functional acknowledgment
    ACK_277CA = "277ca"  # claim acknowledgment
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Submission Contracts
# ---------------------------------------------------------------------------


class ClaimSubmissionRequest(BaseModel):
    """Request to submit a claim to a clearinghouse."""

    claim_id: str
    tenant_id: str

    provider: ClearinghouseProvider
    edi_payload: str = Field(..., description="X12 837 payload")

    submitted_by_user_id: Optional[str] = None


class ClaimSubmissionResponse(BaseModel):
    """Response after attempting submission to clearinghouse."""

    submission_id: str
    claim_id: str
    tenant_id: str

    provider: ClearinghouseProvider
    status: SubmissionStatus

    external_reference_id: Optional[str] = None
    message: Optional[str] = None

    submitted_at: datetime


# ---------------------------------------------------------------------------
# Acknowledgements
# ---------------------------------------------------------------------------


class ClearinghouseAck(BaseModel):
    """Raw acknowledgement from clearinghouse."""

    submission_id: str
    claim_id: str
    tenant_id: str

    provider: ClearinghouseProvider
    ack_type: AckType

    ack_code: str
    ack_message: Optional[str] = None

    accepted: bool
    received_at: datetime


class ClaimAckStatus(BaseModel):
    """Normalized claim status derived from acknowledgements."""

    claim_id: str
    tenant_id: str

    accepted: bool
    rejected: bool
    errors: list[str] = Field(default_factory=list)

    processed_at: datetime


# ---------------------------------------------------------------------------
# Remittance (ERA)
# ---------------------------------------------------------------------------


class RemittanceIngestRequest(BaseModel):
    """Incoming ERA (835) ingestion request."""

    tenant_id: str
    provider: ClearinghouseProvider

    raw_835_payload: str
    received_at: datetime


class RemittanceClaimPayment(BaseModel):
    """Payment detail for a single claim within a remittance."""

    claim_id: str
    paid_cents: int = Field(..., ge=0)
    adjusted_cents: int = Field(..., ge=0)

    payer_claim_control_number: Optional[str] = None


class RemittanceIngestResponse(BaseModel):
    """Result of ERA ingestion."""

    remit_id: str
    tenant_id: str

    claims_processed: int
    claims_failed: int

    processed_at: datetime


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


class ClaimSubmittedToClearinghouseEvent(BaseModel):
    """Published when a claim is sent to a clearinghouse."""

    event_type: str = "billing.clearinghouse.submitted"

    submission_id: str
    claim_id: str
    tenant_id: str

    provider: ClearinghouseProvider
    submitted_at: datetime


class ClearinghouseAckReceivedEvent(BaseModel):
    """Published when an acknowledgement is received from the clearinghouse.

    Merges fields from both clearinghouse and billing acknowledgement contexts.
    Canonical source for billing.clearinghouse.ack_received event consumers.
    """

    event_type: str = "billing.clearinghouse.ack_received"

    submission_id: str
    claim_id: str
    tenant_id: str

    provider: ClearinghouseProvider
    ack_type: AckType
    accepted: bool
    ack_code: Optional[str] = None
    ack_message: Optional[str] = None

    received_at: datetime


class RemittanceIngestedEvent(BaseModel):
    """Published when an ERA is successfully processed."""

    event_type: str = "billing.clearinghouse.remittance_ingested"

    remit_id: str
    tenant_id: str

    claims_processed: int
    processed_at: datetime


# ---------------------------------------------------------------------------
# Stedi inbound webhook
#
# Route:  POST /api/v1/billing/webhooks/stedi
# Source: Adaptix-Billing-Service backend/billing_app/api/webhooks_stedi.py
#         (commit 9ba5c6e2, PR #541). Registered in main.py without the billing
#         module-entitlement gate (Stedi cannot present a tenant JWT); the
#         handler self-authenticates with a constant-time Bearer-token check
#         against ``webhook_bearer_token`` in AWS Secrets Manager.
#
# Status codes emitted by the handler (webhooks_stedi.py:288-296, 302-382):
#   202 — accepted (new event persisted+enqueued) OR duplicate ignored.
#   400 — malformed JSON / wrong shape / missing event id.
#   401 — missing/invalid Authorization (Stedi retries).
#   413 — payload exceeds the size limit.
#   503 — webhook token unconfigured OR durable persist failed (Stedi retries).
#
# These models mirror ONLY the fields the handler reads and returns. The full
# EventBridge envelope is persisted verbatim by the service, so the request
# model allows extra fields rather than fabricating a fixed envelope shape.
# ---------------------------------------------------------------------------


class StediWebhookEventType(str, Enum):
    """Recognized Stedi ``detail-type`` values (the KNOWN set).

    Source: webhooks_stedi.py ``KNOWN_EVENT_TYPES`` (lines 77-83). Unknown
    types are still accepted (202) and persisted for investigation, so the
    request model types ``detail_type`` as a bare ``str`` — this enum enumerates
    only the types the worker recognizes.
    """

    TRANSACTION_PROCESSED = "transaction.processed.v2"
    FILE_DELIVERED = "file.delivered.v2"
    FILE_FAILED = "file.failed.v2"


class StediWebhookRequest(BaseModel):
    """Inbound Stedi webhook envelope (EventBridge-shaped).

    The handler (webhooks_stedi.py:277-356) requires the top-level ``id`` and
    reads ``detail-type``; every other envelope field is accepted and persisted
    verbatim (``extra="allow"``). Authentication is out-of-band via the
    ``Authorization: Bearer <webhook_bearer_token>`` header (constant-time),
    never a body field.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str = Field(
        ...,
        description="Stable Stedi/EventBridge event id; second half of the "
        "(provider, provider_event_id) idempotency key.",
    )
    detail_type: Optional[str] = Field(
        default=None,
        alias="detail-type",
        description="Event type. Known values in StediWebhookEventType; unknown "
        "types are still accepted (202) and persisted for investigation.",
    )
    detail: Optional[dict[str, Any]] = Field(
        default=None,
        description="EventBridge detail payload (transaction/file event body). "
        "Stored verbatim by the service; not validated by the route.",
    )


class StediWebhookAcceptedResponse(BaseModel):
    """202 body for a newly-accepted event.

    Source: webhooks_stedi.py:434-440.
    """

    status: str = "accepted"
    event_id: str
    event_type: Optional[str] = None
    known_event_type: bool
    enqueued: bool


class StediWebhookDuplicateResponse(BaseModel):
    """202 body for an idempotent duplicate delivery (zero side effects).

    Source: webhooks_stedi.py:393-397.
    """

    status: str = "duplicate_ignored"
    event_id: str
    known_event_type: bool


class StediWebhookRejectedResponse(BaseModel):
    """Non-2xx body for 400 / 401 / 413 / 503 rejections.

    Source: webhooks_stedi.py:310, 321, 332, 335, 343, 347, 356, 382.
    ``status`` is one of ``rejected|unauthorized|unconfigured|error``; ``reason``
    is a stable machine code (e.g. ``payload_too_large``, ``invalid_json``,
    ``invalid_payload_shape``, ``missing_event_id``, ``missing_authorization_header``,
    ``invalid_authorization_scheme``, ``empty_bearer_token``, ``invalid_token``,
    ``webhook_verification_unavailable``, ``persist_failed``). The Authorization
    header value is never echoed in any path.
    """

    status: str
    reason: str


# ---------------------------------------------------------------------------
# Clearinghouse retry-eligibility + operator fallback
#
# Routes:
#   GET  /api/v1/billing/clearinghouse/claims/{claim_id}/retry-eligibility
#   POST /api/v1/billing/clearinghouse/claims/{claim_id}/operator-fallback
# Source: backend/billing_app/api/clearinghouse_router_routes.py (commit
#         9dc57abf, PR #539) with value sets from clearinghouse/base.py and
#         clearinghouse/router.py.
#
# Both routes require the ``founder`` OR ``billing_admin`` role
# (clearinghouse_router_routes.py:66-74) and the ``billing`` module entitlement
# (main.py include loop); both are tenant-scoped to the caller's
# ``auth.tenant_id`` and 404 when the claim belongs to another tenant.
# ---------------------------------------------------------------------------


class ClaimTransmissionState(str, Enum):
    """Whether a prior submission attempt reached the clearinghouse.

    Source: clearinghouse/base.py:88-96
    (TRANSMISSION_NOT_SENT / TRANSMISSION_UNKNOWN / TRANSMISSION_CONFIRMED).
    """

    NOT_TRANSMITTED = "not_transmitted"
    UNKNOWN = "unknown"
    TRANSMITTED = "transmitted"


class ClaimRetryReasonCode(str, Enum):
    """Machine-readable retry-eligibility verdict codes.

    Source: clearinghouse/base.py:135-180
    (``retry_eligibility_for_transmission_state``).
    """

    NO_PRIOR_ATTEMPT = "no_prior_attempt"
    PROVEN_NOT_TRANSMITTED = "proven_not_transmitted"
    ALREADY_ACCEPTED = "already_accepted"
    UNKNOWN_TRANSMISSION = "unknown_transmission"


class ClaimRetryEligibilityResponse(BaseModel):
    """200 body for GET .../claims/{claim_id}/retry-eligibility.

    Mirrors ``RetryEligibilityResponse`` field-for-field
    (clearinghouse_router_routes.py:138-148). ``reason_code`` carries a
    ``ClaimRetryReasonCode`` value; ``blocking_state`` and
    ``latest_transmission_state`` carry a ``ClaimTransmissionState`` value or
    null. Typed as ``str`` to match the source contract exactly (the service
    ships raw strings, not enum members). 403 (role) and 404 (claim not found
    for tenant) do not use this shape.
    """

    claim_id: str
    tenant_id: str
    safe: bool
    blocking_state: Optional[str] = None
    reason_code: str
    reason: str
    latest_clearinghouse_slug: Optional[str] = None
    latest_transmission_state: Optional[str] = None


class ClaimOperatorFallbackRequest(BaseModel):
    """Request body for POST .../claims/{claim_id}/operator-fallback.

    Mirrors ``OperatorFallbackRequest`` including field constraints
    (clearinghouse_router_routes.py:151-157). ``target_clearinghouse_slug`` must
    match ``^[a-z][a-z0-9_]+$`` and be a slug on the tenant's roster;
    ``acknowledge_duplicate_risk`` must be true to proceed when the original
    transmission state is ``unknown``.
    """

    target_clearinghouse_slug: str = Field(..., pattern="^[a-z][a-z0-9_]+$")
    reason: str = Field(..., min_length=4, max_length=2000)
    evidence: str = Field(..., min_length=4, max_length=4000)
    acknowledge_duplicate_risk: bool = False


class ClaimOperatorFallbackResponse(BaseModel):
    """200 body for a successful operator-initiated cross-clearinghouse move.

    Mirrors ``OperatorFallbackResponse``
    (clearinghouse_router_routes.py:160-169).
    """

    claim_id: str
    fallback_event_id: str
    original_clearinghouse_slug: str
    original_transmission_state: str
    target_clearinghouse_slug: str
    new_submission_reference: Optional[str] = None
    cost_cents: int


class OperatorFallbackRefusedReasonCode(str, Enum):
    """409 refusal codes for operator-fallback.

    Source: clearinghouse/router.py:1088-1138 (the ``operator_fallback_submit``
    refusal branches). The refusal is persisted and audited before the 409 is
    surfaced.
    """

    NO_ORIGINAL_SUBMISSION = "no_original_submission"
    SAME_VENDOR = "same_vendor"
    ORIGINAL_ALREADY_ACCEPTED = "original_already_accepted"
    UNKNOWN_TRANSMISSION_REQUIRES_ACKNOWLEDGEMENT = (
        "unknown_transmission_requires_acknowledgement"
    )
    TARGET_NOT_CONFIGURED = "target_not_configured"
    TARGET_NOT_ELIGIBLE = "target_not_eligible"


class ClaimOperatorFallbackRefusedError(BaseModel):
    """FastAPI ``detail`` payload for a 409 operator-fallback refusal.

    Source: clearinghouse_router_routes.py:502-509 — raised as
    ``HTTPException(status_code=409, detail={"reason_code", "message"})`` and
    served by FastAPI as ``{"detail": {...}}``. ``reason_code`` is one of
    ``OperatorFallbackRefusedReasonCode``. (Note: the 409 raised for a missing
    stored 837P envelope — clearinghouse_router_routes.py:486-487 — and the 400
    for an unknown slug carry a plain-string ``detail`` instead of this object.)
    """

    reason_code: str
    message: str


class ClaimOperatorFallbackTargetFailedError(BaseModel):
    """FastAPI ``detail`` payload for a 503 target-clearinghouse failure.

    Source: clearinghouse_router_routes.py:510-521 — raised as
    ``HTTPException(status_code=503, detail={"error", "target_slug",
    "transmission_state"})`` when the target vendor itself fails; the failed
    attempt and fallback event are persisted first.
    """

    error: str = "target_clearinghouse_submit_failed"
    target_slug: str
    transmission_state: str
