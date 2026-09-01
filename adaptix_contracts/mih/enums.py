"""Adaptix Community Paramedicine / MIH-CP — Enumerations.

Play P31 (MIH-CP service). Enums are shared across ``models.py`` and
``events.py`` so payer, service type, and enrollment lifecycle strings never
drift between the models a service publishes and the events consumers read.
"""

from __future__ import annotations

from enum import StrEnum


class MihServiceType(StrEnum):
    """The category of community paramedicine service delivered on a visit.

    Mirrors the CalAIM PATH / Community Supports and CMS Medicaid Community
    Health Worker service taxonomies so downstream billing/analytics can map
    a visit to a payer service code without a second translation table.
    """

    POST_DISCHARGE_FOLLOWUP = "post_discharge_followup"
    CHRONIC_DISEASE_MANAGEMENT = "chronic_disease_management"
    FALL_PREVENTION = "fall_prevention"
    MENTAL_HEALTH_OUTREACH = "mental_health_outreach"
    SUBSTANCE_USE_OUTREACH = "substance_use_outreach"
    HIGH_UTILIZER_INTERVENTION = "high_utilizer_intervention"
    MEDICATION_RECONCILIATION = "medication_reconciliation"
    IMMUNIZATION = "immunization"
    WELLNESS_CHECK = "wellness_check"
    HOME_SAFETY_ASSESSMENT = "home_safety_assessment"
    HOSPICE_SUPPORT = "hospice_support"
    HOUSING_NAVIGATION = "housing_navigation"
    SOCIAL_DETERMINANTS_ASSESSMENT = "social_determinants_assessment"
    TRANSPORT_TO_ALTERNATE_DESTINATION = "transport_to_alternate_destination"
    TELEHEALTH_FACILITATION = "telehealth_facilitation"
    OTHER = "other"


class EnrollmentStatus(StrEnum):
    """Lifecycle of a patient's enrollment in an MIH program.

    ``REFERRED`` → ``SCREENING`` → ``ENROLLED`` → (``ACTIVE`` visits) →
    ``DISCHARGED`` is the happy path. ``DECLINED``, ``INELIGIBLE``,
    ``LOST_TO_FOLLOWUP`` and ``TRANSFERRED`` are terminal branches; a
    transition into any of them fires ``mih.discharged`` so downstream
    billing, care coordination, and analytics stop scheduling visits.
    """

    REFERRED = "referred"
    SCREENING = "screening"
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    ENROLLED = "enrolled"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    DECLINED = "declined"
    LOST_TO_FOLLOWUP = "lost_to_followup"
    TRANSFERRED = "transferred"
    DISCHARGED = "discharged"


class MihPayer(StrEnum):
    """Payer / funding source for MIH-CP services.

    The four values Josh named explicitly in Play P31:
    ``calaim`` (California CalAIM PATH / Community Supports),
    ``ma_supplemental`` (Medicare Advantage supplemental benefit),
    ``medicaid_waiver`` (state 1115/1915 Medicaid waivers outside CalAIM),
    and ``private_pay`` (self-pay, employer, or grant-funded engagements).
    ``uncompensated`` and ``other`` are kept for programs that operate
    outside a billable payer relationship so a visit does not have to lie
    about its funding source to satisfy a NOT NULL column.
    """

    CALAIM = "calaim"
    MA_SUPPLEMENTAL = "ma_supplemental"
    MEDICAID_WAIVER = "medicaid_waiver"
    PRIVATE_PAY = "private_pay"
    UNCOMPENSATED = "uncompensated"
    OTHER = "other"


class MihVisitStatus(StrEnum):
    """Lifecycle of a scheduled MIH visit."""

    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    EN_ROUTE = "en_route"
    ARRIVED = "arrived"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    NO_SHOW = "no_show"
    PATIENT_REFUSED = "patient_refused"
    CANCELLED = "cancelled"
    ESCALATED_TO_911 = "escalated_to_911"


class MihOutcomeType(StrEnum):
    """Classification of a discharge / episode-of-care outcome."""

    GOALS_MET = "goals_met"
    PARTIAL_GOALS_MET = "partial_goals_met"
    ESCALATED_TO_HIGHER_LEVEL_OF_CARE = "escalated_to_higher_level_of_care"
    TRANSFERRED_TO_OTHER_PROGRAM = "transferred_to_other_program"
    PATIENT_WITHDREW = "patient_withdrew"
    LOST_TO_FOLLOWUP = "lost_to_followup"
    DECEASED = "deceased"
    OTHER = "other"


