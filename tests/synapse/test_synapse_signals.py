"""SYN-001 ClinicalSignalEnvelope and its discriminated payloads."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from adaptix_contracts.synapse.enums import (
    SynapseConnectionState,
    SynapseSignalKind,
    SynapseTimeQuality,
)
from adaptix_contracts.synapse.signals import (
    AlertPayload,
    ClinicalSignalEnvelope,
    DeviceBatteryState,
    DeviceStatePayload,
    MAX_CLOCK_OFFSET_MS,
    ObservationPayload,
    WaveformReferencePayload,
)

_EXACT_ENVELOPE_FIELDS = {
    "schema_version",
    "event_id",
    "tenant_id",
    "device_id",
    "device_session_id",
    "rail_id",
    "signal_kind",
    "signal_code",
    "device_observed_at",
    "adaptix_received_at",
    "corrected_observed_at",
    "time_quality",
    "clock_offset_ms",
    "adapter_key",
    "adapter_version",
    "source_record_id",
    "idempotency_key",
    "evidence_id",
    "evidence_sha256",
    "normalization_version",
    "quality_flags",
    "correlation_id",
    "payload",
}


def test_envelope_has_exactly_the_specified_fields() -> None:
    assert set(ClinicalSignalEnvelope.model_fields) == _EXACT_ENVELOPE_FIELDS


def _one_of_each_payload(envelope_data, waveform_payload, raw_sha256) -> list[dict]:
    evidence = {"evidence_id": "ev-0001", "evidence_sha256": raw_sha256}
    return [
        envelope_data(),
        envelope_data(
            signal_kind="waveform",
            signal_code="waveform.ecg",
            payload=waveform_payload(),
            **evidence,
        ),
        envelope_data(
            signal_kind="alert",
            signal_code="alert.spo2_low",
            payload={
                "payload_type": "alert",
                "alert_code": "alert.spo2_low",
                "priority": "high",
                "condition": "physiological",
                "state": "active",
                "triggering_value": {"code": "vital.spo2", "value": 84, "unit": "%"},
            },
        ),
        envelope_data(
            signal_kind="therapy_event",
            signal_code="therapy.defibrillation",
            payload={
                "payload_type": "therapy_event",
                "therapy_code": "therapy.defibrillation",
                "phase": "delivered",
                "parameters": [{"code": "energy", "value": 200, "unit": "J"}],
            },
        ),
        envelope_data(
            signal_kind="document",
            signal_code="document.twelve_lead",
            payload={
                "payload_type": "document_reference",
                "document_type": "document.twelve_lead",
                "evidence_id": "ev-0001",
                "media_type": "application/pdf",
            },
            **evidence,
        ),
        envelope_data(
            signal_kind="device_state",
            signal_code="device.battery",
            payload={
                "payload_type": "device_state",
                "state_code": "device.battery",
                "battery": {"level_percent": 64.5, "charging": False},
                "connection_state": "connected",
            },
        ),
    ]


def test_round_trip_every_payload_type(
    envelope_data, waveform_payload, raw_sha256
) -> None:
    for data in _one_of_each_payload(envelope_data, waveform_payload, raw_sha256):
        envelope = ClinicalSignalEnvelope.model_validate(data)
        assert (
            ClinicalSignalEnvelope.model_validate_json(envelope.model_dump_json())
            == envelope
        )
        assert ClinicalSignalEnvelope.model_validate(envelope.model_dump()) == envelope


def test_serialization_uses_stable_wire_values(envelope_data) -> None:
    envelope = ClinicalSignalEnvelope.model_validate(envelope_data())
    wire = envelope.model_dump(mode="json")
    assert wire["schema_version"] == "1.0"
    assert wire["signal_kind"] == "observation"
    assert wire["time_quality"] == "original"
    assert wire["payload"]["payload_type"] == "observation"
    assert wire["device_observed_at"] == "2026-09-24T14:00:00Z"
    assert isinstance(envelope.payload, ObservationPayload)
    assert envelope.signal_kind is SynapseSignalKind.OBSERVATION


def test_json_schema_is_generated_with_discriminator(envelope_data) -> None:
    schema = ClinicalSignalEnvelope.model_json_schema()
    assert set(schema["required"]) >= {"tenant_id", "device_id", "idempotency_key"}
    assert "discriminator" in schema["properties"]["payload"]


def test_envelope_is_immutable(envelope_data) -> None:
    envelope = ClinicalSignalEnvelope.model_validate(envelope_data())
    with pytest.raises(ValidationError):
        setattr(envelope, "tenant_id", "tenant-other")


@pytest.mark.parametrize("missing", ["tenant_id", "device_id"])
def test_missing_tenant_or_device_is_rejected(envelope_data, missing: str) -> None:
    data = envelope_data()
    del data[missing]
    with pytest.raises(ValidationError, match=missing):
        ClinicalSignalEnvelope.model_validate(data)


@pytest.mark.parametrize("value", [None, ""])
def test_empty_tenant_or_device_is_rejected(envelope_data, value) -> None:
    for field in ("tenant_id", "device_id"):
        with pytest.raises(ValidationError):
            ClinicalSignalEnvelope.model_validate(envelope_data(**{field: value}))


def test_idempotency_key_is_required(envelope_data) -> None:
    data = envelope_data()
    del data["idempotency_key"]
    with pytest.raises(ValidationError, match="idempotency_key"):
        ClinicalSignalEnvelope.model_validate(data)
    for bad in ("", None, "key\nwith-newline"):
        with pytest.raises(ValidationError):
            ClinicalSignalEnvelope.model_validate(envelope_data(idempotency_key=bad))


def test_unknown_fields_are_rejected(envelope_data) -> None:
    with pytest.raises(ValidationError, match="extra"):
        ClinicalSignalEnvelope.model_validate(envelope_data(patient_name="x"))


def test_unknown_schema_version_is_rejected(envelope_data) -> None:
    with pytest.raises(ValidationError):
        ClinicalSignalEnvelope.model_validate(envelope_data(schema_version="2.0"))


_WELL_FORMED_SHA = "ab" * 32


@pytest.mark.parametrize(
    "bad_sha",
    [
        _WELL_FORMED_SHA.upper(),
        _WELL_FORMED_SHA[:-1],
        _WELL_FORMED_SHA + "0",
        "z" * 64,
        "",
    ],
)
def test_sha256_shape_is_enforced(envelope_data, bad_sha: str) -> None:
    with pytest.raises(ValidationError):
        ClinicalSignalEnvelope.model_validate(
            envelope_data(evidence_id="ev-0001", evidence_sha256=bad_sha)
        )


def test_well_formed_sha256_is_accepted(envelope_data) -> None:
    envelope = ClinicalSignalEnvelope.model_validate(
        envelope_data(evidence_id="ev-0001", evidence_sha256=_WELL_FORMED_SHA)
    )
    assert envelope.evidence_sha256 == _WELL_FORMED_SHA


def test_evidence_id_and_sha_travel_together(envelope_data, raw_sha256) -> None:
    with pytest.raises(ValidationError, match="together"):
        ClinicalSignalEnvelope.model_validate(envelope_data(evidence_id="ev-0001"))
    with pytest.raises(ValidationError, match="together"):
        ClinicalSignalEnvelope.model_validate(envelope_data(evidence_sha256=raw_sha256))


# --- timestamps --------------------------------------------------------------


@pytest.mark.parametrize("field", ["device_observed_at", "adaptix_received_at"])
def test_naive_timestamps_are_rejected(envelope_data, field: str) -> None:
    naive = datetime(2026, 9, 24, 14, 0, 0)
    with pytest.raises(ValidationError, match="timezone"):
        ClinicalSignalEnvelope.model_validate(envelope_data(**{field: naive}))


def test_original_time_requires_the_device_time(envelope_data, t0) -> None:
    with pytest.raises(ValidationError, match="ORIGINAL"):
        ClinicalSignalEnvelope.model_validate(envelope_data(device_observed_at=None))
    with pytest.raises(ValidationError, match="ORIGINAL"):
        ClinicalSignalEnvelope.model_validate(envelope_data(corrected_observed_at=t0))


def test_corrected_time_keeps_the_original_and_must_add_up(envelope_data, t0) -> None:
    corrected = ClinicalSignalEnvelope.model_validate(
        envelope_data(
            time_quality="corrected",
            clock_offset_ms=-90_500,
            corrected_observed_at=t0 - timedelta(milliseconds=90_500),
        )
    )
    assert corrected.device_observed_at == t0
    assert corrected.time_quality is SynapseTimeQuality.CORRECTED
    with pytest.raises(ValidationError, match="must equal"):
        ClinicalSignalEnvelope.model_validate(
            envelope_data(
                time_quality="corrected",
                clock_offset_ms=-90_500,
                corrected_observed_at=t0,
            )
        )
    with pytest.raises(ValidationError, match="CORRECTED time requires"):
        ClinicalSignalEnvelope.model_validate(
            envelope_data(time_quality="corrected", clock_offset_ms=1000)
        )


def test_clock_offset_only_on_corrected_time_and_bounded(envelope_data, t0) -> None:
    with pytest.raises(ValidationError, match="only carried by CORRECTED"):
        ClinicalSignalEnvelope.model_validate(envelope_data(clock_offset_ms=5))
    with pytest.raises(ValidationError):
        ClinicalSignalEnvelope.model_validate(
            envelope_data(
                time_quality="corrected",
                clock_offset_ms=MAX_CLOCK_OFFSET_MS + 1,
                corrected_observed_at=t0,
            )
        )


def test_estimated_and_untrusted_time_rules(envelope_data, t0) -> None:
    estimated = ClinicalSignalEnvelope.model_validate(
        envelope_data(
            time_quality="estimated",
            device_observed_at=None,
            corrected_observed_at=t0,
        )
    )
    assert estimated.device_observed_at is None
    with pytest.raises(ValidationError, match="ESTIMATED"):
        ClinicalSignalEnvelope.model_validate(
            envelope_data(time_quality="estimated", device_observed_at=None)
        )
    untrusted = ClinicalSignalEnvelope.model_validate(
        envelope_data(time_quality="untrusted")
    )
    assert untrusted.device_observed_at == t0
    with pytest.raises(ValidationError, match="UNTRUSTED"):
        ClinicalSignalEnvelope.model_validate(
            envelope_data(time_quality="untrusted", device_observed_at=None)
        )


def test_quality_flags_do_not_repeat(envelope_data) -> None:
    with pytest.raises(ValidationError, match="repeat"):
        ClinicalSignalEnvelope.model_validate(
            envelope_data(quality_flags=["out_of_order", "out_of_order"])
        )
    with pytest.raises(ValidationError):
        ClinicalSignalEnvelope.model_validate(envelope_data(quality_flags=["made_up"]))


# --- discriminated union -----------------------------------------------------


def test_payload_must_fit_the_signal_kind(
    envelope_data, waveform_payload, raw_sha256
) -> None:
    with pytest.raises(ValidationError, match="cannot carry"):
        ClinicalSignalEnvelope.model_validate(envelope_data(signal_kind="waveform"))
    with pytest.raises(ValidationError, match="cannot carry"):
        ClinicalSignalEnvelope.model_validate(
            envelope_data(
                signal_kind="observation",
                payload=waveform_payload(),
                evidence_id="ev-0001",
                evidence_sha256=raw_sha256,
            )
        )


def test_unknown_payload_type_is_rejected(envelope_data) -> None:
    payload = {"payload_type": "command", "code": "vital.heart_rate", "value": 1}
    with pytest.raises(ValidationError, match="payload_type"):
        ClinicalSignalEnvelope.model_validate(envelope_data(payload=payload))


def test_payload_fields_of_another_member_are_rejected(envelope_data) -> None:
    payload = {
        "payload_type": "observation",
        "code": "vital.heart_rate",
        "value": 72,
        "unit": "/min",
        "sample_rate_hz": 250.0,
    }
    with pytest.raises(ValidationError, match="extra"):
        ClinicalSignalEnvelope.model_validate(envelope_data(payload=payload))


def test_payload_evidence_must_be_the_envelope_evidence(
    envelope_data, waveform_payload, raw_sha256
) -> None:
    with pytest.raises(ValidationError, match="payload references evidence"):
        ClinicalSignalEnvelope.model_validate(
            envelope_data(
                signal_kind="waveform",
                signal_code="waveform.ecg",
                payload=waveform_payload(evidence_id="ev-other"),
                evidence_id="ev-0001",
                evidence_sha256=raw_sha256,
            )
        )


def test_image_signal_needs_an_image_media_type(envelope_data, raw_sha256) -> None:
    def image(media_type: str) -> dict:
        return envelope_data(
            signal_kind="image",
            signal_code="image.monitor_still",
            evidence_id="ev-0001",
            evidence_sha256=raw_sha256,
            payload={
                "payload_type": "document_reference",
                "document_type": "image.monitor_still",
                "evidence_id": "ev-0001",
                "media_type": media_type,
            },
        )

    assert ClinicalSignalEnvelope.model_validate(image("image/png"))
    assert ClinicalSignalEnvelope.model_validate(image("application/dicom"))
    with pytest.raises(ValidationError, match="IMAGE"):
        ClinicalSignalEnvelope.model_validate(image("application/pdf"))


# --- payload shapes ----------------------------------------------------------


def test_observation_value_and_unit_rules() -> None:
    assert ObservationPayload(code="vital.spo2", value=97, unit="%").value == 97
    rhythm = ObservationPayload(code="ecg.rhythm", value="sinus_rhythm")
    assert rhythm.unit is None
    with pytest.raises(ValidationError, match="requires a UCUM unit"):
        ObservationPayload(code="vital.spo2", value=97)
    with pytest.raises(ValidationError, match="must not carry a unit"):
        ObservationPayload(code="ecg.rhythm", value="sinus_rhythm", unit="%")
    with pytest.raises(ValidationError, match="boolean"):
        ObservationPayload(code="vital.spo2", value=True, unit="%")
    with pytest.raises(ValidationError, match="finite"):
        ObservationPayload(code="vital.spo2", value=float("nan"), unit="%")
    with pytest.raises(ValidationError):
        ObservationPayload(code="Vital SpO2", value=97, unit="%")


def test_observation_reference_range_and_device_quality() -> None:
    observation = ObservationPayload(
        code="vital.heart_rate",
        value=140,
        unit="/min",
        reference_range={"low": 50, "high": 120},
        device_quality="questionable",
    )
    assert observation.reference_range is not None
    with pytest.raises(ValidationError, match="low exceeds high"):
        ObservationPayload(
            code="vital.heart_rate",
            value=72,
            unit="/min",
            reference_range={"low": 120, "high": 50},
        )
    with pytest.raises(ValidationError):
        ObservationPayload(
            code="vital.heart_rate", value=72, unit="/min", device_quality="great"
        )


def test_waveform_reference_carries_no_samples(waveform_payload) -> None:
    assert "samples" not in WaveformReferencePayload.model_fields
    with pytest.raises(ValidationError, match="extra"):
        WaveformReferencePayload.model_validate(waveform_payload(samples=[1, 2, 3]))


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"sample_count": 1002}, "exceeds"),
        ({"sample_rate_hz": 0}, "greater_than"),
        ({"sample_count": 0}, "greater_than_equal"),
        ({"calibration": {"unit": "mV", "scale_factor": 0}}, "scale_factor"),
        ({"encoding": "mp3"}, "encoding"),
        ({"evidence_id": None}, "evidence_id"),
        ({"content_type": "not a media type"}, "content_type"),
    ],
)
def test_invalid_waveform_reference_is_rejected(
    waveform_payload, overrides: dict, message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        WaveformReferencePayload.model_validate(waveform_payload(**overrides))


def test_waveform_window_must_have_positive_duration(waveform_payload, t0) -> None:
    with pytest.raises(ValidationError, match="after start_at"):
        WaveformReferencePayload.model_validate(waveform_payload(end_at=t0))
    with pytest.raises(ValidationError, match="timezone"):
        WaveformReferencePayload.model_validate(
            waveform_payload(start_at=datetime(2026, 9, 24, 14, 0, 0))
        )


def test_waveform_window_allows_dropouts_but_not_extra_samples(
    waveform_payload,
) -> None:
    assert WaveformReferencePayload.model_validate(waveform_payload(sample_count=1001))
    assert WaveformReferencePayload.model_validate(waveform_payload(sample_count=900))


def test_device_state_carries_battery_and_connection_state() -> None:
    state = DeviceStatePayload(
        state_code="device.link",
        connection_state="disconnected",
        battery={"level_percent": 12, "charging": False, "remaining_minutes": 18},
    )
    assert state.connection_state is SynapseConnectionState.DISCONNECTED
    assert isinstance(state.battery, DeviceBatteryState)
    mode = DeviceStatePayload(state_code="ventilator.mode", value="volume_control")
    assert mode.value == "volume_control"
    with pytest.raises(
        ValidationError, match="needs value, battery or connection_state"
    ):
        DeviceStatePayload(state_code="device.status")
    with pytest.raises(ValidationError, match="needs level_percent"):
        DeviceBatteryState()
    with pytest.raises(ValidationError):
        DeviceBatteryState(level_percent=101)
    with pytest.raises(ValidationError, match="only carried with a value"):
        DeviceStatePayload(
            state_code="device.link", connection_state="connected", unit="%"
        )
    with pytest.raises(ValidationError):
        DeviceStatePayload(state_code="device.link", connection_state="unplugged")


def test_alert_vocabulary_is_closed() -> None:
    with pytest.raises(ValidationError):
        AlertPayload(
            alert_code="alert.spo2_low",
            priority="critical",
            condition="physiological",
            state="active",
        )
