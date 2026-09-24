"""SYN-001 evidence ledger references, upload authorization, sessions,
signal provenance and replay contracts."""

from __future__ import annotations

from datetime import timedelta

import pytest
from pydantic import ValidationError

from adaptix_contracts.synapse import (
    DeviceEvidenceReference,
    DeviceSessionReference,
    EvidenceUploadAuthorizationRequest,
    EvidenceUploadAuthorizationResponse,
    ReplayRequest,
    ReplayResult,
    SignalProvenance,
    compute_evidence_ledger_entry_sha256,
)

# --- evidence ledger ---------------------------------------------------------


def test_evidence_reference_round_trip(evidence_data) -> None:
    reference = DeviceEvidenceReference.model_validate(evidence_data())
    assert (
        DeviceEvidenceReference.model_validate_json(reference.model_dump_json())
        == reference
    )


def test_ledger_chain_links_entries(evidence_data, raw_sha256, t0) -> None:
    first = DeviceEvidenceReference.model_validate(evidence_data())
    second = DeviceEvidenceReference.model_validate(
        evidence_data(
            id="ev-0002",
            ledger_sequence=2,
            previous_entry_sha256=first.entry_sha256,
            received_at=t0 + timedelta(seconds=1),
        )
    )
    assert second.follows(first)
    assert not first.follows(second)
    other_device = DeviceEvidenceReference.model_validate(
        evidence_data(
            id="ev-0003",
            device_id="dev-ref-0002",
            ledger_sequence=2,
            previous_entry_sha256=first.entry_sha256,
        )
    )
    assert not other_device.follows(first)


def test_tampered_ledger_entry_is_rejected(evidence_data) -> None:
    genuine = evidence_data()
    with pytest.raises(ValidationError, match="entry_sha256 does not match"):
        DeviceEvidenceReference.model_validate(
            evidence_data(
                byte_size=genuine["byte_size"] + 1, entry_sha256=genuine["entry_sha256"]
            )
        )
    with pytest.raises(ValidationError, match="entry_sha256 does not match"):
        DeviceEvidenceReference.model_validate(evidence_data(entry_sha256="0" * 64))


def test_ledger_link_presence_follows_sequence(evidence_data) -> None:
    with pytest.raises(ValidationError, match="previous_entry_sha256"):
        DeviceEvidenceReference.model_validate(
            evidence_data(previous_entry_sha256="a" * 64)
        )
    with pytest.raises(ValidationError, match="previous_entry_sha256"):
        DeviceEvidenceReference.model_validate(evidence_data(ledger_sequence=2))
    with pytest.raises(ValidationError):
        DeviceEvidenceReference.model_validate(evidence_data(ledger_sequence=0))


def test_ledger_digest_is_time_zone_independent(raw_sha256, t0) -> None:
    kwargs = dict(
        tenant_id="tenant-cert-0001",
        device_id="dev-ref-0001",
        ledger_sequence=1,
        previous_entry_sha256=None,
        evidence_id="ev-0001",
        evidence_sha256=raw_sha256,
        byte_size=10,
        media_type="application/octet-stream",
    )
    from datetime import timezone

    shifted = t0.astimezone(timezone(timedelta(hours=-5)))
    assert compute_evidence_ledger_entry_sha256(
        received_at=t0, **kwargs
    ) == compute_evidence_ledger_entry_sha256(received_at=shifted, **kwargs)
    with pytest.raises(ValueError, match="timezone-aware"):
        compute_evidence_ledger_entry_sha256(
            received_at=t0.replace(tzinfo=None), **kwargs
        )


@pytest.mark.parametrize(
    "storage_key",
    [
        "../other-tenant/ev.bin",
        "synapse//ev.bin",
        "/abs/ev.bin",
        "s3://bucket/ev.bin",
        "a/./b",
    ],
)
def test_storage_key_is_confined(evidence_data, storage_key: str) -> None:
    with pytest.raises(ValidationError):
        DeviceEvidenceReference.model_validate(evidence_data(storage_key=storage_key))


