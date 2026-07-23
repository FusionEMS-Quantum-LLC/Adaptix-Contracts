"""Workforce contracts for Adaptix platform.

FATIGUE SEVERITY CONSOLIDATION (SCHEDULING_ARCHITECTURE_LOCK.md section 3.3)
---------------------------------------------------------------------------
``adaptix_contracts.scheduling.models.RiskLevel`` is the canonical severity enum
and ``adaptix_contracts.scheduling.ai.FatigueRiskScore`` is the canonical fatigue
model. ``RiskLevel`` is re-exported from this module so callers can adopt the
canonical name from this module path.

``FatigueRiskLevel`` and ``FatigueAssessment`` are RETAINED, not deleted — see
their docstrings for the exact value-set incompatibility that makes the swap a
major-version change under DEPRECATION_POLICY.md.
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel

# Canonical severity enum — re-exported (additive; does not shadow FatigueRiskLevel).
from adaptix_contracts.scheduling.models import RiskLevel  # noqa: F401

#: Legacy name -> canonical replacement.
DEPRECATED_REPLACEMENTS: dict[str, str] = {
    "FatigueRiskLevel": "adaptix_contracts.scheduling.models.RiskLevel",
    "FatigueAssessment": "adaptix_contracts.scheduling.ai.FatigueRiskScore",
}


class FatigueRiskLevel(str, Enum):
    """DEPRECATED — canonical target is
    ``adaptix_contracts.scheduling.models.RiskLevel``.

    NOT value-compatible. This enum: low/moderate/high/critical. RiskLevel:
    low/medium/high/critical. Aliasing this name to ``RiskLevel`` would delete
    the "moderate" member and reject every persisted or in-flight payload
    carrying it — a major-version change under DEPRECATION_POLICY.md.
    """

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class StaffStatus(str, Enum):
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    RESTRICTED = "restricted"
    RETURN_TO_DUTY = "return_to_duty"
    INACTIVE = "inactive"


class StaffProfile(BaseModel):
    """Staff profile contract."""

    staff_id: str
    tenant_id: str
    name: str
    role: str
    certifications: list[str] = []
    status: StaffStatus = StaffStatus.ACTIVE
    unit_assignment: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class FatigueAssessment(BaseModel):
    """DEPRECATED — canonical target is
    ``adaptix_contracts.scheduling.ai.FatigueRiskScore``.

    ``FatigueRiskScore`` now carries this model's ``risk_factors``,
    ``ai_generated`` and ``supervisor_review_flag`` fields, so the canonical model
    is a superset of this one on those axes. Folding this model away is still
    blocked on the ``FatigueRiskLevel`` -> ``RiskLevel`` value-set
    incompatibility documented above, plus the ``str`` vs ``UUID`` identifier
    difference (``staff_id``/``tenant_id`` here vs ``person_id``/``shift_id``
    ``UUID`` there).
    """

    assessment_id: str
    staff_id: str
    tenant_id: str
    risk_level: FatigueRiskLevel
    hours_worked_last_24h: float
    hours_worked_last_7d: float
    consecutive_shifts: int
    risk_factors: list[str] = []
    recommendation: Optional[str] = None
    human_review_required: bool = True
    supervisor_review_flag: bool = False
    assessed_at: datetime
    ai_generated: bool = False


class StaffRestriction(BaseModel):
    """Staff restriction record."""

    restriction_id: str
    staff_id: str
    tenant_id: str
    actor_id: str
    reason: str
    restriction_type: str
    start_datetime: datetime
    end_datetime: Optional[datetime] = None
    supervisor_id: Optional[str] = None
    audit_event_emitted: bool = True
    created_at: datetime


class ReturnToDutyRecord(BaseModel):
    """Return to duty record."""

    record_id: str
    staff_id: str
    tenant_id: str
    actor_id: str
    cleared_by: str
    clearance_notes: Optional[str] = None
    return_datetime: datetime
    audit_event_emitted: bool = True
    created_at: datetime


class WorkforceAvailability(BaseModel):
    """Workforce availability for CAD/CrewLink linkage."""

    tenant_id: str
    date: str
    shift_type: str
    available_staff: list[str] = []
    unavailable_staff: list[str] = []
    restricted_staff: list[str] = []
    coverage_adequate: bool = True
    fatigue_risk_flags: list[str] = []
    cad_linkage_active: bool = True
    crewlink_linkage_active: bool = True
