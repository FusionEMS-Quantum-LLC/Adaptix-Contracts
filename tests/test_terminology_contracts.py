"""Tests for Phase 2 Concept Intelligence terminology contracts."""

from __future__ import annotations

# import uuid # REMOVED IN PYTHON 3.14
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

import adaptix_contracts as ac
from adaptix_contracts.schemas.terminology_contracts import (
    AssertionContext,
    AssertionStatus,
    AutocodeOutput,
    CodeMapping,
    Concept,
    ConceptResolutionResponse,
    ConceptType,
    CrosswalkClassification,
    GraphRelationship,
    GraphRelationshipProvenance,
    MappingType,
    TerminologyEventEnvelope,
    TerminologyEventType,
)


def test_root_reexports_concept_surface() -> None:
    assert ac.Concept is Concept
    assert ac.CodeMapping is CodeMapping
    assert ac.TerminologyEventEnvelope is TerminologyEventEnvelope


def test_concept_construction_and_schema_version() -> None:
    c = Concept(
        concept_id=uuid.uuid4(),
        authority="UMLS",
        authority_identifier="C0013404",
        preferred_name="Dyspnea",
        normalized_name="dyspnea",
        concept_type=ConceptType.SYMPTOM,
    )
    assert c.schema_version == "1.0"
    assert c.concept_type is ConceptType.SYMPTOM
    assert isinstance(c.model_json_schema(), dict)


def test_code_mapping_rejects_empty_provenance() -> None:
    with pytest.raises(ValidationError):
        CodeMapping(
            mapping_id=uuid.uuid4(),
            concept_id=uuid.uuid4(),
            terminology_code_id=uuid.uuid4(),
            mapping_type=MappingType.EXACT,
            authority="UMLS",
            provenance={},
        )


def test_code_mapping_accepts_nonempty_provenance() -> None:
    m = CodeMapping(
        mapping_id=uuid.uuid4(),
        concept_id=uuid.uuid4(),
        terminology_code_id=uuid.uuid4(),
        mapping_type=MappingType.EXACT,
        authority="UMLS",
        classification=CrosswalkClassification.SOURCE_ASSERTED,
        provenance={"method": "source_asserted"},
    )
    assert m.provenance == {"method": "source_asserted"}
    assert m.classification is CrosswalkClassification.SOURCE_ASSERTED


def test_assertion_context_distinguishes_negation() -> None:
    present = AssertionContext()
    negated = AssertionContext(assertion=AssertionStatus.NEGATED)
    assert present.assertion is AssertionStatus.PRESENT
    assert negated.assertion is AssertionStatus.NEGATED
    assert present != negated


def test_graph_relationship_requires_structured_provenance() -> None:
    rel = GraphRelationship(
        edge_id=uuid.uuid4(),
        from_node_id="a",
        to_node_id="b",
        relationship="supports",
        provenance=GraphRelationshipProvenance(authority="Adaptix rule", method="rule"),
    )
    assert rel.provenance.method == "rule"
    with pytest.raises(ValidationError):
        GraphRelationship(
            edge_id=uuid.uuid4(),
            from_node_id="a",
            to_node_id="b",
            relationship="supports",
        )


def test_event_envelope_type_and_json_schema() -> None:
    env = TerminologyEventEnvelope(
        event_id=uuid.uuid4(),
        event_type=TerminologyEventType.CONCEPT_CREATED,
        occurred_at=datetime.now(UTC),
    )
    assert env.event_type.value == "terminology.concept.created"
    assert env.producer == "terminology"
    assert isinstance(TerminologyEventEnvelope.model_json_schema(), dict)


def test_autocode_and_resolution_json_schema() -> None:
    out = AutocodeOutput(document_id="pcr_1")
    assert out.schema_version == "1.0"
    assert isinstance(out.model_json_schema(), dict)
    resp = ConceptResolutionResponse(original_text="denies chest pain")
    assert isinstance(resp.model_json_schema(), dict)
