"""Pydantic models for the Adaptix Citizen subpackage (Play P31).

All models carry ``tenant_id`` and ``correlation_id`` per platform contract.
Wearable readings are consumer-provided data — services MUST NOT treat them
as clinical truth without provider review.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from adaptix_contracts.citizen.enums import (
    BystanderStatus,
    CheckInType,
    CitizenAccountStatus,
    MihBookingStatus,
    MihVisitType,
    WearableGrantStatus,
    WearableSource,
)


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CitizenBase(BaseModel):
    """Common base for all Citizen contracts.

    Every citizen contract is tenant-scoped and correlation-tagged so that
    events, audits, and downstream integrations remain traceable.
    """

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    tenant_id: str = Field(..., description="Tenant scope — required for every record")
    correlation_id: str = Field(
        default_factory=_new_id,
        description="Correlation ID for tracing across services",
    )


class CitizenAccount(CitizenBase):
    """A consumer-facing Adaptix Citizen account.

    Rules:
    - ``person_id`` is the canonical Adaptix person identity when linked; a
      pending account may exist before a person record is created.
    - ``phone_e164`` MUST be E.164 formatted when present.
    - Verification is authoritative on the server; ``verified_at`` is set only
      after successful verification.
    """

    id: str = Field(default_factory=_new_id)
    person_id: str | None = Field(
        default=None,
        description="Canonical Adaptix person id, once linked",
    )
    display_name: str
    email: EmailStr | None = None
    phone_e164: str | None = Field(
        default=None,
        pattern=r"^\+[1-9]\d{1,14}$",
        description="E.164 phone number, e.g. +15551234567",
    )
    date_of_birth: datetime | None = None
    preferred_language: str = "en"
    status: CitizenAccountStatus = CitizenAccountStatus.PENDING_VERIFICATION
    email_verified: bool = False
    phone_verified: bool = False
    verified_at: datetime | None = None
    marketing_consent: bool = False
    data_sharing_consent: bool = False
    device_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class MihBookingSchedule(BaseModel):
    """Requested and confirmed windows for an MIH visit."""

    requested_window_start: datetime
    requested_window_end: datetime
    scheduled_at: datetime | None = None
    duration_minutes: int = Field(default=60, ge=5, le=480)
    timezone_id: str = Field(
        default="UTC",
        description="IANA timezone id for the visit, e.g. America/Chicago",
    )


class MihBookingLocation(BaseModel):
    """Physical location of an MIH visit."""

    address_line1: str
    address_line2: str | None = None
    city: str
    region: str
    postal_code: str
    country: str = "US"
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    access_notes: str | None = None


class MihBooking(CitizenBase):
    """A Mobile Integrated Health (MIH) visit booking initiated by a citizen.

    An MIH booking is a scheduled, non-emergent visit. It is NOT a 911
    dispatch and MUST NOT be routed through PSAP/NG911.
    """

    id: str = Field(default_factory=_new_id)
    citizen_account_id: str
    person_id: str | None = Field(
        default=None,
        description="Canonical Adaptix person id, once resolved",
    )
    visit_type: MihVisitType
    status: MihBookingStatus = MihBookingStatus.REQUESTED
    reason: str = Field(
        ...,
        max_length=2000,
        description="Citizen-provided reason for the visit",
    )
    schedule: MihBookingSchedule
    location: MihBookingLocation
    referral_source: str | None = Field(
        default=None,
        description="Program, discharge team, or partner that referred the visit",
    )
    assigned_agency_id: str | None = None
    assigned_provider_id: str | None = None
    intake_screening: dict[str, Any] = Field(default_factory=dict)
    consent_snapshot: dict[str, Any] = Field(
        default_factory=dict,
        description="Immutable snapshot of consent flags at booking time",
    )
    cancellation_reason: str | None = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    completed_at: datetime | None = None


class BystanderLocation(BaseModel):
    """Location payload attached to a bystander alert.

    ``accuracy_meters`` reflects the reporting device's confidence and MUST NOT
    be silently coerced to zero when missing.
    """

    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    accuracy_meters: float | None = Field(default=None, ge=0.0)
    address_text: str | None = None


class BystanderAlert(CitizenBase):
    """A community bystander alert (e.g. Good-Samaritan CPR / AED / Naloxone).

    Emergent 911 dispatch remains PSAP-owned. This record represents the
    bystander-response layer that Adaptix Citizen coordinates, and is an
    adapter surface only — it does not replace CAD, PSAP, or NG911.
    """

    id: str = Field(default_factory=_new_id)
    incident_reference: str | None = Field(
        default=None,
        description="External CAD/PSAP incident reference, when linked",
    )
    citizen_account_id: str | None = Field(
        default=None,
        description="Requesting citizen account, when known",
    )
    trigger_source: str = Field(
        ...,
        description="What raised the alert: e.g. citizen_app, wearable_fall, partner",
    )
    condition_hint: str | None = Field(
        default=None,
        description="Short, non-diagnostic condition hint, e.g. suspected_cardiac_arrest",
    )
    location: BystanderLocation
    radius_meters: float = Field(
        default=500.0,
        ge=10.0,
        le=10_000.0,
        description="Search radius used to notify bystanders",
    )
    status: BystanderStatus = BystanderStatus.PENDING
    notified_count: int = Field(default=0, ge=0)
    acknowledged_by: list[str] = Field(default_factory=list)
    responder_ids: list[str] = Field(default_factory=list)
    aed_reference_ids: list[str] = Field(default_factory=list)
    naloxone_reference_ids: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None
    dispatched_at: datetime | None = None
    resolved_at: datetime | None = None
    resolution_notes: str | None = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class WearableGrant(CitizenBase):
    """Consent grant for ingesting data from a wearable / consumer health source.

    The grant is a durable authorization record. Revocation MUST set
    ``status`` to ``REVOKED`` and preserve the original record; grants are
    never deleted in-place.
    """

    id: str = Field(default_factory=_new_id)
    citizen_account_id: str
    person_id: str | None = None
    source: WearableSource
    scopes: list[str] = Field(
        default_factory=list,
        description="Provider-specific scopes granted (e.g. heart_rate, spo2)",
    )
    status: WearableGrantStatus = WearableGrantStatus.PENDING
    granted_at: datetime | None = None
    revoked_at: datetime | None = None
    expires_at: datetime | None = None
    external_grant_id: str | None = Field(
        default=None,
        description="Opaque identifier issued by the wearable provider",
    )
    scope_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class WearableReading(BaseModel):
    """Single wearable reading inside a stream.

    Units are provider-native and MUST be documented in ``unit``.
    """

    metric: str = Field(
        ...,
        description="Metric name, e.g. heart_rate, spo2, steps, hrv, sleep_stage",
    )
    value: float
    unit: str
    observed_at: datetime
    quality: str | None = Field(
        default=None,
        description="Provider-supplied quality indicator, e.g. good/fair/poor",
    )


class WearableStream(CitizenBase):
    """Batch of wearable readings ingested under an active grant.

    Grants MUST be verified before persistence. Streams are consumer-provided
    data and MUST NOT be treated as clinical truth without provider review.
    """

    id: str = Field(default_factory=_new_id)
    grant_id: str
    citizen_account_id: str
    person_id: str | None = None
    source: WearableSource
    stream_start: datetime
    stream_end: datetime
    readings: list[WearableReading] = Field(default_factory=list)
    sample_count: int = Field(default=0, ge=0)
    ingested_at: datetime = Field(default_factory=_now)
    is_clinical_reviewed: bool = False


class RecoveryCheckIn(CitizenBase):
    """A recovery / follow-up check-in touchpoint with a citizen.

    ``mih_booking_id`` and ``chart_id`` are optional linkages to the encounter
    or MIH visit that this check-in follows.
    """

    id: str = Field(default_factory=_new_id)
    citizen_account_id: str
    person_id: str | None = None
    check_in_type: CheckInType
    mih_booking_id: str | None = None
    chart_id: str | None = None
    scheduled_for: datetime
    completed_at: datetime | None = None
    channel: str = Field(
        default="app",
        description="Delivery channel: app, sms, voice, email, in_person",
    )
    responses: dict[str, Any] = Field(default_factory=dict)
    risk_flags: list[str] = Field(default_factory=list)
    escalated: bool = False
    escalation_reason: str | None = None
    provider_review_required: bool = False
    reviewer_id: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


__all__ = [
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
]
