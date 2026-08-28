"""Semantic acknowledgement contracts for exchange delivery."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class AcknowledgementType(str, Enum):
    """Outcome a recipient reports for one delivery of one exchange.

    Transport receipt and semantic acceptance are different facts, which is
    why both members exist: ``RECEIVED`` says only that the peer took
    delivery, ``ACCEPTED`` that it accepted the content. ``PARTIAL`` covers a
    delivery accepted in part and ``REJECTED`` one the peer refused. A sender
    must not read ``RECEIVED`` as ``ACCEPTED``.
    """

    RECEIVED = "RECEIVED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    PARTIAL = "PARTIAL"


# pylint too-few-public-methods (R0903) is disabled per class below. These are
# declarative Pydantic wire contracts whose entire contract IS their field set,
# exactly the shape pylint already exempts for @dataclass; the rule's intent (a
# class doing so little it should be a function or a tuple) cannot apply to a
# validated wire contract. Per class, never module-wide, so a future non-schema
# class added to this module is still checked.
class ExchangeAcknowledgement(BaseModel):  # pylint: disable=too-few-public-methods
    """A recipient's acknowledgement of one delivery of one exchange.

    Tied to both the delivery attempt (``delivery_id``) and the logical
    exchange (``exchange_id``), so repeated deliveries of the same exchange
    each carry their own acknowledgement instead of overwriting one another.
    ``remote_reference`` is the peer's own identifier for what it stored.
    ``error_detail_redacted`` is the only free-text failure field and is
    redacted by contract: the acknowledgement channel carries exchange
    metadata, never protected payload content.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    acknowledgement_id: str = Field(..., min_length=1)
    delivery_id: str = Field(..., min_length=1)
    exchange_id: str = Field(..., min_length=1)
    ack_type: AcknowledgementType
    remote_reference: str | None = None
    error_code: str | None = None
    error_detail_redacted: str | None = None
    received_at: datetime


__all__ = ["AcknowledgementType", "ExchangeAcknowledgement"]
