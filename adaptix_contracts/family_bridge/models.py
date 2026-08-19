"""Adaptix Family-Bridge — Pydantic v2 models.

Play P24. Shared contract surface for the Communications-Service (thread
orchestrator), Patient-Identity-Service (NoK + consent record), Telephony
(SMS gateway), TrustSign (portal token signing), the public Web-App
portal, and Android-EPCR (scene consent + one-tap send).

Design constraints that every consumer relies on:

* Every tenant-scoped model carries ``tenant_id`` + ``correlation_id``.
* The public portal never receives PHI. :class:`FamilyPortalView` is the
  ONLY model exposed on the public read path and it is deliberately
  narrowed to ETA + stage + facility display name + a contact-back
  number. Nothing else. Adding a field to that model requires a
  privacy review — do not do it casually.
* Portal tokens are minted and signed by TrustSign (the sole signature
  authority). The token model here carries the signature reference,
  never the signing key.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from adaptix_contracts.family_bridge.enums import (
    ConsentSource,
    ConsentStatus,
    NoKRelationship,
    PreferredChannel,
    SmsDeliveryStatus,
    ThreadCloseReason,
    ThreadStage,
)


class _FamilyBridgeBase(BaseModel):
    """Base for every Family-Bridge contract that crosses a service boundary."""

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=False,
        extra="forbid",
        str_strip_whitespace=True,
    )

    tenant_id: str = Field(
        ...,
        description=(
            "Tenant scope — resolved server-side from trusted auth context. "
            "Never accept a client-supplied tenant_id as authorization truth."
        ),
    )
    correlation_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Correlation ID for tracing across services and events.",
    )


# ---------------------------------------------------------------------------
# Next-of-kin contact + consent (owned by Patient-Identity-Service)
# ---------------------------------------------------------------------------


class NoKConsent(BaseModel):
    """A consent grant tied to one NoK contact.

    Consent is a first-class record — not a boolean on the contact — so we
    can answer "who consented, when, from where, and is it still valid"
    during any audit. Revocation is a new row, not an update.
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    source: ConsentSource
    status: ConsentStatus = ConsentStatus.ACTIVE
    granted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    granted_by_actor_id: str | None = Field(
        default=None,
        description="Crew member / system actor who recorded the consent.",
    )
    expires_at: datetime | None = Field(
        default=None,
        description="Optional expiry. Scene consents default to a bounded window.",
    )
    revoked_at: datetime | None = None
    revocation_reason: str | None = Field(default=None, max_length=500)
    signature_ref: str | None = Field(
        default=None,
        description=(
            "TrustSign signature reference when the consent was signed. "
            "Verbal / emergency consents have no signature_ref."
        ),
    )
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _revocation_consistency(self) -> "NoKConsent":
        if self.status is ConsentStatus.REVOKED and self.revoked_at is None:
            raise ValueError("REVOKED consent must carry revoked_at")
        if self.status is not ConsentStatus.REVOKED and self.revoked_at is not None:
            raise ValueError("revoked_at is only valid when status is REVOKED")
        return self


class NoKContact(_FamilyBridgeBase):
    """A next-of-kin contact linked to a patient.

    Owned by Patient-Identity-Service (table ``nok_contacts``). A patient
    may have several contacts; the thread opener picks the highest-priority
    contact whose consent is ACTIVE.
    """

    id: UUID = Field(default_factory=uuid4)
    patient_id: str = Field(..., description="Patient-Identity master id.")
    name: str = Field(..., min_length=1, max_length=200)
    relationship: NoKRelationship
    phone_e164: str | None = Field(
        default=None,
        pattern=r"^\+[1-9]\d{6,14}$",
        description="E.164 phone number. Required when preferred_channel is SMS or VOICE.",
    )
    email: str | None = Field(default=None, max_length=320)
    preferred_channel: PreferredChannel = PreferredChannel.SMS
    priority: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Lower is higher priority — thread opener picks the lowest active.",
    )
    consents: list[NoKConsent] = Field(default_factory=list)
    active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def _channel_requires_address(self) -> "NoKContact":
        if self.preferred_channel in (PreferredChannel.SMS, PreferredChannel.VOICE):
            if not self.phone_e164:
                raise ValueError(
                    "phone_e164 is required for SMS / VOICE preferred_channel"
                )
        if self.preferred_channel is PreferredChannel.EMAIL and not self.email:
            raise ValueError("email is required for EMAIL preferred_channel")
        return self

    @property
    def has_active_consent(self) -> bool:
        return any(c.status is ConsentStatus.ACTIVE for c in self.consents)


# ---------------------------------------------------------------------------
# Portal token (minted by Communications, signed by TrustSign)
# ---------------------------------------------------------------------------


