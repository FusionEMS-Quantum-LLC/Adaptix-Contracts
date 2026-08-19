"""Contract tests for the Adaptix Evidence Graph (shared platform primitive A)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from adaptix_contracts.ai.connection import DataClassification
from adaptix_contracts.evidence import (
    EVIDENCE_DECISION_RECEIPT_CREATED,
    EVIDENCE_EDGE_CREATED,
    EVIDENCE_NODE_CREATED,
    DecisionReceipt,
    EvidenceEdge,
    EvidenceNode,
    EvidenceRelation,
    EvidenceRetentionClass,
    is_auto_expiry_allowed,
)
from adaptix_contracts.evidence.events import (
    EvidenceDecisionReceiptCreatedEvent,
    EvidenceEdgeCreatedEvent,
    EvidenceNodeCreatedEvent,
)
from adaptix_contracts.events.operational_envelope import (
    OperationalEventEnvelope,
    assert_event_type_registered,
)
from adaptix_contracts.events.registry import is_registered, producer_of
import pytest
from pydantic import ValidationError

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)


def _node(**overrides: object) -> EvidenceNode:
    payload: dict[str, object] = {
        "evidence_id": "ev-1",
        "tenant_id": "tenant-a",
        "kind": "claim_rejection",
        "source_service": "billing",
        "source_resource_type": "claim",
        "source_resource_id": "claim-1",
        "observed_at": NOW,
        "content_hash": "sha256:abc",
        "sensitivity": DataClassification.FINANCIAL,
        "retention_class": EvidenceRetentionClass.FINANCIAL_RECORD,
    }
    payload.update(overrides)
    return EvidenceNode(**payload)  # type: ignore[arg-type]


class TestEvidenceNode:
    def test_minimal_node_round_trips(self) -> None:
        node = _node()
        assert node.tenant_id == "tenant-a"
        assert node.occurred_at is None
        assert node.metadata == {}

    def test_secret_classification_is_refused(self) -> None:
        """A credential is never evidence, whatever a caller believes."""

        with pytest.raises(ValidationError, match="SECRET"):
            _node(sensitivity=DataClassification.SECRET)

    @pytest.mark.parametrize(
        "classification",
        [
            DataClassification.PUBLIC,
            DataClassification.INTERNAL,
            DataClassification.PII,
            DataClassification.PHI,
            DataClassification.FINANCIAL,
            DataClassification.SECURITY_SENSITIVE,
        ],
    )
    def test_every_non_secret_classification_is_accepted(
        self, classification: DataClassification
    ) -> None:
        assert _node(sensitivity=classification).sensitivity is classification

    def test_observation_may_not_precede_occurrence(self) -> None:
        with pytest.raises(ValidationError, match="observed_at precedes occurred_at"):
            _node(occurred_at=NOW + timedelta(hours=1))

    def test_late_ingestion_keeps_the_two_timestamps_apart(self) -> None:
        """A paper chart scanned a week later occurred then, was observed now."""

        node = _node(occurred_at=NOW - timedelta(days=7))
        assert node.occurred_at is not None
        assert node.observed_at - node.occurred_at == timedelta(days=7)

    def test_unknown_field_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _node(patient_name="never")

    def test_empty_tenant_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _node(tenant_id="")


class TestEvidenceEdge:
    def _edge(self, **overrides: object) -> EvidenceEdge:
        payload: dict[str, object] = {
            "edge_id": "edge-1",
            "tenant_id": "tenant-a",
            "from_evidence_id": "ev-1",
            "to_evidence_id": "ev-2",
            "relation": EvidenceRelation.SUPPORTS,
            "created_at": NOW,
        }
        payload.update(overrides)
        return EvidenceEdge(**payload)  # type: ignore[arg-type]

    def test_deterministic_edge_leaves_confidence_unset(self) -> None:
        """None means certain; 1.0 would mean a very confident guess."""

        assert self._edge().confidence is None

    def test_self_edge_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="may not relate to itself"):
            self._edge(to_evidence_id="ev-1")

    def test_confidence_outside_zero_to_one_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            self._edge(confidence=1.5)

    def test_both_endpoints_must_be_in_tenant(self) -> None:
        edge = self._edge()
        assert edge.references_only_tenant(
            "tenant-a", node_tenants={"ev-1": "tenant-a", "ev-2": "tenant-a"}
        )

    def test_foreign_endpoint_fails_the_tenant_check(self) -> None:
        edge = self._edge()
        assert not edge.references_only_tenant(
            "tenant-a", node_tenants={"ev-1": "tenant-a", "ev-2": "tenant-b"}
        )

    def test_unresolvable_endpoint_fails_closed(self) -> None:
        """An endpoint the caller could not read is a boundary failure, not a pass."""

        edge = self._edge()
        assert not edge.references_only_tenant(
            "tenant-a", node_tenants={"ev-1": "tenant-a"}
        )

    def test_edge_owned_by_another_tenant_fails_the_check(self) -> None:
        edge = self._edge(tenant_id="tenant-b")
        assert not edge.references_only_tenant(
            "tenant-a", node_tenants={"ev-1": "tenant-a", "ev-2": "tenant-a"}
        )


class TestDecisionReceipt:
    def test_receipt_without_a_human_is_representable(self) -> None:
        """Some decisions legitimately need no human; the field says so explicitly."""

        receipt = DecisionReceipt(
            receipt_id="rcpt-1",
            tenant_id="tenant-a",
            decision_type="medical_necessity_evaluated",
            subject_type="epcr_chart",
            subject_id="chart-1",
            evidence_ids=["ev-1", "ev-2"],
            rule_pack_versions=["lcd-l35162@2.1.0"],
            correlation_id="corr-1",
            created_at=NOW,
        )
        assert receipt.human_disposition_id is None
        assert receipt.model_execution_ids == []


class TestRetentionClass:
    @pytest.mark.parametrize(
        "retention_class",
        [
            EvidenceRetentionClass.CONTROLLED_SUBSTANCE,
            EvidenceRetentionClass.LEGAL_HOLD,
            EvidenceRetentionClass.PERMANENT,
        ],
    )
    def test_protected_classes_are_never_auto_expired(
        self, retention_class: EvidenceRetentionClass
    ) -> None:
        assert not is_auto_expiry_allowed(retention_class)

    @pytest.mark.parametrize(
        "retention_class",
        [
            EvidenceRetentionClass.TRANSIENT,
            EvidenceRetentionClass.OPERATIONAL,
            EvidenceRetentionClass.CLINICAL_RECORD,
            EvidenceRetentionClass.FINANCIAL_RECORD,
        ],
    )
    def test_ordinary_classes_may_be_auto_expired(
        self, retention_class: EvidenceRetentionClass
    ) -> None:
        assert is_auto_expiry_allowed(retention_class)

    def test_unknown_class_fails_closed(self) -> None:
        """A retention job that meets a class it does not know deletes nothing."""

        assert not is_auto_expiry_allowed("something_new")

    def test_every_retention_class_is_classified(self) -> None:
        for retention_class in EvidenceRetentionClass:
            assert isinstance(is_auto_expiry_allowed(retention_class), bool)


class TestEvidenceEvents:
    def test_event_types_are_registered_to_their_producer(self) -> None:
        """Registration landed with the producer, not ahead of it.

        The Evidence Graph store in Adaptix-Audit-Service emits all three
        (``audit_app/services/evidence_service.py`` 180 / 309 / 411 at commit
        90a23f08), so each is now in ALL_EVENTS naming the service that actually
        publishes it. ``producer_of`` resolving is what proves the declared
        ``source_service`` is a real registry slug rather than a plausible string.
        """

        for event_type in (
            EVIDENCE_NODE_CREATED,
            EVIDENCE_EDGE_CREATED,
            EVIDENCE_DECISION_RECEIPT_CREATED,
        ):
            assert is_registered(event_type)
            assert producer_of(event_type).slug == "audit"

    def test_the_operational_backbone_gate_accepts_them(self) -> None:
        """The allow-list now admits an evidence event onto the backbone."""

        envelope = OperationalEventEnvelope(
            event_type=EVIDENCE_NODE_CREATED,
            tenant_id="tenant-a",
            source_service="audit",
            source_record_id="ev-1",
            source_version=1,
            observed_at=NOW,
            effective_at=NOW,
        )
        assert_event_type_registered(envelope)

    def test_event_names_are_past_tense_facts(self) -> None:
        assert EVIDENCE_NODE_CREATED == "evidence.node.created"
        assert EVIDENCE_EDGE_CREATED == "evidence.edge.created"
        assert EVIDENCE_DECISION_RECEIPT_CREATED == "evidence.decision_receipt.created"

    def test_node_created_payload_carries_no_transport_fields(self) -> None:
        """tenant_id/correlation_id belong to the envelope, not the payload."""

        fields = set(EvidenceNodeCreatedEvent.model_fields)
        assert not fields & {"tenant_id", "correlation_id", "idempotency_key"}

    def test_node_created_payload_is_a_reference_not_the_node(self) -> None:
        """metadata never fans out to subscribers."""

        assert "metadata" not in EvidenceNodeCreatedEvent.model_fields

    def test_edge_created_payload_round_trips(self) -> None:
        event = EvidenceEdgeCreatedEvent(
            edge_id="edge-1",
            from_evidence_id="ev-1",
            to_evidence_id="ev-2",
            relation=EvidenceRelation.CONTRADICTS,
            created_at=NOW,
        )
        assert event.relation is EvidenceRelation.CONTRADICTS

    def test_receipt_created_payload_carries_a_count_not_the_ids(self) -> None:
        event = EvidenceDecisionReceiptCreatedEvent(
            receipt_id="rcpt-1",
            decision_type="medical_necessity_evaluated",
            subject_type="epcr_chart",
            subject_id="chart-1",
            evidence_count=2,
            created_at=NOW,
        )
        assert event.evidence_count == 2
        assert "evidence_ids" not in EvidenceDecisionReceiptCreatedEvent.model_fields


def test_evidence_is_not_merged_into_microsoft_graph_contracts() -> None:
    """graph_contracts.py is Microsoft Graph integration and must stay separate."""

    from adaptix_contracts.schemas import graph_contracts

    assert not hasattr(graph_contracts, "EvidenceNode")
    assert not hasattr(graph_contracts, "EvidenceEdge")
    assert not hasattr(graph_contracts, "DecisionReceipt")
