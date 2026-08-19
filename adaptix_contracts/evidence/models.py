"""Adaptix Evidence Graph models — shared platform primitive A.

Three contracts, deliberately small:

``EvidenceNode``
    One observed fact, pinned to the domain record it came from. The node is a
    *pointer plus provenance*, never a copy of the record — the owning domain
    service stays the source of truth, and no protected value is carried here.

``EvidenceEdge``
    One directed, typed relationship between two nodes in the same tenant.

``DecisionReceipt``
    What a consequential decision was actually made from: which evidence, which
    rule-pack versions, which model executions, and which human disposition.

Tenant boundary
---------------
Every model carries ``tenant_id`` and every edge can assert both endpoints
belong to that tenant (:meth:`EvidenceEdge.references_only_tenant`).
Cross-tenant traversal is not expressible in this contract; a service that
wants it must build an explicit, audited cross-tenant path rather than reaching
through the graph.

Sensitivity
-----------
``sensitivity`` reuses the canonical platform classification
:class:`adaptix_contracts.ai.connection.DataClassification` rather than
introducing a second vocabulary for the same idea. ``SECRET`` is rejected
outright: a credential is never evidence, and admitting one here would put it
on a traversal path that crosses service boundaries.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from adaptix_contracts.ai.connection import DataClassification
from adaptix_contracts.evidence.enums import EvidenceRelation, EvidenceRetentionClass


class EvidenceNode(BaseModel):
    """A single observed fact, with provenance back to its owning record.

    ``content_hash`` is a hash of the *source record content the node was
    derived from*, not of any payload stored here. It is what makes an evidence
    claim falsifiable: if the domain record later changes, the hash no longer
    matches and the node is known to describe a superseded state — record a
    ``SUPERSEDES`` edge rather than mutating the node.

    ``occurred_at`` is when the fact happened in the world; ``observed_at`` is
    when AdaptixCore learned it. They differ for anything ingested late — a
    scanned paper chart, a delayed remittance, a store-and-forward upload from
    an apparatus that was offline — and conflating them silently backdates
    evidence.
    """

    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(
        ..., min_length=1, description="Stable per-tenant evidence node identifier"
    )
    tenant_id: str = Field(
        ..., min_length=1, description="Tenant scope — required for every node"
    )
    kind: str = Field(
        ...,
        min_length=1,
        description=(
            "Domain-defined kind of fact, e.g. ambient_transcript_segment, "
            "claim_rejection, neris_validation_result. Free-form rather than an "
            "enum because every play adds its own kinds; an enum here would force "
            "a contracts release for each one."
        ),
    )
    source_service: str = Field(
        ...,
        min_length=1,
        description="Service registry slug of the service owning the source record",
    )
    source_resource_type: str = Field(
        ..., min_length=1, description="Owning record type, e.g. epcr_chart"
    )
    source_resource_id: str = Field(
        ..., min_length=1, description="Primary key of the owning record"
    )
    occurred_at: datetime | None = Field(
        default=None,
        description=(
            "When the fact occurred in the world. None when genuinely unknown — "
            "never backfilled from observed_at, which would fabricate a time."
        ),
    )
    observed_at: datetime = Field(..., description="When AdaptixCore observed the fact")
    content_hash: str = Field(
        ...,
        min_length=1,
        description="Hash of the source record content this node was derived from",
    )
    sensitivity: DataClassification = Field(
        ..., description="Canonical platform data classification of the source record"
    )
    retention_class: EvidenceRetentionClass = Field(
        ..., description="Retention obligation attaching to this node"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Non-protected structural context only (counts, versions, model ids, "
            "reason codes). Never PHI, PII, free clinical text, credentials, or "
            "raw provider payloads — this travels to analytics and audit."
        ),
    )

    @field_validator("sensitivity")
    @classmethod
    def _reject_secret_classification(
        cls, value: DataClassification
    ) -> DataClassification:
        if value is DataClassification.SECRET:
            raise ValueError(
                "evidence may not carry SECRET-classified material; a credential "
                "is not evidence"
            )
        return value

    @model_validator(mode="after")
    def _observation_cannot_precede_occurrence(self) -> EvidenceNode:
        if self.occurred_at is not None and self.observed_at < self.occurred_at:
            raise ValueError(
                "observed_at precedes occurred_at: AdaptixCore cannot observe a "
                "fact before it happened"
            )
        return self


class EvidenceEdge(BaseModel):
    """A directed, typed relationship between two evidence nodes.

    ``confidence`` is optional and only meaningful for inferred edges. An edge
    asserted from a deterministic derivation leaves it ``None`` rather than
    claiming ``1.0``, so a consumer can tell "certain" apart from "the model was
    very sure".
    """

    model_config = ConfigDict(extra="forbid")

    edge_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    from_evidence_id: str = Field(..., min_length=1)
    to_evidence_id: str = Field(..., min_length=1)
    relation: EvidenceRelation
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Set only for inferred edges; None means deterministic",
    )
    created_at: datetime

    @model_validator(mode="after")
    def _reject_self_edge(self) -> EvidenceEdge:
        if self.from_evidence_id == self.to_evidence_id:
            raise ValueError("an evidence node may not relate to itself")
        return self

    def references_only_tenant(
        self, tenant_id: str, *, node_tenants: dict[str, str]
    ) -> bool:
        """Return ``True`` when both endpoints are owned by ``tenant_id``.

        ``node_tenants`` maps ``evidence_id -> tenant_id`` for the two endpoints;
        the caller supplies it from its own tenant-scoped read. An endpoint that
        is absent from the mapping returns ``False``: an unresolvable endpoint is
        a tenant-boundary failure, never a pass.
        """

        if self.tenant_id != tenant_id:
            return False
        return all(
            node_tenants.get(evidence_id) == tenant_id
            for evidence_id in (self.from_evidence_id, self.to_evidence_id)
        )


class DecisionReceipt(BaseModel):
    """What a consequential decision was actually made from.

    A receipt is written *with* the decision, in the same transaction as the
    domain state change it explains. It is the record that answers "which
    evidence, which rule version, which model run, and which human" without
    re-deriving anything.

    ``human_disposition_id`` points at a ``HumanConfirmationReceipt`` (see
    ``adaptix_contracts.schemas.human_confirmation_contracts``). It is ``None``
    only for decisions that legitimately required no human — never as a shortcut
    for one that did.
    """

    model_config = ConfigDict(extra="forbid")

    receipt_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    decision_type: str = Field(
        ...,
        min_length=1,
        description="Domain-defined decision, e.g. medical_necessity_evaluated",
    )
    subject_type: str = Field(..., min_length=1)
    subject_id: str = Field(..., min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)
    rule_pack_versions: list[str] = Field(default_factory=list)
    model_execution_ids: list[str] = Field(default_factory=list)
    human_disposition_id: str | None = Field(
        default=None,
        description="HumanConfirmationReceipt id when a human decided this",
    )
    correlation_id: str = Field(..., min_length=1)
    trace_id: str | None = None
    idempotency_key: str | None = None
    created_at: datetime


__all__ = [
    "DecisionReceipt",
    "EvidenceEdge",
    "EvidenceNode",
]
