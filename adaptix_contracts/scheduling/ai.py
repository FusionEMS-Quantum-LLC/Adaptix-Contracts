"""Adaptix Scheduling — AI / Smart Staffing Intelligence Models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SchedulingAIAssessment(BaseModel):
    """Full AI assessment output — advisory only, never auto-approves."""

    id: UUID
    tenant_id: UUID
    capability_key: str
    actor_id: UUID
    schedule_id: UUID | None = None
    shift_id: UUID | None = None
    assessment_type: str
    findings: list[dict[str, Any]] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    blocking_issues: list[str] = Field(default_factory=list)
    human_review_required: bool = True
    policy_references: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    risk_level: str = "low"
    created_at: datetime
    audit_event_id: UUID | None = None


class StaffingShortageFinding(BaseModel):
    shift_id: UUID
    agency_type: str
    shortage_count: int
    required_count: int
    actual_count: int
    missing_ranks: list[str] = Field(default_factory=list)
    missing_specialties: list[str] = Field(default_factory=list)
    risk_level: str = "high"
    explanation: str


class CoverageRiskExplanation(BaseModel):
    area_type: str  # beat, zone, district, station, console
    area_id: UUID
    area_name: str
    risk_level: str
    current_coverage: int
    minimum_required: int
    explanation: str
    recommended_action: str


class FatigueRiskScore(BaseModel):
    """Canonical fatigue risk output for the scheduling domain.

    Consolidation target for ``adaptix_contracts.workforce.models.FatigueAssessment``
    per SCHEDULING_ARCHITECTURE_LOCK.md section 3.3. ``risk_factors``,
    ``ai_generated`` and ``supervisor_review_flag`` were carried over from
    ``FatigueAssessment`` (workforce/models.py:49-54) so this model is a superset
    of the fatigue surface. They are optional with safe defaults, so existing
    producers and payloads are unaffected.

    ``risk_level`` remains ``str`` rather than
    ``adaptix_contracts.scheduling.models.RiskLevel`` because narrowing an
    accepted-value set is a major-version change under DEPRECATION_POLICY.md.
    Producers should emit ``RiskLevel`` values ("low"/"medium"/"high"/"critical").
    """

    person_id: UUID
    shift_id: UUID
    hours_worked_last_24h: float
    hours_worked_last_48h: float
    hours_worked_last_7d: float
    consecutive_shifts: int
    fatigue_score: float  # 0.0 - 1.0
    risk_level: str  # low, medium, high, critical
    explanation: str
    human_review_required: bool = True
    # Carried over from workforce.models.FatigueAssessment (additive, optional).
    risk_factors: list[str] = Field(default_factory=list)
    ai_generated: bool = False
    supervisor_review_flag: bool = False


class OvertimeFairnessScore(BaseModel):
    person_id: UUID
    overtime_hours_ytd: float
    overtime_hours_last_30d: float
    peer_average_overtime_hours: float
    fairness_score: float  # 0.0 - 1.0 (1.0 = perfectly fair)
    rank_in_rotation: int
    explanation: str


class SwapCompatibilityResult(BaseModel):
    requester_id: UUID
    target_id: UUID
    requester_shift_id: UUID
    target_shift_id: UUID
    compatible: bool
    compatibility_score: float
    issues: list[str] = Field(default_factory=list)
    rank_compatible: bool = True
    credential_compatible: bool = True
    fatigue_risk: str = "low"
    explanation: str
    human_review_required: bool = True


class BackfillRecommendation(BaseModel):
    shift_id: UUID
    vacancy_reason: str
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    top_candidate_id: UUID | None = None
    top_candidate_reason: str = ""
    seniority_considered: bool = True
    union_rules_considered: bool = True
    fatigue_considered: bool = True
    overtime_fairness_considered: bool = True
    human_review_required: bool = True
    explanation: str


class HoldoverRecommendation(BaseModel):
    shift_id: UUID
    shortage_reason: str
    recommended_person_id: UUID | None = None
    recommended_person_reason: str = ""
    duration_hours: float = 4.0
    seniority_considered: bool = True
    union_rules_considered: bool = True
    fatigue_risk: str = "medium"
    human_review_required: bool = True
    supervisor_approval_required: bool = True
    explanation: str


class PolicyViolationWarning(BaseModel):
    person_id: UUID
    shift_id: UUID
    policy_type: str  # union, seniority, fatigue, credential, minimum_rest
    policy_key: str
    violation_description: str
    severity: str  # warning, violation, block
    human_review_required: bool = True
    auto_override_forbidden: bool = True
    explanation: str


class SeniorityRuleExplanation(BaseModel):
    person_id: UUID
    rule_key: str
    seniority_rank: int
    bid_priority: int
    applicable_rules: list[str] = Field(default_factory=list)
    explanation: str
    human_decision_required: bool = True


class SupervisorDecisionSummary(BaseModel):
    shift_id: UUID
    schedule_id: UUID | None = None
    pending_approvals: list[dict[str, Any]] = Field(default_factory=list)
    coverage_status: str
    shortage_count: int
    fatigue_flags: int
    policy_warnings: int
    ai_recommendations: list[str] = Field(default_factory=list)
    risk_level: str
    summary: str
    generated_at: datetime


class StaffingCommandBriefing(BaseModel):
    schedule_id: UUID
    briefing_date: datetime
    agency_types: list[str] = Field(default_factory=list)
    total_shifts: int
    filled_shifts: int
    open_shifts: int
    coverage_violations: int
    fatigue_flags: int
    overtime_offers_pending: int
    swap_requests_pending: int
    timeoff_requests_pending: int
    holdover_orders_pending: int
    ai_risk_level: str
    key_findings: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    generated_at: datetime
    human_review_required: bool = True


# AI Capability Keys
SCHED_AI_STAFFING_SHORTAGE = "sched_ai.staffing_shortage"
SCHED_AI_COVERAGE_RISK = "sched_ai.coverage_risk"
SCHED_AI_FATIGUE_RISK = "sched_ai.fatigue_risk"
SCHED_AI_OVERTIME_FAIRNESS = "sched_ai.overtime_fairness"
SCHED_AI_SWAP_COMPATIBILITY = "sched_ai.swap_compatibility"
SCHED_AI_BACKFILL_RECOMMENDATION = "sched_ai.backfill_recommendation"
SCHED_AI_HOLDOVER_RECOMMENDATION = "sched_ai.holdover_recommendation"
SCHED_AI_MIN_STAFFING_VIOLATION = "sched_ai.min_staffing_violation"
SCHED_AI_RANK_COVERAGE_WARNING = "sched_ai.rank_coverage_warning"
SCHED_AI_BEAT_ZONE_COVERAGE_WARNING = "sched_ai.beat_zone_coverage_warning"
SCHED_AI_COURT_TRAINING_CONFLICT = "sched_ai.court_training_conflict"
SCHED_AI_CREDENTIAL_CONFLICT = "sched_ai.credential_conflict"
SCHED_AI_LEAVE_IMPACT = "sched_ai.leave_impact"
SCHED_AI_SPECIAL_EVENT_STAFFING = "sched_ai.special_event_staffing"
SCHED_AI_WEATHER_DEMAND_FORECAST = "sched_ai.weather_demand_forecast"
SCHED_AI_POLICY_VIOLATION_WARNING = "sched_ai.policy_violation_warning"
SCHED_AI_UNION_SENIORITY_EXPLANATION = "sched_ai.union_seniority_explanation"
SCHED_AI_SUPERVISOR_DECISION_SUMMARY = "sched_ai.supervisor_decision_summary"
SCHED_AI_SCHEDULE_FAIRNESS_AUDIT = "sched_ai.schedule_fairness_audit"
SCHED_AI_STAFFING_COMMAND_BRIEFING = "sched_ai.staffing_command_briefing"

ALL_AI_CAPABILITIES = [
    SCHED_AI_STAFFING_SHORTAGE,
    SCHED_AI_COVERAGE_RISK,
    SCHED_AI_FATIGUE_RISK,
    SCHED_AI_OVERTIME_FAIRNESS,
    SCHED_AI_SWAP_COMPATIBILITY,
    SCHED_AI_BACKFILL_RECOMMENDATION,
    SCHED_AI_HOLDOVER_RECOMMENDATION,
    SCHED_AI_MIN_STAFFING_VIOLATION,
    SCHED_AI_RANK_COVERAGE_WARNING,
    SCHED_AI_BEAT_ZONE_COVERAGE_WARNING,
    SCHED_AI_COURT_TRAINING_CONFLICT,
    SCHED_AI_CREDENTIAL_CONFLICT,
    SCHED_AI_LEAVE_IMPACT,
    SCHED_AI_SPECIAL_EVENT_STAFFING,
    SCHED_AI_WEATHER_DEMAND_FORECAST,
    SCHED_AI_POLICY_VIOLATION_WARNING,
    SCHED_AI_UNION_SENIORITY_EXPLANATION,
    SCHED_AI_SUPERVISOR_DECISION_SUMMARY,
    SCHED_AI_SCHEDULE_FAIRNESS_AUDIT,
    SCHED_AI_STAFFING_COMMAND_BRIEFING,
]
