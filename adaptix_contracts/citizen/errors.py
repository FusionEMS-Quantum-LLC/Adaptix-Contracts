"""Service-specific error contracts for the Adaptix Citizen subpackage.

These extend the shared error envelope in ``adaptix_contracts.errors.envelope``
by providing typed exception classes that Citizen-service code can raise and
that boundary handlers can translate into ``AdaptixErrorEnvelope`` responses.

Rules:
- Exceptions MUST carry ``tenant_id`` where the tenant is known so that
  audit and correlation stay accurate.
- Exception messages are safe strings — no raw provider output, no PHI.
- ``to_envelope()`` produces a canonical ``AdaptixErrorEnvelope`` for the
  boundary. Handlers MUST use this rather than serialising the exception
  directly.
"""

from __future__ import annotations

from adaptix_contracts.errors.envelope import (
    AdaptixErrorCode,
    AdaptixErrorEnvelope,
    AdaptixProviderErrorDetail,
    AdaptixTraceContext,
    AdaptixValidationErrorDetail,
)


class CitizenServiceError(Exception):
    """Base for all Adaptix Citizen service errors.

    Subclasses map to a canonical :class:`AdaptixErrorCode` and produce a
    normalised :class:`AdaptixErrorEnvelope` at the boundary.
    """

    error_code: AdaptixErrorCode = AdaptixErrorCode.INTERNAL_ERROR
    default_message: str = "An internal error occurred in the Citizen service"

    def __init__(
        self,
        message: str | None = None,
        *,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
        detail: str | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.tenant_id = tenant_id
        self.correlation_id = correlation_id
        self.detail = detail
        super().__init__(self.message)

    def _trace(self) -> AdaptixTraceContext:
        return AdaptixTraceContext(
            tenant_id=self.tenant_id,
            correlation_id=self.correlation_id,
            service_name="adaptix-citizen-service",
        )

    def to_envelope(self) -> AdaptixErrorEnvelope:
        """Translate the exception into a canonical error envelope."""

        return AdaptixErrorEnvelope(
            error_code=self.error_code,
            message=self.message,
            detail=self.detail,
            trace=self._trace(),
        )


# ---------------------------------------------------------------------------
# Account errors
# ---------------------------------------------------------------------------


class CitizenAccountNotFound(CitizenServiceError):
    """Raised when a citizen account cannot be located under the tenant."""

    error_code = AdaptixErrorCode.RECORD_NOT_FOUND
    default_message = "Citizen account not found"


class CitizenAccountAlreadyExists(CitizenServiceError):
    """Raised when creating a duplicate citizen account."""

    error_code = AdaptixErrorCode.ALREADY_EXISTS
    default_message = "Citizen account already exists"


class CitizenAccountNotVerified(CitizenServiceError):
    """Raised when a protected action requires a verified account."""

    error_code = AdaptixErrorCode.FORBIDDEN
    default_message = "Citizen account is not verified"


class CitizenAccountSuspended(CitizenServiceError):
    """Raised when the account is suspended or deactivated."""

    error_code = AdaptixErrorCode.FORBIDDEN
    default_message = "Citizen account is suspended"


# ---------------------------------------------------------------------------
# MIH booking errors
# ---------------------------------------------------------------------------


class MihBookingNotFound(CitizenServiceError):
    """Raised when an MIH booking cannot be located under the tenant."""

    error_code = AdaptixErrorCode.RECORD_NOT_FOUND
    default_message = "MIH booking not found"


class MihBookingSlotUnavailable(CitizenServiceError):
    """Raised when the requested MIH slot cannot be scheduled."""

    error_code = AdaptixErrorCode.CONFLICT
    default_message = "Requested MIH slot is unavailable"


class MihBookingInvalidState(CitizenServiceError):
    """Raised on an invalid MIH booking state transition."""

    error_code = AdaptixErrorCode.INVALID_STATE_TRANSITION
    default_message = "MIH booking is in an incompatible state for this action"


class MihBookingConsentMissing(CitizenServiceError):
    """Raised when required consent is missing at booking time."""

    error_code = AdaptixErrorCode.WORKFLOW_BLOCKED
    default_message = "MIH booking requires consent that is not present"


# ---------------------------------------------------------------------------
# Bystander errors
# ---------------------------------------------------------------------------


class BystanderAlertNotFound(CitizenServiceError):
    """Raised when a bystander alert cannot be located under the tenant."""

    error_code = AdaptixErrorCode.RECORD_NOT_FOUND
    default_message = "Bystander alert not found"


class BystanderAlertExpired(CitizenServiceError):
    """Raised when acting on an expired bystander alert."""

    error_code = AdaptixErrorCode.INVALID_STATE_TRANSITION
    default_message = "Bystander alert has expired"


class BystanderAlertOutsideRadius(CitizenServiceError):
    """Raised when a responder attempts to accept an alert outside the radius."""

    error_code = AdaptixErrorCode.FORBIDDEN
    default_message = "Responder is outside the alert response radius"


class BystanderNotificationFailed(CitizenServiceError):
    """Raised when the notification fan-out could not be completed."""

    error_code = AdaptixErrorCode.PROVIDER_UNAVAILABLE
    default_message = "Bystander notification could not be dispatched"

    def __init__(
        self,
        message: str | None = None,
        *,
        provider: str,
        retryable: bool = True,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
        detail: str | None = None,
    ) -> None:
        super().__init__(
            message,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            detail=detail,
        )
        self.provider = provider
        self.retryable = retryable

    def to_envelope(self) -> AdaptixErrorEnvelope:
        return AdaptixErrorEnvelope(
            error_code=self.error_code,
            message=self.message,
            detail=self.detail,
            provider_error=AdaptixProviderErrorDetail(
                provider=self.provider,
                status="provider_unavailable",
                message=self.detail or self.message,
                retryable=self.retryable,
            ),
            trace=self._trace(),
        )


# ---------------------------------------------------------------------------
# Wearable errors
# ---------------------------------------------------------------------------


class WearableGrantNotFound(CitizenServiceError):
    """Raised when a wearable grant cannot be located under the tenant."""

    error_code = AdaptixErrorCode.RECORD_NOT_FOUND
    default_message = "Wearable grant not found"


class WearableGrantRevoked(CitizenServiceError):
    """Raised when acting on a revoked or expired wearable grant."""

    error_code = AdaptixErrorCode.FORBIDDEN
    default_message = "Wearable grant is revoked or expired"


class WearableProviderUnavailable(CitizenServiceError):
    """Raised when a wearable provider cannot service the request."""

    error_code = AdaptixErrorCode.PROVIDER_UNAVAILABLE
    default_message = "Wearable provider is unavailable"

    def __init__(
        self,
        message: str | None = None,
        *,
        provider: str,
        retryable: bool = True,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
        detail: str | None = None,
    ) -> None:
        super().__init__(
            message,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            detail=detail,
        )
        self.provider = provider
        self.retryable = retryable

    def to_envelope(self) -> AdaptixErrorEnvelope:
        return AdaptixErrorEnvelope(
            error_code=self.error_code,
            message=self.message,
            detail=self.detail,
            provider_error=AdaptixProviderErrorDetail(
                provider=self.provider,
                status="provider_unavailable",
                message=self.detail or self.message,
                retryable=self.retryable,
            ),
            trace=self._trace(),
        )


class WearableStreamValidationFailed(CitizenServiceError):
    """Raised when an ingested wearable stream fails validation."""

    error_code = AdaptixErrorCode.VALIDATION_FAILED
    default_message = "Wearable stream failed validation"

    def __init__(
        self,
        message: str | None = None,
        *,
        validation_errors: list[AdaptixValidationErrorDetail] | None = None,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
        detail: str | None = None,
    ) -> None:
        super().__init__(
            message,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            detail=detail,
        )
        self.validation_errors = validation_errors or []

    def to_envelope(self) -> AdaptixErrorEnvelope:
        return AdaptixErrorEnvelope(
            error_code=self.error_code,
            message=self.message,
            detail=self.detail,
            validation_errors=self.validation_errors or None,
            trace=self._trace(),
        )


# ---------------------------------------------------------------------------
# Recovery check-in errors
# ---------------------------------------------------------------------------


class RecoveryCheckInNotFound(CitizenServiceError):
    """Raised when a recovery check-in cannot be located under the tenant."""

    error_code = AdaptixErrorCode.RECORD_NOT_FOUND
    default_message = "Recovery check-in not found"


class RecoveryCheckInAlreadyCompleted(CitizenServiceError):
    """Raised on an attempt to complete an already-completed check-in."""

    error_code = AdaptixErrorCode.INVALID_STATE_TRANSITION
    default_message = "Recovery check-in is already completed"


__all__ = [
    "BystanderAlertExpired",
    "BystanderAlertNotFound",
    "BystanderAlertOutsideRadius",
    "BystanderNotificationFailed",
    "CitizenAccountAlreadyExists",
    "CitizenAccountNotFound",
    "CitizenAccountNotVerified",
    "CitizenAccountSuspended",
    "CitizenServiceError",
    "MihBookingConsentMissing",
    "MihBookingInvalidState",
    "MihBookingNotFound",
    "MihBookingSlotUnavailable",
    "RecoveryCheckInAlreadyCompleted",
    "RecoveryCheckInNotFound",
    "WearableGrantNotFound",
    "WearableGrantRevoked",
    "WearableProviderUnavailable",
    "WearableStreamValidationFailed",
]
