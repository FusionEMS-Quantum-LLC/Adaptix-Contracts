"""Sharing policy contracts. Trust and disclosure policy are intentionally separate."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ShareDirection(str, Enum):
    """Direction of disclosure a share policy authorises.

    ``SEND`` and ``RECEIVE`` are separate members so an agency can publish to
    a peer without accepting from it, or the reverse. ``BOTH`` grants both
    and must be chosen explicitly — ``SharePolicy.direction`` has no default.
    """

    SEND = "SEND"
    RECEIVE = "RECEIVE"
    BOTH = "BOTH"


# pylint too-few-public-methods (R0903) is disabled per class below. These are
# declarative Pydantic wire contracts whose entire contract IS their field set,
# exactly the shape pylint already exempts for @dataclass; the rule's intent (a
# class doing so little it should be a function or a tuple) cannot apply to a
# validated wire contract. Per class, never module-wide, so a future non-schema
# class added to this module is still checked.
class SharePolicy(BaseModel):  # pylint: disable=too-few-public-methods
    """A disclosure rule: what may be shared, with whom, and for what purpose.

    Kept separate from ``TrustRelationship`` on purpose, as this module's
    title states. Trust establishes that a peer is who it claims to be and
    may exchange at all; this decides whether a given ``resource_type`` may
    actually move for a given ``purpose_of_use``. A fully verified peer with
    no enabled policy discloses nothing.

    The gates are independent and none implies another:
    ``require_patient_match`` (qualified by ``minimum_identity_confidence``),
    ``require_consent``, ``allow_break_glass``, and ``automatic_share``,
    which is what decides whether disclosure happens without a human in the
    loop. ``enabled`` is the kill switch for the policy as a whole.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    sharing_policy_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    description: str | None = None
    peer_id: str | None = None
    resource_type: str = Field(..., min_length=1)
    purpose_of_use: str = Field(..., min_length=1)
    direction: ShareDirection
    automatic_share: bool = False
    require_patient_match: bool = False
    require_consent: bool = False
    allow_break_glass: bool = False
    minimum_identity_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    enabled: bool = True


__all__ = ["ShareDirection", "SharePolicy"]