class MihReferralSource(StrEnum):
    """Where the enrollment referral originated."""

    HOSPITAL_DISCHARGE = "hospital_discharge"
    EMS_911_RESPONSE = "ems_911_response"
    PRIMARY_CARE = "primary_care"
    PAYER_CARE_MANAGEMENT = "payer_care_management"
    SELF_REFERRAL = "self_referral"
    FAMILY_REFERRAL = "family_referral"
    SOCIAL_SERVICES = "social_services"
    HOMELESS_OUTREACH = "homeless_outreach"
    BEHAVIORAL_HEALTH = "behavioral_health"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Remote patient monitoring (Adaptix-MIH-Service build-order step 4)
# ---------------------------------------------------------------------------


class RemoteReadingMetric(StrEnum):
    """Remote-monitoring metrics the MIH service accepts.

    Mirrors ``READING_METRICS`` in Adaptix-MIH-Service exactly; a metric
    outside this set is refused by the service (422 ``invalid_metric``),
    never coerced.
    """

    SYSTOLIC_BP = "systolic_bp"
    DIASTOLIC_BP = "diastolic_bp"
    HEART_RATE = "heart_rate"
    SPO2 = "spo2"
    WEIGHT_KG = "weight_kg"
    GLUCOSE_MG_DL = "glucose_mg_dl"
    HRV_MS = "hrv_ms"


class MihEscalationState(StrEnum):
    """Lifecycle of a threshold-breach escalation awaiting acknowledgement."""

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"


# ---------------------------------------------------------------------------
# High-utilizer detection (Adaptix-MIH-Service build-order step 5)
# ---------------------------------------------------------------------------


class UtilizationEventType(StrEnum):
    """Normalized utilization evidence the MIH service counts.

    Strict vocabulary shared with the future producers: ePCR supplies
    ``911_call``; the QHIN hospital feed supplies ``ed_visit`` and
    ``hospital_admission``. Anything else is refused, never fuzzy-matched.
    """

    CALL_911 = "911_call"
    ED_VISIT = "ed_visit"
    HOSPITAL_ADMISSION = "hospital_admission"


class UtilizationSourceSystem(StrEnum):
    """Which system asserted a utilization observation.

    ``EPCR`` and ``QHIN`` are the authoritative automated producers (their
    service-to-service identity is a later gateway wave); ``MANUAL_VERIFIED``
    is supervisor-entered, validated historical/backfill evidence. There are
    deliberately no demo, sample or test sources.
    """

    EPCR = "epcr"
    QHIN = "qhin"
    MANUAL_VERIFIED = "manual_verified"


class UtilizationPolicyStatus(StrEnum):
    """A tenant's high-utilizer policy is versioned; one version is active."""

    ACTIVE = "active"
    SUPERSEDED = "superseded"


class UtilizationEvaluationOrigin(StrEnum):
    """Why an evaluation ran, stored on every evaluation row."""

    OBSERVATION_INGEST = "observation_ingest"
    EXPLICIT = "explicit"


class EnrollmentRecommendationStatus(StrEnum):
    """Lifecycle of an MIH enrollment recommendation.

    ``OPEN`` → ``ACKNOWLEDGED`` → one of ``DISMISSED`` (supervisor reason
    required), ``ENROLLED`` (resolved against an existing, consented, active
    enrollment — the recommendation never creates one) or ``EXPIRED`` (the
    person no longer meets the policy, or the policy version was superseded;
    retained, never deleted). ``DISMISSED``/``EXPIRED`` may return to ``OPEN``
    only through an explicit, audited supervisor reopen or, for ``EXPIRED``,
    by re-qualifying under the same policy version.
    """

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    DISMISSED = "dismissed"
    ENROLLED = "enrolled"
    EXPIRED = "expired"


class HighUtilizerRecommendedAction(StrEnum):
    """What a high-utilizer signal asks a consumer to do. Never "enroll"."""

    NONE = "none"
    CONSIDER_ENROLLMENT = "consider_enrollment"
    ALREADY_ENROLLED = "already_enrolled"


__all__ = [
    "EnrollmentRecommendationStatus",
    "EnrollmentStatus",
    "HighUtilizerRecommendedAction",
    "MihEscalationState",
    "MihOutcomeType",
    "MihPayer",
    "MihReferralSource",
    "MihServiceType",
    "MihVisitStatus",
    "RemoteReadingMetric",
    "UtilizationEvaluationOrigin",
    "UtilizationEventType",
    "UtilizationPolicyStatus",
    "UtilizationSourceSystem",
]
