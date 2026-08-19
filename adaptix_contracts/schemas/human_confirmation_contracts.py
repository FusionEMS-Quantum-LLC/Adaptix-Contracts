"""Uniform human confirmation contracts — shared platform primitive B.

Wherever AdaptixCore proposes something a person is accountable for — a
narrative, a code, a medical-necessity determination, a QA finding, a protocol
change, a destination recommendation, a schedule, a controlled-substance
anomaly, an agent execution — the same receipt records what the human actually
did with it.

One contract, not one per module, because the question an auditor asks is always
identical: *was this accepted by a person, was it edited first, or did it just
happen?* A per-module answer makes that unanswerable across the platform.

The invariants below are enforced by the model, not by documentation:

* a decided disposition (``ACCEPTED`` / ``EDITED`` / ``REJECTED``) requires both
  ``decided_by`` and ``decided_at`` — a receipt cannot claim a human decision
  with no human and no time;
* ``EDITED`` requires ``edit_delta_hash`` — "the clinician edited it" is only
  meaningful if what changed is pinned;
* an undecided disposition (``GENERATED`` / ``PRESENTED`` / ``EXPIRED``) must not
  carry a decider — an expiry is the absence of a decision, never a silent one;
* ``decided_at`` cannot precede ``generated_at``.

``expected_state_version`` ties the receipt to the exact version of the subject
the human was looking at. It is the same optimistic-concurrency version used by
``adaptix_contracts.schemas.state_conflict_contracts``: an approval of version 4
must not apply to version 5, or the person approved something they never saw.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class HumanDisposition(str, Enum):
    """What happened to an AI- or system-generated proposal.

    * ``GENERATED`` — produced, not yet shown to anyone.
    * ``PRESENTED`` — shown to a person; still awaiting their decision.
    * ``ACCEPTED`` — taken as-is.
    * ``EDITED`` — taken after the person changed it.
    * ``REJECTED`` — explicitly refused.
    * ``EXPIRED`` — the decision window closed with no decision. Distinct from
      ``REJECTED``: nobody refused it, nobody saw it through.
    """

    GENERATED = "generated"
    PRESENTED = "presented"
    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"
    EXPIRED = "expired"


#: Dispositions that represent an actual decision by an identified person.
DECIDED_DISPOSITIONS: frozenset[HumanDisposition] = frozenset(
    {
        HumanDisposition.ACCEPTED,
        HumanDisposition.EDITED,
        HumanDisposition.REJECTED,
    }
)


def is_decided(disposition: HumanDisposition | str) -> bool:
    """Return ``True`` only when a person actually decided.

    Fails closed: an unrecognised disposition returns ``False``, so a caller
    asking "may I proceed, a human signed off?" never gets a yes from a value it
    does not understand.
    """

    try:
        resolved = HumanDisposition(disposition)
    except ValueError:
        return False
    return resolved in DECIDED_DISPOSITIONS


class HumanConfirmationReceipt(BaseModel):
    """Immutable record of what a person did with a generated proposal."""

    model_config = ConfigDict(extra="forbid")

    receipt_id: str = Field(..., min_length=1)
    tenant_id: str = Field(
        ..., min_length=1, description="Tenant scope — required for every receipt"
    )
    subject_type: str = Field(
        ...,
        min_length=1,
        description="What was proposed, e.g. epcr_narrative, claim_code_recommendation",
    )
    subject_id: str = Field(..., min_length=1)
    disposition: HumanDisposition
    generated_by: str = Field(
        ...,
        min_length=1,
        description=(
            "Producer of the proposal — a model execution id, rules engine id, or "
            "service identity. Never a patient or free clinical text."
        ),
    )
    generated_at: datetime
    presented_at: datetime | None = None
    decided_by: str | None = Field(
        default=None, description="User id of the person who decided"
    )
    decided_at: datetime | None = None
    edit_delta_hash: str | None = Field(
        default=None,
        description=(
            "Hash of the diff between the proposal and what the person kept. A "
            "hash, not the diff itself: the diff can carry protected content."
        ),
    )
    evidence_ids: list[str] = Field(default_factory=list)
    expected_state_version: int = Field(
        ...,
        ge=0,
        description="Version of the subject the person was shown",
    )

    @model_validator(mode="after")
    def _decision_fields_match_disposition(self) -> HumanConfirmationReceipt:
        decided = self.disposition in DECIDED_DISPOSITIONS
        if decided:
            missing = [
                name
                for name, value in (
                    ("decided_by", self.decided_by),
                    ("decided_at", self.decided_at),
                )
                if value is None
            ]
            if missing:
                raise ValueError(
                    f"disposition {self.disposition.value!r} is a human decision but "
                    f"{', '.join(missing)} is missing"
                )
        else:
            present = [
                name
                for name, value in (
                    ("decided_by", self.decided_by),
                    ("decided_at", self.decided_at),
                )
                if value is not None
            ]
            if present:
                raise ValueError(
                    f"disposition {self.disposition.value!r} is not a human decision "
                    f"but carries {', '.join(present)}"
                )

        if self.disposition is HumanDisposition.EDITED and not self.edit_delta_hash:
            raise ValueError("an EDITED receipt must carry edit_delta_hash")
        if self.disposition is not HumanDisposition.EDITED and self.edit_delta_hash:
            raise ValueError("edit_delta_hash is only meaningful on an EDITED receipt")

        if self.decided_at is not None and self.decided_at < self.generated_at:
            raise ValueError("decided_at precedes generated_at")
        if self.presented_at is not None and self.presented_at < self.generated_at:
            raise ValueError("presented_at precedes generated_at")
        return self


__all__ = [
    "DECIDED_DISPOSITIONS",
    "HumanConfirmationReceipt",
    "HumanDisposition",
    "is_decided",
]
