"""Billing domain core contracts for cross-domain communication.

Defines foundational billing entities, claim lifecycle, remittance,
payments, denials, clearinghouse interaction events, payer references,
and claim line-level billing details.

These contracts are the authoritative source for all billing domain
data exchanged across Adaptix services.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ClaimStatus(str, Enum):
    """Lifecycle status of a billing claim."""

    DRAFT = "draft"
    READY = "ready"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DENIED = "denied"
    APPEALING = "appealing"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    CLOSED = "closed"


class DenialStatus(str, Enum):
    """Lifecycle status of a denial."""

    OPEN = "open"
    IN_APPEAL = "in_appeal"
    RESOLVED = "resolved"
    WRITTEN_OFF = "written_off"


class PaymentStatus(str, Enum):
    """Lifecycle status of a payment."""

    POSTED = "posted"
    PENDING = "pending"
    FAILED = "failed"


class ClearinghouseStatus(str, Enum):
    """Claim submission state at the clearinghouse layer."""

    QUEUED = "queued"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ERROR = "error"


class LiveBillingClearinghouse(str, Enum):
    """Clearinghouse allowed to transmit live Adaptix billing claims.

    STEDI is the sole live billing clearinghouse. Legacy clearinghouses are
    represented by ``MigrationSourceVendor`` and must only be used for
    migration/import/read-only tails.
    """

    STEDI = "stedi"


class ClearinghouseProvider(str, Enum):
    """Backward-compatible name for the live billing clearinghouse enum."""

    STEDI = "stedi"


class MigrationSourceVendor(str, Enum):
    """Legacy/import vendor vocabulary; never a live claim-submission target."""

    OFFICE_ALLY = "office_ally"
    WAYSTAR = "waystar"
    AVAILITY = "availity"
    CHANGE_HEALTHCARE = "change_healthcare"
    TRIZETTO = "trizetto"
    OTHER = "other"
    NONE_YET = "none_yet"


class PayerType(str, Enum):
    """Classification of payer entities."""

    MEDICARE = "medicare"
    MEDICAID = "medicaid"
    COMMERCIAL = "commercial"
    SELF_PAY = "self_pay"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Core Contracts
# ---------------------------------------------------------------------------


class ClaimLineItem(BaseModel):
    """A single billable service line on a claim."""

    line_id: str
    procedure_code: str
    modifier_codes: list[str] = Field(default_factory=list)
    diagnosis_codes: list[str] = Field(default_factory=list)

    units: int = Field(..., gt=0)
    charge_cents: int = Field(..., ge=0)

    description: Optional[str] = None


class AdjustmentContract(BaseModel):
    """Financial adjustment applied to a claim."""

    adjustment_id: str
    claim_id: str
    tenant_id: str

    adjustment_type: str
    amount_cents: int = Field(..., ge=0)

    reason_code: Optional[str] = None
    applied_at: datetime


class PayerContract(BaseModel):
    """Read-only payer reference contract."""

    payer_id: str
    payer_name: str
    payer_type: PayerType

    electronic_claims_supported: bool
    electronic_remittance_supported: bool

    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None


class ClaimContract(BaseModel):
    """Canonical claim record for cross-domain consumption."""

    claim_id: str
    tenant_id: str
    patient_id: str

    encounter_id: Optional[str] = None
    transport_request_id: Optional[str] = None

    payer_id: Optional[str] = None
    payer_name: Optional[str] = None

    status: ClaimStatus

    total_charge_cents: int = Field(..., ge=0)
    total_paid_cents: int = Field(0, ge=0)
    total_adjustment_cents: int = Field(0, ge=0)
    balance_cents: int = Field(..., ge=0)

    line_items: list[ClaimLineItem] = Field(default_factory=list)

    created_at: datetime
    updated_at: datetime
    submitted_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None


class DenialContract(BaseModel):
    """Denial record tied to a claim."""

    denial_id: str
    claim_id: str
    tenant_id: str

    reason_code: str
    reason_description: str

    denied_amount_cents: int = Field(..., ge=0)
    status: DenialStatus

    received_at: datetime
    updated_at: datetime


class PaymentContract(BaseModel):
    """Payment record applied to a claim."""

    payment_id: str
    claim_id: str
    tenant_id: str

    amount_cents: int = Field(..., ge=0)
    payer_name: Optional[str] = None

    status: PaymentStatus
    posted_at: datetime


class RemittanceContract(BaseModel):
    """Remittance (ERA/EOB) summary contract."""

    remit_id: str
    tenant_id: str
    payer_name: str

    total_paid_cents: int = Field(..., ge=0)
    total_adjusted_cents: int = Field(..., ge=0)

    received_at: datetime


class ClearinghouseSubmission(BaseModel):
    """Claim submission tracking via clearinghouse."""

    submission_id: str
    claim_id: str
    tenant_id: str

    provider: ClearinghouseProvider
    status: ClearinghouseStatus

    submitted_at: Optional[datetime] = None
    response_received_at: Optional[datetime] = None
    error_message: Optional[str] = None


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


class ClaimCreatedEvent(BaseModel):
    """Published when a claim is created."""

    event_type: str = "billing.claim.created"

    claim_id: str
    tenant_id: str
    patient_id: str

    created_at: datetime


class ClaimSubmittedEvent(BaseModel):
    """Published when a claim is submitted."""

    event_type: str = "billing.claim.submitted"

    claim_id: str
    tenant_id: str
    submission_id: str
    provider: ClearinghouseProvider
    submitted_at: datetime


class ClaimStatusUpdatedEvent(BaseModel):
    """Published when a claim status changes.

    Canonical ePCR back-channel event. Whenever a claim enters one of the
    revenue-terminal states (``paid``, ``denied``, ``partially_paid``,
    ``appealing``), Billing emits this event so the ePCR chart that
    originated the claim (via ``encounter_id``) can render the billing
    outcome without a manual reload.

    ``status`` is the *new* status — kept alongside the original
    ``new_status`` field for backward compatibility with older consumers.
    Producers should populate both; consumers should prefer ``status`` when
    present and fall back to ``new_status`` otherwise.

    Financial fields (``total_paid_cents``, ``patient_balance_cents``,
    ``denial_reason_code``, ``payer_name``) are optional because not every
    status transition has settled balances at publish time (e.g. a fresh
    DENIED before any 835 has applied). The ePCR consumer treats missing
    values as "not yet reported" rather than zero.
    """

    event_type: str = "billing.claim.status_updated"

    claim_id: str
    tenant_id: str
    encounter_id: Optional[str] = None
    status: Optional[ClaimStatus] = None
    old_status: Optional[ClaimStatus] = None
    new_status: Optional[ClaimStatus] = None
    total_paid_cents: Optional[int] = None
    patient_balance_cents: Optional[int] = None
    denial_reason_code: Optional[str] = None
    payer_name: Optional[str] = None
    updated_at: datetime


class DenialCreatedEvent(BaseModel):
    """Published when a denial is created."""

    event_type: str = "billing.denial.created"

    denial_id: str
    claim_id: str
    tenant_id: str
    created_at: datetime


class PaymentPostedEvent(BaseModel):
    """Published when a payment is applied to a claim."""

    event_type: str = "billing.payment.posted"

    payment_id: str
    claim_id: str
    tenant_id: str
    amount_cents: int = Field(..., ge=0)
    payer_id: Optional[str] = None
    posted_at: datetime


class RemittanceReceivedEvent(BaseModel):
    """Published when a remittance is received."""

    event_type: str = "billing.remittance.received"

    remit_id: str
    tenant_id: str
    received_at: datetime
