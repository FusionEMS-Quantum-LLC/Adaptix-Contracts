"""Patient portal contract schemas for cross-domain communication.

Defines all typed request and response contracts for the patient-facing
financial trust layer: verification, account summary, statement history,
payment workflows, payment plans, disputes, document history,
communication history, AI charge explanations, and support escalation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PatientVerificationMethod(str, Enum):
    NAME_DOB_ACCOUNT = "name_dob_account"
    NAME_DOB_LAST4_SSN = "name_dob_last4_ssn"
    TOKEN_LINK = "token_link"


class PaymentMethod(str, Enum):
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    ACH = "ach"
    CHECK = "check"


class DisputeReason(str, Enum):
    INSURANCE_SHOULD_COVER = "insurance_should_cover"
    SERVICE_NOT_RECEIVED = "service_not_received"
    AMOUNT_INCORRECT = "amount_incorrect"
    DUPLICATE_CHARGE = "duplicate_charge"
    FINANCIAL_HARDSHIP = "financial_hardship"
    OTHER = "other"


class PatientVerifyRequest(BaseModel):
    verification_method: PatientVerificationMethod
    patient_name: str = Field(..., max_length=255)
    date_of_birth: str = Field(..., description="ISO 8601 date: YYYY-MM-DD")
    account_last4: Optional[str] = Field(default=None, min_length=4, max_length=4)
    ssn_last4: Optional[str] = Field(default=None, min_length=4, max_length=4)
    access_token: Optional[str] = Field(
        default=None, description="Used with token_link method"
    )


class PatientVerifyResponse(BaseModel):
    session_token: str
    patient_account_id: str
    patient_name: str
    verified_at: datetime
    session_expires_at: datetime


class PatientAccountSummary(BaseModel):
    account_id: str
    patient_name: str
    outstanding_balance_cents: int
    last_statement_date: Optional[datetime] = None
    active_payment_plan: bool
    open_disputes: int
    unread_documents: int
    last_communication_at: Optional[datetime] = None


class StatementSummaryResponse(BaseModel):
    id: str
    account_id: str
    statement_date: datetime
    service_date: Optional[datetime] = None
    total_billed_cents: int
    insurance_paid_cents: int
    adjustments_cents: int
    patient_responsibility_cents: int
    amount_paid_cents: int
    balance_due_cents: int
    status: str
    due_date: Optional[datetime] = None


class StatementLineItem(BaseModel):
    description: str
    service_date: Optional[datetime] = None
    billed_cents: int
    insurance_paid_cents: int
    patient_responsibility_cents: int
    code: Optional[str] = None


class StatementDetailResponse(BaseModel):
    id: str
    account_id: str
    statement_date: datetime
    service_date: Optional[datetime] = None
    total_billed_cents: int
    insurance_paid_cents: int
    adjustments_cents: int
    patient_responsibility_cents: int
    amount_paid_cents: int
    balance_due_cents: int
    status: str
    due_date: Optional[datetime] = None
    line_items: list[StatementLineItem]
    transport_id: Optional[str] = None
    encounter_id: Optional[str] = None


class PaymentOptionResponse(BaseModel):
    accepts_credit_card: bool
    accepts_ach: bool
    payment_plan_eligible: bool
    minimum_payment_cents: int
    outstanding_balance_cents: int
    payment_plan_minimum_monthly_cents: Optional[int] = None


class PaymentSubmitRequest(BaseModel):
    account_id: str
    statement_id: Optional[str] = None
    amount_cents: int = Field(..., gt=0)
    payment_method: PaymentMethod
    payment_token: str = Field(
        ..., description="Stripe token or ACH authorization token"
    )
    apply_to_oldest: bool = Field(
        default=True,
        description="Auto-apply to oldest balance if no statement specified",
    )


class PaymentSubmitResponse(BaseModel):
    payment_id: str
    account_id: str
    amount_cents: int
    status: str
    receipt_url: Optional[str] = None
    processed_at: datetime


class PaymentPlanRequest(BaseModel):
    account_id: str
    total_balance_cents: int
    requested_monthly_payment_cents: int = Field(..., gt=0)
    preferred_payment_day: int = Field(..., ge=1, le=28)
    payment_method: PaymentMethod
    payment_token: str


class PaymentPlanResponse(BaseModel):
    plan_id: str
    account_id: str
    total_balance_cents: int
    monthly_payment_cents: int
    estimated_months: int
    payment_day_of_month: int
    status: str
    next_payment_date: Optional[datetime] = None
    created_at: datetime


class DisputeSubmitRequest(BaseModel):
    account_id: str
    statement_id: Optional[str] = None
    reason: DisputeReason
    description: str = Field(..., min_length=10, max_length=2000)
    supporting_info: Optional[str] = Field(default=None, max_length=2000)


class DisputeSubmitResponse(BaseModel):
    dispute_id: str
    account_id: str
    status: str
    estimated_resolution_days: int
    submitted_at: datetime


class PatientDocumentResponse(BaseModel):
    id: str
    document_type: str
    document_name: str
    service_date: Optional[datetime] = None
    transport_id: Optional[str] = None
    signed: bool
    signed_at: Optional[datetime] = None
    download_url: Optional[str] = None
    created_at: datetime


class CommunicationEventResponse(BaseModel):
    id: str
    channel: str
    direction: str
    subject: Optional[str] = None
    summary: str
    sent_at: datetime
    delivery_status: str


class AiExplanationRequest(BaseModel):
    account_id: str
    statement_id: Optional[str] = None
    question: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional specific question from patient",
    )


class AiExplanationResponse(BaseModel):
    account_id: str
    statement_id: Optional[str] = None
    explanation: str
    disclaimer: str
    generated_at: datetime
    model_version: str


class SupportEscalationRequest(BaseModel):
    account_id: str
    issue_type: str = Field(..., max_length=100)
    description: str = Field(..., min_length=10, max_length=2000)
    preferred_contact_method: str = Field(..., description="email or phone")
    preferred_contact_value: str = Field(..., max_length=255)


class SupportEscalationResponse(BaseModel):
    ticket_id: str
    account_id: str
    status: str
    expected_response_hours: int
    created_at: datetime
