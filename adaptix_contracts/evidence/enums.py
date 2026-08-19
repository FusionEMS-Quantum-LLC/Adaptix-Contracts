"""Adaptix Evidence Graph enums — shared platform primitive A.

The Evidence Graph is the platform's answer to "why does this record say what
it says?". Every consequential AdaptixCore action can point at the facts that
supported it, the facts those were derived from, and the facts that contradict
them — across service boundaries, without a human opening six databases.

Two deliberate boundaries:

* This is **not** ``adaptix_contracts.schemas.graph_contracts``. That module is
  Microsoft Graph API integration territory (Adaptix-Graph-Service) and has
  nothing to do with evidence provenance. The two must never be merged.
* This is **not** a canonical transactional source of truth. An evidence node
  *references* a domain record; the owning domain service still owns the record
  itself.

Every enum here is a ``StrEnum`` so the wire format is a stable string, matching
the convention already used by the sibling contract subpackages
(``adaptix_contracts.crr.enums``, ``adaptix_contracts.qhin.enums``,
``adaptix_contracts.part5_sms.enums``).
"""

from __future__ import annotations

from enum import StrEnum


class EvidenceRelation(StrEnum):
    """Directed relationship between two evidence nodes.

    Read every relation as ``from_evidence <relation> to_evidence``:

    * ``SUPPORTS`` — the source is corroborating evidence for the target
      (a documented complaint supports a medical-necessity determination).
    * ``DERIVED_FROM`` — the source was computed/extracted from the target
      (a structured vital sign derived from an OCR capture).
    * ``CONTRADICTS`` — the two cannot both be true; a human must reconcile
      them. Recording a contradiction never auto-resolves it.
    * ``SUPERSEDES`` — the source replaces the target as the current fact. The
      target is retained, never deleted: historical evidence is not rewritten.
    * ``CAUSED`` — the source is the causal antecedent of the target
      (a claim rejection caused an exception record).
    * ``REFERENCES`` — a weaker pointer than ``SUPPORTS``: related context with
      no assertion that it corroborates anything.
    """

    SUPPORTS = "supports"
    DERIVED_FROM = "derived_from"
    CONTRADICTS = "contradicts"
    SUPERSEDES = "supersedes"
    CAUSED = "caused"
    REFERENCES = "references"


class EvidenceRetentionClass(StrEnum):
    """Operational retention bucket an evidence node belongs to.

    This classifies *what kind of obligation* attaches to the node, not how many
    days it lives. The concrete duration is jurisdiction- and tenant-specific
    and is owned by the retention policy of the service that stores the
    underlying record — encoding a fixed number of days here would be a legal
    claim this package has no authority to make.

    * ``TRANSIENT`` — safe to age out on the platform's default schedule; no
      external obligation (cache-shaped derivations, ephemeral telemetry).
    * ``OPERATIONAL`` — ordinary agency operational record (dispatch, unit
      status, scheduling).
    * ``CLINICAL_RECORD`` — attached to a patient care record; retention follows
      the tenant's clinical-records policy.
    * ``FINANCIAL_RECORD`` — attached to a claim, payment, or remittance.
    * ``CONTROLLED_SUBSTANCE`` — attached to a controlled-substance custody
      event. Never expires ahead of the custody ledger it references.
    * ``LEGAL_HOLD`` — under an active hold; nothing in this class may be aged
      out by any automated retention job until the hold is lifted.
    * ``PERMANENT`` — retained for the life of the tenant record set.
    """

    TRANSIENT = "transient"
    OPERATIONAL = "operational"
    CLINICAL_RECORD = "clinical_record"
    FINANCIAL_RECORD = "financial_record"
    CONTROLLED_SUBSTANCE = "controlled_substance"
    LEGAL_HOLD = "legal_hold"
    PERMANENT = "permanent"


#: Retention classes that an automated retention/expiry job must never delete.
#: A job that cannot read this set must fail closed rather than guess.
RETENTION_CLASSES_EXEMPT_FROM_AUTO_EXPIRY: frozenset[EvidenceRetentionClass] = (
    frozenset(
        {
            EvidenceRetentionClass.CONTROLLED_SUBSTANCE,
            EvidenceRetentionClass.LEGAL_HOLD,
            EvidenceRetentionClass.PERMANENT,
        }
    )
)


def is_auto_expiry_allowed(retention_class: EvidenceRetentionClass | str) -> bool:
    """Return ``True`` only when automated expiry may delete this class.

    Fails closed: an unrecognised value returns ``False``, so a retention job
    that meets an unknown class leaves the evidence in place instead of
    destroying a record it does not understand.
    """

    try:
        resolved = EvidenceRetentionClass(retention_class)
    except ValueError:
        return False
    return resolved not in RETENTION_CLASSES_EXEMPT_FROM_AUTO_EXPIRY


__all__ = [
    "RETENTION_CLASSES_EXEMPT_FROM_AUTO_EXPIRY",
    "EvidenceRelation",
    "EvidenceRetentionClass",
    "is_auto_expiry_allowed",
]
