"""Agency peer and trust relationship contracts."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PeerType(str, Enum):
    """What kind of counterparty a peer is, which governs how it is reached.

    ``ADAPTIX`` is another Adaptix tenant, ``EXTERNAL_API`` a direct
    point-to-point integration, and ``QHIN`` / ``HIE`` health-information
    networks, whose exchange rules are not a point-to-point peer's.
    """

    ADAPTIX = "ADAPTIX"
    EXTERNAL_API = "EXTERNAL_API"
    QHIN = "QHIN"
    HIE = "HIE"


class PeerStatus(str, Enum):
    """Operational state of a peer connection.

    ``PAUSED`` and ``REVOKED`` are distinct because a pause is reversible and
    expected while a revocation ends the relationship — the
    ``interoperability.peer.paused`` / ``.resumed`` / ``.revoked`` events
    split the same way. ``ERROR`` is the connection failing, not a decision
    to stop using it.
    """

    PENDING = "PENDING"
    VERIFYING = "VERIFYING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    REVOKED = "REVOKED"
    ERROR = "ERROR"


class VerificationState(str, Enum):
    """How far identity verification of a peer has actually progressed.

    Held separately from ``PeerStatus`` because the two are independent: a
    peer can be operationally ``ACTIVE`` while verification is still
    ``PENDING``, so an ``ACTIVE`` status is not by itself evidence the peer's
    identity was proven. ``AgencyPeer`` defaults it to ``UNVERIFIED``.
    """

    UNVERIFIED = "UNVERIFIED"
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"


class TrustDirection(str, Enum):
    """Which way exchange authority runs in a trust relationship.

    ``INBOUND`` and ``OUTBOUND`` are separate members so accepting data from
    a peer and sending data to it are granted independently;
    ``BIDIRECTIONAL`` grants both explicitly rather than by inference.
    """

    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"
    BIDIRECTIONAL = "BIDIRECTIONAL"


class TrustStatus(str, Enum):
    """Lifecycle state of a trust relationship.

    ``PENDING`` has not been approved and grants nothing, ``PAUSED`` is a
    reversible suspension, and ``REVOKED`` is terminal and paired with
    ``TrustRelationship.revoked_at``.
    """

    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    REVOKED = "REVOKED"


# pylint too-few-public-methods (R0903) is disabled per class below. These are
# declarative Pydantic wire contracts whose entire contract IS their field set,
# exactly the shape pylint already exempts for @dataclass; the rule's intent (a
# class doing so little it should be a function or a tuple) cannot apply to a
# validated wire contract. Per class, never module-wide, so a future non-schema
# class added to this module is still checked.
class AgencyPeer(BaseModel):  # pylint: disable=too-few-public-methods
    """A counterparty agency Adaptix can exchange with, and its standing.

    Reachability, identity and health are deliberately separate fields:
    ``status`` is whether the connection is usable, ``verification_state`` /
    ``certificate_fingerprint`` / ``last_verified_at`` are whether the peer
    has been proven to be who it claims, and ``last_successful_exchange_at``
    is when it last actually worked. ``peer_tenant_id`` is populated only for
    an Adaptix peer. Frozen: a change of standing is a new record, not an
    in-place edit.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    peer_id: str = Field(..., min_length=1)
    peer_agency_id: str = Field(..., min_length=1)
    peer_tenant_id: str | None = None
    display_name: str = Field(..., min_length=1)
    peer_type: PeerType
    endpoint_url: str | None = None
    status: PeerStatus
    certificate_fingerprint: str | None = None
    verification_state: VerificationState = VerificationState.UNVERIFIED
    last_verified_at: datetime | None = None
    last_successful_exchange_at: datetime | None = None


class TrustRelationship(BaseModel):  # pylint: disable=too-few-public-methods
    """A time-bounded grant of authority to exchange with one peer.

    Authority is enumerated, never implied: ``allowed_purposes`` and
    ``allowed_resource_types`` are EMPTY by default, so a relationship grants
    nothing until they are populated. ``valid_from`` / ``valid_until`` bound
    it in time (see :meth:`validate_window`) and ``status`` can withdraw it
    inside that window. This is authority to exchange at all; whether one
    specific disclosure is permitted is ``SharePolicy``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    trust_id: str = Field(..., min_length=1)
    peer_id: str = Field(..., min_length=1)
    trust_direction: TrustDirection
    status: TrustStatus
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    allowed_purposes: tuple[str, ...] = ()
    allowed_resource_types: tuple[str, ...] = ()
    approved_by: str | None = None
    revoked_at: datetime | None = None

    @model_validator(mode="after")
    def validate_window(self) -> "TrustRelationship":
        """Reject a validity window that closes at or before it opens.

        A ``valid_until`` that is not strictly after ``valid_from`` describes
        a grant that is never in force. That is far more likely a timezone or
        data-entry error than an intent, and left unvalidated it would
        silently deny every exchange with the peer.
        """
        if self.valid_from and self.valid_until and self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be after valid_from")
        return self


__all__ = [
    "AgencyPeer",
    "PeerStatus",
    "PeerType",
    "TrustDirection",
    "TrustRelationship",
    "TrustStatus",
    "VerificationState",
]
