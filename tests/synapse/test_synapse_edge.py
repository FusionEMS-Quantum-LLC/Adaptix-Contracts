"""SYN-001 Synapse Edge protocol: registration, negotiation, records,
ordered batches, contiguous acknowledgement and heartbeats."""

from __future__ import annotations

from datetime import timedelta

import pytest
from pydantic import ValidationError

from adaptix_contracts.synapse.edge import (
    EDGE_BATCH_MAX_RECORDS,
    EdgeBatch,
    EdgeBatchAck,
    EdgeHeartbeat,
    EdgeInstanceRegistration,
    EdgeProtocolNegotiation,
    EdgeProtocolOffer,
    EdgeRecordAck,
    EdgeSignalRecord,
    SUPPORTED_EDGE_PROTOCOL_VERSIONS,
    SYNAPSE_EDGE_PROTOCOL_VERSION,
    advance_contiguous_watermark,
    select_edge_protocol_version,
)

_EDGE_RECORD_FIELDS = {
    "edge_instance_id",
    "device_id",
    "device_session_id",
    "local_sequence",
    "source_record_id",
    "observed_at",
    "captured_at",
    "evidence_sha256",
    "idempotency_key",
    "adapter_key",
    "adapter_version",
    "correlation_id",
    "envelope",
}


def _batch(edge_record_data, t0, sequences=(1, 2, 3), **overrides) -> dict:
    data = {
        "batch_id": "batch-0001",
        "edge_instance_id": "edge-inst-0001",
        "protocol_version": SYNAPSE_EDGE_PROTOCOL_VERSION,
        "sent_at": t0 + timedelta(seconds=30),
        "records": [edge_record_data(seq) for seq in sequences],
        "correlation_id": "corr-batch-0001",
    }
    data.update(overrides)
    return data


def _ack(result_specs, watermark: int, t0, **overrides) -> dict:
    results = []
    for seq, outcome, reason in result_specs:
        result = {
            "local_sequence": seq,
            "idempotency_key": f"dev-ref-0001:ref-rec-{seq:06d}",
            "outcome": outcome,
        }
        if reason is not None:
            result["rejection_reason"] = reason
        results.append(result)
    data = {
        "batch_id": "batch-0001",
        "edge_instance_id": "edge-inst-0001",
        "results": results,
        "highest_contiguous_acknowledged_sequence": watermark,
        "server_received_at": t0 + timedelta(seconds=31),
        "correlation_id": "corr-batch-0001",
    }
    data.update(overrides)
    return data


# --- registration and negotiation --------------------------------------------


def test_registration_declares_profile_protocols_and_transports() -> None:
    registration = EdgeInstanceRegistration(
        edge_instance_id="edge-inst-0001",
        deployment_profile="linux_gateway",
        runtime_version="1.0.0",
        supported_protocol_versions=["1.0"],
        supported_transports=["ble", "usb", "serial", "tcp"],
        supported_protocols=["adaptix_reference", "hl7_device"],
        correlation_id="corr-reg-0001",
    )
    assert EdgeInstanceRegistration.model_validate_json(
        registration.model_dump_json()
    ) == (registration)
    assert "tenant_id" not in EdgeInstanceRegistration.model_fields
    with pytest.raises(ValidationError):
        EdgeInstanceRegistration.model_validate(
            registration.model_dump() | {"deployment_profile": "raspberry_pi"}
        )
    with pytest.raises(ValidationError, match="repeat"):
        EdgeInstanceRegistration.model_validate(
            registration.model_dump() | {"supported_transports": ["ble", "ble"]}
        )
    with pytest.raises(ValidationError):
        EdgeInstanceRegistration.model_validate(
            registration.model_dump() | {"supported_protocol_versions": ["1"]}
        )


def test_negotiation_selects_the_highest_common_version() -> None:
    assert select_edge_protocol_version(["1.0", "1.2", "2.0"], ["1.0", "1.2"]) == "1.2"
    assert select_edge_protocol_version(["1.9", "1.10"], ["1.9", "1.10"]) == "1.10"
    assert (
        select_edge_protocol_version(["3.0"], SUPPORTED_EDGE_PROTOCOL_VERSIONS) is None
    )
    assert (
        select_edge_protocol_version(["1.0"], SUPPORTED_EDGE_PROTOCOL_VERSIONS) == "1.0"
    )


