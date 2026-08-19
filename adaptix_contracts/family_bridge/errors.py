"""Adaptix Family-Bridge — Service error contracts.

Play P24. Family-Bridge-specific error codes plus convenience constructors
that return a canonical
:class:`adaptix_contracts.errors.envelope.AdaptixErrorEnvelope`, so the
Communications-Service, Patient-Identity, the public portal route, and
Android-EPCR all read a single error shape.

Design note: the platform contract is the envelope model in
``adaptix_contracts/errors/envelope.py``. This module extends that contract
with Family-Bridge codes and typed factories; services that want to raise
may wrap ``FamilyBridgeServiceError`` around an envelope.
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


class FamilyBridgeErrorCode(str, Enum):
    """Family-Bridge-specific error codes, namespaced ``bridge.``."""

    NOK_CONTACT_NOT_FOUND = "bridge.nok_contact_not_found"
    NOK_CONTACT_INACTIVE = "bridge.nok_contact_inactive"
    NOK_CONTACT_NO_REACHABLE_CHANNEL = "bridge.nok_contact_no_reachable_channel"

    CONSENT_REQUIRED = "bridge.consent_required"
    CONSENT_REVOKED = "bridge.consent_revoked"
    CONSENT_EXPIRED = "bridge.consent_expired"

    THREAD_NOT_FOUND = "bridge.thread_not_found"
    THREAD_ALREADY_OPEN_FOR_CHART = "bridge.thread_already_open_for_chart"
    THREAD_ALREADY_CLOSED = "bridge.thread_already_closed"
    THREAD_INVALID_STAGE_TRANSITION = "bridge.thread_invalid_stage_transition"

    PORTAL_TOKEN_INVALID = "bridge.portal_token_invalid"
    PORTAL_TOKEN_EXPIRED = "bridge.portal_token_expired"
    PORTAL_TOKEN_REVOKED = "bridge.portal_token_revoked"
    PORTAL_TOKEN_SIGNATURE_MISMATCH = "bridge.portal_token_signature_mismatch"

    SMS_DELIVERY_FAILED = "bridge.sms_delivery_failed"
    SMS_PROVIDER_UNAVAILABLE = "bridge.sms_provider_unavailable"
    SMS_OPTED_OUT = "bridge.sms_opted_out"

    TRUSTSIGN_UNAVAILABLE = "bridge.trustsign_unavailable"
    CHART_LINK_INVALID = "bridge.chart_link_invalid"


_BRIDGE_TO_PLATFORM: dict[FamilyBridgeErrorCode, AdaptixErrorCode] = {
    FamilyBridgeErrorCode.NOK_CONTACT_NOT_FOUND: AdaptixErrorCode.NOT_FOUND,
    FamilyBridgeErrorCode.NOK_CONTACT_INACTIVE: AdaptixErrorCode.WORKFLOW_BLOCKED,
    FamilyBridgeErrorCode.NOK_CONTACT_NO_REACHABLE_CHANNEL: AdaptixErrorCode.CONSTRAINT_VIOLATION,
    FamilyBridgeErrorCode.CONSENT_REQUIRED: AdaptixErrorCode.WORKFLOW_BLOCKED,
    FamilyBridgeErrorCode.CONSENT_REVOKED: AdaptixErrorCode.WORKFLOW_BLOCKED,
    FamilyBridgeErrorCode.CONSENT_EXPIRED: AdaptixErrorCode.WORKFLOW_BLOCKED,
    FamilyBridgeErrorCode.THREAD_NOT_FOUND: AdaptixErrorCode.NOT_FOUND,
    FamilyBridgeErrorCode.THREAD_ALREADY_OPEN_FOR_CHART: AdaptixErrorCode.ALREADY_EXISTS,
    FamilyBridgeErrorCode.THREAD_ALREADY_CLOSED: AdaptixErrorCode.INVALID_STATE_TRANSITION,
    FamilyBridgeErrorCode.THREAD_INVALID_STAGE_TRANSITION: AdaptixErrorCode.INVALID_STATE_TRANSITION,
    FamilyBridgeErrorCode.PORTAL_TOKEN_INVALID: AdaptixErrorCode.INVALID_VALUE,
    FamilyBridgeErrorCode.PORTAL_TOKEN_EXPIRED: AdaptixErrorCode.WORKFLOW_BLOCKED,
    FamilyBridgeErrorCode.PORTAL_TOKEN_REVOKED: AdaptixErrorCode.WORKFLOW_BLOCKED,
    FamilyBridgeErrorCode.PORTAL_TOKEN_SIGNATURE_MISMATCH: AdaptixErrorCode.INVALID_VALUE,
    FamilyBridgeErrorCode.SMS_DELIVERY_FAILED: AdaptixErrorCode.EXPORT_FAILED,
    FamilyBridgeErrorCode.SMS_PROVIDER_UNAVAILABLE: AdaptixErrorCode.EXPORT_FAILED,
    FamilyBridgeErrorCode.SMS_OPTED_OUT: AdaptixErrorCode.WORKFLOW_BLOCKED,
    FamilyBridgeErrorCode.TRUSTSIGN_UNAVAILABLE: AdaptixErrorCode.EXPORT_FAILED,
    FamilyBridgeErrorCode.CHART_LINK_INVALID: AdaptixErrorCode.INVALID_VALUE,
}


def to_adaptix_error_code(bridge_code: FamilyBridgeErrorCode) -> AdaptixErrorCode:
    """Return the closest :class:`AdaptixErrorCode` for a Family-Bridge code."""

    return _BRIDGE_TO_PLATFORM[bridge_code]


class FamilyBridgeErrorEnvelope(AdaptixErrorEnvelope):
    """Family-Bridge-scoped error envelope."""

    bridge_error_code: FamilyBridgeErrorCode | None = Field(
        default=None,
        description="Family-Bridge-specific error code, alongside the platform error_code.",
    )

    @classmethod
    def from_bridge_code(
        cls,
        bridge_code: FamilyBridgeErrorCode,
        *,
        message: str,
        detail: Optional[str] = None,
        validation_errors: Optional[list[AdaptixValidationErrorDetail]] = None,
        provider_error: Optional[AdaptixProviderErrorDetail] = None,
        trace: Optional[AdaptixTraceContext] = None,
    ) -> "FamilyBridgeErrorEnvelope":
        return cls(
            error_code=to_adaptix_error_code(bridge_code),
            bridge_error_code=bridge_code,
            message=message,
            detail=detail,
            validation_errors=validation_errors,
            provider_error=provider_error,
            trace=trace,
        )


class FamilyBridgeServiceError(Exception):
    """Exception carrier for :class:`FamilyBridgeErrorEnvelope`."""

    def __init__(
        self, envelope: FamilyBridgeErrorEnvelope, http_status: int = 400
    ) -> None:
        super().__init__(envelope.message)
        self.envelope = envelope
        self.http_status = http_status

    @classmethod
    def from_bridge_code(
        cls,
        bridge_code: FamilyBridgeErrorCode,
        *,
        message: str,
        http_status: int = 400,
        detail: Optional[str] = None,
        validation_errors: Optional[list[AdaptixValidationErrorDetail]] = None,
        provider_error: Optional[AdaptixProviderErrorDetail] = None,
        trace: Optional[AdaptixTraceContext] = None,
    ) -> "FamilyBridgeServiceError":
        envelope = FamilyBridgeErrorEnvelope.from_bridge_code(
            bridge_code,
            message=message,
            detail=detail,
            validation_errors=validation_errors,
            provider_error=provider_error,
            trace=trace,
        )
        return cls(envelope=envelope, http_status=http_status)


# ---------------------------------------------------------------------------
# Convenience constructors for the most common Family-Bridge error paths
# ---------------------------------------------------------------------------


def consent_required(
    patient_id: str,
    trace: Optional[AdaptixTraceContext] = None,
) -> FamilyBridgeErrorEnvelope:
    return FamilyBridgeErrorEnvelope.from_bridge_code(
        FamilyBridgeErrorCode.CONSENT_REQUIRED,
        message=(
            f"Family-Bridge cannot open for patient {patient_id}: "
            "no active next-of-kin consent on record"
        ),
        trace=trace,
    )


def thread_not_found(
    thread_id: str,
    trace: Optional[AdaptixTraceContext] = None,
) -> FamilyBridgeErrorEnvelope:
    return FamilyBridgeErrorEnvelope.from_bridge_code(
        FamilyBridgeErrorCode.THREAD_NOT_FOUND,
        message=f"Family-Bridge thread {thread_id} not found",
        trace=trace,
    )


def thread_invalid_stage_transition(
    thread_id: str,
    from_stage: str,
    to_stage: str,
    trace: Optional[AdaptixTraceContext] = None,
) -> FamilyBridgeErrorEnvelope:
    return FamilyBridgeErrorEnvelope.from_bridge_code(
        FamilyBridgeErrorCode.THREAD_INVALID_STAGE_TRANSITION,
        message=(
            f"Family-Bridge thread {thread_id} cannot transition from "
            f"{from_stage} to {to_stage}"
        ),
        trace=trace,
    )


def portal_token_invalid(
    trace: Optional[AdaptixTraceContext] = None,
) -> FamilyBridgeErrorEnvelope:
    # Deliberately does not echo the token or any identifier — the public
    # portal returns this generically to avoid oracle behaviour.
    return FamilyBridgeErrorEnvelope.from_bridge_code(
        FamilyBridgeErrorCode.PORTAL_TOKEN_INVALID,
        message="This update link is not valid.",
        trace=trace,
    )


def portal_token_expired(
    trace: Optional[AdaptixTraceContext] = None,
) -> FamilyBridgeErrorEnvelope:
    return FamilyBridgeErrorEnvelope.from_bridge_code(
        FamilyBridgeErrorCode.PORTAL_TOKEN_EXPIRED,
        message="This update link has expired.",
        trace=trace,
    )


def sms_delivery_failed(
    thread_id: str,
    provider_error: Optional[AdaptixProviderErrorDetail] = None,
    trace: Optional[AdaptixTraceContext] = None,
) -> FamilyBridgeErrorEnvelope:
    return FamilyBridgeErrorEnvelope.from_bridge_code(
        FamilyBridgeErrorCode.SMS_DELIVERY_FAILED,
        message=f"Family-Bridge SMS for thread {thread_id} could not be delivered",
        provider_error=provider_error,
        trace=trace,
    )


__all__ = [
    "FamilyBridgeErrorCode",
    "FamilyBridgeErrorEnvelope",
    "FamilyBridgeServiceError",
    "consent_required",
    "portal_token_expired",
    "portal_token_invalid",
    "sms_delivery_failed",
    "thread_invalid_stage_transition",
    "thread_not_found",
    "to_adaptix_error_code",
]
