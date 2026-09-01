"""Adaptix Community Paramedicine / MIH-CP — Pydantic v2 models.

Play P31. Shared contract surface for the MIH-CP service, the AdaptixCore
UI, the Billing service (CalAIM / MA supplemental / Medicaid waiver claim
build), and downstream analytics.

Every tenant-scoped model carries ``tenant_id`` and ``correlation_id`` so
tenant isolation and cross-service tracing survive marshalling into events
and audit records.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from adaptix_contracts.mih.enums import (
    EnrollmentRecommendationStatus,
    EnrollmentStatus,
    HighUtilizerRecommendedAction,
    MihEscalationState,
    MihOutcomeType,
    MihPayer,
    MihReferralSource,
    MihServiceType,
    MihVisitStatus,
    RemoteReadingMetric,
    UtilizationEvaluationOrigin,
    UtilizationEventType,
    UtilizationPolicyStatus,
    UtilizationSourceSystem,
)


class _MihBase(BaseModel):
    """Base model for every MIH contract.

    Enforces tenant scope and correlation on every payload that crosses a
    service or event boundary. ``model_config`` uses Pydantic v2's
    ``populate_by_name`` so downstream consumers may deserialize either the
    canonical snake_case names or common camelCase aliases already used by
    the UI donors.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=False,
        extra="forbid",
        str_strip_whitespace=True,
    )

    tenant_id: str = Field(
        ...,
        description=(
            "Tenant scope — resolved server-side from trusted auth context. "
            "Never accept a client-supplied tenant_id as authorization truth."
        ),
    )
    correlation_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Correlation ID for tracing across services and events.",
    )


# ---------------------------------------------------------------------------
# Program — the agency's MIH program configuration
# ---------------------------------------------------------------------------


class MihProgramSchedule(BaseModel):
    """Program operating hours / staffing bands."""

    model_config = ConfigDict(extra="forbid")

    day_of_week: int = Field(..., ge=0, le=6, description="0=Monday … 6=Sunday")
    start_time: str = Field(..., description="HH:MM 24h local")
    end_time: str = Field(..., description="HH:MM 24h local")
    min_staff: int = Field(default=1, ge=0)


class MihProgram(_MihBase):
    """An MIH-CP program operated by an agency.

    A tenant may run more than one program (e.g. one CalAIM contract and one
    hospital-partnership program). Every downstream ``MihEnrollment``,
    ``MihServicePlan``, ``MihVisit``, and ``MihOutcome`` cites the
    ``program_id`` it belongs to.
    """

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)

    payers: list[MihPayer] = Field(
        default_factory=list,
        description="Payers this program is authorized to bill.",
    )
    service_types: list[MihServiceType] = Field(
        default_factory=list,
        description="Services this program is authorized to deliver.",
    )
    schedule: list[MihProgramSchedule] = Field(default_factory=list)

    eligibility_criteria: str | None = Field(default=None, max_length=4000)
    referral_sources: list[MihReferralSource] = Field(default_factory=list)

    active: bool = True
    started_on: date | None = None
    ended_on: date | None = None

    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Enrollment — a patient's participation in a program
# ---------------------------------------------------------------------------


class MihEnrollment(_MihBase):
    """Patient enrollment record for a specific MIH program.

    ``patient_id`` is the platform patient identifier (Patient-Identity
    service). PHI is intentionally NOT duplicated onto this contract; look
    up demographics through the patient identity service using
    ``patient_id`` under tenant scope.
    """

    id: UUID = Field(default_factory=uuid4)
    program_id: UUID
    patient_id: str = Field(..., min_length=1)

    status: EnrollmentStatus = EnrollmentStatus.REFERRED
    payer: MihPayer
    payer_member_id: str | None = Field(
        default=None,
        description=("Payer-issued member ID. Treated as PHI; do not log outside billing/enrollment services."),
    )

    referral_source: MihReferralSource | None = None
    referral_reason: str | None = Field(default=None, max_length=2000)
    referring_provider_npi: str | None = Field(
        default=None,
        pattern=r"^\d{10}$",
        description="Referring provider National Provider Identifier (10 digits).",
    )

    consent_obtained: bool = Field(
        default=False,
        description="True once patient consent to MIH participation is recorded.",
    )
    consent_obtained_at: datetime | None = None

    referred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    enrolled_at: datetime | None = None
    discharged_at: datetime | None = None
    discharge_reason: str | None = Field(default=None, max_length=2000)

    assigned_paramedic_id: str | None = None
    assigned_care_coordinator_id: str | None = None

    linked_epcr_chart_ids: list[str] = Field(
        default_factory=list,
        description="ePCR chart_ids that originated or informed this enrollment.",
    )
    linked_cad_incident_ids: list[str] = Field(default_factory=list)

    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Service Plan — care plan bound to an enrollment
