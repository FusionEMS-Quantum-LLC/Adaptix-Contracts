"""Adaptix Citizen subpackage (Play P31).

Consumer-facing surface: citizen accounts, Mobile Integrated Health (MIH)
bookings, bystander alerts, wearable / consumer health ingest, and recovery
check-ins. This subpackage defines the shared contracts only — services own
storage and enforcement.

Boundary rules:

* The bystander surface is an adapter only. It coordinates community-response
  layers around a live 911 dispatch; it does NOT replace CAD, PSAP, or NG911.
* Wearable readings are consumer-provided data. Services MUST NOT treat them
  as clinical truth without provider review.
* TrustSign is the sole signature authority for any signed artifacts produced
  by these flows (DocuSeal retired 2026-08-18).
"""

from adaptix_contracts.citizen.enums import (
    BystanderStatus,
    CheckInType,
    CitizenAccountStatus,
    MihBookingStatus,
    MihVisitType,
    WearableGrantStatus,
    WearableSource,
)
from adaptix_contracts.citizen.errors import (
    BystanderAlertExpired,
    BystanderAlertNotFound,
    BystanderAlertOutsideRadius,
    BystanderNotificationFailed,
    CitizenAccountAlreadyExists,
    CitizenAccountNotFound,
    CitizenAccountNotVerified,
    CitizenAccountSuspended,
    CitizenServiceError,
    MihBookingConsentMissing,
    MihBookingInvalidState,
    MihBookingNotFound,
    MihBookingSlotUnavailable,
    RecoveryCheckInAlreadyCompleted,
    RecoveryCheckInNotFound,
    WearableGrantNotFound,
    WearableGrantRevoked,
    WearableProviderUnavailable,
    WearableStreamValidationFailed,
)
from adaptix_contracts.citizen.events import (
    BYSTANDER_ALERT_SENT,
    BystanderAlertSentPayload,
    CITIZEN_EVENTS,
    CITIZEN_MIH_BOOKED,
    CITIZEN_SOURCE_SERVICE,
    CitizenMihBookedPayload,
    RECOVERY_CHECK_IN_COMPLETED,
    RecoveryCheckInCompletedPayload,
    WEARABLE_GRANT_ISSUED,
    WearableGrantIssuedPayload,
    build_bystander_alert_sent_event,
    build_citizen_mih_booked_event,
    build_recovery_check_in_completed_event,
    build_wearable_grant_issued_event,
)
from adaptix_contracts.citizen.models import (
    BystanderAlert,
    BystanderLocation,
    CitizenAccount,
    CitizenBase,
    MihBooking,
    MihBookingLocation,
    MihBookingSchedule,
    RecoveryCheckIn,
    WearableGrant,
    WearableReading,
    WearableStream,
)

__all__ = [
    # Enums
    "BystanderStatus",
    "CheckInType",
    "CitizenAccountStatus",
    "MihBookingStatus",
    "MihVisitType",
    "WearableGrantStatus",
    "WearableSource",
    # Models
    "BystanderAlert",
    "BystanderLocation",
    "CitizenAccount",
    "CitizenBase",
    "MihBooking",
    "MihBookingLocation",
    "MihBookingSchedule",
    "RecoveryCheckIn",
    "WearableGrant",
    "WearableReading",
    "WearableStream",
    # Events
    "BYSTANDER_ALERT_SENT",
    "BystanderAlertSentPayload",
    "CITIZEN_EVENTS",
    "CITIZEN_MIH_BOOKED",
    "CITIZEN_SOURCE_SERVICE",
    "CitizenMihBookedPayload",
    "RECOVERY_CHECK_IN_COMPLETED",
    "RecoveryCheckInCompletedPayload",
    "WEARABLE_GRANT_ISSUED",
    "WearableGrantIssuedPayload",
    "build_bystander_alert_sent_event",
    "build_citizen_mih_booked_event",
    "build_recovery_check_in_completed_event",
    "build_wearable_grant_issued_event",
    # Errors
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
