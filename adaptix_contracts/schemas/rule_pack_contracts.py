"""Versioned rule pack contracts — shared platform primitive C.

A rule pack is a dated, approved, immutable set of rules that some part of
AdaptixCore evaluated: LCD coverage rules, labor-agreement rules, protocol
rules, NERIS validation rules, credential rules.

The reason this is a platform primitive rather than a per-module table: when a
determination is challenged months later, the only defensible answer is "these
exact rules, at this version, effective on that date". A rules table that is
edited in place cannot produce that answer — it can only describe today.

Hence the two invariants the model enforces:

* an ``EFFECTIVE`` pack must carry ``approved_by``, ``approval_receipt_id`` and
  ``effective_from`` — nothing becomes live without a named approver and a
  confirmation receipt;
* an ``EFFECTIVE`` or ``SUPERSEDED`` pack is frozen. Pydantic ``model_config``
  cannot express "immutable only in some states", so
  :meth:`RulePack.assert_mutable` is the explicit check a writer calls before
  persisting an update; a superseding pack is created instead.

``semantic_version`` versions the *pack*, and ``source_hash`` pins the
authoritative source text it was derived from. Both are needed: two packs can
share a source and differ in interpretation, and one pack can be re-derived
unchanged from a re-published source.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RulePackState(str, Enum):
    """Lifecycle of a rule pack.

    ``DRAFT`` → ``PROPOSED`` → ``APPROVED`` → ``EFFECTIVE`` → ``SUPERSEDED`` /
    ``RETIRED``. ``APPROVED`` and ``EFFECTIVE`` are deliberately separate: a
    pack can be approved today and take effect on the first of next month, which
    is how nearly every real regulatory and labor change arrives.
    """

    DRAFT = "draft"
    PROPOSED = "proposed"
    APPROVED = "approved"
    EFFECTIVE = "effective"
    SUPERSEDED = "superseded"
    RETIRED = "retired"


#: States in which a pack's content may still change.
MUTABLE_RULE_PACK_STATES: frozenset[RulePackState] = frozenset(
    {
        RulePackState.DRAFT,
        RulePackState.PROPOSED,
    }
)


class RulePackRule(BaseModel):
    """One rule inside a pack.

    ``expression`` is intentionally opaque to this contract: each domain's
    engine owns its own evaluation language, and a shared expression grammar
    would force every domain through one evaluator. What is shared is the
    identity, the citation, and the severity — the parts an auditor reads.
    """

    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    severity: str = Field(
        ...,
        min_length=1,
        description="Domain-defined severity, e.g. block, warn, inform",
    )
    source_reference: str | None = Field(
        default=None,
        description="Citation into the authoritative source (section, page, rule no.)",
    )
    expression: dict[str, Any] = Field(
        default_factory=dict,
        description="Domain-engine-specific evaluable form of the rule",
    )


class RulePack(BaseModel):
    """A dated, approved, versioned set of rules.

    Exactly one of ``tenant_id`` / ``global_scope`` describes who the pack
    applies to: a tenant-authored pack (a specific agency's labor agreement) or a
    platform-wide pack (a federal rule). Allowing both, or neither, makes the
    applicability question unanswerable at evaluation time.
    """

    model_config = ConfigDict(extra="forbid")

    rule_pack_id: str = Field(..., min_length=1)
    tenant_id: str | None = Field(
        default=None, description="Set for a tenant-scoped pack; None when global"
    )
    global_scope: bool = Field(
        default=False, description="True for a platform-wide pack"
    )
    authority: str = Field(
        ...,
        min_length=1,
        description="Who issued the underlying rules, e.g. CMS, NFPA, the agency",
    )
    jurisdiction: str | None = Field(
        default=None, description="Geographic or organizational scope of the authority"
    )
    source_reference: str | None = Field(
        default=None, description="Citation for the authoritative source document"
    )
    source_hash: str | None = Field(
        default=None,
        description="Hash of the authoritative source snapshot this was derived from",
    )
    semantic_version: str = Field(..., min_length=1)
    state: RulePackState
    effective_from: date | None = None
    effective_until: date | None = None
    approved_by: str | None = Field(default=None, description="User id of the approver")
    approval_receipt_id: str | None = Field(
        default=None,
        description="HumanConfirmationReceipt id recording the approval",
    )
    supersedes: str | None = Field(
        default=None, description="rule_pack_id this pack replaces"
    )
    rules: list[RulePackRule] = Field(default_factory=list)
    created_at: datetime

    @model_validator(mode="after")
    def _scope_and_approval_invariants(self) -> RulePack:
        if self.global_scope == (self.tenant_id is not None):
            raise ValueError(
                "a rule pack is either tenant-scoped (tenant_id set, "
                "global_scope False) or global (global_scope True, tenant_id None)"
            )

        if self.state is RulePackState.EFFECTIVE:
            missing = [
                name
                for name, value in (
                    ("approved_by", self.approved_by),
                    ("approval_receipt_id", self.approval_receipt_id),
                    ("effective_from", self.effective_from),
                )
                if value is None
            ]
            if missing:
                raise ValueError(
                    "an EFFECTIVE rule pack requires " + ", ".join(missing)
                )

        if (
            self.effective_from is not None
            and self.effective_until is not None
            and self.effective_until < self.effective_from
        ):
            raise ValueError("effective_until precedes effective_from")
        return self

    def is_mutable(self) -> bool:
        """Return ``True`` when this pack's content may still be edited."""

        return self.state in MUTABLE_RULE_PACK_STATES

    def assert_mutable(self) -> None:
        """Raise ``ValueError`` when the pack must not be edited in place.

        An ``APPROVED``, ``EFFECTIVE``, ``SUPERSEDED`` or ``RETIRED`` pack is a
        historical record. Changing one rewrites what a past determination was
        made from; create a superseding pack instead.
        """

        if not self.is_mutable():
            raise ValueError(
                f"rule pack {self.rule_pack_id!r} is {self.state.value} and must not "
                "be edited in place; create a superseding pack"
            )

    def is_in_effect_on(self, when: date) -> bool:
        """Return ``True`` when this pack governs ``when``.

        Only an ``EFFECTIVE`` pack governs anything. ``effective_until`` is
        inclusive — a pack that runs until the 31st still governs the 31st.
        """

        if self.state is not RulePackState.EFFECTIVE:
            return False
        if self.effective_from is None or when < self.effective_from:
            return False
        return self.effective_until is None or when <= self.effective_until


__all__ = [
    "MUTABLE_RULE_PACK_STATES",
    "RulePack",
    "RulePackRule",
    "RulePackState",
]