def test_evidence_reference_carries_no_secret(evidence_data) -> None:
    with pytest.raises(ValidationError, match="SECRET"):
        DeviceEvidenceReference.model_validate(evidence_data(classification="SECRET"))
    with pytest.raises(ValidationError, match="not a URL"):
        DeviceEvidenceReference.model_validate(
            evidence_data(source_reference="https://vendor.example/export?sig=abc")
        )
    with pytest.raises(ValidationError):
        DeviceEvidenceReference.model_validate(evidence_data(sha256="A" * 64))


def _upload_request(raw_sha256: str, **overrides) -> dict:
    data = {
        "device_id": "dev-ref-0001",
        "device_session_id": "sess-0001",
        "rail_id": "rail-0001",
        "sha256": raw_sha256,
        "byte_size": 40,
        "media_type": "application/octet-stream",
        "source_reference": "ref-rec-000001",
        "adapter_key": "adaptix.reference",
        "adapter_version": "1.0.0",
        "correlation_id": "corr-0001",
    }
    data.update(overrides)
    return data


def test_upload_request_carries_no_tenant(raw_sha256) -> None:
    assert "tenant_id" not in EvidenceUploadAuthorizationRequest.model_fields
    assert EvidenceUploadAuthorizationRequest.model_validate(
        _upload_request(raw_sha256)
    )
    with pytest.raises(ValidationError, match="extra"):
        EvidenceUploadAuthorizationRequest.model_validate(
            _upload_request(raw_sha256, tenant_id="tenant-cert-0001")
        )
    with pytest.raises(ValidationError):
        EvidenceUploadAuthorizationRequest.model_validate(
            _upload_request(raw_sha256, byte_size=0)
        )


def test_upload_response_coherence(t0) -> None:
    required = EvidenceUploadAuthorizationResponse(
        evidence_id="ev-0001",
        upload_required=True,
        upload_url="https://uploads.example/object?X-Amz-Signature=synthetic",
        required_headers={"x-amz-checksum-sha256": "synthetic"},
        expires_at=t0 + timedelta(minutes=5),
    )
    assert "X-Amz-Signature" not in repr(required)
    already_stored = EvidenceUploadAuthorizationResponse(
        evidence_id="ev-0001", upload_required=False
    )
    assert already_stored.upload_url is None
    with pytest.raises(ValidationError, match="needs upload_url and expires_at"):
        EvidenceUploadAuthorizationResponse(evidence_id="ev-0001", upload_required=True)
    with pytest.raises(ValidationError, match="must be empty"):
        EvidenceUploadAuthorizationResponse(
            evidence_id="ev-0001", upload_required=False, expires_at=t0
        )
    with pytest.raises(ValidationError, match="https"):
        EvidenceUploadAuthorizationResponse(
            evidence_id="ev-0001",
            upload_required=True,
            upload_url="http://uploads.example/object",
            expires_at=t0,
        )


# --- device sessions ---------------------------------------------------------


def _session(t0, **overrides) -> dict:
    data = {
        "id": "sess-0001",
        "tenant_id": "tenant-cert-0001",
        "device_id": "dev-ref-0001",
        "external_session_key": "ref-case-000001",
        "session_type": "clinical",
        "started_at": t0,
        "state": "open",
        "primary_rail_id": "rail-0001",
    }
    data.update(overrides)
    return data


def test_session_lifecycle_rules(t0, raw_sha256) -> None:
    session = DeviceSessionReference.model_validate(
        _session(t0, care_pairing_reference_sha256=raw_sha256)
    )
    assert (
        DeviceSessionReference.model_validate_json(session.model_dump_json()) == session
    )
    with pytest.raises(ValidationError, match="OPEN"):
        DeviceSessionReference.model_validate(_session(t0, ended_at=t0))
    with pytest.raises(ValidationError, match="CLOSED"):
        DeviceSessionReference.model_validate(_session(t0, state="closed"))
    with pytest.raises(ValidationError, match="precedes"):
        DeviceSessionReference.model_validate(
            _session(t0, state="closed", ended_at=t0 - timedelta(seconds=1))
        )
    with pytest.raises(ValidationError, match="together"):
        DeviceSessionReference.model_validate(_session(t0, first_signal_at=t0))


