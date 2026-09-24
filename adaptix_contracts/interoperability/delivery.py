"""Exchange delivery lifecycle: one exchange sent through one gateway.

A delivery is one attempt, repeated as needed, to move one
:class:`~adaptix_contracts.interoperability.exchange.PublicSafetyExchangeEnvelope`
(``exchange_id``) through one
:class:`~adaptix_contracts.interoperability.gateway.ExchangeGatewayDescriptor`
(``gateway_id``). Its state machine is the one vocabulary every gateway uses,
whatever transport sits underneath.

State machine
-------------
::

    DRAFT -> QUEUED -> SENDING -> DELIVERED -> ACKNOWLEDGED
                          |           \\-----> REJECTED
                          |-> ACKNOWLEDGED | REJECTED   (synchronous answer)
                          |-> RETRYABLE_FAILURE -> QUEUED | DEAD_LETTER
                          \\-> PERMANENT_FAILURE -> DEAD_LETTER
    DEAD_LETTER -> QUEUED   (operator replay)

* ``DELIVERED`` means the counterparty took the transport; ``ACKNOWLEDGED``
  means it accepted the content. A sender never reads one as the other, the
  same split :class:`~adaptix_contracts.interoperability.acknowledgements.AcknowledgementType`
  draws between ``RECEIVED`` and ``ACCEPTED``.
* ``RETRYABLE_FAILURE`` is a transient transport failure (timeout, 5xx,
  connection refused). ``PERMANENT_FAILURE`` is deterministic (4xx,
  malformed payload, missing configuration) and is never retried
  automatically: it can only be parked in ``DEAD_LETTER`` for an operator.
* ``REJECTED`` and ``ACKNOWLEDGED`` are terminal. A rejected exchange is
  corrected and sent as a new exchange version, never re-sent unchanged.
* ``DEAD_LETTER`` is parked, not terminal: an operator replay returns it to
  ``QUEUED``. The replay keeps ``idempotency_key``, so a counterparty that did
  receive an earlier attempt can discard the duplicate.

Idempotency and concurrency
---------------------------
``idempotency_key`` is sent to the counterparty on every attempt of the same
delivery, so a retry or a replay can never be applied twice. ``version`` is
the optimistic-concurrency version of the delivery row; each state change
increments it and a writer holding an older version must be refused.
"""

from __future__ import annotations

from enum import Enum
from typing import Final

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from .gateway import ExchangeGatewayKind, ExchangeReference, RedactedText


class ExchangeDeliveryState(str, Enum):
    """Where one delivery of one exchange through one gateway stands."""

    DRAFT = "DRAFT"
    QUEUED = "QUEUED"
    SENDING = "SENDING"
    DELIVERED = "DELIVERED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    REJECTED = "REJECTED"
    RETRYABLE_FAILURE = "RETRYABLE_FAILURE"
    PERMANENT_FAILURE = "PERMANENT_FAILURE"
    DEAD_LETTER = "DEAD_LETTER"


_S = ExchangeDeliveryState

#: Every permitted transition. A pair that is not listed is refused.
EXCHANGE_DELIVERY_TRANSITIONS: Final[
    dict[ExchangeDeliveryState, frozenset[ExchangeDeliveryState]]
] = {
    _S.DRAFT: frozenset({_S.QUEUED}),
    _S.QUEUED: frozenset({_S.SENDING}),
    _S.SENDING: frozenset(
        {
            _S.DELIVERED,
            _S.ACKNOWLEDGED,
            _S.REJECTED,
            _S.RETRYABLE_FAILURE,
            _S.PERMANENT_FAILURE,
        }
    ),
    _S.DELIVERED: frozenset({_S.ACKNOWLEDGED, _S.REJECTED}),
    _S.ACKNOWLEDGED: frozenset(),
    _S.REJECTED: frozenset(),
    _S.RETRYABLE_FAILURE: frozenset({_S.QUEUED, _S.DEAD_LETTER}),
    _S.PERMANENT_FAILURE: frozenset({_S.DEAD_LETTER}),
    _S.DEAD_LETTER: frozenset({_S.QUEUED}),
}

#: States no transition leaves.
EXCHANGE_DELIVERY_TERMINAL_STATES: Final[frozenset[ExchangeDeliveryState]] = frozenset(
    state for state, targets in EXCHANGE_DELIVERY_TRANSITIONS.items() if not targets
)

#: States a new delivery may be created in.
EXCHANGE_DELIVERY_INITIAL_STATES: Final[frozenset[ExchangeDeliveryState]] = frozenset(
    {_S.DRAFT, _S.QUEUED}
)

#: States that describe a failure and therefore must carry an error code.
_FAILURE_STATES: Final[frozenset[ExchangeDeliveryState]] = frozenset(
    {_S.REJECTED, _S.RETRYABLE_FAILURE, _S.PERMANENT_FAILURE, _S.DEAD_LETTER}
)


class ExchangeDeliveryTransitionError(ValueError):
    """A delivery was asked to move between two states that are not linked."""


def validate_exchange_delivery_transition(
    current: ExchangeDeliveryState | None, target: ExchangeDeliveryState
) -> None:
    """Refuse a delivery transition the state machine does not permit.

    ``current=None`` means the delivery does not exist yet; it may only be
    created in :data:`EXCHANGE_DELIVERY_INITIAL_STATES`. A transition to the
    same state is refused: a no-op is not a state change and must not be
    recorded or published as one.
    """

    if current is None:
        if target not in EXCHANGE_DELIVERY_INITIAL_STATES:
            raise ExchangeDeliveryTransitionError(
                f"a delivery is created as DRAFT or QUEUED, not {target.value}"
            )
        return
    if target not in EXCHANGE_DELIVERY_TRANSITIONS[current]:
        raise ExchangeDeliveryTransitionError(
            f"exchange delivery cannot move from {current.value} to {target.value}"
        )


