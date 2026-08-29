"""Finance and ledger contracts shared across Adaptix services.

Defines contracts for the Adaptix Finance Service: financial summaries,
revenue records, ledger accounts, journal entries, reconciliation,
and the finance dashboard.

These contracts are the authoritative source for all finance domain
data exchanged across Adaptix services.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AccountType(str, Enum):
    """US-GAAP account classification."""

    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"


class TransactionSource(str, Enum):
    """Origin of a ledger transaction."""

    CSV = "csv"
    MANUAL = "manual"
    STRIPE = "stripe"


class ReconciliationStatus(str, Enum):
    """Reconciliation lifecycle state."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"


class FinancialSummaryStatus(str, Enum):
    """Status of a financial summary record."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    DRAFT = "draft"


# ---------------------------------------------------------------------------
# Financial Summary Contracts
# ---------------------------------------------------------------------------


class FinancialSummaryCreateRequest(BaseModel):
    """Request schema for creating a FinancialSummary."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=4000)
    status: str = Field(default="active", min_length=1, max_length=50)
    metadata_json: Optional[dict] = Field(default=None)


class FinancialSummaryUpdateRequest(BaseModel):
    """Request schema for updating a FinancialSummary."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=4000)
    status: Optional[str] = Field(default=None, min_length=1, max_length=50)
    metadata_json: Optional[dict] = Field(default=None)


class FinancialSummaryResponse(BaseModel):
    """Response schema for a FinancialSummary."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: Optional[str] = None
    description: Optional[str] = None
    status: str
    metadata_json: Optional[dict] = None
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class FinancialSummaryListResponse(BaseModel):
    """Paginated list response for FinancialSummary."""

    total: int
    items: list[FinancialSummaryResponse]


# ---------------------------------------------------------------------------
# Revenue Record Contracts
# ---------------------------------------------------------------------------


class RevenueRecordCreateRequest(BaseModel):
    """Request schema for creating a RevenueRecord."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=4000)
    status: str = Field(default="active", min_length=1, max_length=50)
    metadata_json: Optional[dict] = Field(default=None)
    amount: Optional[Decimal] = Field(default=None)
    currency: str = Field(default="USD", max_length=3)
    recorded_at: Optional[datetime] = None


class RevenueRecordResponse(BaseModel):
    """Response schema for a RevenueRecord."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: Optional[str] = None
    description: Optional[str] = None
    status: str
    amount: Optional[Decimal] = None
    currency: str
    recorded_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class RevenueRecordListResponse(BaseModel):
    """Paginated list response for RevenueRecord."""

    total: int
    items: list[RevenueRecordResponse]


# ---------------------------------------------------------------------------
# Ledger Account Contracts
# ---------------------------------------------------------------------------


class LedgerAccountCreateRequest(BaseModel):
    """Request to create a chart-of-accounts entry."""

    code: str = Field(..., min_length=1, max_length=24)
    name: str = Field(..., min_length=1, max_length=160)
    type: AccountType
    parent_id: Optional[UUID] = None
    is_active: bool = True


class LedgerAccountUpdateRequest(BaseModel):
    """Partial update for a ledger account."""

    name: Optional[str] = Field(default=None, max_length=160)
    type: Optional[AccountType] = None
    parent_id: Optional[UUID] = None
    is_active: Optional[bool] = None


class LedgerAccountResponse(BaseModel):
    """Response schema for a ledger account."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    type: AccountType
    parent_id: Optional[UUID] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class LedgerAccountListResponse(BaseModel):
    """Paginated list response for ledger accounts."""

    items: list[LedgerAccountResponse]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Journal Entry Contracts
# ---------------------------------------------------------------------------


class JournalLineRequest(BaseModel):
    """Single debit/credit line in a journal entry."""

    account_id: UUID
    debit_cents: int = Field(default=0, ge=0)
    credit_cents: int = Field(default=0, ge=0)
    memo: Optional[str] = Field(default=None, max_length=500)

    @field_validator("debit_cents", "credit_cents")
    @classmethod
    def non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Amount must be non-negative")
        return v


class JournalEntryCreateRequest(BaseModel):
    """Request to post a double-entry journal entry."""

    entry_date: date
    memo: str = Field(..., min_length=1, max_length=500)
    source: TransactionSource = TransactionSource.MANUAL
    reference_id: Optional[str] = Field(default=None, max_length=255)
    lines: list[JournalLineRequest] = Field(..., min_length=2)


class JournalLineResponse(BaseModel):
    """Response for a single journal entry line."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    debit_cents: int
    credit_cents: int
    memo: Optional[str] = None


class JournalEntryResponse(BaseModel):
    """Response schema for a posted journal entry."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    entry_date: date
    memo: str
    source: TransactionSource
    reference_id: Optional[str] = None
    posted_by: Optional[UUID] = None
    created_at: datetime
    lines: list[JournalLineResponse]


class JournalEntryListResponse(BaseModel):
    """Paginated list of journal entries."""

    items: list[JournalEntryResponse]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Reconciliation Contracts
# ---------------------------------------------------------------------------


class ReconciliationPeriodResponse(BaseModel):
    """Response schema for a reconciliation period."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    period_start: date
    period_end: date
    status: ReconciliationStatus
    reconciled_by: Optional[UUID] = None
    reconciled_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Finance Dashboard Contracts
# ---------------------------------------------------------------------------


class FinanceDashboardSummaryResponse(BaseModel):
    """High-level financial KPIs for the founder finance dashboard."""

    total_revenue_cents: int
    total_expenses_cents: int
    net_income_cents: int
    cash_balance_cents: int
    accounts_receivable_cents: int
    accounts_payable_cents: int
    period_start: date
    period_end: date
    currency: str = "USD"


# ---------------------------------------------------------------------------
# Finance Events
# ---------------------------------------------------------------------------


class RevenueRecordCreatedEvent(BaseModel):
    """Emitted when a revenue record is created."""

    event_type: str = "finance.revenue_record.created"
    tenant_id: UUID
    record_id: UUID
    amount_cents: Optional[int] = None
    currency: str = "USD"
    created_at: datetime


class JournalEntryPostedEvent(BaseModel):
    """Emitted when a journal entry is posted."""

    event_type: str = "finance.journal_entry.posted"
    tenant_id: UUID
    entry_id: UUID
    entry_date: date
    source: TransactionSource
    posted_by: Optional[UUID] = None
    posted_at: datetime
