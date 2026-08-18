"""Enums for the Adaptix Citizen subpackage (consumer + MIH booking + bystander).

Play P31 — Adaptix Citizen surface.
"""

from __future__ import annotations

from enum import StrEnum


class WearableSource(StrEnum):
    """Recognised wearable / consumer health data sources.

    Only these sources are accepted at ingest. Any other value must be
    rejected at the boundary, not silently coerced.
    """

    APPLE_HEALTH = "apple_health"
    GOOGLE_HEALTH = "google_health"
    WHOOP = "whoop"
    OURA = "oura"
    GARMIN = "garmin"
    PATCH = "patch"


class BystanderStatus(StrEnum):
    """Lifecycle status of a bystander alert.

    An alert progresses through these states; terminal states are
    ``responded``, ``expired``, ``cancelled``, and ``no_response``.
    """

    PENDING = "pending"
    DISPATCHED = "dispatched"
    ACKNOWLEDGED = "acknowledged"
    ENROUTE = "enroute"
    ARRIVED = "arrived"
    RESPONDED = "responded"
    NO_RESPONSE = "no_response"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class CheckInType(StrEnum):
    """Type of a recovery / post-encounter check-in touchpoint."""

    POST_DISCHARGE = "post_discharge"
    MEDICATION_ADHERENCE = "medication_adherence"
    SYMPTOM = "symptom"
    APPOINTMENT_REMINDER = "appointment_reminder"
    WELLNESS = "wellness"
    MIH_FOLLOW_UP = "mih_follow_up"
    CRISIS_FOLLOW_UP = "crisis_follow_up"


class MihBookingStatus(StrEnum):
    """Lifecycle status of a Mobile Integrated Health (MIH) booking."""

    REQUESTED = "requested"
    TRIAGED = "triaged"
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    ENROUTE = "enroute"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    NO_SHOW = "no_show"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class MihVisitType(StrEnum):
    """Category of MIH visit being booked."""

    CHRONIC_CARE = "chronic_care"
    POST_DISCHARGE = "post_discharge"
    WELLNESS_CHECK = "wellness_check"
    FALL_RISK = "fall_risk"
    BEHAVIORAL_HEALTH = "behavioral_health"
    MEDICATION_RECONCILIATION = "medication_reconciliation"
    WOUND_CARE = "wound_care"
    VACCINE = "vaccine"
    OTHER = "other"


class WearableGrantStatus(StrEnum):
    """Consent grant status for a wearable data source."""

    PENDING = "pending"
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class CitizenAccountStatus(StrEnum):
    """Lifecycle status of a citizen account."""

    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"


__all__ = [
    "BystanderStatus",
    "CheckInType",
    "CitizenAccountStatus",
    "MihBookingStatus",
    "MihVisitType",
    "WearableGrantStatus",
    "WearableSource",
]