# ---------------------------------------------------------------------------


class MihServicePlanGoal(BaseModel):
    """A single measurable goal on a service plan."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    description: str = Field(..., min_length=1, max_length=2000)
    target_date: date | None = None
    measurable_criteria: str | None = Field(default=None, max_length=2000)
    achieved: bool = False
    achieved_at: datetime | None = None


class MihServicePlanIntervention(BaseModel):
    """A prescribed intervention that visits should deliver."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    service_type: MihServiceType
    frequency: str | None = Field(
        default=None,
        description="Free-form cadence (e.g. 'weekly x 6 weeks').",
        max_length=200,
    )
    responsible_role: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2000)


class MihServicePlan(_MihBase):
    """Care plan bound to an enrollment.

    A plan is versioned (``version`` increments on every mutation) so a
    Reality projection of what the plan looked like at a given visit stays
    verifiable after the plan is revised.
    """

    id: UUID = Field(default_factory=uuid4)
    enrollment_id: UUID
    program_id: UUID

    version: int = Field(default=1, ge=1)

    goals: list[MihServicePlanGoal] = Field(default_factory=list)
    interventions: list[MihServicePlanIntervention] = Field(default_factory=list)

    review_due_on: date | None = None
    approved_by: str | None = Field(
        default=None,
        description="User id of the licensed clinician who approved this plan.",
    )
    approved_at: datetime | None = None

    active: bool = True
    superseded_by_id: UUID | None = None

    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Visit — a scheduled/completed encounter
# ---------------------------------------------------------------------------


class MihVisitLocation(BaseModel):
    """Where the visit was performed."""

    model_config = ConfigDict(extra="forbid")

    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    location_notes: str | None = Field(default=None, max_length=1000)


class MihVisitVitalSigns(BaseModel):
    """Optional vital-signs snapshot captured on the visit.

    Kept intentionally minimal — the ePCR chart remains the authoritative
    clinical record. This exists so screening visits that never create an
    ePCR chart still have structured triage data.
    """

    model_config = ConfigDict(extra="forbid")

    captured_at: datetime
    systolic_bp: int | None = Field(default=None, ge=0, le=300)
    diastolic_bp: int | None = Field(default=None, ge=0, le=200)
    heart_rate: int | None = Field(default=None, ge=0, le=300)
    respiratory_rate: int | None = Field(default=None, ge=0, le=80)
    spo2: int | None = Field(default=None, ge=0, le=100)
    temperature_c: Decimal | None = Field(default=None, ge=Decimal("20"), le=Decimal("45"))
    blood_glucose_mg_dl: int | None = Field(default=None, ge=0, le=1000)
    pain_scale_0_10: int | None = Field(default=None, ge=0, le=10)


class MihVisit(_MihBase):
    """A scheduled or completed MIH visit."""

    id: UUID = Field(default_factory=uuid4)
    enrollment_id: UUID
    program_id: UUID
    service_plan_id: UUID | None = None

    status: MihVisitStatus = MihVisitStatus.SCHEDULED
    service_types: list[MihServiceType] = Field(default_factory=list)

    scheduled_start_at: datetime
    scheduled_end_at: datetime | None = None
    actual_start_at: datetime | None = None
    actual_end_at: datetime | None = None

    location: MihVisitLocation | None = None
    telehealth: bool = False

    assigned_staff_ids: list[str] = Field(default_factory=list)
    primary_paramedic_id: str | None = None

    vitals: MihVisitVitalSigns | None = None
    subjective_notes: str | None = Field(default=None, max_length=8000)
    objective_notes: str | None = Field(default=None, max_length=8000)
    interventions_delivered: list[MihServiceType] = Field(default_factory=list)

    outcome_summary: str | None = Field(default=None, max_length=4000)
    escalation_to_911_reason: str | None = Field(default=None, max_length=2000)
    linked_epcr_chart_id: str | None = None
    linked_cad_incident_id: str | None = None

    billable: bool = True
    billing_snapshot_id: str | None = None

    cancelled_reason: str | None = Field(default=None, max_length=2000)

    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Outcome — episode of care result recorded at / after discharge
# ---------------------------------------------------------------------------


