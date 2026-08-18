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


__all__ = [
    "EnrollmentStatus",
    "MihOutcomeType",
    "MihPayer",
    "MihReferralSource",
    "MihServiceType",
    "MihVisitStatus",
]
