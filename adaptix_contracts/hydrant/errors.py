"""Adaptix Hydrant Registry — Service error contracts.

Play P07. Hydrant-specific error codes plus convenience constructors that
return a canonical :class:`adaptix_contracts.errors.envelope.AdaptixErrorEnvelope`,
so the Hydrant-Service, pre-plan/dispatch consumers, Core, and the UI all
read a single error shape rather than a domain-specific exception
hierarchy.

Design note: Adaptix does not use Python exception classes as its public
error contract — the platform contract is the envelope model in
``adaptix_contracts/errors/envelope.py``. This module extends that
contract with Hydrant-specific error codes and typed factory functions;
services that want to raise may wrap ``HydrantServiceError`` around an
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


class HydrantErrorCode(str, Enum):
    """Hydrant-specific error codes.

    Values are namespaced with ``hydrant.`` so they never collide with the
    platform-wide :class:`AdaptixErrorCode` when serialized side-by-side.
    Consumers that only understand :class:`AdaptixErrorCode` MUST map
    these to the closest generic code using :func:`to_adaptix_error_code`.
    """

    HYDRANT_NOT_FOUND = "hydrant.hydrant_not_found"
    HYDRANT_ALREADY_EXISTS = "hydrant.hydrant_already_exists"
    HYDRANT_ALREADY_OUT_OF_SERVICE = "hydrant.hydrant_already_out_of_service"
    HYDRANT_INVALID_STATUS_TRANSITION = "hydrant.hydrant_invalid_status_transition"

    TEST_NOT_FOUND = "hydrant.test_not_found"
    TEST_INVALID_READING = "hydrant.test_invalid_reading"
    TEST_DUPLICATE_SUBMISSION = "hydrant.test_duplicate_submission"

    MAINTENANCE_NOT_FOUND = "hydrant.maintenance_not_found"
    MAINTENANCE_ALREADY_CLOSED = "hydrant.maintenance_already_closed"

    LOCATION_REQUIRED = "hydrant.location_required"
    ASSET_TAG_REQUIRED = "hydrant.asset_tag_required"


_HYDRANT_TO_PLATFORM: dict[HydrantErrorCode, AdaptixErrorCode] = {
    HydrantErrorCode.HYDRANT_NOT_FOUND: AdaptixErrorCode.NOT_FOUND,
    HydrantErrorCode.HYDRANT_ALREADY_EXISTS: AdaptixErrorCode.ALREADY_EXISTS,
    HydrantErrorCode.HYDRANT_ALREADY_OUT_OF_SERVICE: AdaptixErrorCode.INVALID_STATE_TRANSITION,
    HydrantErrorCode.HYDRANT_INVALID_STATUS_TRANSITION: AdaptixErrorCode.INVALID_STATE_TRANSITION,
    HydrantErrorCode.TEST_NOT_FOUND: AdaptixErrorCode.NOT_FOUND,
    HydrantErrorCode.TEST_INVALID_READING: AdaptixErrorCode.INVALID_VALUE,
    HydrantErrorCode.TEST_DUPLICATE_SUBMISSION: AdaptixErrorCode.DUPLICATE_RECORD,
    HydrantErrorCode.MAINTENANCE_NOT_FOUND: AdaptixErrorCode.NOT_FOUND,
    HydrantErrorCode.MAINTENANCE_ALREADY_CLOSED: AdaptixErrorCode.INVALID_STATE_TRANSITION,
    HydrantErrorCode.LOCATION_REQUIRED: AdaptixErrorCode.REQUIRED_FIELD_MISSING,
    HydrantErrorCode.ASSET_TAG_REQUIRED: AdaptixErrorCode.REQUIRED_FIELD_MISSING,
}


def to_adaptix_error_code(hydrant_code: HydrantErrorCode) -> AdaptixErrorCode:
    """Return the closest :class:`AdaptixErrorCode` for a Hydrant-specific code."""

    return _HYDRANT_TO_PLATFORM[hydrant_code]


class HydrantErrorEnvelope(AdaptixErrorEnvelope):
    """Hydrant-scoped error envelope.

    Adds ``hydrant_error_code`` alongside the canonical
    :attr:`AdaptixErrorEnvelope.error_code` so a consumer that understands
    Hydrant can branch on the specific reason without parsing message
    strings, while a generic consumer keeps reading the platform
    ``error_code``.
    """

    hydrant_error_code: HydrantErrorCode | None = Field(
        default=None,
        description="Hydrant-specific error code, alongside the platform error_code.",
    )

    @classmethod
    def from_hydrant_code(
        cls,
        hydrant_code: HydrantErrorCode,
        *,
        message: str,
        detail: Optional[str] = None,
        validation_errors: Optional[list[AdaptixValidationErrorDetail]] = None,
        provider_error: Optional[AdaptixProviderErrorDetail] = None,
        trace: Optional[AdaptixTraceContext] = None,
    ) -> "HydrantErrorEnvelope":
        return cls(
            error_code=to_adaptix_error_code(hydrant_code),
            hydrant_error_code=hydrant_code,
            message=message,
            detail=detail,
            validation_errors=validation_errors,
            provider_error=provider_error,
            trace=trace,
        )


class HydrantServiceError(Exception):
    """Exception carrier for :class:`HydrantErrorEnvelope`.

    Hydrant service handlers may raise this to short-circuit request
    handling with a canonical error envelope. The API layer maps
    ``HydrantServiceError`` → HTTP response using
    :meth:`AdaptixErrorEnvelope.to_http_response`.
    """

    def __init__(self, envelope: HydrantErrorEnvelope, http_status: int = 400) -> None:
        super().__init__(envelope.message)
        self.envelope = envelope
        self.http_status = http_status

    @classmethod
    def from_hydrant_code(
        cls,
        hydrant_code: HydrantErrorCode,
        *,
        message: str,
        http_status: int = 400,
        detail: Optional[str] = None,
        validation_errors: Optional[list[AdaptixValidationErrorDetail]] = None,
        provider_error: Optional[AdaptixProviderErrorDetail] = None,
        trace: Optional[AdaptixTraceContext] = None,
    ) -> "HydrantServiceError":
        envelope = HydrantErrorEnvelope.from_hydrant_code(
            hydrant_code,
            message=message,
            detail=detail,
            validation_errors=validation_errors,
            provider_error=provider_error,
            trace=trace,
        )
        return cls(envelope=envelope, http_status=http_status)


# ---------------------------------------------------------------------------
# Convenience constructors for the most common Hydrant error paths
# ---------------------------------------------------------------------------


def hydrant_not_found(
    hydrant_id: str,
    trace: Optional[AdaptixTraceContext] = None,
) -> HydrantErrorEnvelope:
    return HydrantErrorEnvelope.from_hydrant_code(
        HydrantErrorCode.HYDRANT_NOT_FOUND,
        message=f"Hydrant {hydrant_id} not found",
        trace=trace,
    )


def hydrant_invalid_status_transition(
    hydrant_id: str,
    from_status: str,
    to_status: str,
    trace: Optional[AdaptixTraceContext] = None,
) -> HydrantErrorEnvelope:
    return HydrantErrorEnvelope.from_hydrant_code(
        HydrantErrorCode.HYDRANT_INVALID_STATUS_TRANSITION,
        message=(
            f"Hydrant {hydrant_id} cannot transition from {from_status} to {to_status}"
        ),
        trace=trace,
    )


def test_invalid_reading(
    hydrant_test_id: str,
    reason: str,
    trace: Optional[AdaptixTraceContext] = None,
) -> HydrantErrorEnvelope:
    return HydrantErrorEnvelope.from_hydrant_code(
        HydrantErrorCode.TEST_INVALID_READING,
        message=f"Hydrant test {hydrant_test_id} has an invalid reading: {reason}",
        trace=trace,
    )


def maintenance_not_found(
    hydrant_maintenance_id: str,
    trace: Optional[AdaptixTraceContext] = None,
) -> HydrantErrorEnvelope:
    return HydrantErrorEnvelope.from_hydrant_code(
        HydrantErrorCode.MAINTENANCE_NOT_FOUND,
        message=f"Hydrant maintenance record {hydrant_maintenance_id} not found",
        trace=trace,
    )


__all__ = [
    "HydrantErrorCode",
    "HydrantErrorEnvelope",
    "HydrantServiceError",
    "hydrant_invalid_status_transition",
    "hydrant_not_found",
    "maintenance_not_found",
    "test_invalid_reading",
    "to_adaptix_error_code",
]
