"""Adaptix Family-Bridge — enumerations.

Play P24. Family-Bridge is the SMS-to-next-of-kin thread that opens the
moment a chart opens in the field, tracks the patient through arrival,
admission, discharge and a bounded follow-up window, and closes. Every
value here is stable on the wire — do not renumber, do not reuse.
"""

from __future__ import annotations

from enum import StrEnum


class ThreadStage(StrEnum):
    """Lifecycle stage of a Family-Bridge thread.

    Ordered transitions:
        EN_ROUTE → ARRIVED → ADMITTED → DISCHARGED → FOLLOW_UP → CLOSED

    A thread may skip ADMITTED (treat-and-release / refusal) and go
    ARRIVED → DISCHARGED. Any stage may terminate to CLOSED on
    opt-out, patient death, or supervisor close. Stages never move
    backward.
    """

    EN_ROUTE = "en_route"
    ARRIVED = "arrived"
    ADMITTED = "admitted"
    DISCHARGED = "discharged"
    FOLLOW_UP = "follow_up"
    CLOSED = "closed"


class ConsentSource(StrEnum):
    """Where next-of-kin consent came from.

    * ``PATIENT_PRIOR``   — patient pre-registered NoK + consent (Citizen app,
                            prior encounter, agency enrollment).
    * ``PATIENT_SCENE``   — patient consented at the scene, verbal or signed.
    * ``GUARDIAN_SCENE``  — legal guardian / parent consented at the scene.
    * ``EMERGENCY``       — patient unable to consent; HIPAA §164.510(b)
                            incapacity provision — minimal-disclosure path.
    """

    PATIENT_PRIOR = "patient_prior"
    PATIENT_SCENE = "patient_scene"
    GUARDIAN_SCENE = "guardian_scene"
    EMERGENCY = "emergency"


class ConsentStatus(StrEnum):
    """Current standing of a NoK contact's consent."""

    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    PENDING = "pending"


class PreferredChannel(StrEnum):
    """How the NoK asked to be reached."""

    SMS = "sms"
    VOICE = "voice"
    EMAIL = "email"


class NoKRelationship(StrEnum):
    """Relationship of the NoK contact to the patient."""

    SPOUSE = "spouse"
    PARTNER = "partner"
    PARENT = "parent"
    CHILD = "child"
    SIBLING = "sibling"
    GUARDIAN = "guardian"
    CAREGIVER = "caregiver"
    FRIEND = "friend"
    OTHER = "other"


class ThreadCloseReason(StrEnum):
    """Why a thread closed."""

    COMPLETED = "completed"
    OPTED_OUT = "opted_out"
    SUPERVISOR_CLOSED = "supervisor_closed"
    PATIENT_DECEASED = "patient_deceased"
    CONSENT_REVOKED = "consent_revoked"
    NO_CONTACT = "no_contact"


class SmsDeliveryStatus(StrEnum):
    """Delivery result of an outbound SMS on a thread."""

    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    UNDELIVERED = "undelivered"


__all__ = [
    "ConsentSource",
    "ConsentStatus",
    "NoKRelationship",
    "PreferredChannel",
    "SmsDeliveryStatus",
    "ThreadCloseReason",
    "ThreadStage",
]
