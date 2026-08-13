"""Tests for canonical terminology concept event contracts (SignalCore-based)."""

from __future__ import annotations

# import uuid # REMOVED IN PYTHON 3.14
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

import adaptix_contracts as ac
from adaptix_contracts.schemas.signalcore_contracts import SignalCoreEvent
from adaptix_contracts.schemas.terminology_event_contracts import (
    SCHEMA_VERSION,
    SOURCE_SERVICE,
    TerminologyConceptEventPayload,
    TerminologyEventType,
    build_terminology_event,
    validate_terminology_event,
)


def _payload() -> TerminologyConceptEventPayload:
    return TerminologyConceptEventPayload(
        concept_id=uuid.uuid4(),
        preferred_name="Dyspnea",
        concept_type="symptom",
    )


def test_canonical_event_type_values_are_exact() -> None:
    """The wire vocabulary is a contract — lock the exact string values."""
    assert {member.value for member in TerminologyEventType} == {
        "terminology.concept.created",
        "terminology.concept.updated",
        "terminology.concept.retired",
        "terminology.concept.term_added",
        "terminology.concept.term_removed",
        "terminology.concept.code_mapped",
        "terminology.concept.semantic_type_changed",
        "terminology.concept.enriched",
    }
    assert SCHEMA_VERSION == "1.0"
    assert SOURCE_SERVICE == "terminology-service"


def test_root_reexports_event_surface() -> None:
    """Publisher + consumer resolve one definition via the package root alias."""
    assert ac.TerminologyConceptEventType is TerminologyEventType
    assert ac.TerminologyConceptEventPayload is TerminologyConceptEventPayload
    assert ac.build_terminology_event is build_terminology_event
    assert ac.validate_terminology_event is validate_terminology_event


def test_build_sets_canonical_envelope_fields() -> None:
    payload = _payload()
    tenant_id = uuid.uuid4()
    event = build_terminology_event(
        event_type=TerminologyEventType.CONCEPT_CREATED,
        tenant_id=tenant_id,
        payload=payload,
        correlation_id="corr-1",
        idempotency_key="idem-1",
    )
    assert isinstance(event, SignalCoreEvent)
    assert event.source_service == "terminology-service"
    assert event.source_entity_type == "concept"
    assert event.source_entity_id == str(payload.concept_id)
    assert event.event_type == "terminology.concept.created"
    assert event.schema_version == "1.0"
    assert event.tenant_id == tenant_id
    assert event.correlation_id == "corr-1"
    assert event.idempotency_key == "idem-1"
    assert event.payload["preferred_name"] == "Dyspnea"
    assert isinstance(event.occurred_at, datetime)


def test_build_accepts_mapping_payload() -> None:
    concept_id = uuid.uuid4()
    event = build_terminology_event(
        event_type=TerminologyEventType.CONCEPT_CODE_MAPPED,
        tenant_id=uuid.uuid4(),
        payload={"concept_id": concept_id, "code_system": "ICD10CM", "code": "R06.00"},
    )
    assert event.source_entity_id == str(concept_id)
    assert event.payload["code"] == "R06.00"


def test_valid_event_round_trips_through_validate() -> None:
    event = build_terminology_event(
        event_type=TerminologyEventType.CONCEPT_ENRICHED,
        tenant_id=uuid.uuid4(),
        payload=_payload(),
    )
    # dict round-trip (wire form) then validate
    validated = validate_terminology_event(event.model_dump(mode="json"))
    assert validated.event_type == "terminology.concept.enriched"
    assert validated.source_service == "terminology-service"
    # SignalCoreEvent instances pass straight through
    assert validate_terminology_event(event) is event


def test_unknown_event_type_rejected() -> None:
    event = build_terminology_event(
        event_type=TerminologyEventType.CONCEPT_CREATED,
        tenant_id=uuid.uuid4(),
        payload=_payload(),
    ).model_dump(mode="json")
    event["event_type"] = "terminology.concept.frobnicated"
    with pytest.raises(ValueError, match="Unknown terminology event_type"):
        validate_terminology_event(event)


def test_wrong_source_service_rejected() -> None:
    event = build_terminology_event(
        event_type=TerminologyEventType.CONCEPT_CREATED,
        tenant_id=uuid.uuid4(),
        payload=_payload(),
    ).model_dump(mode="json")
    event["source_service"] = "graph-service"
    with pytest.raises(ValueError, match="source_service must be"):
        validate_terminology_event(event)


def test_unknown_schema_major_version_rejected() -> None:
    event = build_terminology_event(
        event_type=TerminologyEventType.CONCEPT_UPDATED,
        tenant_id=uuid.uuid4(),
        payload=_payload(),
    ).model_dump(mode="json")
    event["schema_version"] = "2.0"
    with pytest.raises(
        ValueError, match="Unsupported terminology event schema_version"
    ):
        validate_terminology_event(event)


def test_additive_minor_schema_version_accepted() -> None:
    """Backward/forward compatible: a minor bump within major 1 still validates."""
    event = build_terminology_event(
        event_type=TerminologyEventType.CONCEPT_UPDATED,
        tenant_id=uuid.uuid4(),
        payload=_payload(),
    ).model_dump(mode="json")
    event["schema_version"] = "1.7"
    validated = validate_terminology_event(event)
    assert validated.schema_version == "1.7"


def test_tolerates_additive_unknown_payload_fields() -> None:
    """A newer publisher may add payload fields a lagging consumer ignores."""
    concept_id = uuid.uuid4()
    payload = TerminologyConceptEventPayload.model_validate(
        {
            "concept_id": concept_id,
            "preferred_name": "Dyspnea",
            "future_field_not_yet_modelled": {"nested": True},
        }
    )
    # extra field survives on the model
    assert payload.model_dump()["future_field_not_yet_modelled"] == {"nested": True}

    event = build_terminology_event(
        event_type=TerminologyEventType.CONCEPT_ENRICHED,
        tenant_id=uuid.uuid4(),
        payload=payload,
    )
    # extra field survives into the envelope payload and through validate
    assert event.payload["future_field_not_yet_modelled"] == {"nested": True}
    validated = validate_terminology_event(event.model_dump(mode="json"))
    assert validated.payload["future_field_not_yet_modelled"] == {"nested": True}


def test_structurally_invalid_envelope_raises_validation_error() -> None:
    """A dict missing required envelope fields fails pydantic validation."""
    with pytest.raises(ValidationError):
        validate_terminology_event({"event_type": "terminology.concept.created"})


def test_payload_and_event_emit_json_schema() -> None:
    assert isinstance(TerminologyConceptEventPayload.model_json_schema(), dict)
    event = build_terminology_event(
        event_type=TerminologyEventType.CONCEPT_TERM_ADDED,
        tenant_id=uuid.uuid4(),
        payload=TerminologyConceptEventPayload(
            concept_id=uuid.uuid4(), term="SOB", term_type="abbreviation"
        ),
    )
    assert isinstance(event.model_json_schema(), dict)
    assert event.occurred_at.tzinfo is not None
    assert event.occurred_at.tzinfo.utcoffset(event.occurred_at) == UTC.utcoffset(None)
