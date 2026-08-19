"""Adaptix Evidence Graph — shared platform primitive A.

The Evidence Graph answers "why does this record say what it says?" across
service boundaries. A denial can be traced back through the remittance, the
claim, the coding recommendation, the billing snapshot, the locked chart, the
narrative, and the transcript segment it came from — without a human querying
six databases by hand.

What lives here
---------------
* :mod:`adaptix_contracts.evidence.enums` —
  :class:`~adaptix_contracts.evidence.enums.EvidenceRelation` (the six edge
  types) and :class:`~adaptix_contracts.evidence.enums.EvidenceRetentionClass`
  plus its fail-closed auto-expiry predicate.
* :mod:`adaptix_contracts.evidence.models` —
  :class:`~adaptix_contracts.evidence.models.EvidenceNode`,
  :class:`~adaptix_contracts.evidence.models.EvidenceEdge`, and
  :class:`~adaptix_contracts.evidence.models.DecisionReceipt`.
* :mod:`adaptix_contracts.evidence.events` — the three cross-domain event-type
  strings and their payload models.

What does not live here
-----------------------
* **Storage.** The ``evidence_nodes`` / ``evidence_edges`` /
  ``decision_receipts`` tables are owned by Adaptix-Audit-Service. This package
  is the shared contract only.
* **Microsoft Graph.** ``adaptix_contracts.schemas.graph_contracts`` is
  Microsoft Graph API integration (Adaptix-Graph-Service). The two are unrelated
  and must never be merged.
* **Transactional truth.** An evidence node references a domain record; the
  owning domain service remains the source of truth for that record.
"""

from adaptix_contracts.evidence.enums import (
    RETENTION_CLASSES_EXEMPT_FROM_AUTO_EXPIRY,
    EvidenceRelation,
    EvidenceRetentionClass,
    is_auto_expiry_allowed,
)
from adaptix_contracts.evidence.events import (
    EVIDENCE_DECISION_RECEIPT_CREATED,
    EVIDENCE_EDGE_CREATED,
    EVIDENCE_NODE_CREATED,
    EvidenceDecisionReceiptCreatedEvent,
    EvidenceEdgeCreatedEvent,
    EvidenceNodeCreatedEvent,
)
from adaptix_contracts.evidence.models import (
    DecisionReceipt,
    EvidenceEdge,
    EvidenceNode,
)

__all__ = [
    "EVIDENCE_DECISION_RECEIPT_CREATED",
    "EVIDENCE_EDGE_CREATED",
    "EVIDENCE_NODE_CREATED",
    "RETENTION_CLASSES_EXEMPT_FROM_AUTO_EXPIRY",
    "DecisionReceipt",
    "EvidenceDecisionReceiptCreatedEvent",
    "EvidenceEdge",
    "EvidenceEdgeCreatedEvent",
    "EvidenceNode",
    "EvidenceNodeCreatedEvent",
    "EvidenceRelation",
    "EvidenceRetentionClass",
    "is_auto_expiry_allowed",
]
