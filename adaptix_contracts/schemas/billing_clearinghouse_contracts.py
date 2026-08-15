"""Billing clearinghouse integration contracts.

Defines all typed request/response/event contracts for live Stedi claim
submission, acknowledgements, remittance ingestion, migration/source vendor
settings, migration-mode controls, and error handling.

STEDI is the only live billing clearinghouse. Office Ally, Waystar, Availity,
Change Healthcare, TriZetto, and other legacy vendors are migration/source
systems only and must never be interpreted as live claim-submission targets by
consumers of these contracts.
"""
# Pydantic schema DTOs intentionally expose fields, not behavior.
# pylint: disable=too-few-public-methods

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Import shared enums from core billing contracts
from .billing_contracts import ClearinghouseProvider, MigrationSourceVendor


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


class StediReadinessState(str, Enum):
    """The 15 wire readiness states shared by Billing Service and Web App."""

    NOT_CONFIGURED = "not_configured"
    CREDENTIALS_MISSING = "credentials_missing"
    CREDENTIALS_INVALID = "credentials_invalid"
    CREDENTIALS_CONFIGURED = "credentials_configured"
    CONNECTION_VERIFICATION_PENDING = "connection_verification_pending"
    CONNECTION_VERIFIED = "connection_verified"
    PROVIDER_INCOMPLETE = "provider_incomplete"
    ENROLLMENT_REQUIRED = "enrollment_required"
    TEST_READY = "test_ready"
    TESTING = "testing"
    TEST_FAILED = "test_failed"
    PRODUCTION_PENDING = "production_pending"
    PRODUCTION_READY = "production_ready"
    DEGRADED = "degraded"
    SUSPENDED = "suspended"


class StediWebhookVerification(str, Enum):
    """Inbound Stedi webhook verification tri-state."""

    VERIFIED = "verified"
    NOT_VERIFIED = "not_verified"
    UNKNOWN = "unknown"


class StediReadinessBlockerOwner(str, Enum):
    """Who must clear a Stedi readiness blocker."""

    AGENCY = "agency"
    ADAPTIX = "adaptix"
    PAYER = "payer"


class StediMigrationMode(str, Enum):
    """Server-enforced Stedi migration modes.

    ``office_ally_active`` is retained as a legacy/source-mode wire value for
    migration compatibility. It must not be interpreted by contract consumers as
    permission to route new live claims through Office Ally.
    """

    OFFICE_ALLY_ACTIVE = "office_ally_active"
    STEDI_SHADOW = "stedi_shadow"
    STEDI_TEST = "stedi_test"
    STEDI_PRIMARY = "stedi_primary"
    OFFICE_ALLY_READ_ONLY = "office_ally_read_only"
    MIGRATION_BLOCKED = "migration_blocked"


class StediMigrationTransitionKind(str, Enum):
    """Classification of a migration-mode transition."""

    ADVANCE = "advance"
    ROLLBACK = "rollback"
    BLOCK = "block"
    RECOVER = "recover"


class StediEnrollmentTransactionType(str, Enum):
    """Logical transaction types accepted by the Stedi enrollment API."""

    CLAIMS = "claims"
    ERA = "era"
    ELIGIBILITY = "eligibility"


