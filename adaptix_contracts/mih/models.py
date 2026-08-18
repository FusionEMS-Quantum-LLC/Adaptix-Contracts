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

from pydantic import BaseModel, ConfigDict, Field

from adaptix_contracts.mih.enums import (
    EnrollmentStatus,
    MihOutcomeType,
    MihPayer,
    MihReferralSource,
    MihServiceType,
    MihVisitStatus,
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
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


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
        description=(
            "Payer-issued member ID. Treated as PHI; do not log outside "
            "billing/enrollment services."
        ),
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

    referred_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
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
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


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
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


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
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


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
    recorded_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Program-specific outcome fields not modelled above.",
    )


__all__ = [
    "MihEnrollment",
    "MihOutcome",
    "MihOutcomeMetric",
    "MihProgram",
    "MihProgramSchedule",
    "MihServicePlan",
    "MihServicePlanGoal",
    "MihServicePlanIntervention",
    "MihVisit",
    "MihVisitLocation",
    "MihVisitVitalSigns",
]
