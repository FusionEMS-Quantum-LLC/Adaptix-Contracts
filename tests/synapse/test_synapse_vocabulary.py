"""SYN-001 vocabulary: the enums are exactly what the Synapse Fabric specifies.

These assert the full member set, not a sample: a member added or dropped
here changes what every Synapse producer and consumer may say on the wire.
"""

from __future__ import annotations

import enum
import inspect

import pytest
from pydantic import ValidationError

from adaptix_contracts.synapse import enums as synapse_enums
from adaptix_contracts.synapse import (
    FORBIDDEN_CONTROL_CAPABILITIES,
    RETRYABLE_EDGE_REJECTIONS,
    SIGNAL_KIND_PAYLOAD_TYPES,
    SIGNAL_KIND_REQUIRED_CAPABILITY,
    ClinicalSignalEnvelope,
    DeploymentProfile,
    EdgeRecordRejectionReason,
    ProtocolKind,
    SynapseDeviceCapability,
    SynapseForbiddenControlCapability,
    SynapseRailResolution,
    SynapseRailType,
    SynapseSignalKind,
    SynapseTimeQuality,
    TransportKind,
    is_forbidden_control_capability,
)


def _values(enum_cls: type[enum.Enum]) -> set[str]:
    return {member.value for member in enum_cls}


def _names(enum_cls: type[enum.Enum]) -> set[str]:
    return {member.name for member in enum_cls}


def test_signal_kind_is_exactly_the_specified_set() -> None:
    assert _names(SynapseSignalKind) == {
        "OBSERVATION",
        "WAVEFORM",
        "ALERT",
        "THERAPY_EVENT",
        "DOCUMENT",
        "IMAGE",
        "VENTILATOR_STATE",
        "PUMP_STATE",
        "TEMPERATURE",
        "DIAGNOSTIC",
        "DEVICE_STATE",
    }


def test_device_capability_is_exactly_the_specified_set() -> None:
    assert _names(SynapseDeviceCapability) == {
        "OBSERVATIONS",
        "WAVEFORMS",
        "ALERTS",
        "THERAPY_EVENTS",
        "DOCUMENTS",
        "IMAGES",
        "VENTILATOR_TELEMETRY",
        "PUMP_TELEMETRY",
        "TEMPERATURE",
        "DIAGNOSTICS",
    }


def test_time_quality_is_exactly_the_specified_set() -> None:
    assert _names(SynapseTimeQuality) == {
        "ORIGINAL",
        "ESTIMATED",
        "CORRECTED",
        "UNTRUSTED",
    }


def test_rail_types_are_exactly_the_specified_set() -> None:
    assert _values(SynapseRailType) == {
        "direct_wifi",
        "bluetooth",
        "usb",
        "serial",
        "tcp",
        "udp",
        "mqtt",
        "http",
        "vendor_cloud",
        "webhook",
        "sftp",
        "file_import",
        "directory_watch",
        "sdc",
        "hl7_device",
    }


def test_transport_kinds_are_exactly_the_specified_set() -> None:
    assert _names(TransportKind) == {
        "BLE",
        "USB",
        "SERIAL",
        "TCP",
        "UDP",
        "WIFI",
        "MQTT",
        "HTTP",
        "WEBHOOK",
        "SFTP",
        "FILE",
        "DIRECTORY_WATCH",
        "VENDOR_CLOUD",
        "SDC",
    }


def test_protocol_kinds_are_exactly_the_specified_set() -> None:
    assert _values(ProtocolKind) == {
        "hl7_device",
        "ieee_11073_phd",
        "structured_json",
        "structured_xml",
        "structured_csv",
        "image_document",
        "waveform_stream",
        "adaptix_reference",
    }


def test_rail_resolution_classes() -> None:
    assert _values(SynapseRailResolution) == {
        "exact_duplicate",
        "probable_duplicate",
        "independent_corroborating_source",
        "conflicting_observation",
    }


def test_deployment_profiles() -> None:
    assert _names(DeploymentProfile) == {
        "WINDOWS_MDT",
        "LINUX_GATEWAY",
        "ANDROID_FIELD",
    }


def test_forbidden_control_vocabulary_is_present_and_complete() -> None:
    assert FORBIDDEN_CONTROL_CAPABILITIES == {
        "shock",
        "cardiovert",
        "pace",
        "change_infusion",
        "administer_medication",
        "alter_ventilator_therapy",
        "start_critical_treatment",
        "stop_critical_treatment",
    }
    assert FORBIDDEN_CONTROL_CAPABILITIES == _values(SynapseForbiddenControlCapability)


@pytest.mark.parametrize(
    "spelling",
    [
        "shock",
        "SHOCK",
        " Change-Infusion ",
        "change infusion",
        "Alter Ventilator Therapy",
    ],
)
def test_forbidden_control_is_recognised_regardless_of_spelling(spelling: str) -> None:
    assert is_forbidden_control_capability(spelling)


def test_no_read_capability_or_signal_kind_is_a_control_action() -> None:
    for member in [*SynapseDeviceCapability, *SynapseSignalKind]:
        assert not is_forbidden_control_capability(member.value)
        assert "command" not in member.value
        assert "control" not in member.value


def test_no_enum_member_names_a_manufacturer() -> None:
    """LAW SYN-001: capabilities, not manufacturers. No manufacturer is a type."""

    manufacturer_tokens = {
        "zoll",
        "stryker",
        "physio",
        "lifepak",
        "philips",
        "masimo",
        "medtronic",
        "draeger",
        "mindray",
        "nihon",
        "kohden",
        "hamilton",
        "baxter",
        "carefusion",
        "welch",
        "allyn",
        "nonin",
        "corpuls",
        "schiller",
        "spacelabs",
    }
    enum_classes = [
        obj
        for _, obj in inspect.getmembers(synapse_enums, inspect.isclass)
        if issubclass(obj, enum.Enum) and obj.__module__ == synapse_enums.__name__
    ]
    assert enum_classes
    for enum_cls in enum_classes:
        for member in enum_cls:
            tokens = set(member.value.split("_")) | set(member.name.lower().split("_"))
            assert not tokens & manufacturer_tokens, (enum_cls.__name__, member)


def test_every_signal_kind_has_a_payload_rule_and_a_capability_rule() -> None:
    assert set(SIGNAL_KIND_PAYLOAD_TYPES) == set(SynapseSignalKind)
    assert set(SIGNAL_KIND_REQUIRED_CAPABILITY) == set(SynapseSignalKind)


def test_only_missing_evidence_is_a_retryable_edge_rejection() -> None:
    assert RETRYABLE_EDGE_REJECTIONS == {
        EdgeRecordRejectionReason.EVIDENCE_NOT_RECEIVED
    }


@pytest.mark.parametrize("kind", ["command", "shock", "OBSERVATION", "vitals", ""])
def test_unknown_signal_kind_is_rejected(envelope_data, kind: str) -> None:
    with pytest.raises(ValidationError):
        ClinicalSignalEnvelope.model_validate(envelope_data(signal_kind=kind))


@pytest.mark.parametrize("quality", ["exact", "ORIGINAL", "trusted"])
def test_unknown_time_quality_is_rejected(envelope_data, quality: str) -> None:
    with pytest.raises(ValidationError):
        ClinicalSignalEnvelope.model_validate(envelope_data(time_quality=quality))