class FamilyPortalToken(_FamilyBridgeBase):
    """An opaque, signed, expiring token that unlocks the public portal read.

    The token string itself is what the family taps. It is high-entropy
    and single-purpose. The signature is TrustSign's; ``signature_ref``
    lets the portal verify the token without holding any signing key.
    Never log the raw token. Never place the token in an event payload.
    """

    id: UUID = Field(default_factory=uuid4)
    thread_id: UUID
    token_hash: str = Field(
        ...,
        min_length=32,
        description="SHA-256 (hex) of the raw token. The raw token is never stored.",
    )
    signature_ref: str = Field(
        ...,
        description="TrustSign signature reference over (thread_id, token_hash, expires_at).",
    )
    issued_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
    revoked_at: datetime | None = None
    last_viewed_at: datetime | None = None
    view_count: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _expiry_after_issue(self) -> "FamilyPortalToken":
        if self.expires_at <= self.issued_at:
            raise ValueError("expires_at must be after issued_at")
        return self


# ---------------------------------------------------------------------------
# Thread + status events (owned by Communications-Service)
# ---------------------------------------------------------------------------


class ThreadStatusEvent(BaseModel):
    """One transition on a thread's timeline.

    Append-only. The thread's ``stage`` is always the ``to_stage`` of the
    most recent event.
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    thread_id: UUID
    from_stage: ThreadStage | None = Field(
        default=None,
        description="None on the opening event.",
    )
    to_stage: ThreadStage
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_event_type: str | None = Field(
        default=None,
        description=(
            "Upstream Signal Bus event that caused this transition, e.g. "
            "'chart.opened', 'hospital.admission', 'hospital.discharge'."
        ),
    )
    source_event_id: str | None = None
    actor_id: str | None = None
    sms_sent: bool = False
    sms_delivery_status: SmsDeliveryStatus | None = None
    sms_provider_message_id: str | None = None
    note: str | None = Field(default=None, max_length=500)


class FamilyBridgeThread(_FamilyBridgeBase):
    """The Family-Bridge thread — one per (chart, NoK contact).

    Owned by Communications-Service. Opened by Android-EPCR on chart open
    (after consent). Advanced by Signal Bus consumers listening to
    ``chart.updated``, ``hospital.admission``, ``hospital.discharge``.
    Closed on completion, opt-out, revocation, or supervisor action.

    Deliberately carries **no clinical content**. Chief complaint class is
    stored only as an opaque coarse bucket that drives SMS wording, never
    the actual complaint text.
    """

    id: UUID = Field(default_factory=uuid4)
    patient_id: str
    chart_id: str = Field(..., description="EPCR chart id that opened this thread.")
    incident_id: str | None = Field(
        default=None, description="CAD incident id, if any."
    )
    nok_contact_id: UUID
    consent_id: UUID
    stage: ThreadStage = ThreadStage.EN_ROUTE
    complaint_class: str | None = Field(
        default=None,
        max_length=64,
        description=(
            "Coarse bucket used ONLY to select SMS wording tone "
            "(e.g. 'cardiac', 'trauma', 'medical', 'behavioral'). "
            "Never the actual chief complaint text."
        ),
    )
    destination_facility_id: str | None = None
    destination_facility_display_name: str | None = Field(
        default=None,
        max_length=200,
        description="Public-safe facility name shown on the portal.",
    )
    eta_at: datetime | None = Field(
        default=None,
        description="Estimated arrival at destination. Public on portal.",
    )
    contact_back_phone_e164: str | None = Field(
        default=None,
        pattern=r"^\+[1-9]\d{6,14}$",
        description="Agency / hospital line the family can call. Public on portal.",
    )
    portal_token_id: UUID | None = None
    opened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    opened_by_actor_id: str | None = None
    closed_at: datetime | None = None
    close_reason: ThreadCloseReason | None = None
    follow_up_until: datetime | None = Field(
        default=None,
        description="End of the bounded follow-up window (CMS 30-day readmission bridge).",
    )
    events: list[ThreadStatusEvent] = Field(default_factory=list)

    @model_validator(mode="after")
    def _closed_consistency(self) -> "FamilyBridgeThread":
        if self.stage is ThreadStage.CLOSED:
            if self.closed_at is None or self.close_reason is None:
                raise ValueError("CLOSED thread must carry closed_at and close_reason")
        elif self.closed_at is not None or self.close_reason is not None:
            raise ValueError(
                "closed_at / close_reason are only valid when stage is CLOSED"
            )
        return self


# ---------------------------------------------------------------------------
# Public portal view — the ONLY thing the family ever reads
# ---------------------------------------------------------------------------


class FamilyPortalView(BaseModel):
    """The response body of the public portal read.

    THIS MODEL IS THE PHI BOUNDARY. It intentionally contains no name, no
    complaint, no vitals, no chart id, no incident id, no patient id, no
    tenant id. Adding any field here requires a privacy review.
    """

    model_config = ConfigDict(extra="forbid")

    stage: ThreadStage
    stage_display: str = Field(
        ...,
        description="Human-readable stage phrase, e.g. 'On the way to the hospital'.",
    )
    facility_display_name: str | None = None
    eta_at: datetime | None = None
    contact_back_phone_e164: str | None = None
    last_updated_at: datetime
    opt_out_instructions: str = Field(
        default="Reply STOP to any message to stop updates.",
    )


__all__ = [
    "FamilyBridgeThread",
    "FamilyPortalToken",
    "FamilyPortalView",
    "NoKConsent",
    "NoKContact",
    "ThreadStatusEvent",
]
