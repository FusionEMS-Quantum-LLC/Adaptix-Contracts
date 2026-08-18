"""Signal Bus event contracts for the Adaptix Citizen subpackage (Play P31).

Follows the canonical event envelope in ``adaptix_contracts.events.envelope``.
Every event carries ``tenant_id`` and ``correlation_id`` via the envelope, and
its payload uses the typed models defined here.

Event names are strings — services publish them wrapped inside
``AdaptixEventEnvelope`` and consumers dispatch off ``event_type``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from adaptix_contracts.citizen.enums import (
    BystanderStatus,
    CheckInType,
    MihBookingStatus,
    MihVisitType,
    WearableGrantStatus,
    WearableSource,
)
from adaptix_contracts.events.envelope import AdaptixEventEnvelope


# ---------------------------------------------------------------------------
# Canonical event names
# ---------------------------------------------------------------------------

CITIZEN_MIH_BOOKED = "citizen.mih_booked"
BYSTANDER_ALERT_SENT = "bystander.alert_sent"
WEARABLE_GRANT_ISSUED = "wearable.grant_issued"
RECOVERY_CHECK_IN_COMPLETED = "recovery.check_in.completed"

CITIZEN_EVENTS: frozenset[str] = frozenset(
    {
        CITIZEN_MIH_BOOKED,
        BYSTANDER_ALERT_SENT,
        WEARABLE_GRANT_ISSUED,
        RECOVERY_CHECK_IN_COMPLETED,
    }
)

CITIZEN_SOURCE_SERVICE = "adaptix-citizen-service"


# ---------------------------------------------------------------------------
# Typed payloads
# ---------------------------------------------------------------------------


class _CitizenEventPayload(BaseModel):
    """Common base for Citizen event payloads."""

    model_config = ConfigDict(populate_by_name=True)

    tenant_id: str
    correlation_id: str


class CitizenMihBookedPayload(_CitizenEventPayload):
    """Payload for ``citizen.mih_booked``.

    Emitted when a citizen successfully creates an MIH booking. This is NOT a
    911 dispatch and MUST NOT be routed through PSAP/NG911 consumers.
    """

    booking_id: str
    citizen_account_id: str
    person_id: str | None = None
    visit_type: MihVisitType
    status: MihBookingStatus
    referral_source: str | None = None
    assigned_agency_id: str | None = None
    requested_window_start: datetime
    requested_window_end: datetime
    scheduled_at: datetime | None = None
    booked_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Server-authoritative timestamp when the booking was created",
    )


class BystanderAlertSentPayload(_CitizenEventPayload):
    """Payload for ``bystander.alert_sent``.

    Emitted after a bystander alert has been broadcast to eligible responders.
    Recipient identities are NOT included in the payload — consumers should
    query the bystander service directly for detail under audited scope.
    """

    alert_id: str
    trigger_source: str
    condition_hint: str | None = None
    status: BystanderStatus
    notified_count: int = Field(ge=0)
    radius_meters: float = Field(ge=0.0)
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    incident_reference: str | None = None
    dispatched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WearableGrantIssuedPayload(_CitizenEventPayload):
    """Payload for ``wearable.grant_issued``.

    Emitted when a citizen grants (or re-grants after revocation) access to a
    wearable data source. Provider tokens are NOT included — only the grant
    identity and scope metadata safe for downstream routing.
    """

    grant_id: str
    citizen_account_id: str
    person_id: str | None = None
    source: WearableSource
    status: WearableGrantStatus
    scopes: list[str] = Field(default_factory=list)
    granted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None


class RecoveryCheckInCompletedPayload(_CitizenEventPayload):
    """Payload for ``recovery.check_in.completed``.

    Emitted when a citizen completes a scheduled recovery check-in. The
    payload carries risk flags but NOT the full response body — that stays in
    the recovery service and is queried under audited scope.
    """

    check_in_id: str
    citizen_account_id: str
    person_id: str | None = None
    check_in_type: CheckInType
    mih_booking_id: str | None = None
    chart_id: str | None = None
    channel: str = "app"
    risk_flags: list[str] = Field(default_factory=list)
    escalated: bool = False
    provider_review_required: bool = False
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Envelope builders
# ---------------------------------------------------------------------------


def _build_envelope(
    event_type: str,
    payload: _CitizenEventPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    event_version: str = "1.0",
    source_service: str = CITIZEN_SOURCE_SERVICE,
    metadata: dict[str, Any] | None = None,
) -> AdaptixEventEnvelope:
    envelope = AdaptixEventEnvelope.create(
        event_type=event_type,
        tenant_id=payload.tenant_id,
        source_service=source_service,
        payload=payload.model_dump(mode="json"),
        actor_id=actor_id,
        correlation_id=payload.correlation_id,
        causation_id=causation_id,
        idempotency_key=idempotency_key,
        event_version=event_version,
    )
    if metadata is not None:
        envelope.metadata = metadata
    return envelope


def build_citizen_mih_booked_event(
    payload: CitizenMihBookedPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AdaptixEventEnvelope:
    """Build a Signal Bus envelope for ``citizen.mih_booked``."""

    return _build_envelope(
        CITIZEN_MIH_BOOKED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )


def build_bystander_alert_sent_event(
    payload: BystanderAlertSentPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AdaptixEventEnvelope:
    """Build a Signal Bus envelope for ``bystander.alert_sent``."""

    return _build_envelope(
        BYSTANDER_ALERT_SENT,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )


def build_wearable_grant_issued_event(
    payload: WearableGrantIssuedPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AdaptixEventEnvelope:
    """Build a Signal Bus envelope for ``wearable.grant_issued``."""

    return _build_envelope(
        WEARABLE_GRANT_ISSUED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )


def build_recovery_check_in_completed_event(
    payload: RecoveryCheckInCompletedPayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AdaptixEventEnvelope:
    """Build a Signal Bus envelope for ``recovery.check_in.completed``."""

    return _build_envelope(
        RECOVERY_CHECK_IN_COMPLETED,
        payload,
        actor_id=actor_id,
        causation_id=causation_id,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )


__all__ = [
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
]
