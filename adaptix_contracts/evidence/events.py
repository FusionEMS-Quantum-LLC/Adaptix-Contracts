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
All three are registered in ``adaptix_contracts.events.registry.ALL_EVENTS`` with
``source_service="audit"``. The producer is the Evidence Graph store in
Adaptix-Audit-Service (``audit_app/services/evidence_service.py``, lines 180 /
309 / 411 at commit 90a23f08), and the registry entry carries that citation, as
the registry's own drift guard requires.

They are INDIRECT productions: the event-type string is a field default on the
publication model rather than a literal at the envelope construction site, so a
scanner that only reads ``EventSchema(event_type=...)`` call sites will not see
them. They are inventoried in
``tests/test_event_producer_registry_drift.py::INDIRECT_ENVELOPE_PRODUCERS``.

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
