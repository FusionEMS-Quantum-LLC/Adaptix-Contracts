"""Exchange gateway descriptors: every route by which Adaptix exchanges records.

An exchange gateway is one configured way of moving a
:class:`~adaptix_contracts.interoperability.exchange.PublicSafetyExchangeEnvelope`
between Adaptix and a counterparty. Adaptix owns the exchange model; an outside
system plugs into it through a gateway, and Adaptix never depends on one.

Ownership rule
--------------
Only :attr:`ExchangeGatewayKind.ADAPTIX_PEER` is Adaptix-owned. Every other
kind reaches an outside system (a hospital interface, a FHIR API, Direct
messaging, an HIE, a QHIN, a regional exchange, a state system) and is
therefore OPTIONAL: its descriptor must say ``optional=True`` so no readiness
check can ever treat an outside system as a prerequisite of core behaviour.
An Adaptix-owned gateway never waits on an outside credential.

Status is configuration, not proof
----------------------------------
``CONFIGURED`` says the gateway has the configuration it needs. It does not
say a connection was proven, that a counterparty certified it, or that a QHIN
connection is live. Runtime proof comes from the Adaptix Certification Fabric.

Reuse
-----
* :class:`~adaptix_contracts.interoperability.trust.TrustDirection` states
  which way the gateway moves records.
* ``peer_id`` references :class:`~adaptix_contracts.interoperability.trust.AgencyPeer`.
* ``qhin_credential_id`` references
  :class:`adaptix_contracts.qhin.models.QhinCredential` (``id``), which holds
  only secret-store pointers.
* ``supported_resource_types`` uses the vocabulary of
  ``PublicSafetyExchangeEnvelope.resource_type``.

A descriptor never carries a secret, an endpoint credential or a patient
record. ``credential_ref`` is a pointer into the approved secret store.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from .trust import TrustDirection

#: Identifier or reference carried by an exchange contract: bounded and free
#: of control characters, so it can never smuggle a log-injection or
#: header-splitting payload into an audit row or an outbound request.
ExchangeReference = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=255,
        pattern=r"^[^\x00-\x1f\x7f]+$",
    ),
]

#: Redacted, bounded operator text (a status reason, a redacted error detail).
#: It carries exchange metadata only, never protected payload content.
RedactedText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=2000,
        pattern=r"^[^\x00-\x08\x0b\x0c\x0e-\x1f\x7f]+$",
    ),
]


class ExchangeGatewayKind(str, Enum):
    """The kind of route a gateway uses to reach its counterparty.

    ``ADAPTIX_PEER`` reaches another Adaptix tenant over the Adaptix peer
    fabric. Every other member reaches an outside system:
    ``HOSPITAL_INTERFACE`` a hospital's own interface (for example HL7 v2),
    ``FHIR_API`` a FHIR REST endpoint, ``DIRECT`` Direct secure messaging,
    ``HIE`` a health information exchange, ``QHIN`` a TEFCA QHIN,
    ``REGIONAL_EXCHANGE`` a regional public-safety exchange and
    ``STATE_SYSTEM`` a state registry or reporting system.
    """

    ADAPTIX_PEER = "adaptix_peer"
    HOSPITAL_INTERFACE = "hospital_interface"
    FHIR_API = "fhir_api"
    DIRECT = "direct"
    HIE = "hie"
    QHIN = "qhin"
    REGIONAL_EXCHANGE = "regional_exchange"
    STATE_SYSTEM = "state_system"


#: Gateway kinds Adaptix owns end to end. Deliberately one member.
ADAPTIX_OWNED_GATEWAY_KINDS: frozenset[ExchangeGatewayKind] = frozenset(
    {ExchangeGatewayKind.ADAPTIX_PEER}
)

#: Gateway kinds that reach an outside system. Always optional.
EXTERNAL_GATEWAY_KINDS: frozenset[ExchangeGatewayKind] = frozenset(
    kind for kind in ExchangeGatewayKind if kind not in ADAPTIX_OWNED_GATEWAY_KINDS
)


class ExchangeGatewayStatus(str, Enum):
    """Whether a gateway can be used, stated honestly.

    ``CONFIGURED`` has what it needs to attempt an exchange (not proof that
    one succeeded). ``NOT_CONFIGURED`` was never set up for this tenant.
    ``DEGRADED`` is configured but failing or partially available.
    ``DISABLED`` was switched off on purpose. ``WAITING_EXTERNAL_CREDENTIAL``
    is blocked on a credential only the outside party can issue; it never
    applies to an Adaptix-owned gateway.
    """

    CONFIGURED = "CONFIGURED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    DEGRADED = "DEGRADED"
    DISABLED = "DISABLED"
    WAITING_EXTERNAL_CREDENTIAL = "WAITING_EXTERNAL_CREDENTIAL"


#: Statuses under which a gateway may be selected to send or receive.
USABLE_GATEWAY_STATUSES: frozenset[ExchangeGatewayStatus] = frozenset(
    {ExchangeGatewayStatus.CONFIGURED, ExchangeGatewayStatus.DEGRADED}
)


def is_external_gateway_kind(kind: ExchangeGatewayKind | str) -> bool:
    """Return ``True`` when ``kind`` reaches an outside system.

    Fails closed: a value that is not a known kind is treated as external,
    so an unclassified route can never be mistaken for an Adaptix-owned one.
    """

    try:
        resolved = ExchangeGatewayKind(kind)
    except ValueError:
        return True
    return resolved in EXTERNAL_GATEWAY_KINDS


# pylint too-few-public-methods (R0903) is disabled per class below. These are
# declarative Pydantic wire contracts whose entire contract IS their field set,
# exactly the shape pylint already exempts for @dataclass; the rule's intent (a
# class doing so little it should be a function or a tuple) cannot apply to a
# validated wire contract. Per class, never module-wide, so a future non-schema
# class added to this module is still checked.
class ExchangeGatewayDescriptor(BaseModel):  # pylint: disable=too-few-public-methods
    """One tenant's configured exchange gateway and its honest standing.

    ``tenant_id`` is the owning tenant, resolved server-side from the verified
    caller; a consumer never trusts a value supplied in a request body.
    ``version`` is the optimistic-concurrency version of the descriptor: an
    update built on an older version must be refused, not merged.

    Invariants (see :meth:`validate_ownership_and_status`):

    * an external kind is always ``optional=True``;
    * an Adaptix-owned kind is never ``WAITING_EXTERNAL_CREDENTIAL``;
    * ``ADAPTIX_PEER`` names the ``AgencyPeer`` it reaches;
    * only a ``QHIN`` gateway may carry ``qhin_credential_id``, and a usable
      ``QHIN`` gateway must carry one;
    * every status other than ``CONFIGURED`` states its ``status_reason``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    gateway_id: ExchangeReference
    tenant_id: ExchangeReference
    kind: ExchangeGatewayKind
    display_name: ExchangeReference
    status: ExchangeGatewayStatus
    status_reason: RedactedText | None = None
    optional: bool = Field(default=True, strict=True)
    direction: TrustDirection
    supported_resource_types: tuple[ExchangeReference, ...] = Field(
        default=(), max_length=64
    )
    peer_id: ExchangeReference | None = None
    qhin_credential_id: UUID | None = None
    credential_ref: ExchangeReference | None = None
    status_changed_at: AwareDatetime
    last_successful_exchange_at: AwareDatetime | None = None
    version: int = Field(..., ge=1, strict=True)

    @model_validator(mode="after")
    def validate_ownership_and_status(self) -> ExchangeGatewayDescriptor:
        """Enforce the ownership rule and an honest status."""

        external = self.kind in EXTERNAL_GATEWAY_KINDS
        if external and not self.optional:
            raise ValueError(
                f"{self.kind.value} reaches an outside system and must be "
                "optional=True; an outside system is never a core prerequisite"
            )
        if (
            not external
            and self.status is ExchangeGatewayStatus.WAITING_EXTERNAL_CREDENTIAL
        ):
            raise ValueError(
                "an Adaptix-owned gateway never waits on an external credential"
            )
        if self.kind is ExchangeGatewayKind.ADAPTIX_PEER and self.peer_id is None:
            raise ValueError("an adaptix_peer gateway must name its peer_id")
        if self.kind is not ExchangeGatewayKind.QHIN:
            if self.qhin_credential_id is not None:
                raise ValueError("only a qhin gateway may carry qhin_credential_id")
        elif self.status in USABLE_GATEWAY_STATUSES and self.qhin_credential_id is None:
            raise ValueError(
                "a CONFIGURED or DEGRADED qhin gateway must reference its "
                "QhinCredential through qhin_credential_id"
            )
        if (
            self.status is not ExchangeGatewayStatus.CONFIGURED
            and not self.status_reason
        ):
            raise ValueError(f"status {self.status.value} must state its status_reason")
        return self


__all__ = [
    "ADAPTIX_OWNED_GATEWAY_KINDS",
    "EXTERNAL_GATEWAY_KINDS",
    "USABLE_GATEWAY_STATUSES",
    "ExchangeGatewayDescriptor",
    "ExchangeGatewayKind",
    "ExchangeGatewayStatus",
    "ExchangeReference",
    "RedactedText",
    "is_external_gateway_kind",
]
