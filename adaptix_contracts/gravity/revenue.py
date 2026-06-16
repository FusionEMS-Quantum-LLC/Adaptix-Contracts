"""
GRAVITY REVENUE CONTRACTS
ADAPTIX_PLATFORM_GRAVITY_COMPLETION_LOCK
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class PaymentFailureState(str, Enum):
    OPEN = "open"
    RETRYING = "retrying"
    RESOLVED = "resolved"
    WRITTEN_OFF = "written_off"


class ChurnRisk(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RevenueOverviewResponse(BaseModel):
    mrr: int  # cents
    arr: int  # cents
    mrr_delta: int
    mrr_delta_pct: float
    arr_delta: int
    active_subscriptions: int
    trialing: int
    past_due: int
    churn_rate_pct: float
    expansion_mrr: int
    contraction_mrr: int
    net_new_mrr: int
    payment_failure_count: int
    generated_at: datetime


class PaymentFailureResponse(BaseModel):
    id: str
    tenant_id: str
    customer_id: str
    customer_name: str
    invoice_id: str
    amount_cents: int
    currency: str
    failure_reason: str
    state: PaymentFailureState
    attempt_count: int
    next_retry_at: datetime | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ChurnRiskScoreResponse(BaseModel):
    customer_id: str
    customer_name: str
    risk: ChurnRisk
    score: float
    signals: list[str]
    mrr_at_risk: int
    last_activity_at: datetime | None = None


class RevenueForecastResponse(BaseModel):
    period: str
    projected_mrr: int
    projected_arr: int
    confidence: float
    churn_risk_mrr: int
    expansion_opportunity_mrr: int
    generated_at: datetime


class RetryPaymentResponse(BaseModel):
    failure: PaymentFailureResponse
    audit_event_id: str
