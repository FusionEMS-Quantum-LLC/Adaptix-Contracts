"""SYN-001 strict validation: scalars are never coerced and timestamps are
never inferred from a bare epoch number, while the JSON wire form every
producer sends (ISO 8601 strings, enum values, integer JSON numbers for float
fields) keeps validating through both Python-mode and JSON-mode entry points.
"""

from __future__ import annotations

import importlib
import inspect
import json
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from adaptix_contracts.synapse.devices import DeviceGenome
from adaptix_contracts.synapse.edge import (
    SYNAPSE_EDGE_PROTOCOL_VERSION,
    EdgeBatch,
    EdgeProtocolNegotiation,
    EdgeRecordAck,
)
from adaptix_contracts.synapse.evidence import (
    DeviceEvidenceReference,
    EvidenceUploadAuthorizationResponse,
)
from adaptix_contracts.synapse.signals import (
    ClinicalSignalEnvelope,
    DeviceBatteryState,
    SignalQuantity,
)

_MODULES = ("devices", "edge", "evidence", "provenance", "sessions", "signals")


def _synapse_models() -> list[type[BaseModel]]:
    models: list[type[BaseModel]] = []
    for name in _MODULES:
        module = importlib.import_module(f"adaptix_contracts.synapse.{name}")
        models.extend(
            obj
            for _, obj in inspect.getmembers(module, inspect.isclass)
            if issubclass(obj, BaseModel) and obj.__module__ == module.__name__
        )
    return models


def _schema_nodes(node: Any) -> Iterator[dict[str, Any]]:
    """Every dict node of a pydantic core schema, depth first."""

    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _schema_nodes(value)
    elif isinstance(node, list):
        for item in node:
            yield from _schema_nodes(item)


def test_every_scalar_field_of_every_model_is_strict() -> None:
    """No int, float or bool anywhere in a Synapse model (nested payloads
    included) is validated in lax mode, so nothing coerces ``True`` into a
    sequence number or ``"7"`` into a count."""

    models = _synapse_models()
    assert ClinicalSignalEnvelope in models
    checked = 0
    for model in models:
        for node in _schema_nodes(model.__pydantic_core_schema__):
            if node.get("type") in {"int", "float", "bool"}:
                assert node.get("strict") is True, (model.__name__, node)
                checked += 1
    assert checked > 0


def _published_datetime_fields(model: type[BaseModel]) -> set[str]:
    """Fields the model's own JSON schema publishes as ``date-time``."""

    names: set[str] = set()
    for name, prop in model.model_json_schema().get("properties", {}).items():
        variants = [prop, *prop.get("anyOf", [])]
        if any(variant.get("format") == "date-time" for variant in variants):
            names.add(name)
    return names


def test_every_datetime_is_timezone_aware() -> None:
    checked = 0
    for model in _synapse_models():
        for node in _schema_nodes(model.__pydantic_core_schema__):
            if node.get("type") == "datetime":
                assert node.get("tz_constraint") == "aware", (model.__name__, node)
                checked += 1
    assert checked > 0


@pytest.mark.parametrize("epoch", [1727186400, 1727186400000, "1727186400"])
def test_every_timestamp_of_every_model_refuses_a_bare_epoch(epoch: Any) -> None:
    """Discovered from each model's published schema, not from a hand list, so
    a timestamp added later is covered without editing this test."""

    checked: set[tuple[str, str]] = set()
    for model in _synapse_models():
        for name in sorted(_published_datetime_fields(model)):
            with pytest.raises(ValidationError, match=f"{name}: a timestamp must be"):
                model.model_validate({name: epoch})
            checked.add((model.__name__, name))
    # Discovery is not vacuous: the device clock, the edge capture clock, the
    # edge wall clock, the evidence ledger and the session all reached it.
    assert {
        ("ClinicalSignalEnvelope", "device_observed_at"),
        ("EdgeSignalRecord", "captured_at"),
        ("EdgeClockMetadata", "edge_clock_at"),
        ("DeviceEvidenceReference", "received_at"),
        ("DeviceSessionReference", "started_at"),
    } <= checked


@pytest.mark.parametrize("sequence", [True, "7", 7.0])
def test_a_local_sequence_is_an_integer_not_a_lookalike(sequence: Any) -> None:
    with pytest.raises(ValidationError):
        EdgeRecordAck.model_validate(
            {
                "local_sequence": sequence,
                "idempotency_key": "dev-ref-0001:ref-rec-000007",
                "outcome": "accepted",
            }
        )


def test_integer_sequence_is_accepted() -> None:
    ack = EdgeRecordAck.model_validate(
        {
            "local_sequence": 7,
            "idempotency_key": "dev-ref-0001:ref-rec-000007",
            "outcome": "accepted",
        }
    )
    assert ack.local_sequence == 7


