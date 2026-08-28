"""Adaptix Community Paramedicine / MIH-CP contracts (Play P31).

Re-exports the models, enums, event names/payloads/envelope factories,
and service error contracts for the MIH-CP service.

``MIH_ENTITLEMENT_ID`` and ``MIH_SERVICE_AUDIENCE`` are the canonical
cross-repository identifiers used while the state-restricted MIH entitlement
is activated in Core and routed through Gateway. Keeping both values in the
shared contract package prevents Core, Gateway, and MIH from inventing their
own spellings while the broader module registry remains deliberately strict.
"""

from adaptix_contracts.mih.enums import (
    EnrollmentStatus,
    MihOutcomeType,
    MihPayer,
    MihReferralSource,
    MihServiceType,
    MihVisitStatus,
)
from adaptix_contracts.mih.errors import (
    MihErrorCode,
    MihErrorEnvelope,
    MihServiceError,
    enrollment_consent_required,
    enrollment_not_found,
    payer_not_authorized_for_program,
    to_adaptix_error_code,
    visit_invalid_state_transition,
)
from adaptix_contracts.mih.events import (
    MIH_DISCHARGED,
    MIH_ENROLLED,
    MIH_EVENTS,
    MIH_SOURCE_SERVICE,
    MIH_VISIT_COMPLETED,
    MIH_VISIT_SCHEDULED,
    MihDischargedPayload,
    MihEnrolledPayload,
    MihVisitCompletedPayload,
    MihVisitScheduledPayload,
    build_mih_discharged_event,
    build_mih_enrolled_event,
    build_mih_visit_completed_event,
    build_mih_visit_scheduled_event,
)
from adaptix_contracts.mih.models import (
    MihEnrollment,
    MihOutcome,
    MihOutcomeMetric,
    MihProgram,
    MihProgramSchedule,
    MihServicePlan,
    MihServicePlanGoal,
    MihServicePlanIntervention,
    MihVisit,
    MihVisitLocation,
    MihVisitVitalSigns,
)

MIH_ENTITLEMENT_ID = "mih_community_paramedicine"
MIH_SERVICE_AUDIENCE = "adaptix-mih"

__all__ = [
    "EnrollmentStatus",
    "MIH_DISCHARGED",
    "MIH_ENROLLED",
    "MIH_ENTITLEMENT_ID",
    "MIH_EVENTS",
    "MIH_SERVICE_AUDIENCE",
    "MIH_SOURCE_SERVICE",
    "MIH_VISIT_COMPLETED",
    "MIH_VISIT_SCHEDULED",
    "MihDischargedPayload",
    "MihEnrolledPayload",
    "MihEnrollment",
    "MihErrorCode",
    "MihErrorEnvelope",
    "MihOutcome",
    "MihOutcomeMetric",
    "MihOutcomeType",
    "MihPayer",
    "MihProgram",
    "MihProgramSchedule",
    "MihReferralSource",
    "MihServiceError",
    "MihServicePlan",
    "MihServicePlanGoal",
    "MihServicePlanIntervention",
    "MihServiceType",
    "MihVisit",
    "MihVisitCompletedPayload",
    "MihVisitLocation",
    "MihVisitScheduledPayload",
    "MihVisitStatus",
    "MihVisitVitalSigns",
    "build_mih_discharged_event",
    "build_mih_enrolled_event",
    "build_mih_visit_completed_event",
    "build_mih_visit_scheduled_event",
    "enrollment_consent_required",
    "enrollment_not_found",
    "payer_not_authorized_for_program",
    "to_adaptix_error_code",
    "visit_invalid_state_transition",
]