class StediPayerEnrollmentStatus(str, Enum):
    """Adaptix-normalized Stedi payer-enrollment lifecycle."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    PENDING = "pending"
    LIVE = "live"
    REJECTED = "rejected"
    CANCELED = "canceled"
    UNKNOWN = "unknown"


class SubmissionAttemptStatus(str, Enum):
    """Persisted claim-submission attempt lifecycle statuses."""

    PENDING = "pending"
    PREFLIGHT_FAILED = "preflight_failed"
    QUEUED = "queued"
    TRANSMITTED = "transmitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    RESUBMIT_REQUIRED = "resubmit_required"


class RemittancePostingStatus(str, Enum):
    """Derived posting status for parsed 835 remittances."""

    POSTED = "posted"
    UNPOSTED = "unposted"


class SubmissionFrequency(str, Enum):
    """Migration-source polling/submission cadence."""

    DAILY = "daily"
    WEEKLY = "weekly"


class StediArtifactTransactionKind(str, Enum):
    """Kinds of Stedi artifacts the reconciler classifies."""

    FILE_DELIVERED = "file_delivered"
    FILE_FAILED = "file_failed"
    ACK_999 = "ack_999"
    ACK_277CA = "ack_277ca"
    REMITTANCE_835 = "remittance_835"


class StediClaimTransition(str, Enum):
    """Claim transition emitted by normalized Stedi artifact reconciliation."""

    DELIVERED_TO_PAYER = "delivered_to_payer"
    DELIVERY_FAILED = "delivery_failed"
    ACK_ACCEPTED = "ack_accepted"
    ACK_REJECTED = "ack_rejected"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DENIED = "denied"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    UNDETERMINED = "undetermined"


class StediWebhookProcessingStatus(str, Enum):
    """Durable Stedi webhook receipt processing statuses."""

    RECEIVED = "received"
    QUEUED = "queued"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    PENDING_RECONCILIATION = "pending_reconciliation"
    RECEIVED_UNKNOWN_TYPE = "received_unknown_type"


# ---------------------------------------------------------------------------
# Stedi readiness + migration-mode contracts
# ---------------------------------------------------------------------------


class StediProviderRow(BaseModel):
    """One tenant billing-provider identity row for Stedi readiness."""

    provider_id: str
    provider_name: Optional[str] = None
    npi_masked: Optional[str] = None
    state: StediReadinessState


class StediPayerRow(BaseModel):
    """One Stedi payer enrollment row and whether enrollment is required."""

    payer_id: str
    payer_name: Optional[str] = None
    state: StediReadinessState
    enrollment_required: bool


class StediWebhookStatus(BaseModel):
    """Tri-state inbound-webhook verification for Stedi events."""

    verification: StediWebhookVerification
    last_event_at: Optional[str] = None


class StediStatusBlocker(BaseModel):
    """One readiness blocker surfaced to UI and migration-mode gates."""

    code: str
    label: str
    section: str
    owner: StediReadinessBlockerOwner


class StediStatusResponse(BaseModel):
    """GET /api/v1/billing/stedi/status response."""

    tenant_id: str
    state: StediReadinessState
    checked_at: Optional[str] = None
    providers: list[StediProviderRow]
    payers: list[StediPayerRow]
    webhook: StediWebhookStatus
    blockers: list[StediStatusBlocker]


class StediAllowedTransition(BaseModel):
    """One legal migration-mode transition returned by the backend."""

    to_mode: StediMigrationMode
    kind: StediMigrationTransitionKind
    requires_founder: bool
    caller_authorized: bool
    description: str


class StediMigrationModeResponse(BaseModel):
    """GET /api/v1/billing/stedi/migration-mode response."""

    tenant_id: str
    mode: StediMigrationMode
    description: str
    updated_by: Optional[str] = None
    last_reason: Optional[str] = None
    updated_at: Optional[str] = None
    is_default: bool
    allowed_transitions: list[StediAllowedTransition]


class StediMigrationTransitionRequest(BaseModel):
    """POST /api/v1/billing/stedi/migration-mode/transition request."""

    to_mode: StediMigrationMode
    reason: str = Field(..., min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def _reason_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("reason must not be blank")
        return cleaned


class StediMigrationTransitionResponse(BaseModel):
    """Response for a successful audited migration-mode transition."""

    transition_id: str
    tenant_id: str
    from_mode: StediMigrationMode
    to_mode: StediMigrationMode
    kind: StediMigrationTransitionKind
    reason: str
    actor_id: Optional[str] = None
    actor_role: Optional[str] = None
    founder_authorized: bool
    occurred_at: str


class StediMigrationTransitionHistoryRow(BaseModel):  # pylint: disable=invalid-name
    """One append-only migration-mode audit row."""

    id: str
    tenant_id: str
    from_mode: Optional[StediMigrationMode] = None
    to_mode: StediMigrationMode
    kind: StediMigrationTransitionKind
    reason: str
    actor_id: Optional[str] = None
    actor_role: Optional[str] = None
    founder_authorized: bool
    created_at: str


class StediCreateEnrollmentRequest(BaseModel):
    """POST /api/v1/billing/stedi/enrollments request body."""

    model_config = ConfigDict(extra="forbid")

    payer_id: str = Field(..., min_length=1, max_length=80)
    payer_name: Optional[str] = Field(None, max_length=200)
    transaction_types: list[StediEnrollmentTransactionType] = Field(..., min_length=1)

    @field_validator("payer_id")
    @classmethod
    def _payer_id_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("payer_id must not be blank")
        return cleaned


class StediCreateEnrollmentResponse(BaseModel):
    """Response for a successful Stedi payer-enrollment initiation."""

    enrollment_id: str
    stedi_enrollment_id: str
    status: StediPayerEnrollmentStatus
    payer_id: str
    transaction_types: list[StediEnrollmentTransactionType]


class MigrationSourceClearinghouseSettingsResponse(BaseModel):
    """Read-only/import clearinghouse settings for a tenant.

    ``clearinghouse_vendor`` is the migration source/incumbent vendor. It is
    not a live submission route; live claim submission remains STEDI-only.
    """

    tenant_id: str
    clearinghouse_vendor: MigrationSourceVendor
    oa_sftp_username: Optional[str] = None
    oa_tpid: Optional[str] = None
    oa_sftp_verified: bool
    edi_837p_enabled: bool
    edi_835_enabled: bool
    edi_999_enabled: bool
    edi_277_enabled: bool
    submission_frequency: SubmissionFrequency
    updated_at: Optional[str] = None


class MigrationSourceClearinghouseSettingsUpdate(BaseModel):
    """PUT body for migration-source clearinghouse settings."""

    model_config = ConfigDict(extra="forbid")

    clearinghouse_vendor: MigrationSourceVendor = Field(
        default=MigrationSourceVendor.OFFICE_ALLY
    )
    oa_sftp_username: Optional[str] = Field(None, max_length=200)
    oa_tpid: Optional[str] = Field(None, max_length=50)
    oa_sftp_verified: bool = False
    edi_837p_enabled: bool = True
    edi_835_enabled: bool = True
    edi_999_enabled: bool = True
    edi_277_enabled: bool = True
    submission_frequency: SubmissionFrequency = SubmissionFrequency.DAILY


class SubmissionSummaryResponse(BaseModel):
    """Tenant submission-attempt roll-up grouped by persisted status."""

    availability: str
    by_status: dict[SubmissionAttemptStatus, int] = Field(default_factory=dict)
    total_queued: int = Field(..., ge=0)
    total_transmitted: int = Field(..., ge=0)
    total_accepted: int = Field(..., ge=0)
    total_rejected: int = Field(..., ge=0)
    as_of: str


class RemittanceSummary(BaseModel):
    """Parsed 835 remittance summary with posting status."""

    id: str
    era_check_number: Optional[str] = None
    payer_name: Optional[str] = None
    payer_id: Optional[str] = None
    total_paid_cents: int = Field(..., ge=0)
    claim_count: int = Field(..., ge=0)
    source_filename: Optional[str] = None
    received_at: Optional[str] = None
    posting_status: RemittancePostingStatus


class RemittanceListResponse(BaseModel):
    """GET /api/v1/billing/eob/remittances response."""

    items: list[RemittanceSummary]
    count: int = Field(..., ge=0)
    unposted_count: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
    offset: int = Field(..., ge=0)


class StediServiceLineOutcome(BaseModel):
    """One 835 service-line adjudication result used for reconciliation."""

    billed_cents: int = Field(..., ge=0)
    paid_cents: int = Field(..., ge=0)
    denied: bool = False
    patient_responsibility_cents: int = Field(0, ge=0)


class StediNormalizedArtifact(BaseModel):
    """Provider-agnostic Stedi artifact view used by the state machine."""

    kind: StediArtifactTransactionKind
    ack_accepted: Optional[bool] = None
    syntactic_accepted: Optional[bool] = None
    service_lines: list[StediServiceLineOutcome] = Field(default_factory=list)


class StediNormalizationResult(BaseModel):
    """Normalized artifact plus tenant/claim reference for reconciliation."""

    artifact: StediNormalizedArtifact
    tenant_id: Optional[str] = None
    claim_ref: Optional[str] = None


class StediWebhookReconcileOutcome(BaseModel):
    """Worker outcome for one durable Stedi webhook receipt."""

    status: StediWebhookProcessingStatus
    detail: str = ""


# ---------------------------------------------------------------------------
# Submission Contracts
# ---------------------------------------------------------------------------


class ClaimSubmissionRequest(BaseModel):
    """Request to submit a claim to the live billing clearinghouse (STEDI only)."""

    claim_id: str
    tenant_id: str

    provider: ClearinghouseProvider
    edi_payload: str = Field(..., description="X12 837 payload")

    submitted_by_user_id: Optional[str] = None


class ClaimSubmissionResponse(BaseModel):
    """Response after attempting submission to the live clearinghouse."""

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

    STEDI is the only valid target for new/live outbound billing submissions.
    Migration/source vendors may appear as historical originals, but this
    contract must not let clients target Office Ally/Waystar/Availity as live
    submitters. ``acknowledge_duplicate_risk`` must be true to proceed when the
    original transmission state is ``unknown``.
    """

    target_clearinghouse_slug: ClearinghouseProvider
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
    target_clearinghouse_slug: ClearinghouseProvider
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
    target_slug: ClearinghouseProvider
    transmission_state: str