class MihOutcomeMetric(BaseModel):
    """A single measured outcome on the discharge report."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200)
    value: str = Field(..., max_length=500)
    unit: str | None = Field(default=None, max_length=50)
    baseline_value: str | None = Field(default=None, max_length=500)
    captured_at: datetime | None = None


class MihOutcome(_MihBase):
    """Episode-of-care outcome for an enrollment."""

    id: UUID = Field(default_factory=uuid4)
    enrollment_id: UUID
    program_id: UUID

    outcome_type: MihOutcomeType
    summary: str = Field(..., min_length=1, max_length=8000)

    goals_met_count: int = Field(default=0, ge=0)
    goals_total_count: int = Field(default=0, ge=0)
    metrics: list[MihOutcomeMetric] = Field(default_factory=list)

    ed_visits_pre_enrollment: int | None = Field(default=None, ge=0)
    ed_visits_during_enrollment: int | None = Field(default=None, ge=0)
    inpatient_admits_pre_enrollment: int | None = Field(default=None, ge=0)
    inpatient_admits_during_enrollment: int | None = Field(default=None, ge=0)
    ems_911_calls_pre_enrollment: int | None = Field(default=None, ge=0)
    ems_911_calls_during_enrollment: int | None = Field(default=None, ge=0)

    total_visit_count: int = Field(default=0, ge=0)
    total_billable_visit_count: int = Field(default=0, ge=0)

    recorded_by: str | None = None
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Program-specific outcome fields not modelled above.",
    )


# ---------------------------------------------------------------------------
# Remote patient monitoring — reading, tenant threshold, escalation
# (Adaptix-MIH-Service ``/api/v1/mih/patients/{id}/readings``,
#  ``/thresholds``, ``/escalations``)
# ---------------------------------------------------------------------------


def _require_aware(value: datetime) -> datetime:
    """Timestamps that cross a service boundary must carry an offset."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must carry a timezone offset")
    return value.astimezone(timezone.utc)


class MihMonitoringThreshold(_MihBase):
    """Per-tenant escalation limit for one remote-monitoring metric.

    There are no platform defaults: until a tenant sets a threshold for a
    metric, readings for it are stored NOT EVALUATED.
    """

    metric: RemoteReadingMetric
    min_value: float | None = Field(default=None)
    max_value: float | None = Field(default=None)
    updated_by: str = Field(..., min_length=1)
    updated_at: datetime

    @model_validator(mode="after")
    def _bounds(self) -> "MihMonitoringThreshold":
        if self.min_value is None and self.max_value is None:
            raise ValueError("at least one of min_value / max_value is required")
        if self.min_value is not None and self.max_value is not None and self.min_value >= self.max_value:
            raise ValueError("min_value must be below max_value")
        return self


class MihRemoteReadingBreach(BaseModel):
    """Which bound a reading crossed. Mirrors the service's ``breach_detail``."""

    model_config = ConfigDict(extra="forbid")

    bound: str = Field(..., pattern=r"^(min|max)$")
    limit: float
    observed: float
    metric: RemoteReadingMetric


class MihRemoteReading(_MihBase):
    """One remote-monitoring reading for an enrolled MIH patient.

    ``threshold_breached`` is tri-state on purpose: True/False means the
    reading was evaluated against the tenant's threshold; ``None`` means the
    tenant has no threshold for this metric and the reading was NOT
    evaluated. Honest absence, never coerced to False.
    """

    id: UUID
    patient_id: UUID = Field(..., description="The MIH enrollment record id (``mih_patients.id``).")
    client_reference_id: str = Field(..., min_length=1, max_length=128)
    device_id: str | None = Field(default=None, max_length=128)
    metric: RemoteReadingMetric
    value: float
    unit: str = Field(..., min_length=1, max_length=32)
    taken_at: datetime
    threshold_breached: bool | None = Field(default=None)
    breach_detail: MihRemoteReadingBreach | None = Field(default=None)
    created_at: datetime

    @field_validator("taken_at")
    @classmethod
    def _taken_at_aware(cls, value: datetime) -> datetime:
        return _require_aware(value)


class MihEscalation(_MihBase):
    """A threshold breach awaiting supervisor acknowledgement."""

    id: UUID
    patient_id: UUID
    reading_id: UUID
    reason: str = Field(..., min_length=1)
    state: MihEscalationState = Field(default=MihEscalationState.OPEN)
    acknowledged_by: str | None = Field(default=None)
    acknowledged_at: datetime | None = Field(default=None)
    created_at: datetime