def test_negotiation_decision_is_coherent_and_answers_the_offer(t0) -> None:
    offer = EdgeProtocolOffer(
        edge_instance_id="edge-inst-0001",
        runtime_version="1.0.0",
        offered_protocol_versions=["1.0"],
        edge_sent_at=t0,
        correlation_id="corr-neg-0001",
    )
    accepted = EdgeProtocolNegotiation(
        edge_instance_id="edge-inst-0001",
        accepted=True,
        selected_protocol_version="1.0",
        server_received_at=t0,
        server_sent_at=t0 + timedelta(milliseconds=3),
        correlation_id="corr-neg-0001",
    )
    assert accepted.answers(offer)
    wrong_version = accepted.model_copy(update={"selected_protocol_version": "2.0"})
    assert not wrong_version.answers(offer)
    refused = EdgeProtocolNegotiation(
        edge_instance_id="edge-inst-0001",
        accepted=False,
        refusal_reason="no_common_version",
        server_received_at=t0,
        server_sent_at=t0,
        correlation_id="corr-neg-0001",
    )
    assert refused.answers(offer)
    with pytest.raises(ValidationError, match="accepted negotiation"):
        EdgeProtocolNegotiation(
            edge_instance_id="edge-inst-0001",
            accepted=True,
            server_received_at=t0,
            server_sent_at=t0,
            correlation_id="corr-neg-0001",
        )
    with pytest.raises(ValidationError, match="refused negotiation"):
        EdgeProtocolNegotiation(
            edge_instance_id="edge-inst-0001",
            accepted=False,
            selected_protocol_version="1.0",
            refusal_reason="no_common_version",
            server_received_at=t0,
            server_sent_at=t0,
            correlation_id="corr-neg-0001",
        )
    with pytest.raises(ValidationError, match="precedes"):
        EdgeProtocolNegotiation(
            edge_instance_id="edge-inst-0001",
            accepted=True,
            selected_protocol_version="1.0",
            server_received_at=t0,
            server_sent_at=t0 - timedelta(seconds=1),
            correlation_id="corr-neg-0001",
        )


# --- records -----------------------------------------------------------------


def test_edge_record_carries_every_capture_fact(edge_record_data) -> None:
    assert set(EdgeSignalRecord.model_fields) == _EDGE_RECORD_FIELDS
    record = EdgeSignalRecord.model_validate(edge_record_data())
    assert EdgeSignalRecord.model_validate_json(record.model_dump_json()) == record


@pytest.mark.parametrize(
    "field, value",
    [
        ("device_id", "dev-ref-0002"),
        ("device_session_id", "sess-0002"),
        ("source_record_id", "ref-rec-999999"),
        ("idempotency_key", "dev-ref-0001:other"),
        ("adapter_key", "adaptix.other"),
        ("adapter_version", "9.9.9"),
        ("correlation_id", "corr-other"),
    ],
)
def test_edge_record_must_agree_with_its_envelope(
    edge_record_data, field, value
) -> None:
    with pytest.raises(ValidationError, match=field):
        EdgeSignalRecord.model_validate(edge_record_data(**{field: value}))


def test_edge_record_times_must_agree_with_its_envelope(edge_record_data, t0) -> None:
    with pytest.raises(ValidationError, match="captured_at"):
        EdgeSignalRecord.model_validate(
            edge_record_data(captured_at=t0 + timedelta(hours=1))
        )
    with pytest.raises(ValidationError, match="observed_at"):
        EdgeSignalRecord.model_validate(edge_record_data(observed_at=None))
    with pytest.raises(ValidationError, match="timezone"):
        EdgeSignalRecord.model_validate(
            edge_record_data(captured_at=t0.replace(tzinfo=None))
        )


def test_edge_record_requires_session_and_evidence_hash(edge_record_data) -> None:
    for field in (
        "device_session_id",
        "evidence_sha256",
        "idempotency_key",
        "observed_at",
    ):
        data = edge_record_data()
        del data[field]
        with pytest.raises(ValidationError, match=field):
            EdgeSignalRecord.model_validate(data)
    with pytest.raises(ValidationError):
        EdgeSignalRecord.model_validate(edge_record_data(evidence_sha256="F" * 64))
    with pytest.raises(ValidationError):
        EdgeSignalRecord.model_validate(edge_record_data(local_sequence=0))


def test_edge_record_evidence_must_be_the_captured_bytes(
    edge_record_data, raw_sha256
) -> None:
    data = edge_record_data()
    data["envelope"] = data["envelope"] | {
        "evidence_id": "ev-0001",
        "evidence_sha256": "0" * 64,
    }
    with pytest.raises(ValidationError, match="evidence_sha256"):
        EdgeSignalRecord.model_validate(data)
    data["envelope"]["evidence_sha256"] = raw_sha256
    assert EdgeSignalRecord.model_validate(data)


# --- batches -----------------------------------------------------------------