@pytest.mark.parametrize("value", ["72", "7.2e1", b"72"])
def test_a_quantity_value_is_never_parsed_from_text(value: Any) -> None:
    with pytest.raises(ValidationError):
        SignalQuantity.model_validate(
            {"code": "therapy.energy", "value": value, "unit": "J"}
        )


@pytest.mark.parametrize(
    ("model", "data"),
    [
        (
            EvidenceUploadAuthorizationResponse,
            {"evidence_id": "ev-0001", "upload_required": "false"},
        ),
        (
            EvidenceUploadAuthorizationResponse,
            {"evidence_id": "ev-0001", "upload_required": 0},
        ),
        (DeviceBatteryState, {"charging": 1}),
        (DeviceBatteryState, {"charging": "yes"}),
        (DeviceBatteryState, {"level_percent": "80"}),
        (DeviceBatteryState, {"remaining_minutes": True}),
    ],
)
def test_booleans_and_numbers_are_not_coerced(
    model: type[BaseModel], data: dict[str, Any]
) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(data)


def test_negotiation_decision_must_be_a_real_boolean(t0) -> None:
    data = {
        "edge_instance_id": "edge-inst-0001",
        "accepted": 1,
        "selected_protocol_version": SYNAPSE_EDGE_PROTOCOL_VERSION,
        "server_received_at": t0,
        "server_sent_at": t0,
        "correlation_id": "corr-neg-0001",
    }
    with pytest.raises(ValidationError):
        EdgeProtocolNegotiation.model_validate(data)
    assert EdgeProtocolNegotiation.model_validate({**data, "accepted": True}).accepted


def test_genome_version_is_an_integer(genome_data) -> None:
    with pytest.raises(ValidationError):
        DeviceGenome.model_validate(genome_data(genome_version=True))
    with pytest.raises(ValidationError):
        DeviceGenome.model_validate(genome_data(genome_version="2"))
    assert (
        DeviceGenome.model_validate(genome_data(genome_version=2)).genome_version == 2
    )


@pytest.mark.parametrize(
    "epoch",
    [1727186400, 1727186400000, 1727186400.5, "1727186400", " 1727186400 ", "-1.5"],
)
def test_device_time_is_never_inferred_from_a_bare_epoch(
    envelope_data, epoch: Any
) -> None:
    """A bare epoch would make pydantic guess seconds vs milliseconds and UTC;
    the device's own time must reach Adaptix exactly as the driver decoded it."""

    with pytest.raises(ValidationError, match="bare number"):
        ClinicalSignalEnvelope.model_validate(envelope_data(device_observed_at=epoch))


def test_a_bare_epoch_is_refused_in_json_too(envelope_data) -> None:
    envelope = ClinicalSignalEnvelope.model_validate(envelope_data())
    wire = json.loads(envelope.model_dump_json())
    wire["adaptix_received_at"] = 1727186402
    with pytest.raises(ValidationError, match="bare number"):
        ClinicalSignalEnvelope.model_validate_json(json.dumps(wire))


def test_iso_timestamps_with_an_offset_are_accepted_and_kept(envelope_data, t0) -> None:
    envelope = ClinicalSignalEnvelope.model_validate(
        envelope_data(device_observed_at="2026-09-24T09:00:00-05:00")
    )
    assert envelope.device_observed_at == t0
    assert envelope.device_observed_at is not None
    assert envelope.device_observed_at.utcoffset() == timedelta(hours=-5)


def test_json_decoded_wire_dicts_still_validate(
    envelope_data, waveform_payload, evidence_data, edge_record_data, raw_sha256, t0
) -> None:
    """The path a FastAPI body takes (JSON text -> dict -> Python-mode
    validation) still accepts ISO strings, enum values and integer JSON numbers
    for float fields: strictness is per scalar, not model-wide."""

    waveform = ClinicalSignalEnvelope.model_validate(
        envelope_data(
            signal_kind="waveform",
            signal_code="ecg.lead_ii",
            evidence_id="ev-0001",
            evidence_sha256=raw_sha256,
            payload=waveform_payload(sample_rate_hz=250),
        )
    )
    batch = EdgeBatch.model_validate(
        {
            "batch_id": "batch-0001",
            "edge_instance_id": "edge-inst-0001",
            "protocol_version": SYNAPSE_EDGE_PROTOCOL_VERSION,
            "sent_at": t0 + timedelta(seconds=30),
            "records": [edge_record_data(1), edge_record_data(2)],
            "correlation_id": "corr-batch-0001",
        }
    )
    evidence = DeviceEvidenceReference.model_validate(evidence_data())
    for model in (waveform, batch, evidence):
        decoded = json.loads(model.model_dump_json())
        assert type(model).model_validate(decoded) == model
        assert type(model).model_validate_json(model.model_dump_json()) == model
