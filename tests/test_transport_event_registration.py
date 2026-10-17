"""Registry guards for the two TransportLink events (COM-07).

``transportlink.request.created`` and ``transportlink.signature.completed``
already had typed payloads in ``adaptix_contracts.schemas.transport_contracts``
but no registry entry, so ``assert_event_type_registered`` refused both on the
operational backbone. These tests fix four properties:

* each event is registered once, under the name its existing payload model
  already carries, with Adaptix-Transport-Service as the producer;
* the registry constant and the payload model's ``event_type`` default are
  the same string, so the registry and the payload name one event;
* the operational backbone gate accepts both;
* the existing payload field sets and required fields are pinned, so a
  producer or consumer can rely on them and a change to either is a red test.
"""

from __future__ import annotations

import pytest

from adaptix_contracts import schemas
from adaptix_contracts.events.operational_envelope import (
    OperationalEventEnvelope,
    assert_event_type_registered,
)
from adaptix_contracts.events.registry import (
    ALL_EVENTS,
    TRANSPORTLINK_REQUEST_CREATED,
    TRANSPORTLINK_SIGNATURE_COMPLETED,
    is_registered,
    producer_of,
)
from adaptix_contracts.schemas.service_registry import TRANSPORT_SERVICE
from adaptix_contracts.schemas.transport_contracts import (
    SignatureCompletedEvent,
    TransportRequestCreatedEvent,
)

_EVENTS = (
    (TRANSPORTLINK_REQUEST_CREATED, "transportlink.request.created"),
    (TRANSPORTLINK_SIGNATURE_COMPLETED, "transportlink.signature.completed"),
)
_EVENT_TYPES = tuple(event_type for _, event_type in _EVENTS)

_PAYLOAD_BY_EVENT: dict[
    str, type[TransportRequestCreatedEvent] | type[SignatureCompletedEvent]
] = {
    "transportlink.request.created": TransportRequestCreatedEvent,
    "transportlink.signature.completed": SignatureCompletedEvent,
}


@pytest.mark.parametrize(("constant", "event_type"), _EVENTS)
def test_constant_names_the_event(constant: str, event_type: str) -> None:
    assert constant == event_type


@pytest.mark.parametrize("event_type", _EVENT_TYPES)
def test_event_is_registered_to_the_transport_service(event_type: str) -> None:
    assert is_registered(event_type) is True
    assert ALL_EVENTS[event_type] == {"version": "1.0", "source_service": "transport"}
    assert producer_of(event_type) is TRANSPORT_SERVICE


@pytest.mark.parametrize(("constant", "event_type"), _EVENTS)
def test_registry_name_is_the_payload_models_event_type(
    constant: str, event_type: str
) -> None:
    """One name for one fact: the registry and the payload must agree."""
    payload_model = _PAYLOAD_BY_EVENT[event_type]
    assert payload_model.model_fields["event_type"].default == constant


@pytest.mark.parametrize("event_type", _EVENT_TYPES)
def test_event_passes_the_operational_backbone_gate(event_type: str) -> None:
    envelope = OperationalEventEnvelope(
        event_type=event_type,
        tenant_id="tenant-transport-registration",
        source_service="transport",
        source_record_id="request-1",
        source_version=1,
        observed_at="2026-10-16T00:00:00Z",
        effective_at="2026-10-16T00:00:00Z",
    )
    assert_event_type_registered(envelope)


def test_request_created_payload_fields_are_pinned() -> None:
    assert set(TransportRequestCreatedEvent.model_fields) == {
        "event_type",
        "request_id",
        "tenant_id",
        "transport_type",
        "pickup_facility_id",
        "destination_facility_id",
        "created_at",
    }
    required = {
        name
        for name, field in TransportRequestCreatedEvent.model_fields.items()
        if field.is_required()
    }
    assert required == {
        "request_id",
        "tenant_id",
        "transport_type",
        "pickup_facility_id",
        "destination_facility_id",
        "created_at",
    }


def test_signature_completed_payload_fields_are_pinned() -> None:
    assert set(SignatureCompletedEvent.model_fields) == {
        "event_type",
        "signature_request_id",
        "request_id",
        "tenant_id",
        "document_types",
        "completed_at",
    }
    required = {
        name
        for name, field in SignatureCompletedEvent.model_fields.items()
        if field.is_required()
    }
    assert required == {
        "signature_request_id",
        "request_id",
        "tenant_id",
        "document_types",
        "completed_at",
    }


@pytest.mark.parametrize(
    ("name", "payload_model"),
    [
        ("TransportRequestCreatedEvent", TransportRequestCreatedEvent),
        ("SignatureCompletedEvent", SignatureCompletedEvent),
    ],
)
def test_payload_models_stay_exported_from_schemas(
    name: str,
    payload_model: type[TransportRequestCreatedEvent] | type[SignatureCompletedEvent],
) -> None:
    assert name in schemas.__all__
    assert getattr(schemas, name) is payload_model
