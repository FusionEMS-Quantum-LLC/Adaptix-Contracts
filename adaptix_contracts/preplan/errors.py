"""NFPA 1620 Pre-Incident Planning — Service error contracts.

Play P07. Preplan-specific error codes plus convenience constructors that
return a canonical :class:`adaptix_contracts.errors.envelope.AdaptixErrorEnvelope`,
so the Preplan service, dispatch/CAD context enrichment, and the UI all
read a single error shape rather than a domain-specific exception
hierarchy.

Design note: Adaptix does not use Python exception classes as its public
error contract — the platform contract is the envelope model in
``adaptix_contracts/errors/envelope.py``. This module extends that
contract with Preplan-specific error codes and typed factory functions;
services that want to raise may wrap ``PreplanServiceError`` around an
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


class PreplanErrorCode(str, Enum):
    """Preplan-specific error codes.

    Values are namespaced with ``preplan.`` so they never collide with
    the platform-wide :class:`AdaptixErrorCode` when serialized
    side-by-side. Consumers that only understand :class:`AdaptixErrorCode`
    MUST map these to the closest generic code using
    :func:`to_adaptix_error_code`.
    """

    OCCUPANCY_NOT_FOUND = "preplan.occupancy_not_found"
    OCCUPANCY_ALREADY_EXISTS = "preplan.occupancy_already_exists"
    OCCUPANCY_INACTIVE = "preplan.occupancy_inactive"

    PREPLAN_NOT_FOUND = "preplan.preplan_not_found"
    PREPLAN_ALREADY_PUBLISHED = "preplan.preplan_already_published"
    PREPLAN_NOT_APPROVED = "preplan.preplan_not_approved"
    PREPLAN_SUPERSEDED = "preplan.preplan_superseded"
    PREPLAN_NOT_READY_FOR_RESPONSE = "preplan.preplan_not_ready_for_response"

    FLOOR_PLAN_NOT_FOUND = "preplan.floor_plan_not_found"
    FLOOR_PLAN_ARTIFACT_UNAVAILABLE = "preplan.floor_plan_artifact_unavailable"

    HAZARD_NOT_FOUND = "preplan.hazard_not_found"
    HAZARD_INVALID_CLASSIFICATION = "preplan.hazard_invalid_classification"

    KNOX_BOX_MISSING = "preplan.knox_box_missing"
    KNOX_BOX_INOPERABLE = "preplan.knox_box_inoperable"
    KNOX_BOX_VERIFICATION_STALE = "preplan.knox_box_verification_stale"

    CAD_LINK_INVALID = "preplan.cad_link_invalid"


_PREPLAN_TO_PLATFORM: dict[PreplanErrorCode, AdaptixErrorCode] = {
    PreplanErrorCode.OCCUPANCY_NOT_FOUND: AdaptixErrorCode.NOT_FOUND,
    PreplanErrorCode.OCCUPANCY_ALREADY_EXISTS: AdaptixErrorCode.ALREADY_EXISTS,
    PreplanErrorCode.OCCUPANCY_INACTIVE: AdaptixErrorCode.WORKFLOW_BLOCKED,
    PreplanErrorCode.PREPLAN_NOT_FOUND: AdaptixErrorCode.NOT_FOUND,
    PreplanErrorCode.PREPLAN_ALREADY_PUBLISHED: AdaptixErrorCode.INVALID_STATE_TRANSITION,
    PreplanErrorCode.PREPLAN_NOT_APPROVED: AdaptixErrorCode.WORKFLOW_BLOCKED,
    PreplanErrorCode.PREPLAN_SUPERSEDED: AdaptixErrorCode.INVALID_STATE_TRANSITION,
    PreplanErrorCode.PREPLAN_NOT_READY_FOR_RESPONSE: AdaptixErrorCode.WORKFLOW_BLOCKED,
    PreplanErrorCode.FLOOR_PLAN_NOT_FOUND: AdaptixErrorCode.NOT_FOUND,
    PreplanErrorCode.FLOOR_PLAN_ARTIFACT_UNAVAILABLE: AdaptixErrorCode.ARTIFACT_UNAVAILABLE,
    PreplanErrorCode.HAZARD_NOT_FOUND: AdaptixErrorCode.NOT_FOUND,
    PreplanErrorCode.HAZARD_INVALID_CLASSIFICATION: AdaptixErrorCode.INVALID_VALUE,
    PreplanErrorCode.KNOX_BOX_MISSING: AdaptixErrorCode.WORKFLOW_BLOCKED,
    PreplanErrorCode.KNOX_BOX_INOPERABLE: AdaptixErrorCode.WORKFLOW_BLOCKED,
    PreplanErrorCode.KNOX_BOX_VERIFICATION_STALE: AdaptixErrorCode.WORKFLOW_BLOCKED,
    PreplanErrorCode.CAD_LINK_INVALID: AdaptixErrorCode.INVALID_VALUE,
}


def to_adaptix_error_code(preplan_code: PreplanErrorCode) -> AdaptixErrorCode:
    """Return the closest :class:`AdaptixErrorCode` for a Preplan-specific code."""

    return _PREPLAN_TO_PLATFORM[preplan_code]


class PreplanErrorEnvelope(AdaptixErrorEnvelope):
    """Preplan-scoped error envelope.

    Adds ``preplan_error_code`` alongside the canonical
    :attr:`AdaptixErrorEnvelope.error_code` so a consumer that understands
    Preplan can branch on the specific reason without parsing message
    strings, while a generic consumer keeps reading the platform
    ``error_code``.
    """

    preplan_error_code: PreplanErrorCode | None = Field(
        default=None,
        description="Preplan-specific error code, alongside the platform error_code.",
    )

    @classmethod
    def from_preplan_code(
        cls,
        preplan_code: PreplanErrorCode,
        *,
        message: str,
        detail: Optional[str] = None,
        validation_errors: Optional[list[AdaptixValidationErrorDetail]] = None,
        provider_error: Optional[AdaptixProviderErrorDetail] = None,
        trace: Optional[AdaptixTraceContext] = None,
    ) -> "PreplanErrorEnvelope":
        return cls(
            error_code=to_adaptix_error_code(preplan_code),
            preplan_error_code=preplan_code,
            message=message,
            detail=detail,
            validation_errors=validation_errors,
            provider_error=provider_error,
            trace=trace,
        )


class PreplanServiceError(Exception):
    """Exception carrier for :class:`PreplanErrorEnvelope`.

    Preplan service handlers may raise this to short-circuit request
    handling with a canonical error envelope. The API layer maps
    ``PreplanServiceError`` → HTTP response using
    :meth:`AdaptixErrorEnvelope.to_http_response`.
    """

    def __init__(self, envelope: PreplanErrorEnvelope, http_status: int = 400) -> None:
        super().__init__(envelope.message)
        self.envelope = envelope
        self.http_status = http_status

    @classmethod
    def from_preplan_code(
        cls,
        preplan_code: PreplanErrorCode,
        *,
        message: str,
        http_status: int = 400,
        detail: Optional[str] = None,
        validation_errors: Optional[list[AdaptixValidationErrorDetail]] = None,
        provider_error: Optional[AdaptixProviderErrorDetail] = None,
        trace: Optional[AdaptixTraceContext] = None,
    ) -> "PreplanServiceError":
        envelope = PreplanErrorEnvelope.from_preplan_code(
            preplan_code,
            message=message,
            detail=detail,
            validation_errors=validation_errors,
            provider_error=provider_error,
            trace=trace,
        )
        return cls(envelope=envelope, http_status=http_status)


# ---------------------------------------------------------------------------
# Convenience constructors for the most common Preplan error paths
# ---------------------------------------------------------------------------


def occupancy_not_found(
    occupancy_id: str,
    trace: Optional[AdaptixTraceContext] = None,
) -> PreplanErrorEnvelope:
    return PreplanErrorEnvelope.from_preplan_code(
        PreplanErrorCode.OCCUPANCY_NOT_FOUND,
        message=f"Preplan occupancy {occupancy_id} not found",
        trace=trace,
    )


def preplan_not_found(
    preplan_id: str,
    trace: Optional[AdaptixTraceContext] = None,
) -> PreplanErrorEnvelope:
    return PreplanErrorEnvelope.from_preplan_code(
        PreplanErrorCode.PREPLAN_NOT_FOUND,
        message=f"Preplan {preplan_id} not found",
        trace=trace,
    )


def preplan_not_ready_for_response(
    preplan_id: str,
    reason: str,
    trace: Optional[AdaptixTraceContext] = None,
) -> PreplanErrorEnvelope:
    return PreplanErrorEnvelope.from_preplan_code(
        PreplanErrorCode.PREPLAN_NOT_READY_FOR_RESPONSE,
        message=f"Preplan {preplan_id} is not ready for response: {reason}",
        trace=trace,
    )


def knox_box_missing(
    preplan_id: str,
    trace: Optional[AdaptixTraceContext] = None,
) -> PreplanErrorEnvelope:
    return PreplanErrorEnvelope.from_preplan_code(
        PreplanErrorCode.KNOX_BOX_MISSING,
        message=(
            f"Preplan {preplan_id} cannot be marked ready for response: "
            "Knox Box status is missing"
        ),
        trace=trace,
    )


__all__ = [
    "PreplanErrorCode",
    "PreplanErrorEnvelope",
    "PreplanServiceError",
    "knox_box_missing",
    "occupancy_not_found",
    "preplan_not_found",
    "preplan_not_ready_for_response",
    "to_adaptix_error_code",
]
