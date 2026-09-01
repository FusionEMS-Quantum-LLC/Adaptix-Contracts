"""Adaptix Third-Party Billing portal home and operational contracts.

Defines typed shapes for the authenticated billing command portal:
priority queue summaries, claims, denials, AR, patient financial,
integration health, analytics, and founder oversight surfaces.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

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
    unavailable_reason: Optional[str] = None
    new_intake_ready_count: Optional[int] = Field(default=None, ge=0)
    blocked_claims_count: Optional[int] = Field(default=None, ge=0)
    claim_defects_count: Optional[int] = Field(default=None, ge=0)
    timely_filing_risk_count: Optional[int] = Field(default=None, ge=0)
    as_of: Optional[datetime] = None


class BillingBlockedClaimsSummary(BaseModel):
    availability: SurfaceAvailability
    unavailable_reason: Optional[str] = None
    total_blocked: Optional[int] = Field(default=None, ge=0)
    top_block_reasons: Optional[list[str]] = None
    estimated_revenue_at_risk_cents: Optional[int] = Field(default=None, ge=0)
    as_of: Optional[datetime] = None


class BillingDenialQueueSummary(BaseModel):
    availability: SurfaceAvailability
    unavailable_reason: Optional[str] = None
    total_open_denials: Optional[int] = Field(default=None, ge=0)
    high_value_denial_count: Optional[int] = Field(default=None, ge=0)
    appeal_eligible_count: Optional[int] = Field(default=None, ge=0)
    total_denied_revenue_cents: Optional[int] = Field(default=None, ge=0)
    as_of: Optional[datetime] = None


class BillingAgedARSummary(BaseModel):
    availability: SurfaceAvailability
    unavailable_reason: Optional[str] = None
    bucket_0_30_cents: Optional[int] = Field(default=None, ge=0)
    bucket_31_60_cents: Optional[int] = Field(default=None, ge=0)
    bucket_61_90_cents: Optional[int] = Field(default=None, ge=0)
    bucket_91_120_cents: Optional[int] = Field(default=None, ge=0)
    bucket_over_120_cents: Optional[int] = Field(default=None, ge=0)
    total_ar_cents: Optional[int] = Field(default=None, ge=0)
    recoverable_estimate_cents: Optional[int] = Field(default=None, ge=0)
    as_of: Optional[datetime] = None


class BillingUnderpaymentSummary(BaseModel):
    availability: SurfaceAvailability
    unavailable_reason: Optional[str] = None
    total_underpayment_candidates: Optional[int] = Field(default=None, ge=0)
    estimated_underpayment_cents: Optional[int] = Field(default=None, ge=0)
    as_of: Optional[datetime] = None


class BillingPatientFinancialSummary(BaseModel):
    availability: SurfaceAvailability
    unavailable_reason: Optional[str] = None
    outstanding_balance_cents: Optional[int] = Field(default=None, ge=0)
    payment_plans_active: Optional[int] = Field(default=None, ge=0)
    disputes_open: Optional[int] = Field(default=None, ge=0)
    statements_pending_delivery: Optional[int] = Field(default=None, ge=0)
    as_of: Optional[datetime] = None


class BillingIntegrationHealthSummary(BaseModel):
    availability: SurfaceAvailability
    unavailable_reason: Optional[str] = None
    connectors_healthy: Optional[int] = Field(default=None, ge=0)
    connectors_failing: Optional[int] = Field(default=None, ge=0)
    webhook_failures_pending: Optional[int] = Field(default=None, ge=0)
    credential_expiry_warnings: Optional[int] = Field(default=None, ge=0)
    mapping_drift_detected: Optional[bool] = None
    as_of: Optional[datetime] = None


class BillingOperatorSummary(BaseModel):
    availability: SurfaceAvailability
    unavailable_reason: Optional[str] = None
    operator_name: Optional[str] = None
    role: Optional[str] = None
    claims_worked_today: Optional[int] = Field(default=None, ge=0)
    revenue_touched_today_cents: Optional[int] = Field(default=None, ge=0)
    queue_pressure: Optional[str] = None
    recommended_next_action: Optional[str] = None
    as_of: Optional[datetime] = None


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
    remediation_hint: Optional[str] = None


class ClaimReadinessSummary(BaseModel):
    claim_id: str
    readiness_score: int = Field(..., ge=0, le=100)
    is_billable: bool
    defects: list[ClaimDefect]
    urgency: UrgencyLevel
    estimated_value_cents: Optional[int] = Field(default=None, ge=0)
    evaluated_at: datetime


class ClaimIntakeRecord(BaseModel):
    claim_id: str
    patient_id: str
    encounter_date: Optional[str] = None
    transport_type: Optional[str] = None
    payer_name: Optional[str] = None
    readiness_score: Optional[int] = Field(default=None, ge=0, le=100)
    urgency: UrgencyLevel
    status: str
    created_at: datetime


# ---------------- Submission ----------------


class SubmissionAttempt(BaseModel):
    attempt_id: str
    claim_id: str
    batch_id: Optional[str] = None
    clearinghouse: str
    status: str
    error_code: Optional[str] = None
    error_description: Optional[str] = None
    submitted_at: Optional[datetime] = None
    response_received_at: Optional[datetime] = None
    retry_count: int = Field(default=0, ge=0)


class SubmissionTimelineEvent(BaseModel):
    event_type: str
    description: str
    occurred_at: datetime
    actor: Optional[str] = None


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
    follow_up_due_date: Optional[str] = None


class DenialCluster(BaseModel):
    cluster_id: str
    root_cause_label: str
    denial_count: int = Field(..., ge=0)
    total_denied_cents: int = Field(..., ge=0)
    top_payers: list[str]
    recommended_action: str


class DenialRootCauseSummary(BaseModel):
    availability: SurfaceAvailability
    unavailable_reason: Optional[str] = None
    top_causes: Optional[list[DenialCluster]] = None
    as_of: Optional[datetime] = None


class DenialRecoveryForecast(BaseModel):
    availability: SurfaceAvailability
    unavailable_reason: Optional[str] = None
    estimated_recoverable_cents: Optional[int] = Field(default=None, ge=0)
    appeal_yield_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    high_confidence_count: Optional[int] = Field(default=None, ge=0)
    as_of: Optional[datetime] = None


# ---------------- Founder ----------------


class FounderTenantFinancialSummary(BaseModel):
    tenant_id: str
    tenant_name: str
    total_charges_cents: Optional[int] = Field(default=None, ge=0)
    total_paid_cents: Optional[int] = Field(default=None, ge=0)
    outstanding_ar_cents: Optional[int] = Field(default=None, ge=0)
    denial_rate_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    recovery_opportunity_cents: Optional[int] = Field(default=None, ge=0)
    integration_health: Optional[str] = None
    as_of: Optional[datetime] = None


class FounderBillingOverview(BaseModel):
    availability: SurfaceAvailability
    unavailable_reason: Optional[str] = None
    total_tenants: Optional[int] = Field(default=None, ge=0)
    tenants_with_ar_risk: Optional[int] = Field(default=None, ge=0)
    total_recovery_opportunity_cents: Optional[int] = Field(default=None, ge=0)
    total_integration_failures: Optional[int] = Field(default=None, ge=0)
    migrations_in_progress: Optional[int] = Field(default=None, ge=0)
    as_of: Optional[datetime] = None