def test_batch_is_ordered_single_instance_and_bounded(edge_record_data, t0) -> None:
    assert EdgeBatch.model_validate(_batch(edge_record_data, t0))
    assert EdgeBatch.model_validate(_batch(edge_record_data, t0, sequences=(4, 7, 9)))
    with pytest.raises(ValidationError, match="ascend strictly"):
        EdgeBatch.model_validate(_batch(edge_record_data, t0, sequences=(2, 1)))
    with pytest.raises(ValidationError, match="ascend strictly"):
        EdgeBatch.model_validate(_batch(edge_record_data, t0, sequences=(1, 1)))
    foreign = _batch(edge_record_data, t0)
    foreign["records"][1] = edge_record_data(2, edge_instance_id="edge-inst-0002")
    with pytest.raises(ValidationError, match="another edge instance"):
        EdgeBatch.model_validate(foreign)
    with pytest.raises(ValidationError):
        EdgeBatch.model_validate(_batch(edge_record_data, t0, sequences=()))
    too_many = range(1, EDGE_BATCH_MAX_RECORDS + 2)
    with pytest.raises(ValidationError):
        EdgeBatch.model_validate(_batch(edge_record_data, t0, sequences=too_many))


def test_batch_rejects_repeated_idempotency_keys(edge_record_data, t0) -> None:
    batch = _batch(edge_record_data, t0, sequences=(1, 2))
    second = edge_record_data(2)
    key = batch["records"][0]["idempotency_key"]
    second["idempotency_key"] = key
    second["envelope"] = second["envelope"] | {"idempotency_key": key}
    batch["records"][1] = second
    with pytest.raises(ValidationError, match="idempotency keys must not repeat"):
        EdgeBatch.model_validate(batch)


# --- acknowledgement: contiguous watermark semantics -------------------------


def test_watermark_advances_only_across_an_unbroken_run() -> None:
    assert advance_contiguous_watermark(0, []) == 0
    assert advance_contiguous_watermark(0, {1, 2, 3, 5}) == 3
    assert advance_contiguous_watermark(3, {4, 5, 6}) == 6
    assert advance_contiguous_watermark(0, {2, 3}) == 0
    assert advance_contiguous_watermark(5, {1, 2}) == 5
    with pytest.raises(ValueError):
        advance_contiguous_watermark(-1, {1})


def test_record_ack_reason_matches_outcome() -> None:
    with pytest.raises(ValidationError, match="REJECTED"):
        EdgeRecordAck(local_sequence=1, idempotency_key="k", outcome="rejected")
    with pytest.raises(ValidationError, match="REJECTED"):
        EdgeRecordAck(
            local_sequence=1,
            idempotency_key="k",
            outcome="accepted",
            rejection_reason="invalid_envelope",
        )
    duplicate = EdgeRecordAck(
        local_sequence=1, idempotency_key="k", outcome="duplicate"
    )
    assert duplicate.releasable and duplicate.final
    retryable = EdgeRecordAck(
        local_sequence=2,
        idempotency_key="k2",
        outcome="rejected",
        rejection_reason="evidence_not_received",
    )
    assert not retryable.releasable and not retryable.final
    terminal = EdgeRecordAck(
        local_sequence=3,
        idempotency_key="k3",
        outcome="rejected",
        rejection_reason="tenant_mismatch",
    )
    assert not terminal.releasable and terminal.final


def test_ack_watermark_never_passes_a_record_awaiting_resend(t0) -> None:
    specs = [
        (1, "accepted", None),
        (2, "rejected", "evidence_not_received"),
        (3, "accepted", None),
    ]
    with pytest.raises(ValidationError, match="awaiting resend"):
        EdgeBatchAck.model_validate(_ack(specs, 3, t0))
    ack = EdgeBatchAck.model_validate(_ack(specs, 1, t0))
    assert ack.releasable_local_sequences() == {1, 3}


def test_ack_watermark_passes_terminal_rejections_but_they_are_not_released(t0) -> None:
    specs = [
        (1, "accepted", None),
        (2, "rejected", "invalid_envelope"),
        (3, "duplicate", None),
    ]
    ack = EdgeBatchAck.model_validate(_ack(specs, 3, t0))
    assert ack.highest_contiguous_acknowledged_sequence == advance_contiguous_watermark(
        0, [r.local_sequence for r in ack.results if r.final]
    )
    assert ack.releasable_local_sequences() == {1, 3}