def test_session_carries_no_phi(t0) -> None:
    for name in DeviceSessionReference.model_fields:
        assert "patient" not in name and "chart" not in name and "mrn" not in name
    with pytest.raises(ValidationError, match="extra"):
        DeviceSessionReference.model_validate(_session(t0, patient_name="synthetic"))
    with pytest.raises(ValidationError):
        DeviceSessionReference.model_validate(
            _session(t0, care_pairing_reference_sha256="chart-12345")
        )


# --- provenance and replay ---------------------------------------------------


def test_signal_provenance_rules(raw_sha256) -> None:
    provenance = SignalProvenance(
        device_event_id="evt-0002",
        device_session_id="sess-0001",
        evidence_id="ev-0001",
        evidence_sha256=raw_sha256,
        adapter_key="adaptix.reference",
        adapter_version="1.0.0",
        normalization_version="1.1.0",
        supersedes_event_id="evt-0001",
    )
    assert (
        SignalProvenance.model_validate_json(provenance.model_dump_json()) == provenance
    )
    with pytest.raises(ValidationError, match="together"):
        SignalProvenance(
            device_event_id="evt-0002",
            evidence_id="ev-0001",
            adapter_key="adaptix.reference",
            adapter_version="1.0.0",
            normalization_version="1.1.0",
        )
    with pytest.raises(ValidationError, match="supersede itself"):
        SignalProvenance(
            device_event_id="evt-0002",
            adapter_key="adaptix.reference",
            adapter_version="1.0.0",
            normalization_version="1.1.0",
            supersedes_event_id="evt-0002",
        )


def _replay_request(t0) -> ReplayRequest:
    return ReplayRequest(
        replay_id="replay-0001",
        tenant_id="tenant-cert-0001",
        device_id="dev-ref-0001",
        adapter_key="adaptix.reference",
        evidence_ids=["ev-0001", "ev-0002"],
        target_normalization_version="1.1.0",
        reason="normalization_upgrade",
        requested_at=t0,
        correlation_id="corr-0001",
    )


def _replay_result(t0, **overrides) -> ReplayResult:
    data = {
        "replay_id": "replay-0001",
        "tenant_id": "tenant-cert-0001",
        "device_id": "dev-ref-0001",
        "status": "completed",
        "normalization_version": "1.1.0",
        "renormalized_evidence_ids": ["ev-0001", "ev-0002"],
        "produced_event_ids": ["evt-0101", "evt-0102"],
        "completed_at": t0,
        "correlation_id": "corr-0001",
    }
    data.update(overrides)
    return ReplayResult.model_validate(data)


def test_replay_request_rejects_repeats(t0) -> None:
    with pytest.raises(ValidationError, match="repeat"):
        ReplayRequest.model_validate(
            _replay_request(t0).model_dump() | {"evidence_ids": ["ev-0001", "ev-0001"]}
        )


def test_replay_partial_failure_is_never_success(t0) -> None:
    failure = [{"evidence_id": "ev-0002", "reason": "evidence_hash_mismatch"}]
    with pytest.raises(ValidationError, match="COMPLETED requires"):
        _replay_result(t0, renormalized_evidence_ids=["ev-0001"], failures=failure)
    partial = _replay_result(
        t0,
        status="partially_completed",
        renormalized_evidence_ids=["ev-0001"],
        produced_event_ids=["evt-0101"],
        failures=failure,
    )
    assert partial.unaccounted_evidence_ids(_replay_request(t0)) == frozenset()
    with pytest.raises(ValidationError, match="FAILED requires"):
        _replay_result(t0, status="failed")


def test_replay_result_exposes_silently_dropped_evidence(t0) -> None:
    result = _replay_result(
        t0, renormalized_evidence_ids=["ev-0001"], produced_event_ids=["evt-0101"]
    )
    assert result.unaccounted_evidence_ids(_replay_request(t0)) == {"ev-0002"}
    other = _replay_request(t0).model_copy(update={"replay_id": "replay-0002"})
    with pytest.raises(ValueError, match="does not answer"):
        result.unaccounted_evidence_ids(other)