# pylint too-few-public-methods (R0903) is disabled per class below. These are
# declarative Pydantic wire contracts whose entire contract IS their field set,
# exactly the shape pylint already exempts for @dataclass; the rule's intent (a
# class doing so little it should be a function or a tuple) cannot apply to a
# validated wire contract. Per class, never module-wide, so a future non-schema
# class added to this module is still checked.
class ExchangeDelivery(BaseModel):  # pylint: disable=too-few-public-methods
    """The current state of one exchange's delivery through one gateway.

    ``payload_sha256`` repeats the envelope's digest so the delivery is bound
    to the exact payload it sent; a changed payload is a new exchange, not a
    new attempt. The row carries references and redacted error metadata
    only, never payload content.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    delivery_id: ExchangeReference
    tenant_id: ExchangeReference
    exchange_id: ExchangeReference
    gateway_id: ExchangeReference
    gateway_kind: ExchangeGatewayKind
    state: ExchangeDeliveryState
    payload_sha256: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    idempotency_key: ExchangeReference
    attempt_count: int = Field(..., ge=0, strict=True)
    max_attempts: int = Field(..., ge=1, strict=True)
    next_attempt_at: AwareDatetime | None = None
    error_code: ExchangeReference | None = None
    error_detail_redacted: RedactedText | None = None
    acknowledgement_id: ExchangeReference | None = None
    correlation_id: ExchangeReference
    version: int = Field(..., ge=1, strict=True)
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @model_validator(mode="after")
    def validate_state_evidence(self) -> ExchangeDelivery:
        """Each state carries the evidence that justifies it."""

        if self.attempt_count > self.max_attempts:
            raise ValueError("attempt_count cannot exceed max_attempts")
        if self.state in _FAILURE_STATES and self.error_code is None:
            raise ValueError(f"state {self.state.value} must carry error_code")
        if self.state not in _FAILURE_STATES and self.error_code is not None:
            raise ValueError(f"state {self.state.value} cannot carry error_code")
        if self.state is _S.ACKNOWLEDGED and self.acknowledgement_id is None:
            raise ValueError("an ACKNOWLEDGED delivery names its acknowledgement_id")
        if self.state is _S.RETRYABLE_FAILURE and self.next_attempt_at is None:
            raise ValueError("a RETRYABLE_FAILURE delivery states next_attempt_at")
        if self.state is _S.DRAFT and self.attempt_count:
            raise ValueError("a DRAFT delivery has made no attempt")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at precedes created_at")
        return self


#: Published on every delivery state change. Producer: the Core interoperability
#: fabric (service-registry slug ``core``), which owns the exchange delivery
#: rows (``core_app/interoperability/exchange_models.py`` ``ExchangeDelivery``).
INTEROPERABILITY_EXCHANGE_DELIVERY_STATE_CHANGED: Final[str] = (
    "interoperability.exchange.delivery.state_changed"
)

EXCHANGE_DELIVERY_SOURCE_SERVICE: Final[str] = "core"
"""Service-registry slug of the producer."""


class ExchangeDeliveryStateChangedPayload(BaseModel):  # pylint: disable=too-few-public-methods
    """Payload of ``interoperability.exchange.delivery.state_changed``.

    ``from_state`` is ``None`` only for the event that creates the delivery.
    ``delivery_version`` is the delivery's ``version`` after this change, so
    a consumer can discard an event older than the state it already holds.
    ``idempotency_key`` identifies this state change (not the delivery), so a
    redelivered event is applied once.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    tenant_id: ExchangeReference
    delivery_id: ExchangeReference
    exchange_id: ExchangeReference
    gateway_id: ExchangeReference
    gateway_kind: ExchangeGatewayKind
    from_state: ExchangeDeliveryState | None
    to_state: ExchangeDeliveryState
    attempt_count: int = Field(..., ge=0, strict=True)
    error_code: ExchangeReference | None = None
    delivery_version: int = Field(..., ge=1, strict=True)
    occurred_at: AwareDatetime
    correlation_id: ExchangeReference
    idempotency_key: ExchangeReference

    @model_validator(mode="after")
    def validate_transition(self) -> ExchangeDeliveryStateChangedPayload:
        """A published change must be a permitted one."""

        validate_exchange_delivery_transition(self.from_state, self.to_state)
        if self.to_state in _FAILURE_STATES and self.error_code is None:
            raise ValueError(f"a change to {self.to_state.value} must carry error_code")
        return self


__all__ = [
    "EXCHANGE_DELIVERY_INITIAL_STATES",
    "EXCHANGE_DELIVERY_SOURCE_SERVICE",
    "EXCHANGE_DELIVERY_TERMINAL_STATES",
    "EXCHANGE_DELIVERY_TRANSITIONS",
    "INTEROPERABILITY_EXCHANGE_DELIVERY_STATE_CHANGED",
    "ExchangeDelivery",
    "ExchangeDeliveryState",
    "ExchangeDeliveryStateChangedPayload",
    "ExchangeDeliveryTransitionError",
    "validate_exchange_delivery_transition",
]
