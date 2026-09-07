"""Patient-Identity next-of-kin consent event contracts.

Producer: Adaptix-Patient-Identity-Service (service-registry slug
``patient-identity``), which is the canonical owner of next-of-kin records
and of their consent standing. No other service may assert that consent
changed.

Why this event exists
---------------------
Consent is not a value read once at thread-open time. A next-of-kin can
revoke, a guardian relationship can end, and a phone number can be replaced
while a Family-Bridge thread is still live and still sending. Without a
published fact, every consumer is left holding a snapshot it has no way to
learn is stale, and the first sign of a revocation is a message that should
never have been sent.

Revocation is modelled the same way
:class:`adaptix_contracts.family_bridge.models.NoKConsent` models it — a new
row, never an update — so ``consent_id`` identifies the row that is now in
force, and ``supersedes_consent_id`` names the one it replaced.

PHI boundary
------------
Deliberately absent, per the Family-Bridge disclosure rules: next-of-kin
name, email address, and full phone number. ``phone_last4`` is carried
instead so an operator can reconcile which contact changed without the
platform republishing a reachable phone number onto the bus.

Enum placement note
-------------------
``ConsentSource``, ``ConsentStatus`` and ``NoKRelationship`` are imported
from :mod:`adaptix_contracts.family_bridge.enums` rather than redefined
here. They are shared next-of-kin vocabulary that happens to be housed in
the family_bridge package because that consumer landed first. Duplicating
them would create two competing definitions of the same wire values, which
is the worse defect; relocating them is a separate breaking change and is
not folded into this one.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from adaptix_contracts.family_bridge.enums import (
    ConsentSource,
    ConsentStatus,
    NoKRelationship,
)

# ---------------------------------------------------------------------------
# Event name constant
# ---------------------------------------------------------------------------

#: A next-of-kin contact's consent standing changed — granted, revoked, or
#: expired — or the contact's reachable number was replaced.
PATIENT_NOK_CONSENT_CHANGED: Final[str] = "patient.nok.consent.changed"

PATIENT_IDENTITY_SOURCE_SERVICE: Final[str] = "patient-identity"
"""Service-registry slug of the producing service."""


# ---------------------------------------------------------------------------
# Payload
# ---------------------------------------------------------------------------


class PatientNokConsentChangedPayload(BaseModel):
    """Payload for ``patient.nok.consent.changed``.

    ``extra="forbid"`` is the disclosure guard: a producer that attaches the
    contact's name, email or full phone number fails validation at the
    publish site rather than leaking it to every subscriber.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    tenant_id: str = Field(..., description="Tenant scope.")
    patient_id: str = Field(..., description="Opaque patient identifier.")
    nok_contact_id: UUID = Field(
        ..., description="The next-of-kin contact whose consent changed."
    )
    consent_id: UUID = Field(
        ...,
        description="The consent row now in force for this contact.",
    )
    supersedes_consent_id: UUID | None = Field(
        default=None,
        description=(
            "The consent row this one replaces. Present on a revocation or "
            "re-grant; absent on a first grant."
        ),
    )
    status: ConsentStatus = Field(
        ...,
        description=(
            "Standing after the change. Authoritative — a consumer holding "
            "an older snapshot must adopt this value, and must stop sending "
            "on anything other than ACTIVE."
        ),
    )
    consent_source: ConsentSource = Field(
        ...,
        description="How the consent now in force was obtained.",
    )
    relationship: NoKRelationship | None = Field(
        default=None,
        description="Relationship of the contact to the patient.",
    )
    phone_last4: str | None = Field(
        default=None,
        min_length=4,
        max_length=4,
        description=(
            "Last 4 digits of the contact's number, for reconciliation only. "
            "The full number is never published."
        ),
    )
    phone_changed: bool = Field(
        default=False,
        description=(
            "True when this change replaced the contact's reachable number. "
            "A consumer holding a live thread must re-resolve the number "
            "before its next send rather than reuse the one it cached."
        ),
    )
    effective_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description=(
            "When the change took effect at the owner, not when it was "
            "published. Ordering key for out-of-order delivery: an older "
            "effective_at must never overwrite a newer standing."
        ),
    )
    changed_by_actor_id: str | None = Field(
        default=None,
        description=(
            "Actor who made the change, when a human did. Absent for a system expiry."
        ),
    )
    correlation_id: str | None = Field(
        default=None,
        description="Correlation id for tracing (mirrors envelope.correlation_id).",
    )


__all__ = [
    "PATIENT_IDENTITY_SOURCE_SERVICE",
    "PATIENT_NOK_CONSENT_CHANGED",
    "PatientNokConsentChangedPayload",
]
