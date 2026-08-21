"""Founder intelligence contracts shared across Adaptix services."""

from __future__ import annotations

import enum
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class RevenueTimePeriod(str, enum.Enum):
    LAST_30 = "last_30"
    LAST_60 = "last_60"
    LAST_90 = "last_90"
    YTD = "ytd"
    CUSTOM = "custom"


class FounderRevenueMetricContract(BaseModel):
    tenant_id: UUID
    period: RevenueTimePeriod
    total_revenue: Decimal
    total_collected: Decimal
    total_outstanding: Decimal
    denial_rate: float
    appeal_success_rate: float
    average_days_to_payment: float
    claims_aging_0_30: int = 0
    claims_aging_31_60: int = 0
    claims_aging_61_90: int = 0
    claims_aging_90_plus: int = 0
    ai_high_risk_percentage: float = 0.0
    stripe_net_revenue: Decimal = Decimal("0")
    snapshot_at: datetime


class FounderOperatingExpenseContract(BaseModel):
    id: UUID
    tenant_id: UUID
    category: str
    description: str
    amount: Decimal
    incurred_date: date
    vendor: Optional[str] = None
    created_at: datetime


class FounderRevenueEntryContract(BaseModel):
    id: UUID
    tenant_id: UUID
    source: str
    amount: Decimal
    description: Optional[str] = None
    entry_date: date
    claim_id: Optional[UUID] = None
    payment_id: Optional[UUID] = None
    created_at: datetime


class FounderFinancialTransactionContract(BaseModel):
    id: UUID
    tenant_id: UUID
    transaction_type: str
    amount: Decimal
    description: str
    reference_id: Optional[UUID] = None
    reference_type: Optional[str] = None
    entry_date: date
    created_at: datetime


class FounderDashboardSummary(BaseModel):
    tenant_id: UUID
    revenue_metrics: FounderRevenueMetricContract
    total_claims: int
    open_claims: int
    denied_claims: int
    pending_appeals: int
    total_patients: int
    active_staff: int
    snapshot_at: datetime


class FounderExportRequest(BaseModel):
    tenant_id: UUID
    export_type: str  # "csv_revenue", "annual_summary", "cpa_package"
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class FounderExportResponse(BaseModel):
    export_id: UUID
    export_type: str
    status: str
    s3_key: Optional[str] = None
    created_at: datetime