# ---------------------------------------------------------------------------
# High-utilizer detection — policy, observation, evaluation, recommendation
# (Adaptix-MIH-Service ``/api/v1/mih/utilization/*``)
#
# The trigger score is a TRANSPARENT count of satisfied dimensions (0..3).
# It is not a clinical acuity or risk score: no weighting, no inference. A
# tenant with no active policy is ``not_configured`` — there are no default
# thresholds anywhere on the platform.
# ---------------------------------------------------------------------------

UTILIZATION_LOOKBACK_MIN_DAYS = 1
UTILIZATION_LOOKBACK_MAX_DAYS = 365
UTILIZATION_TRIGGER_SCORE_MAX = 3


class MihUtilizationPolicy(_MihBase):
    """A tenant's versioned high-utilizer policy.

    A policy change is a NEW version that supersedes the prior one; history
    is never edited. ``None`` for a threshold means that dimension is
    disabled; an enabled threshold is always >= 1.
    """

    id: UUID
    version: int = Field(..., ge=1)
    status: UtilizationPolicyStatus
    lookback_days: int = Field(..., ge=UTILIZATION_LOOKBACK_MIN_DAYS, le=UTILIZATION_LOOKBACK_MAX_DAYS)
    min_911_calls: int | None = Field(default=None, ge=1)
    min_ed_visits: int | None = Field(default=None, ge=1)
    min_admissions: int | None = Field(default=None, ge=1)
    recommendation_min_score: int = Field(..., ge=1, le=UTILIZATION_TRIGGER_SCORE_MAX)
    created_by: str = Field(..., min_length=1)
    created_at: datetime
    superseded_at: datetime | None = Field(default=None)
    superseded_by_policy_id: UUID | None = Field(default=None)

    @property
    def enabled_dimensions(self) -> int:
        return sum(1 for t in (self.min_911_calls, self.min_ed_visits, self.min_admissions) if t is not None)

    @model_validator(mode="after")
    def _reachable(self) -> "MihUtilizationPolicy":
        enabled = self.enabled_dimensions
        if enabled == 0:
            raise ValueError("at least one utilization dimension must be enabled")
        if self.recommendation_min_score > enabled:
            raise ValueError(
                f"recommendation_min_score {self.recommendation_min_score} can "
                f"never be reached with {enabled} enabled dimension(s)"
            )
        return self


class MihUtilizationObservation(_MihBase):
    """One normalized utilization event for an opaque patient identity.

    The person does NOT need an MIH enrollment. Minimum necessary only: no
    name, date of birth, address, chart narrative or diagnosis ever rides on
    this contract. Idempotent per (tenant, source_system, source_event_id).
    """

    id: UUID
    patient_identity_id: str = Field(..., min_length=1, max_length=64)
    event_type: UtilizationEventType
    source_system: UtilizationSourceSystem
    source_event_id: str = Field(..., min_length=1, max_length=128)
    occurred_at: datetime
    recorded_by: str = Field(..., min_length=1)
    recorded_at: datetime

    @field_validator("occurred_at")
    @classmethod
    def _occurred_at_aware(cls, value: datetime) -> datetime:
        return _require_aware(value)


class MihUtilizationCounts(BaseModel):
    """Observation counts inside one rolling window."""

    model_config = ConfigDict(extra="forbid")

    count_911_calls: int = Field(default=0, ge=0)
    count_ed_visits: int = Field(default=0, ge=0)
    count_admissions: int = Field(default=0, ge=0)


