"""Adaptix Community Paramedicine / MIH-CP — Service error contracts.

Play P31. MIH-specific error codes plus convenience constructors that
return a canonical :class:`adaptix_contracts.errors.envelope.AdaptixErrorEnvelope`,
so the MIH-CP service, Billing, Core, and the UI all read a single error
shape rather than a domain-specific exception hierarchy.

Design note: Adaptix does not use Python exception classes as its public
error contract — the platform contract is the envelope model in
``adaptix_contracts/errors/envelope.py``. This module extends that
contract with MIH-specific error codes and typed factory functions;
services that want to raise may wrap ``MihServiceError`` around an
envelope.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import Field

from adaptix_contracts.errors.envelope import (
    AdaptixErrorCode,
    AdaptixErrorEnvelope,
    AdaptixProviderErrorDetail,
    AdaptixTraceContext,
    AdaptixValidationErrorDetail,
)


class MihErrorCode(str, Enum):
    """MIH-specific error codes.

    Values are namespaced with ``mih.`` so they never collide with the
    platform-wide :class:`AdaptixErrorCode` when serialized side-by-side.
    Consumers that only understand :class:`AdaptixErrorCode` MUST map
    these to the closest generic code using :func:`to_adaptix_error_code`.
    """

    PROGRAM_INACTIVE = "mih.program_inactive"
    PROGRAM_NOT_FOUND = "mih.program_not_found"

    ENROLLMENT_NOT_FOUND = "mih.enrollment_not_found"
    ENROLLMENT_ALREADY_EXISTS = "mih.enrollment_already_exists"
    ENROLLMENT_ALREADY_DISCHARGED = "mih.enrollment_already_discharged"
    ENROLLMENT_CONSENT_REQUIRED = "mih.enrollment_consent_required"
    ENROLLMENT_INELIGIBLE_FOR_PROGRAM = "mih.enrollment_ineligible_for_program"

    SERVICE_PLAN_NOT_FOUND = "mih.service_plan_not_found"
    SERVICE_PLAN_NOT_APPROVED = "mih.service_plan_not_approved"
    SERVICE_PLAN_SUPERSEDED = "mih.service_plan_superseded"

    VISIT_NOT_FOUND = "mih.visit_not_found"
    VISIT_INVALID_STATE_TRANSITION = "mih.visit_invalid_state_transition"
    VISIT_ALREADY_COMPLETED = "mih.visit_already_completed"
    VISIT_TIME_CONFLICT = "mih.visit_time_conflict"

    OUTCOME_NOT_FOUND = "mih.outcome_not_found"
    OUTCOME_REQUIRED_BEFORE_DISCHARGE = "mih.outcome_required_before_discharge"

    PAYER_NOT_AUTHORIZED_FOR_PROGRAM = "mih.payer_not_authorized_for_program"
    PAYER_REQUIRED_FIELD_MISSING = "mih.payer_required_field_missing"

    BILLING_HANDOFF_FAILED = "mih.billing_handoff_failed"
    EPCR_LINK_INVALID = "mih.epcr_link_invalid"
    CAD_LINK_INVALID = "mih.cad_link_invalid"

    # Remote patient monitoring
    READING_INVALID_METRIC = "mih.reading_invalid_metric"
    ESCALATION_NOT_FOUND = "mih.escalation_not_found"

    # High-utilizer detection. Each code corresponds to one bare
    # ``error_code`` string Adaptix-MIH-Service answers on
    # ``/api/v1/mih/utilization/*`` (see ``MIH_SERVICE_ERROR_CODES``); the
    # ``mih.`` namespace follows the rest of this enum.
    UTILIZATION_POLICY_NOT_CONFIGURED = "mih.utilization_policy_not_configured"
    UTILIZATION_POLICY_VERSION_CONFLICT = "mih.utilization_policy_version_conflict"
    UTILIZATION_INVALID_EVENT_TYPE = "mih.utilization_invalid_event_type"
    UTILIZATION_INVALID_SOURCE_SYSTEM = "mih.utilization_invalid_source_system"
    UTILIZATION_OCCURRED_AT_IN_FUTURE = "mih.utilization_occurred_at_in_future"
    UTILIZATION_SOURCE_EVENT_CONFLICT = "mih.utilization_source_event_conflict"
    UTILIZATION_EVALUATION_CONFLICT = "mih.utilization_evaluation_conflict"
    RECOMMENDATION_NOT_FOUND = "mih.recommendation_not_found"
    RECOMMENDATION_ALREADY_DISMISSED = "mih.recommendation_already_dismissed"
    RECOMMENDATION_ALREADY_ENROLLED = "mih.recommendation_already_enrolled"
    RECOMMENDATION_INVALID_TRANSITION = "mih.recommendation_invalid_transition"
    RECOMMENDATION_PATIENT_IDENTITY_MISMATCH = (
        "mih.recommendation_patient_identity_mismatch"
    )
    RECOMMENDATION_ENROLLMENT_NOT_ACTIVE = "mih.recommendation_enrollment_not_active"


_MIH_TO_PLATFORM: dict[MihErrorCode, AdaptixErrorCode] = {
    MihErrorCode.PROGRAM_INACTIVE: AdaptixErrorCode.WORKFLOW_BLOCKED,
    MihErrorCode.PROGRAM_NOT_FOUND: AdaptixErrorCode.NOT_FOUND,
    MihErrorCode.ENROLLMENT_NOT_FOUND: AdaptixErrorCode.NOT_FOUND,
    MihErrorCode.ENROLLMENT_ALREADY_EXISTS: AdaptixErrorCode.ALREADY_EXISTS,
    MihErrorCode.ENROLLMENT_ALREADY_DISCHARGED: AdaptixErrorCode.INVALID_STATE_TRANSITION,
    MihErrorCode.ENROLLMENT_CONSENT_REQUIRED: AdaptixErrorCode.WORKFLOW_BLOCKED,
    MihErrorCode.ENROLLMENT_INELIGIBLE_FOR_PROGRAM: AdaptixErrorCode.CONSTRAINT_VIOLATION,
    MihErrorCode.SERVICE_PLAN_NOT_FOUND: AdaptixErrorCode.NOT_FOUND,
    MihErrorCode.SERVICE_PLAN_NOT_APPROVED: AdaptixErrorCode.WORKFLOW_BLOCKED,
    MihErrorCode.SERVICE_PLAN_SUPERSEDED: AdaptixErrorCode.INVALID_STATE_TRANSITION,
    MihErrorCode.VISIT_NOT_FOUND: AdaptixErrorCode.NOT_FOUND,
    MihErrorCode.VISIT_INVALID_STATE_TRANSITION: AdaptixErrorCode.INVALID_STATE_TRANSITION,
    MihErrorCode.VISIT_ALREADY_COMPLETED: AdaptixErrorCode.INVALID_STATE_TRANSITION,
    MihErrorCode.VISIT_TIME_CONFLICT: AdaptixErrorCode.CONFLICT,
    MihErrorCode.OUTCOME_NOT_FOUND: AdaptixErrorCode.NOT_FOUND,
    MihErrorCode.OUTCOME_REQUIRED_BEFORE_DISCHARGE: AdaptixErrorCode.WORKFLOW_BLOCKED,
    MihErrorCode.PAYER_NOT_AUTHORIZED_FOR_PROGRAM: AdaptixErrorCode.CONSTRAINT_VIOLATION,
    MihErrorCode.PAYER_REQUIRED_FIELD_MISSING: AdaptixErrorCode.REQUIRED_FIELD_MISSING,
    MihErrorCode.BILLING_HANDOFF_FAILED: AdaptixErrorCode.EXPORT_FAILED,
    MihErrorCode.EPCR_LINK_INVALID: AdaptixErrorCode.INVALID_VALUE,
    MihErrorCode.CAD_LINK_INVALID: AdaptixErrorCode.INVALID_VALUE,
    MihErrorCode.READING_INVALID_METRIC: AdaptixErrorCode.INVALID_VALUE,
    MihErrorCode.ESCALATION_NOT_FOUND: AdaptixErrorCode.NOT_FOUND,
    MihErrorCode.UTILIZATION_POLICY_NOT_CONFIGURED: AdaptixErrorCode.NOT_CONFIGURED,
    MihErrorCode.UTILIZATION_POLICY_VERSION_CONFLICT: AdaptixErrorCode.CONFLICT,
    MihErrorCode.UTILIZATION_INVALID_EVENT_TYPE: AdaptixErrorCode.INVALID_VALUE,
    MihErrorCode.UTILIZATION_INVALID_SOURCE_SYSTEM: AdaptixErrorCode.INVALID_VALUE,
    MihErrorCode.UTILIZATION_OCCURRED_AT_IN_FUTURE: AdaptixErrorCode.INVALID_VALUE,
    MihErrorCode.UTILIZATION_SOURCE_EVENT_CONFLICT: AdaptixErrorCode.CONFLICT,
    MihErrorCode.UTILIZATION_EVALUATION_CONFLICT: AdaptixErrorCode.CONFLICT,
    MihErrorCode.RECOMMENDATION_NOT_FOUND: AdaptixErrorCode.NOT_FOUND,
    MihErrorCode.RECOMMENDATION_ALREADY_DISMISSED: (
        AdaptixErrorCode.INVALID_STATE_TRANSITION
    ),
    MihErrorCode.RECOMMENDATION_ALREADY_ENROLLED: (
        AdaptixErrorCode.INVALID_STATE_TRANSITION
    ),
    MihErrorCode.RECOMMENDATION_INVALID_TRANSITION: (
        AdaptixErrorCode.INVALID_STATE_TRANSITION
    ),
    MihErrorCode.RECOMMENDATION_PATIENT_IDENTITY_MISMATCH: (
        AdaptixErrorCode.CONSTRAINT_VIOLATION
    ),
    MihErrorCode.RECOMMENDATION_ENROLLMENT_NOT_ACTIVE: AdaptixErrorCode.WORKFLOW_BLOCKED,
}


#: Translation from the bare ``error_code`` strings Adaptix-MIH-Service puts
#: in ``HTTPException.detail`` to this enum. The service does not prefix its
#: codes with ``mih.``; consumers that receive a raw service response use
#: :func:`from_service_error_code` to classify it.
MIH_SERVICE_ERROR_CODES: dict[str, MihErrorCode] = {
    "consent_required": MihErrorCode.ENROLLMENT_CONSENT_REQUIRED,
    "patient_not_found": MihErrorCode.ENROLLMENT_NOT_FOUND,
    "already_enrolled": MihErrorCode.ENROLLMENT_ALREADY_EXISTS,
    "invalid_metric": MihErrorCode.READING_INVALID_METRIC,
    "escalation_not_found": MihErrorCode.ESCALATION_NOT_FOUND,
    "policy_not_configured": MihErrorCode.UTILIZATION_POLICY_NOT_CONFIGURED,
    "policy_version_conflict": MihErrorCode.UTILIZATION_POLICY_VERSION_CONFLICT,
    "invalid_event_type": MihErrorCode.UTILIZATION_INVALID_EVENT_TYPE,
    "invalid_source_system": MihErrorCode.UTILIZATION_INVALID_SOURCE_SYSTEM,
    "occurred_at_in_future": MihErrorCode.UTILIZATION_OCCURRED_AT_IN_FUTURE,
    "source_event_conflict": MihErrorCode.UTILIZATION_SOURCE_EVENT_CONFLICT,
    "evaluation_conflict": MihErrorCode.UTILIZATION_EVALUATION_CONFLICT,
    "recommendation_not_found": MihErrorCode.RECOMMENDATION_NOT_FOUND,
    "recommendation_already_dismissed": MihErrorCode.RECOMMENDATION_ALREADY_DISMISSED,
    "recommendation_already_enrolled": MihErrorCode.RECOMMENDATION_ALREADY_ENROLLED,
    "invalid_transition": MihErrorCode.RECOMMENDATION_INVALID_TRANSITION,
    "patient_identity_mismatch": (
        MihErrorCode.RECOMMENDATION_PATIENT_IDENTITY_MISMATCH
    ),
    "enrollment_not_active": MihErrorCode.RECOMMENDATION_ENROLLMENT_NOT_ACTIVE,
}


def from_service_error_code(error_code: str) -> Optional[MihErrorCode]:
    """Classify a bare Adaptix-MIH-Service ``error_code``; ``None`` if unknown.

    Unknown is returned rather than guessed: a consumer must not invent a
    meaning for a code this package does not know.
    """

    return MIH_SERVICE_ERROR_CODES.get(error_code)


def to_adaptix_error_code(mih_code: MihErrorCode) -> AdaptixErrorCode:
    """Return the closest :class:`AdaptixErrorCode` for a MIH-specific code."""

    return _MIH_TO_PLATFORM[mih_code]


class MihErrorEnvelope(AdaptixErrorEnvelope):
    """MIH-scoped error envelope.

    Adds ``mih_error_code`` alongside the canonical
    :attr:`AdaptixErrorEnvelope.error_code` so a consumer that understands
    MIH can branch on the specific reason without parsing message strings,
    while a generic consumer keeps reading the platform ``error_code``.
    """

    mih_error_code: MihErrorCode | None = Field(
        default=None,
        description="MIH-specific error code, alongside the platform error_code.",
    )

    @classmethod
    def from_mih_code(
        cls,
        mih_code: MihErrorCode,
        *,
        message: str,
        detail: Optional[str] = None,
        validation_errors: Optional[list[AdaptixValidationErrorDetail]] = None,
        provider_error: Optional[AdaptixProviderErrorDetail] = None,
        trace: Optional[AdaptixTraceContext] = None,
    ) -> "MihErrorEnvelope":
        return cls(
            error_code=to_adaptix_error_code(mih_code),
            mih_error_code=mih_code,
            message=message,
            detail=detail,
            validation_errors=validation_errors,
            provider_error=provider_error,
            trace=trace,
        )


class MihServiceError(Exception):
    """Exception carrier for :class:`MihErrorEnvelope`.

    MIH service handlers may raise this to short-circuit request handling
    with a canonical error envelope. The API layer maps
    ``MihServiceError`` → HTTP response using
    :meth:`AdaptixErrorEnvelope.to_http_response`.
    """

    def __init__(self, envelope: MihErrorEnvelope, http_status: int = 400) -> None:
        super().__init__(envelope.message)
        self.envelope = envelope
        self.http_status = http_status

    @classmethod
    def from_mih_code(
        cls,
        mih_code: MihErrorCode,
        *,
        message: str,
        http_status: int = 400,
        detail: Optional[str] = None,
        validation_errors: Optional[list[AdaptixValidationErrorDetail]] = None,
        provider_error: Optional[AdaptixProviderErrorDetail] = None,
        trace: Optional[AdaptixTraceContext] = None,
    ) -> "MihServiceError":
        envelope = MihErrorEnvelope.from_mih_code(
            mih_code,
            message=message,
            detail=detail,
            validation_errors=validation_errors,
            provider_error=provider_error,
            trace=trace,
        )
        return cls(envelope=envelope, http_status=http_status)


# ---------------------------------------------------------------------------
# Convenience constructors for the most common MIH error paths
# ---------------------------------------------------------------------------


def enrollment_not_found(
    enrollment_id: str,
    trace: Optional[AdaptixTraceContext] = None,
) -> MihErrorEnvelope:
    return MihErrorEnvelope.from_mih_code(
        MihErrorCode.ENROLLMENT_NOT_FOUND,
        message=f"MIH enrollment {enrollment_id} not found",
        trace=trace,
    )


def enrollment_consent_required(
    enrollment_id: str,
    trace: Optional[AdaptixTraceContext] = None,
) -> MihErrorEnvelope:
    return MihErrorEnvelope.from_mih_code(
        MihErrorCode.ENROLLMENT_CONSENT_REQUIRED,
        message=(
            f"MIH enrollment {enrollment_id} cannot proceed: "
            "patient consent has not been recorded"
        ),
        trace=trace,
    )


def visit_invalid_state_transition(
    visit_id: str,
    from_status: str,
    to_status: str,
    trace: Optional[AdaptixTraceContext] = None,
) -> MihErrorEnvelope:
    return MihErrorEnvelope.from_mih_code(
        MihErrorCode.VISIT_INVALID_STATE_TRANSITION,
        message=(
            f"MIH visit {visit_id} cannot transition from {from_status} to {to_status}"
        ),
        trace=trace,
    )


def payer_not_authorized_for_program(
    program_id: str,
    payer: str,
    trace: Optional[AdaptixTraceContext] = None,
) -> MihErrorEnvelope:
    return MihErrorEnvelope.from_mih_code(
        MihErrorCode.PAYER_NOT_AUTHORIZED_FOR_PROGRAM,
        message=(f"MIH program {program_id} is not authorized to bill payer {payer}"),
        trace=trace,
    )


def utilization_policy_not_configured(
    trace: Optional[AdaptixTraceContext] = None,
) -> MihErrorEnvelope:
    return MihErrorEnvelope.from_mih_code(
        MihErrorCode.UTILIZATION_POLICY_NOT_CONFIGURED,
        message=(
            "This tenant has not configured a high-utilizer policy; no default thresholds are assumed"
        ),
        trace=trace,
    )


def recommendation_not_found(
    recommendation_id: str,
    trace: Optional[AdaptixTraceContext] = None,
) -> MihErrorEnvelope:
    return MihErrorEnvelope.from_mih_code(
        MihErrorCode.RECOMMENDATION_NOT_FOUND,
        message=f"MIH enrollment recommendation {recommendation_id} not found",
        trace=trace,
    )


def recommendation_invalid_transition(
    recommendation_id: str,
    current_status: str,
    action: str,
    trace: Optional[AdaptixTraceContext] = None,
) -> MihErrorEnvelope:
    return MihErrorEnvelope.from_mih_code(
        MihErrorCode.RECOMMENDATION_INVALID_TRANSITION,
        message=(
            f"MIH enrollment recommendation {recommendation_id} cannot {action} from status {current_status}"
        ),
        trace=trace,
    )


__all__ = [
    "MIH_SERVICE_ERROR_CODES",
    "MihErrorCode",
    "MihErrorEnvelope",
    "MihServiceError",
    "enrollment_consent_required",
    "enrollment_not_found",
    "from_service_error_code",
    "payer_not_authorized_for_program",
    "recommendation_invalid_transition",
    "recommendation_not_found",
    "to_adaptix_error_code",
    "utilization_policy_not_configured",
    "visit_invalid_state_transition",
]
