"""Billing eligibility and insurance verification contracts.

Defines typed contracts for payer eligibility verification prior to claim creation,
authorization workflows, and downstream billing readiness decisions.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EligibilityStatus(str, Enum):
    """Eligibility verification outcome."""

    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"
    UNKNOWN = "unknown"
    ERROR = "error"


class CoverageLevel(str, Enum):
    """Insurance coverage order."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"


class AuthorizationStatus(str, Enum):
    """Authorization state tied to payer verification."""

    NOT_REQUIRED = "not_required"
    REQUIRED = "required"
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    UNKNOWN = "unknown"


class EligibilityRequest(BaseModel):
    """Request to verify coverage for a patient encounter or transport."""

    patient_id: str
    tenant_id: str
    payer_id: str
    service_date: datetime

    transport_request_id: Optional[str] = None
    chart_id: Optional[str] = None
    requested_by_user_id: Optional[str] = None


class EligibilityBenefitSummary(BaseModel):
    """High-level benefit snapshot returned from verification."""

    plan_name: Optional[str] = None
    member_id: Optional[str] = None
    group_number: Optional[str] = None

    copay_cents: Optional[int] = Field(default=None, ge=0)
    deductible_remaining_cents: Optional[int] = Field(default=None, ge=0)
    out_of_pocket_remaining_cents: Optional[int] = Field(default=None, ge=0)


class EligibilityResponse(BaseModel):
    """Result of an eligibility verification attempt."""

    request_id: str
    patient_id: str
    tenant_id: str
    payer_id: str

    status: EligibilityStatus
    coverage_level: Optional[CoverageLevel] = None
    authorization_status: AuthorizationStatus = AuthorizationStatus.UNKNOWN

    benefit_summary: Optional[EligibilityBenefitSummary] = None
    message: Optional[str] = None

    verified_at: datetime


class EligibilityCheckedEvent(BaseModel):
    """Published when eligibility verification completes."""

    event_type: str = "billing.eligibility.checked"

    request_id: str
    patient_id: str
    tenant_id: str
    payer_id: str

    status: EligibilityStatus
    checked_at: datetime


class AuthorizationStatusUpdatedEvent(BaseModel):
    """Published when authorization state changes after verification."""

    event_type: str = "billing.authorization.status_updated"

    patient_id: str
    tenant_id: str
    payer_id: str

    old_status: AuthorizationStatus
    new_status: AuthorizationStatus
    updated_at: datetime