class HighUtilizerSignal(_MihBase):
    """The transparent result of evaluating one person under one policy.

    This is the shared shape Adaptix-MIH-Service produces on every evaluation
    (``MihUtilizationEvaluation`` rows) and the payload of
    ``mih.high_utilizer.evaluated``. Each ``trigger_*`` is tri-state: True /
    False when the dimension is enabled and evaluated, ``None`` when the
    policy disables it (not evaluated). ``trigger_score`` is exactly the
    number of ``True`` triggers.
    """

    evaluation_id: UUID
    patient_identity_id: str = Field(..., min_length=1, max_length=64)
    policy_id: UUID
    policy_version: int = Field(..., ge=1)
    window_start: datetime
    window_end: datetime
    count_911_calls: int = Field(..., ge=0)
    count_ed_visits: int = Field(..., ge=0)
    count_admissions: int = Field(..., ge=0)
    trigger_911: bool | None = Field(default=None)
    trigger_ed: bool | None = Field(default=None)
    trigger_admission: bool | None = Field(default=None)
    trigger_score: int = Field(..., ge=0, le=UTILIZATION_TRIGGER_SCORE_MAX)
    recommendation_triggered: bool
    already_enrolled: bool
    recommended_action: HighUtilizerRecommendedAction
    evaluated_at: datetime
    evaluated_by: str = Field(..., min_length=1)
    evaluation_origin: UtilizationEvaluationOrigin

    @model_validator(mode="after")
    def _consistent(self) -> "HighUtilizerSignal":
        expected = sum(1 for t in (self.trigger_911, self.trigger_ed, self.trigger_admission) if t is True)
        if self.trigger_score != expected:
            raise ValueError(
                f"trigger_score {self.trigger_score} does not equal the number of satisfied dimensions ({expected})"
            )
        if self.window_end <= self.window_start:
            raise ValueError("window_end must be after window_start")
        if self.already_enrolled:
            allowed = HighUtilizerRecommendedAction.ALREADY_ENROLLED
        elif self.recommendation_triggered:
            allowed = HighUtilizerRecommendedAction.CONSIDER_ENROLLMENT
        else:
            allowed = HighUtilizerRecommendedAction.NONE
        if self.recommended_action != allowed:
            raise ValueError(
                f"recommended_action must be {allowed.value!r} for "
                f"recommendation_triggered={self.recommendation_triggered}, "
                f"already_enrolled={self.already_enrolled}"
            )
        return self


class MihEnrollmentRecommendation(_MihBase):
    """ "Consider / contact this person for MIH enrollment" — never "enrolled".

    One row per (tenant, patient identity, policy version). Further
    qualifying evidence refreshes the snapshot; it never adds a row.
    ``resolved_patient_id`` is set only when a supervisor resolves the
    recommendation against an enrollment that already exists with recorded
    consent; this contract carries no path that creates an enrollment.
    """

    id: UUID
    patient_identity_id: str = Field(..., min_length=1, max_length=64)
    policy_id: UUID
    policy_version: int = Field(..., ge=1)
    latest_evaluation_id: UUID
    trigger_score: int = Field(..., ge=0, le=UTILIZATION_TRIGGER_SCORE_MAX)
    count_911_calls: int = Field(..., ge=0)
    count_ed_visits: int = Field(..., ge=0)
    count_admissions: int = Field(..., ge=0)
    status: EnrollmentRecommendationStatus
    status_reason: str | None = Field(default=None)
    created_at: datetime
    updated_at: datetime
    acknowledged_by: str | None = Field(default=None)
    acknowledged_at: datetime | None = Field(default=None)
    dismissed_by: str | None = Field(default=None)
    dismissed_at: datetime | None = Field(default=None)
    dismissal_reason: str | None = Field(default=None)
    reopened_by: str | None = Field(default=None)
    reopened_at: datetime | None = Field(default=None)
    resolved_patient_id: UUID | None = Field(default=None)
    resolved_by: str | None = Field(default=None)
    resolved_at: datetime | None = Field(default=None)

    @model_validator(mode="after")
    def _status_fields(self) -> "MihEnrollmentRecommendation":
        if self.status == EnrollmentRecommendationStatus.DISMISSED and not (
            self.dismissal_reason and self.dismissal_reason.strip()
        ):
            raise ValueError("a dismissed recommendation must carry dismissal_reason")
        if self.status == EnrollmentRecommendationStatus.ENROLLED and self.resolved_patient_id is None:
            raise ValueError("an enrolled recommendation must reference resolved_patient_id")
        if self.status != EnrollmentRecommendationStatus.ENROLLED and self.resolved_patient_id is not None:
            raise ValueError("resolved_patient_id is only valid when status=enrolled")
        return self


__all__ = [
    "HighUtilizerSignal",
    "MihEnrollment",
    "MihEnrollmentRecommendation",
    "MihEscalation",
    "MihMonitoringThreshold",
    "MihOutcome",
    "MihOutcomeMetric",
    "MihProgram",
    "MihProgramSchedule",
    "MihRemoteReading",
    "MihRemoteReadingBreach",
    "MihServicePlan",
    "MihServicePlanGoal",
    "MihServicePlanIntervention",
    "MihUtilizationCounts",
    "MihUtilizationObservation",
    "MihUtilizationPolicy",
    "MihVisit",
    "MihVisitLocation",
    "MihVisitVitalSigns",
    "UTILIZATION_LOOKBACK_MAX_DAYS",
    "UTILIZATION_LOOKBACK_MIN_DAYS",
    "UTILIZATION_TRIGGER_SCORE_MAX",
]
