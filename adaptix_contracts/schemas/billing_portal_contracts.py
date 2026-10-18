"""Adaptix Third-Party Billing portal home and operational contracts.

Defines typed shapes for the authenticated billing command portal:
priority queue summaries, claims, denials, AR, patient financial,
integration health, analytics, and founder oversight surfaces.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SurfaceAvailability(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    LOADING = "loading"


class UrgencyLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ---------------- Portal Home ----------------


class BillingPriorityQueueSummary(BaseModel):
    availability: SurfaceAvailability
    unavailable_reason: str | None = None
    new_intake_ready_count: int | None = Field(default=None, ge=0)
    blocked_claims_count: int | None = Field(default=None, ge=0)
    claim_defects_count: int | None = Field(default=None, ge=0)
    timely_filing_risk_count: int | None = Field(default=None, ge=0)
    as_of: datetime | None = None


class BillingBlockedClaimsSummary(BaseModel):
    availability: SurfaceAvailability
    unavailable_reason: str | None = None
    total_blocked: int | None = Field(default=None, ge=0)
    top_block_reasons: list[str] | None = None
    estimated_revenue_at_risk_cents: int | None = Field(default=None, ge=0)
    as_of: datetime | None = None


class BillingDenialQueueSummary(BaseModel):
    availability: SurfaceAvailability
    unavailable_reason: str | None = None
    total_open_denials: int | None = Field(default=None, ge=0)
    high_value_denial_count: int | None = Field(default=None, ge=0)
    appeal_eligible_count: int | None = Field(default=None, ge=0)
    total_denied_revenue_cents: int | None = Field(default=None, ge=0)
    as_of: datetime | None = None


class BillingAgedARSummary(BaseModel):
    availability: SurfaceAvailability
    unavailable_reason: str | None = None
    bucket_0_30_cents: int | None = Field(default=None, ge=0)
    bucket_31_60_cents: int | None = Field(default=None, ge=0)
    bucket_61_90_cents: int | None = Field(default=None, ge=0)
    bucket_91_120_cents: int | None = Field(default=None, ge=0)
    bucket_over_120_cents: int | None = Field(default=None, ge=0)
    total_ar_cents: int | None = Field(default=None, ge=0)
    recoverable_estimate_cents: int | None = Field(default=None, ge=0)
    as_of: datetime | None = None


class BillingUnderpaymentSummary(BaseModel):
    availability: SurfaceAvailability
    unavailable_reason: str | None = None
    total_underpayment_candidates: int | None = Field(default=None, ge=0)
    estimated_underpayment_cents: int | None = Field(default=None, ge=0)
    as_of: datetime | None = None


class BillingPatientFinancialSummary(BaseModel):
    availability: SurfaceAvailability
    unavailable_reason: str | None = None
    outstanding_balance_cents: int | None = Field(default=None, ge=0)
    payment_plans_active: int | None = Field(default=None, ge=0)
    disputes_open: int | None = Field(default=None, ge=0)
    statements_pending_delivery: int | None = Field(default=None, ge=0)
    as_of: datetime | None = None


class BillingIntegrationHealthSummary(BaseModel):
    availability: SurfaceAvailability
    unavailable_reason: str | None = None
    connectors_healthy: int | None = Field(default=None, ge=0)
    connectors_failing: int | None = Field(default=None, ge=0)
    webhook_failures_pending: int | None = Field(default=None, ge=0)
    credential_expiry_warnings: int | None = Field(default=None, ge=0)
    mapping_drift_detected: bool | None = None
    as_of: datetime | None = None


class BillingOperatorSummary(BaseModel):
    availability: SurfaceAvailability
    unavailable_reason: str | None = None
    operator_name: str | None = None
    role: str | None = None
    claims_worked_today: int | None = Field(default=None, ge=0)
    revenue_touched_today_cents: int | None = Field(default=None, ge=0)
    queue_pressure: str | None = None
    recommended_next_action: str | None = None
    as_of: datetime | None = None


class BillingPortalHomeSummary(BaseModel):
    tenant_id: str
    user_id: str
    generated_at: datetime

    priority_queue: BillingPriorityQueueSummary
    blocked_claims: BillingBlockedClaimsSummary
    denial_queue: BillingDenialQueueSummary
    aged_ar: BillingAgedARSummary
    underpayments: BillingUnderpaymentSummary
    patient_financial: BillingPatientFinancialSummary
    integration_health: BillingIntegrationHealthSummary
    operator: BillingOperatorSummary


# ---------------- Claims ----------------


class ClaimDefectSeverity(str, Enum):
    BLOCKING = "blocking"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ClaimDefect(BaseModel):
    field_name: str
    defect_type: str
    severity: ClaimDefectSeverity
    description: str
    remediation_hint: str | None = None


class ClaimReadinessSummary(BaseModel):
    claim_id: str
    readiness_score: int = Field(..., ge=0, le=100)
    is_billable: bool
    defects: list[ClaimDefect]
    urgency: UrgencyLevel
    estimated_value_cents: int | None = Field(default=None, ge=0)
    evaluated_at: datetime


class ClaimIntakeRecord(BaseModel):
    claim_id: str
    patient_id: str
    encounter_date: str | None = None
    transport_type: str | None = None
    payer_name: str | None = None
    readiness_score: int | None = Field(default=None, ge=0, le=100)
    urgency: UrgencyLevel
    status: str
    created_at: datetime


# ---------------- Submission ----------------


class SubmissionAttempt(BaseModel):
    attempt_id: str
    claim_id: str
    batch_id: str | None = None
    clearinghouse: str
    status: str
    error_code: str | None = None
    error_description: str | None = None
    submitted_at: datetime | None = None
    response_received_at: datetime | None = None
    retry_count: int = Field(default=0, ge=0)


class SubmissionTimelineEvent(BaseModel):
    event_type: str
    description: str
    occurred_at: datetime
    actor: str | None = None


# ---------------- Denials ----------------


class DenialRecord(BaseModel):
    denial_id: str
    claim_id: str
    patient_id: str
    payer_name: str
    denial_reason_code: str
    denial_reason_description: str
    denied_amount_cents: int = Field(..., ge=0)
    appeal_eligible: bool
    urgency: UrgencyLevel
    received_at: datetime
    follow_up_due_date: str | None = None


class DenialCluster(BaseModel):
    cluster_id: str
    root_cause_label: str
    denial_count: int = Field(..., ge=0)
    total_denied_cents: int = Field(..., ge=0)
    top_payers: list[str]
    recommended_action: str


class DenialRootCauseSummary(BaseModel):
    availability: SurfaceAvailability
    unavailable_reason: str | None = None
    top_causes: list[DenialCluster] | None = None
    as_of: datetime | None = None


class DenialRecoveryForecast(BaseModel):
    availability: SurfaceAvailability
    unavailable_reason: str | None = None
    estimated_recoverable_cents: int | None = Field(default=None, ge=0)
    appeal_yield_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    high_confidence_count: int | None = Field(default=None, ge=0)
    as_of: datetime | None = None


# ---------------- Founder ----------------


class FounderTenantFinancialSummary(BaseModel):
    tenant_id: str
    tenant_name: str
    total_charges_cents: int | None = Field(default=None, ge=0)
    total_paid_cents: int | None = Field(default=None, ge=0)
    outstanding_ar_cents: int | None = Field(default=None, ge=0)
    denial_rate_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    recovery_opportunity_cents: int | None = Field(default=None, ge=0)
    integration_health: str | None = None
    as_of: datetime | None = None


class FounderBillingOverview(BaseModel):
    availability: SurfaceAvailability
    unavailable_reason: str | None = None
    total_tenants: int | None = Field(default=None, ge=0)
    tenants_with_ar_risk: int | None = Field(default=None, ge=0)
    total_recovery_opportunity_cents: int | None = Field(default=None, ge=0)
    total_integration_failures: int | None = Field(default=None, ge=0)
    migrations_in_progress: int | None = Field(default=None, ge=0)
    as_of: datetime | None = None
