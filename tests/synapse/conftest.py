"""Shared synthetic builders for the Synapse contract tests.

Every value here is synthetic certification data: the device is the
first-party Adaptix Synapse Reference Device, ids are obviously fabricated
test identifiers, and no record describes a real person.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from adaptix_contracts.synapse import (
    compute_evidence_ledger_entry_sha256,
    compute_physical_identity_hash,
)

T0 = datetime(2026, 9, 24, 14, 0, 0, tzinfo=UTC)
RAW_BYTES = b"synthetic reference-device record 000001"
RAW_SHA256 = hashlib.sha256(RAW_BYTES).hexdigest()

Builder = Callable[..., dict[str, Any]]


def _envelope(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "event_id": "evt-0001",
        "tenant_id": "tenant-cert-0001",
        "device_id": "dev-ref-0001",
        "device_session_id": "sess-0001",
        "rail_id": "rail-0001",
        "signal_kind": "observation",
        "signal_code": "vital.heart_rate",
        "device_observed_at": T0,
        "adaptix_received_at": T0 + timedelta(seconds=2),
        "time_quality": "original",
        "adapter_key": "adaptix.reference",
        "adapter_version": "1.0.0",
        "source_record_id": "ref-rec-000001",
        "idempotency_key": "dev-ref-0001:ref-rec-000001",
        "normalization_version": "1.0.0",
        "correlation_id": "corr-0001",
        "payload": {
            "payload_type": "observation",
            "code": "vital.heart_rate",
            "value": 72,
            "unit": "/min",
        },
    }
    data.update(overrides)
    return data


def _waveform_payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "payload_type": "waveform_reference",
        "channel": "ecg.lead_ii",
        "sample_rate_hz": 250.0,
        "start_at": T0,
        "end_at": T0 + timedelta(seconds=4),
        "sample_count": 1000,
        "calibration": {"unit": "mV", "scale_factor": 0.005, "offset": 0.0},
        "evidence_id": "ev-0001",
        "content_type": "application/octet-stream",
        "encoding": "int16_le",
    }
    data.update(overrides)
    return data


def _genome(**overrides: Any) -> dict[str, Any]:
    identity = {
        "manufacturer": "Adaptix",
        "model": "Synapse Reference Device",
        "serial_number": "SRD-000001",
        "physical_identity_hash": compute_physical_identity_hash(
            "Adaptix", "Synapse Reference Device", "SRD-000001"
        ),
    }
    data: dict[str, Any] = {
        "device_id": "dev-ref-0001",
        "genome_version": 1,
        "identity": identity,
        "device_class": "physiological_monitor",
        "transports": ["tcp", "ble", "usb"],
        "capabilities": [
            "observations",
            "waveforms",
            "alerts",
            "therapy_events",
            "documents",
            "temperature",
        ],
        "signals": [
            "observation",
            "waveform",
            "alert",
            "therapy_event",
            "document",
            "temperature",
            "device_state",
        ],
        "adapter": {"key": "adaptix.reference", "version": "1.0.0"},
        "last_verified_at": T0,
    }
    data.update(overrides)
    return data


def _evidence(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": "ev-0001",
        "tenant_id": "tenant-cert-0001",
        "device_id": "dev-ref-0001",
        "device_session_id": "sess-0001",
        "rail_id": "rail-0001",
        "sha256": RAW_SHA256,
        "byte_size": len(RAW_BYTES),
        "media_type": "application/octet-stream",
        "storage_key": "synapse/tenant-cert-0001/dev-ref-0001/ev-0001.bin",
        "storage_version": "v1",
        "adapter_key": "adaptix.reference",
        "adapter_version": "1.0.0",
        "source_reference": "ref-rec-000001",
        "received_at": T0,
        "classification": "PHI",
        "retention_class": "clinical_record",
        "ledger_sequence": 1,
        "previous_entry_sha256": None,
    }
    data.update(overrides)
    if "entry_sha256" not in overrides:
        data["entry_sha256"] = compute_evidence_ledger_entry_sha256(
            tenant_id=data["tenant_id"],
            device_id=data["device_id"],
            ledger_sequence=data["ledger_sequence"],
            previous_entry_sha256=data["previous_entry_sha256"],
            evidence_id=data["id"],
            evidence_sha256=data["sha256"],
            byte_size=data["byte_size"],
            media_type=data["media_type"],
            received_at=data["received_at"],
        )
    return data


def _edge_record(local_sequence: int = 1, **overrides: Any) -> dict[str, Any]:
    source_record_id = f"ref-rec-{local_sequence:06d}"
    idempotency_key = f"dev-ref-0001:{source_record_id}"
    envelope = _envelope(
        event_id=f"evt-{local_sequence:04d}",
        source_record_id=source_record_id,
        idempotency_key=idempotency_key,
    )
    data: dict[str, Any] = {
        "edge_instance_id": "edge-inst-0001",
        "device_id": envelope["device_id"],
        "device_session_id": envelope["device_session_id"],
        "local_sequence": local_sequence,
        "source_record_id": source_record_id,
        "observed_at": envelope["device_observed_at"],
        "captured_at": envelope["adaptix_received_at"],
        "evidence_sha256": RAW_SHA256,
        "idempotency_key": idempotency_key,
        "adapter_key": envelope["adapter_key"],
        "adapter_version": envelope["adapter_version"],
        "correlation_id": envelope["correlation_id"],
        "envelope": envelope,
    }
    data.update(overrides)
    return data


@pytest.fixture
def t0() -> datetime:
    return T0


@pytest.fixture
def raw_sha256() -> str:
    return RAW_SHA256


@pytest.fixture
def envelope_data() -> Builder:
    return _envelope


@pytest.fixture
def waveform_payload() -> Builder:
    return _waveform_payload


@pytest.fixture
def genome_data() -> Builder:
    return _genome


@pytest.fixture
def evidence_data() -> Builder:
    return _evidence


@pytest.fixture
def edge_record_data() -> Builder:
    return _edge_record
