"""Adaptix TEFCA QHIN Sub-Participant — Service error contracts.

Play P26. QHIN-specific error codes plus convenience constructors that
return a canonical :class:`adaptix_contracts.errors.envelope.AdaptixErrorEnvelope`,
so the QHIN-Service, Core, and the UI all read a single error shape rather
than a domain-specific exception hierarchy.

Design note: Adaptix does not use Python exception classes as its public
error contract — the platform contract is the envelope model in
``adaptix_contracts/errors/envelope.py``. This module extends that
contract with QHIN-specific error codes and typed factory functions;
services that want to raise may wrap ``QhinServiceError`` around an
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


class QhinErrorCode(str, Enum):
    """QHIN-specific error codes.

    Values are namespaced with ``qhin.`` so they never collide with the
    platform-wide :class:`AdaptixErrorCode` when serialized side-by-side.
    Consumers that only understand :class:`AdaptixErrorCode` MUST map
    these to the closest generic code using :func:`to_adaptix_error_code`.
    """

    CREDENTIAL_NOT_FOUND = "qhin.credential_not_found"
    CREDENTIAL_INACTIVE = "qhin.credential_inactive"
    CREDENTIAL_EXPIRED = "qhin.credential_expired"
    CREDENTIAL_PURPOSE_NOT_AUTHORIZED = "qhin.credential_purpose_not_authorized"

    TRANSACTION_NOT_FOUND = "qhin.transaction_not_found"
    TRANSACTION_ALREADY_COMPLETED = "qhin.transaction_already_completed"
    TRANSACTION_TIMED_OUT = "qhin.transaction_timed_out"
    TRANSACTION_RETRY_EXHAUSTED = "qhin.transaction_retry_exhausted"

    BUNDLE_NOT_FOUND = "qhin.bundle_not_found"
    BUNDLE_INVALID_FHIR = "qhin.bundle_invalid_fhir"
    BUNDLE_PATIENT_MISMATCH = "qhin.bundle_patient_mismatch"

    ACKNOWLEDGMENT_NOT_FOUND = "qhin.acknowledgment_not_found"
    ACKNOWLEDGMENT_REJECTED = "qhin.acknowledgment_rejected"

    QHIN_UNAVAILABLE = "qhin.qhin_unavailable"
    QHIN_AUTH_FAILED = "qhin.qhin_auth_failed"
    FHIR_VERSION_UNSUPPORTED = "qhin.fhir_version_unsupported"
    PATIENT_NOT_DISCOVERABLE = "qhin.patient_not_discoverable"


_QHIN_TO_PLATFORM: dict[QhinErrorCode, AdaptixErrorCode] = {
    QhinErrorCode.CREDENTIAL_NOT_FOUND: AdaptixErrorCode.NOT_FOUND,
    QhinErrorCode.CREDENTIAL_INACTIVE: AdaptixErrorCode.WORKFLOW_BLOCKED,
    QhinErrorCode.CREDENTIAL_EXPIRED: AdaptixErrorCode.CREDENTIAL_GATED,
    QhinErrorCode.CREDENTIAL_PURPOSE_NOT_AUTHORIZED: AdaptixErrorCode.CONSTRAINT_VIOLATION,
    QhinErrorCode.TRANSACTION_NOT_FOUND: AdaptixErrorCode.NOT_FOUND,
    QhinErrorCode.TRANSACTION_ALREADY_COMPLETED: AdaptixErrorCode.INVALID_STATE_TRANSITION,
    QhinErrorCode.TRANSACTION_TIMED_OUT: AdaptixErrorCode.TIMEOUT,
    QhinErrorCode.TRANSACTION_RETRY_EXHAUSTED: AdaptixErrorCode.PROVIDER_UNAVAILABLE,
    QhinErrorCode.BUNDLE_NOT_FOUND: AdaptixErrorCode.NOT_FOUND,
    QhinErrorCode.BUNDLE_INVALID_FHIR: AdaptixErrorCode.VALIDATION_FAILED,
    QhinErrorCode.BUNDLE_PATIENT_MISMATCH: AdaptixErrorCode.CONSTRAINT_VIOLATION,
    QhinErrorCode.ACKNOWLEDGMENT_NOT_FOUND: AdaptixErrorCode.NOT_FOUND,
    QhinErrorCode.ACKNOWLEDGMENT_REJECTED: AdaptixErrorCode.PROVIDER_ERROR,
    QhinErrorCode.QHIN_UNAVAILABLE: AdaptixErrorCode.PROVIDER_UNAVAILABLE,
    QhinErrorCode.QHIN_AUTH_FAILED: AdaptixErrorCode.UNAUTHORIZED,
    QhinErrorCode.FHIR_VERSION_UNSUPPORTED: AdaptixErrorCode.INVALID_VALUE,
    QhinErrorCode.PATIENT_NOT_DISCOVERABLE: AdaptixErrorCode.NOT_FOUND,
}


def to_adaptix_error_code(qhin_code: QhinErrorCode) -> AdaptixErrorCode:
    """Return the closest :class:`AdaptixErrorCode` for a QHIN-specific code."""

    return _QHIN_TO_PLATFORM[qhin_code]


class QhinErrorEnvelope(AdaptixErrorEnvelope):
    """QHIN-scoped error envelope.

    Adds ``qhin_error_code`` alongside the canonical
    :attr:`AdaptixErrorEnvelope.error_code` so a consumer that understands
    QHIN can branch on the specific reason without parsing message strings,
    while a generic consumer keeps reading the platform ``error_code``.
    """

    qhin_error_code: QhinErrorCode | None = Field(
        default=None,
        description="QHIN-specific error code, alongside the platform error_code.",
    )

    @classmethod
    def from_qhin_code(
        cls,
        qhin_code: QhinErrorCode,
        *,
        message: str,
        detail: Optional[str] = None,
        validation_errors: Optional[list[AdaptixValidationErrorDetail]] = None,
        provider_error: Optional[AdaptixProviderErrorDetail] = None,
        trace: Optional[AdaptixTraceContext] = None,
    ) -> "QhinErrorEnvelope":
        return cls(
            error_code=to_adaptix_error_code(qhin_code),
            qhin_error_code=qhin_code,
            message=message,
            detail=detail,
            validation_errors=validation_errors,
            provider_error=provider_error,
            trace=trace,
        )


class QhinServiceError(Exception):
    """Exception carrier for :class:`QhinErrorEnvelope`.

    QHIN service handlers may raise this to short-circuit request handling
    with a canonical error envelope. The API layer maps
    ``QhinServiceError`` → HTTP response using
    :meth:`AdaptixErrorEnvelope.to_http_response`.
    """

    def __init__(self, envelope: QhinErrorEnvelope, http_status: int = 400) -> None:
        super().__init__(envelope.message)
        self.envelope = envelope
        self.http_status = http_status

    @classmethod
    def from_qhin_code(
        cls,
        qhin_code: QhinErrorCode,
        *,
        message: str,
        http_status: int = 400,
        detail: Optional[str] = None,
        validation_errors: Optional[list[AdaptixValidationErrorDetail]] = None,
        provider_error: Optional[AdaptixProviderErrorDetail] = None,
        trace: Optional[AdaptixTraceContext] = None,
    ) -> "QhinServiceError":
        envelope = QhinErrorEnvelope.from_qhin_code(
            qhin_code,
            message=message,
            detail=detail,
            validation_errors=validation_errors,
            provider_error=provider_error,
            trace=trace,
        )
        return cls(envelope=envelope, http_status=http_status)


# ---------------------------------------------------------------------------
# Convenience constructors for the most common QHIN error paths
# ---------------------------------------------------------------------------


def credential_not_found(
    credential_id: str,
    trace: Optional[AdaptixTraceContext] = None,
) -> QhinErrorEnvelope:
    return QhinErrorEnvelope.from_qhin_code(
        QhinErrorCode.CREDENTIAL_NOT_FOUND,
        message=f"QHIN credential {credential_id} not found",
        trace=trace,
    )


def credential_purpose_not_authorized(
    credential_id: str,
    purpose: str,
    trace: Optional[AdaptixTraceContext] = None,
) -> QhinErrorEnvelope:
    return QhinErrorEnvelope.from_qhin_code(
        QhinErrorCode.CREDENTIAL_PURPOSE_NOT_AUTHORIZED,
        message=(
            f"QHIN credential {credential_id} is not authorized to assert "
            f"exchange purpose {purpose}"
        ),
        trace=trace,
    )


def transaction_not_found(
    transaction_id: str,
    trace: Optional[AdaptixTraceContext] = None,
) -> QhinErrorEnvelope:
    return QhinErrorEnvelope.from_qhin_code(
        QhinErrorCode.TRANSACTION_NOT_FOUND,
        message=f"QHIN transaction {transaction_id} not found",
        trace=trace,
    )


def qhin_unavailable(
    qhin: str,
    trace: Optional[AdaptixTraceContext] = None,
) -> QhinErrorEnvelope:
    return QhinErrorEnvelope.from_qhin_code(
        QhinErrorCode.QHIN_UNAVAILABLE,
        message=f"QHIN {qhin} is unavailable",
        trace=trace,
    )


__all__ = [
    "QhinErrorCode",
    "QhinErrorEnvelope",
    "QhinServiceError",
    "credential_not_found",
    "credential_purpose_not_authorized",
    "qhin_unavailable",
    "to_adaptix_error_code",
    "transaction_not_found",
]
