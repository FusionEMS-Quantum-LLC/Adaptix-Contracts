"""SYN-001 device genome, capability profile and driver pack support."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from adaptix_contracts.synapse import (
    DeviceAdapterRef,
    DeviceCapabilityProfile,
    DeviceGenome,
    DeviceIdentity,
    DriverPackSupport,
    DriverPackSupportStatus,
    DriverPackTier,
    SynapseDeviceCapability,
    SynapseSignalKind,
    compute_physical_identity_hash,
)

#: Field-name fragments that would indicate patient identity or chart linkage.
_PHI_FRAGMENTS = (
    "patient",
    "person",
    "mrn",
    "dob",
    "birth",
    "ssn",
    "chart",
    "pcr",
    "first_name",
    "last_name",
    "address",
    "phone",
    "encounter",
)


def test_genome_carries_the_specified_fields(genome_data) -> None:
    assert set(DeviceGenome.model_fields) == {
        "device_id",
        "genome_version",
        "identity",
        "device_class",
        "transports",
        "capabilities",
        "signals",
        "adapter",
        "last_verified_at",
    }
    assert set(DeviceIdentity.model_fields) == {
        "manufacturer",
        "model",
        "serial_number",
        "physical_identity_hash",
    }
    assert set(DeviceAdapterRef.model_fields) == {"key", "version"}


def test_genome_round_trip(genome_data) -> None:
    genome = DeviceGenome.model_validate(genome_data())
    assert DeviceGenome.model_validate_json(genome.model_dump_json()) == genome
    assert genome.provides(SynapseDeviceCapability.WAVEFORMS)
    assert not genome.provides(SynapseDeviceCapability.PUMP_TELEMETRY)
    assert genome.emits(SynapseSignalKind.DEVICE_STATE)


@pytest.mark.parametrize(
    "model", [DeviceGenome, DeviceIdentity, DeviceCapabilityProfile, DeviceAdapterRef]
)
def test_phi_is_not_in_the_genome(model) -> None:
    names = set(model.model_fields)
    properties = set(model.model_json_schema().get("properties", {}))
    for name in names | properties:
        assert not any(fragment in name for fragment in _PHI_FRAGMENTS), (model, name)


def test_patient_fields_cannot_be_attached(genome_data) -> None:
    with pytest.raises(ValidationError, match="extra"):
        DeviceGenome.model_validate(genome_data(patient_name="synthetic"))
    identity = genome_data()["identity"] | {"patient_id": "synthetic"}
    with pytest.raises(ValidationError, match="extra"):
        DeviceGenome.model_validate(genome_data(identity=identity))


def test_genome_carries_no_tenant_claim(genome_data) -> None:
    assert "tenant_id" not in DeviceGenome.model_fields
    with pytest.raises(ValidationError, match="extra"):
        DeviceGenome.model_validate(genome_data(tenant_id="tenant-cert-0001"))


def test_capability_profile_drops_physical_identity(genome_data) -> None:
    genome = DeviceGenome.model_validate(genome_data())
    profile = genome.capability_profile()
    assert isinstance(profile, DeviceCapabilityProfile)
    assert "identity" not in DeviceCapabilityProfile.model_fields
    assert profile.capabilities == genome.capabilities
    assert profile.genome_version == genome.genome_version


def test_physical_identity_hash_is_one_normalised_definition() -> None:
    a = compute_physical_identity_hash("Adaptix", "Synapse Reference Device", "SRD-1")
    b = compute_physical_identity_hash(" adaptix ", "SYNAPSE REFERENCE DEVICE", "srd-1")
    assert a == b
    assert len(a) == 64
    assert compute_physical_identity_hash(
        "ab", "c", "d"
    ) != compute_physical_identity_hash("a", "bc", "d")


def test_identity_hash_must_match_identity(genome_data) -> None:
    identity = genome_data()["identity"] | {"serial_number": "SRD-999999"}
    with pytest.raises(ValidationError, match="physical_identity_hash"):
        DeviceGenome.model_validate(genome_data(identity=identity))
    identity = genome_data()["identity"] | {"physical_identity_hash": "A" * 64}
    with pytest.raises(ValidationError):
        DeviceGenome.model_validate(genome_data(identity=identity))


@pytest.mark.parametrize(
    "control", ["shock", "Change-Infusion", "administer medication"]
)
def test_forbidden_control_capability_is_refused_by_name(
    genome_data, control: str
) -> None:
    capabilities = [*genome_data()["capabilities"], control]
    with pytest.raises(ValidationError, match="forbidden in Synapse v1"):
        DeviceGenome.model_validate(genome_data(capabilities=capabilities))


def test_signals_require_their_capability(genome_data) -> None:
    with pytest.raises(ValidationError, match="without the capability"):
        DeviceGenome.model_validate(
            genome_data(
                capabilities=["observations"], signals=["observation", "waveform"]
            )
        )
    assert DeviceGenome.model_validate(
        genome_data(
            capabilities=["observations"], signals=["observation", "device_state"]
        )
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"transports": []},
        {"transports": ["tcp", "tcp"]},
        {"transports": ["bluetooth_classic"]},
        {"capabilities": ["observations", "observations"]},
        {"genome_version": 0},
        {"device_class": "Physiological Monitor"},
        {"adapter": {"key": "Adaptix Reference", "version": "1.0.0"}},
        {"adapter": {"key": "adaptix.reference", "version": "v1"}},
        {"device_id": "x" * 37},
    ],
)
def test_invalid_genome_declarations_are_rejected(genome_data, overrides: dict) -> None:
    with pytest.raises(ValidationError):
        DeviceGenome.model_validate(genome_data(**overrides))


def test_naive_last_verified_at_is_rejected(genome_data, t0) -> None:
    with pytest.raises(ValidationError, match="timezone"):
        DeviceGenome.model_validate(
            genome_data(last_verified_at=t0.replace(tzinfo=None))
        )


# --- driver packs: optional compatibility packs are never prerequisites -------


@pytest.mark.parametrize("status", list(DriverPackSupportStatus))
def test_optional_compat_pack_states_are_not_prerequisites(t0, status) -> None:
    certified = status is DriverPackSupportStatus.CERTIFIED
    pack = DriverPackSupport(
        driver_pack_id="COMPAT-ZOLL-001",
        tier=DriverPackTier.OPTIONAL_COMPAT,
        status=status,
        adapter=DeviceAdapterRef(key="compat.example", version="1.0.0")
        if certified
        else None,
        certified_at=t0 if certified else None,
        status_changed_at=t0,
    )
    assert pack.blocks_core_readiness is False
    assert pack.supported is certified


@pytest.mark.parametrize("status", ["waiting_external_access", "not_configured"])
def test_a_pack_cannot_be_declared_a_core_prerequisite(t0, status: str) -> None:
    with pytest.raises(ValidationError, match="blocks_core_readiness"):
        DriverPackSupport(
            driver_pack_id="COMPAT-ZOLL-001",
            tier="optional_compat",
            status=status,
            status_changed_at=t0,
            blocks_core_readiness=True,
        )


@pytest.mark.parametrize(
    "status", ["waiting_external_access", "waiting_external_credential"]
)
def test_first_party_packs_never_wait_on_an_outside_party(t0, status: str) -> None:
    with pytest.raises(ValidationError, match="never waits on an outside party"):
        DriverPackSupport(
            driver_pack_id="ADAPTIX-REFERENCE-001",
            tier="first_party",
            status=status,
            status_changed_at=t0,
        )


def test_pack_ids_cannot_cross_tiers(t0) -> None:
    with pytest.raises(ValidationError, match="must start with"):
        DriverPackSupport(
            driver_pack_id="ADAPTIX-REFERENCE-001",
            tier="optional_compat",
            status="not_configured",
            status_changed_at=t0,
        )
    with pytest.raises(ValidationError, match="must not start with"):
        DriverPackSupport(
            driver_pack_id="COMPAT-ZOLL-001",
            tier="first_party",
            status="in_certification",
            status_changed_at=t0,
        )
    with pytest.raises(ValidationError):
        DriverPackSupport(
            driver_pack_id="compat-zoll-1",
            tier="optional_compat",
            status="not_configured",
            status_changed_at=t0,
        )


def test_only_a_certified_pack_is_supported_and_it_names_what_was_certified(t0) -> None:
    with pytest.raises(ValidationError, match="CERTIFIED requires"):
        DriverPackSupport(
            driver_pack_id="ADAPTIX-REFERENCE-001",
            tier="first_party",
            status="certified",
            status_changed_at=t0,
        )
    with pytest.raises(ValidationError, match="only carried by a CERTIFIED"):
        DriverPackSupport(
            driver_pack_id="ADAPTIX-REFERENCE-001",
            tier="first_party",
            status="in_certification",
            certified_at=t0,
            status_changed_at=t0,
        )
    certified = DriverPackSupport(
        driver_pack_id="ADAPTIX-REFERENCE-001",
        tier="first_party",
        status="certified",
        adapter={"key": "adaptix.reference", "version": "1.0.0"},
        certified_at=t0,
        status_changed_at=t0,
    )
    assert certified.supported
    assert certified.blocks_core_readiness is False
