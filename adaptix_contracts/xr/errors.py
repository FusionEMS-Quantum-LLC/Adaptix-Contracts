"""Adaptix AR/XR Remote Physician Overwatch + Training — Service error contracts.

Play P04. XR-specific error codes plus typed error models that subclass the
canonical :class:`adaptix_contracts.errors.envelope.AdaptixErrorEnvelope`, so
the XR service, ePCR, Core, and the UI all read a single wire error shape
rather than a domain-specific exception hierarchy. Each subclass below pins
its own ``error_code``/``xr_error_code`` defaults so a caller can construct
the correct envelope with only the fields that vary per failure.
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field

from adaptix_contracts.errors.envelope import (
    AdaptixErrorCode,
    AdaptixErrorEnvelope,
    AdaptixTraceContext,
)


class XrErrorCode(str, Enum):
    """XR-specific error codes.

    Values are namespaced with ``xr.`` so they never collide with the
    platform-wide :class:`AdaptixErrorCode` when serialized side-by-side.
    Consumers that only understand :class:`AdaptixErrorCode` MUST map these
    to the closest generic code using :func:`to_adaptix_error_code`.
    """

    SESSION_NOT_FOUND = "xr.session_not_found"
    SESSION_ALREADY_ACTIVE = "xr.session_already_active"
    SESSION_ALREADY_ENDED = "xr.session_already_ended"
    SESSION_INVALID_STATE_TRANSITION = "xr.session_invalid_state_transition"
    SESSION_DEVICE_UNSUPPORTED = "xr.session_device_unsupported"
    SESSION_PHYSICIAN_REQUIRED = "xr.session_physician_required"

    ANNOTATION_NOT_FOUND = "xr.annotation_not_found"
    ANNOTATION_SESSION_NOT_ACTIVE = "xr.annotation_session_not_active"

    RECORDING_NOT_FOUND = "xr.recording_not_found"
    RECORDING_CONSENT_REQUIRED = "xr.recording_consent_required"
    RECORDING_PROCESSING_FAILED = "xr.recording_processing_failed"
    RECORDING_ALREADY_PURGED = "xr.recording_already_purged"

    TRAINING_SCENARIO_NOT_FOUND = "xr.training_scenario_not_found"
    TRAINING_SCENARIO_INACTIVE = "xr.training_scenario_inactive"


_XR_TO_PLATFORM: dict[XrErrorCode, AdaptixErrorCode] = {
    XrErrorCode.SESSION_NOT_FOUND: AdaptixErrorCode.NOT_FOUND,
    XrErrorCode.SESSION_ALREADY_ACTIVE: AdaptixErrorCode.CONFLICT,
    XrErrorCode.SESSION_ALREADY_ENDED: AdaptixErrorCode.INVALID_STATE_TRANSITION,
    XrErrorCode.SESSION_INVALID_STATE_TRANSITION: AdaptixErrorCode.INVALID_STATE_TRANSITION,
    XrErrorCode.SESSION_DEVICE_UNSUPPORTED: AdaptixErrorCode.INVALID_VALUE,
    XrErrorCode.SESSION_PHYSICIAN_REQUIRED: AdaptixErrorCode.REQUIRED_FIELD_MISSING,
    XrErrorCode.ANNOTATION_NOT_FOUND: AdaptixErrorCode.NOT_FOUND,
    XrErrorCode.ANNOTATION_SESSION_NOT_ACTIVE: AdaptixErrorCode.WORKFLOW_BLOCKED,
    XrErrorCode.RECORDING_NOT_FOUND: AdaptixErrorCode.NOT_FOUND,
    XrErrorCode.RECORDING_CONSENT_REQUIRED: AdaptixErrorCode.WORKFLOW_BLOCKED,
    XrErrorCode.RECORDING_PROCESSING_FAILED: AdaptixErrorCode.INTERNAL_ERROR,
    XrErrorCode.RECORDING_ALREADY_PURGED: AdaptixErrorCode.INVALID_STATE_TRANSITION,
    XrErrorCode.TRAINING_SCENARIO_NOT_FOUND: AdaptixErrorCode.NOT_FOUND,
    XrErrorCode.TRAINING_SCENARIO_INACTIVE: AdaptixErrorCode.WORKFLOW_BLOCKED,
}


def to_adaptix_error_code(xr_code: XrErrorCode) -> AdaptixErrorCode:
    """Return the closest :class:`AdaptixErrorCode` for an XR-specific code."""

    return _XR_TO_PLATFORM[xr_code]


class XrErrorEnvelope(AdaptixErrorEnvelope):
    """XR-scoped error envelope.

    Adds ``xr_error_code`` alongside the canonical
    :attr:`AdaptixErrorEnvelope.error_code` so a consumer that understands
    XR can branch on the specific reason without parsing message strings,
    while a generic consumer keeps reading the platform ``error_code``. This
    is the common base every typed XR error subclass below inherits.
    """

    xr_error_code: XrErrorCode = Field(
        ...,
        description="XR-specific error code, alongside the platform error_code.",
    )


# ---------------------------------------------------------------------------
# Typed error subclasses — one per XR error code, each with pinned defaults
# ---------------------------------------------------------------------------


class XrSessionNotFoundError(XrErrorEnvelope):
    """Raised/returned when a referenced ``XrSession`` id does not exist."""

    error_code: AdaptixErrorCode = AdaptixErrorCode.NOT_FOUND
    xr_error_code: XrErrorCode = XrErrorCode.SESSION_NOT_FOUND

    @classmethod
    def for_session(
        cls, session_id: str, trace: AdaptixTraceContext | None = None
    ) -> "XrSessionNotFoundError":
        return cls(message=f"XR session {session_id} not found", trace=trace)


class XrSessionAlreadyActiveError(XrErrorEnvelope):
    """Raised/returned when starting a session that is already ACTIVE."""

    error_code: AdaptixErrorCode = AdaptixErrorCode.CONFLICT
    xr_error_code: XrErrorCode = XrErrorCode.SESSION_ALREADY_ACTIVE

    @classmethod
    def for_session(
        cls, session_id: str, trace: AdaptixTraceContext | None = None
    ) -> "XrSessionAlreadyActiveError":
        return cls(message=f"XR session {session_id} is already active", trace=trace)


class XrSessionInvalidStateTransitionError(XrErrorEnvelope):
    """Raised/returned when a session status transition is not legal."""

    error_code: AdaptixErrorCode = AdaptixErrorCode.INVALID_STATE_TRANSITION
    xr_error_code: XrErrorCode = XrErrorCode.SESSION_INVALID_STATE_TRANSITION

    @classmethod
    def for_transition(
        cls,
        session_id: str,
        from_status: str,
        to_status: str,
        trace: AdaptixTraceContext | None = None,
    ) -> "XrSessionInvalidStateTransitionError":
        return cls(
            message=(
                f"XR session {session_id} cannot transition from {from_status} "
                f"to {to_status}"
            ),
            trace=trace,
        )


class XrSessionDeviceUnsupportedError(XrErrorEnvelope):
    """Raised/returned when a session references an unsupported device."""

    error_code: AdaptixErrorCode = AdaptixErrorCode.INVALID_VALUE
    xr_error_code: XrErrorCode = XrErrorCode.SESSION_DEVICE_UNSUPPORTED

    @classmethod
    def for_device(
        cls, device: str, trace: AdaptixTraceContext | None = None
    ) -> "XrSessionDeviceUnsupportedError":
        return cls(message=f"XR device {device} is not supported", trace=trace)


class XrSessionPhysicianRequiredError(XrErrorEnvelope):
    """Raised/returned when an overwatch session activates with no physician assigned."""

    error_code: AdaptixErrorCode = AdaptixErrorCode.REQUIRED_FIELD_MISSING
    xr_error_code: XrErrorCode = XrErrorCode.SESSION_PHYSICIAN_REQUIRED

    @classmethod
    def for_session(
        cls, session_id: str, trace: AdaptixTraceContext | None = None
    ) -> "XrSessionPhysicianRequiredError":
        return cls(
            message=(
                f"XR overwatch session {session_id} requires a remote physician "
                "before it can become active"
            ),
            trace=trace,
        )


class XrAnnotationNotFoundError(XrErrorEnvelope):
    """Raised/returned when a referenced ``PhysicianAnnotation`` id does not exist."""

    error_code: AdaptixErrorCode = AdaptixErrorCode.NOT_FOUND
    xr_error_code: XrErrorCode = XrErrorCode.ANNOTATION_NOT_FOUND

    @classmethod
    def for_annotation(
        cls, annotation_id: str, trace: AdaptixTraceContext | None = None
    ) -> "XrAnnotationNotFoundError":
        return cls(message=f"XR annotation {annotation_id} not found", trace=trace)


class XrAnnotationSessionNotActiveError(XrErrorEnvelope):
    """Raised/returned when an annotation is placed on a non-ACTIVE session."""

    error_code: AdaptixErrorCode = AdaptixErrorCode.WORKFLOW_BLOCKED
    xr_error_code: XrErrorCode = XrErrorCode.ANNOTATION_SESSION_NOT_ACTIVE

    @classmethod
    def for_session(
        cls, session_id: str, trace: AdaptixTraceContext | None = None
    ) -> "XrAnnotationSessionNotActiveError":
        return cls(
            message=f"XR session {session_id} is not active; annotations cannot be placed",
            trace=trace,
        )


class XrRecordingNotFoundError(XrErrorEnvelope):
    """Raised/returned when a referenced ``RecordingManifest`` id does not exist."""

    error_code: AdaptixErrorCode = AdaptixErrorCode.NOT_FOUND
    xr_error_code: XrErrorCode = XrErrorCode.RECORDING_NOT_FOUND

    @classmethod
    def for_recording(
        cls, recording_id: str, trace: AdaptixTraceContext | None = None
    ) -> "XrRecordingNotFoundError":
        return cls(message=f"XR recording {recording_id} not found", trace=trace)


class XrRecordingConsentRequiredError(XrErrorEnvelope):
    """Raised/returned when a recording is started without consent on file."""

    error_code: AdaptixErrorCode = AdaptixErrorCode.WORKFLOW_BLOCKED
    xr_error_code: XrErrorCode = XrErrorCode.RECORDING_CONSENT_REQUIRED

    @classmethod
    def for_session(
        cls, session_id: str, trace: AdaptixTraceContext | None = None
    ) -> "XrRecordingConsentRequiredError":
        return cls(
            message=(
                f"XR session {session_id} cannot record: consent has not been recorded"
            ),
            trace=trace,
        )


class XrRecordingProcessingFailedError(XrErrorEnvelope):
    """Raised/returned when a recording manifest fails to reach AVAILABLE."""

    error_code: AdaptixErrorCode = AdaptixErrorCode.INTERNAL_ERROR
    xr_error_code: XrErrorCode = XrErrorCode.RECORDING_PROCESSING_FAILED

    @classmethod
    def for_recording(
        cls,
        recording_id: str,
        detail: str | None = None,
        trace: AdaptixTraceContext | None = None,
    ) -> "XrRecordingProcessingFailedError":
        return cls(
            message=f"XR recording {recording_id} failed to process",
            detail=detail,
            trace=trace,
        )


class XrRecordingAlreadyPurgedError(XrErrorEnvelope):
    """Raised/returned when an operation targets an already-purged recording."""

    error_code: AdaptixErrorCode = AdaptixErrorCode.INVALID_STATE_TRANSITION
    xr_error_code: XrErrorCode = XrErrorCode.RECORDING_ALREADY_PURGED

    @classmethod
    def for_recording(
        cls, recording_id: str, trace: AdaptixTraceContext | None = None
    ) -> "XrRecordingAlreadyPurgedError":
        return cls(
            message=f"XR recording {recording_id} has already been purged",
            trace=trace,
        )


class XrTrainingScenarioNotFoundError(XrErrorEnvelope):
    """Raised/returned when a referenced ``TrainingScenario`` id does not exist."""

    error_code: AdaptixErrorCode = AdaptixErrorCode.NOT_FOUND
    xr_error_code: XrErrorCode = XrErrorCode.TRAINING_SCENARIO_NOT_FOUND

    @classmethod
    def for_scenario(
        cls, scenario_id: str, trace: AdaptixTraceContext | None = None
    ) -> "XrTrainingScenarioNotFoundError":
        return cls(message=f"XR training scenario {scenario_id} not found", trace=trace)


class XrTrainingScenarioInactiveError(XrErrorEnvelope):
    """Raised/returned when a training session references an inactive scenario."""

    error_code: AdaptixErrorCode = AdaptixErrorCode.WORKFLOW_BLOCKED
    xr_error_code: XrErrorCode = XrErrorCode.TRAINING_SCENARIO_INACTIVE

    @classmethod
    def for_scenario(
        cls, scenario_id: str, trace: AdaptixTraceContext | None = None
    ) -> "XrTrainingScenarioInactiveError":
        return cls(
            message=f"XR training scenario {scenario_id} is not active",
            trace=trace,
        )


__all__ = [
    "XrAnnotationNotFoundError",
    "XrAnnotationSessionNotActiveError",
    "XrErrorCode",
    "XrErrorEnvelope",
    "XrRecordingAlreadyPurgedError",
    "XrRecordingConsentRequiredError",
    "XrRecordingNotFoundError",
    "XrRecordingProcessingFailedError",
    "XrSessionAlreadyActiveError",
    "XrSessionDeviceUnsupportedError",
    "XrSessionInvalidStateTransitionError",
    "XrSessionNotFoundError",
    "XrSessionPhysicianRequiredError",
    "XrTrainingScenarioInactiveError",
    "XrTrainingScenarioNotFoundError",
    "to_adaptix_error_code",
]