def test_ack_must_answer_every_record_of_its_batch(edge_record_data, t0) -> None:
    batch = EdgeBatch.model_validate(_batch(edge_record_data, t0))
    full = EdgeBatchAck.model_validate(
        _ack(
            [(1, "accepted", None), (2, "accepted", None), (3, "accepted", None)], 3, t0
        )
    )
    assert full.unanswered_local_sequences(batch) == frozenset()
    partial = EdgeBatchAck.model_validate(
        _ack([(1, "accepted", None), (3, "accepted", None)], 1, t0)
    )
    assert partial.unanswered_local_sequences(batch) == {2}
    foreign = EdgeBatchAck.model_validate(_ack([(9, "accepted", None)], 0, t0))
    with pytest.raises(ValueError, match="did not contain"):
        foreign.unanswered_local_sequences(batch)
    wrong_batch = EdgeBatchAck.model_validate(
        _ack([(1, "accepted", None)], 1, t0, batch_id="batch-0002")
    )
    with pytest.raises(ValueError, match="does not answer this batch"):
        wrong_batch.unanswered_local_sequences(batch)
    wrong_key = _ack([(1, "accepted", None)], 1, t0)
    wrong_key["results"][0]["idempotency_key"] = "dev-ref-0001:other"
    with pytest.raises(ValueError, match="different idempotency key"):
        EdgeBatchAck.model_validate(wrong_key).unanswered_local_sequences(batch)


def test_ack_answers_each_sequence_once(t0) -> None:
    with pytest.raises(ValidationError, match="repeat"):
        EdgeBatchAck.model_validate(
            _ack([(1, "accepted", None), (1, "duplicate", None)], 1, t0)
        )


# --- heartbeat ---------------------------------------------------------------


def _heartbeat(t0, **overrides) -> dict:
    data = {
        "edge_instance_id": "edge-inst-0001",
        "runtime_version": "1.0.0",
        "protocol_version": "1.0",
        "health": "degraded",
        "spool_depth": 42,
        "oldest_spooled_captured_at": t0,
        "highest_spooled_sequence": 142,
        "highest_acknowledged_sequence": 100,
        "quarantined_record_count": 1,
        "clock": {
            "edge_clock_at": t0 + timedelta(minutes=5),
            "clock_source": "gnss",
            "last_synchronized_at": t0,
            "estimated_offset_ms": 1200,
            "estimated_uncertainty_ms": 40,
        },
        "transport_states": [
            {"transport": "ble", "state": "connected", "connected_device_count": 2},
            {"transport": "tcp", "state": "disconnected", "connected_device_count": 0},
        ],
        "correlation_id": "corr-hb-0001",
    }
    data.update(overrides)
    return data


def test_heartbeat_round_trip(t0) -> None:
    heartbeat = EdgeHeartbeat.model_validate(_heartbeat(t0))
    assert EdgeHeartbeat.model_validate_json(heartbeat.model_dump_json()) == heartbeat
    empty = EdgeHeartbeat.model_validate(
        _heartbeat(
            t0,
            spool_depth=0,
            oldest_spooled_captured_at=None,
            quarantined_record_count=0,
            highest_acknowledged_sequence=142,
        )
    )
    assert empty.spool_depth == 0


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"oldest_spooled_captured_at": None}, "spool_depth"),
        ({"spool_depth": 0, "quarantined_record_count": 0}, "spool_depth"),
        ({"highest_acknowledged_sequence": 143}, "cannot exceed"),
        ({"quarantined_record_count": 43}, "part of spool_depth"),
        ({"health": "fine"}, "health"),
        (
            {
                "transport_states": [
                    {
                        "transport": "ble",
                        "state": "connected",
                        "connected_device_count": 1,
                    },
                    {
                        "transport": "ble",
                        "state": "degraded",
                        "connected_device_count": 1,
                    },
                ]
            },
            "repeat",
        ),
        (
            {
                "transport_states": [
                    {
                        "transport": "usb",
                        "state": "disconnected",
                        "connected_device_count": 1,
                    }
                ]
            },
            "DISCONNECTED",
        ),
    ],
)
def test_invalid_heartbeat_is_rejected(t0, overrides: dict, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        EdgeHeartbeat.model_validate(_heartbeat(t0, **overrides))


def test_clock_metadata_rules(t0) -> None:
    clock = _heartbeat(t0)["clock"] | {"estimated_offset_ms": None}
    with pytest.raises(ValidationError, match="only carried with estimated_offset_ms"):
        EdgeHeartbeat.model_validate(_heartbeat(t0, clock=clock))
    clock = _heartbeat(t0)["clock"] | {"clock_source": "wall_socket"}
    with pytest.raises(ValidationError):
        EdgeHeartbeat.model_validate(_heartbeat(t0, clock=clock))
    clock = _heartbeat(t0)["clock"] | {"edge_clock_at": t0.replace(tzinfo=None)}
    with pytest.raises(ValidationError, match="timezone"):
        EdgeHeartbeat.model_validate(_heartbeat(t0, clock=clock))
