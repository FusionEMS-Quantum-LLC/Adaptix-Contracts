"""Adaptix Evidence Graph event definitions — shared platform primitive A.

Three cross-domain events let a consumer react to provenance without polling the
graph:

* ``evidence.node.created``    — a new fact was recorded.
* ``evidence.edge.created``    — two facts were related. ``CONTRADICTS`` edges
  are the operationally interesting case: a consumer can open an exception the
  moment two records disagree, rather than at the next audit.
* ``evidence.decision_receipt.created`` — a consequential decision recorded what
  it was made from.

Registration
------------
These constants are **not** yet entries in
``adaptix_contracts.events.registry.ALL_EVENTS``. That registry is an allow-list
whose own drift guard
(``tests/test_event_producer_registry_drift.py::test_registry_module_cites_a_producer_for_each_indirect_event``)
requires every registered event to cite the exact producing file and line in a
service repository. No service emits these yet — the Evidence Graph store lives
in Adaptix-Audit-Service and has not been built. Registering them ahead of a
producer would put an unproducible event type on the operational backbone and
break that guard. Each constant is registered in the same change that lands its
producer.

Payload models carry no transport fields: ``tenant_id``, ``correlation_id``,
``occurred_at`` and friends belong to the envelope
(``adaptix_contracts.events.operational_envelope.OperationalEventEnvelope``),
not to the payload, matching the convention in
``adaptix_contracts.necessity.events``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from adaptix_contracts.evidence.enums import EvidenceRelation

# ---------------------------------------------------------------------------
# Canonical event-type strings (registered alongside their producer)
# ---------------------------------------------------------------------------

EVIDENCE_NODE_CREATED: Final[str] = "evidence.node.created"
EVIDENCE_EDGE_CREATED: Final[str] = "evidence.edge.created"
EVIDENCE_DECISION_RECEIPT_CREATED: Final[str] = "evidence.decision_receipt.created"


# ---------------------------------------------------------------------------
# Event payload models
# ---------------------------------------------------------------------------


class EvidenceNodeCreatedEvent(BaseModel):
    """Payload for ``evidence.node.created``.

    Deliberately a *reference*, not the node itself: a consumer that needs the
    full node reads it back through the Evidence Graph API under its own tenant
    scope. Fanning a node's ``metadata`` out to every subscriber would widen the
    blast radius of anything mistakenly written into it.
    """

    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(..., min_length=1)
    kind: str = Field(..., min_length=1)
    source_service: str = Field(..., min_length=1)
    source_resource_type: str = Field(..., min_length=1)
    source_resource_id: str = Field(..., min_length=1)
    observed_at: datetime


class EvidenceEdgeCreatedEvent(BaseModel):
    """Payload for ``evidence.edge.created``."""

    model_config = ConfigDict(extra="forbid")

    edge_id: str = Field(..., min_length=1)
    from_evidence_id: str = Field(..., min_length=1)
    to_evidence_id: str = Field(..., min_length=1)
    relation: EvidenceRelation
    created_at: datetime


class EvidenceDecisionReceiptCreatedEvent(BaseModel):
    """Payload for ``evidence.decision_receipt.created``.

    ``evidence_count`` rather than the evidence ids themselves: the ids are only
    resolvable inside the owning tenant, and a consumer that is entitled to them
    can read the receipt directly.
    """

    model_config = ConfigDict(extra="forbid")

    receipt_id: str = Field(..., min_length=1)
    decision_type: str = Field(..., min_length=1)
    subject_type: str = Field(..., min_length=1)
    subject_id: str = Field(..., min_length=1)
    evidence_count: int = Field(..., ge=0)
    human_disposition_id: str | None = None
    created_at: datetime


__all__ = [
    "EVIDENCE_DECISION_RECEIPT_CREATED",
    "EVIDENCE_EDGE_CREATED",
    "EVIDENCE_NODE_CREATED",
    "EvidenceDecisionReceiptCreatedEvent",
    "EvidenceEdgeCreatedEvent",
    "EvidenceNodeCreatedEvent",
]
