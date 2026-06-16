"""
GRAVITY EPCR FRONTEND CONTRACTS
ADAPTIX_EPCR_FRONTEND_GRAVITY_LOCK

Frontend-facing contracts for EPCR visual command surface.
These are NOT the authoritative EPCR clinical contracts — those live in
adaptix_contracts/epcr/. These are the frontend display contracts only.

DEPENDENCY TRUTH:
- CPAE: BLOCKED — backend implementation required
- VAS: BLOCKED — backend implementation required
- Vision review: BLOCKED — backend implementation required
- CareGraph writes: BLOCKED — backend implementation required
- NEMSIS generated registry: BLOCKED — backend implementation required
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class EPCRChartState(str, Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    LOCKED = "locked"
    EXPORTED = "exported"
    REJECTED = "rejected"


class NEMSISReadiness(str, Enum):
    READY = "ready"
    BLOCKED = "blocked"
    WARNING = "warning"
    NOT_VALIDATED = "not_validated"


class BillingReadiness(str, Enum):
    READY = "ready"
    INCOMPLETE = "incomplete"
    BLOCKED = "blocked"


class NEMSISBlocker(BaseModel):
    field: str
    message: str
    severity: str


class EPCRChartListItemResponse(BaseModel):
    id: str
    incident_number: str
    patient_name: str | None = None
    state: EPCRChartState
    nemsis_readiness: NEMSISReadiness
    billing_readiness: BillingReadiness
    clinical_completeness_pct: float
    created_at: datetime
    updated_at: datetime


class EPCRChartDetailResponse(BaseModel):
    id: str
    incident_number: str
    patient_name: str | None = None
    state: EPCRChartState
    nemsis_readiness: NEMSISReadiness
    billing_readiness: BillingReadiness
    clinical_completeness_pct: float
    nemsis_blockers: list[NEMSISBlocker] = []
    nemsis_warnings: list[NEMSISBlocker] = []
    timeline: list[dict] = []
    audit_state: str
    validation_state: str
    created_at: datetime
    updated_at: datetime


class EPCRChartListResponse(BaseModel):
    items: list[EPCRChartListItemResponse]
    total: int
