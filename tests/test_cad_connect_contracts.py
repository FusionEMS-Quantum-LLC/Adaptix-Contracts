"""Tests for the AdaptixCore Fire CAD Connect shared contracts.

Lock the CAD Connect non-negotiables at the contract layer:
- a normalized value is a FieldValue carrying confidence + status + source ref,
- FieldStatus.MISSING never carries a value (no fabrication),
- FieldStatus.CONFLICT lists >= 2 candidate values (no silent selection),
- CONFIRMED/REVIEW require a value,
- the normalized incident round-trips through JSON,
- mapping profiles are versioned,
- event constants are DEFINED but NOT yet registered (registered in producer PRs).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

import adaptix_contracts.cad_connect as cad_connect
from adaptix_contracts.cad_connect import (
    CAD_CONNECT_EVENT_TYPES,
    AgencyCadMappingProfile,
    CadConnectIncident,
    CadConnectProvenance,
    CadConnectSource,
    CadConnectSourceRef,
    CadConnectUnit,
    CadFieldMappingRule,
    ConnectorSupportStatus,
    FieldStatus,
    FieldValue,
    IngestionMethod,
    MappingProfileStatus,
)


def _confirmed(value: str) -> FieldValue:
    return FieldValue(
        value=value, raw_text=value, confidence=0.99, status=FieldStatus.CONFIRMED
    )


def test_public_exports_are_unique_and_resolvable() -> None:
    assert len(cad_connect.__all__) == len(set(cad_connect.__all__))
    for symbol in cad_connect.__all__:
        assert hasattr(cad_connect, symbol), f"Missing CAD Connect export: {symbol}"


def test_field_value_missing_must_not_carry_value() -> None:
    with pytest.raises(ValidationError):
        FieldValue(value="14:11:42", status=FieldStatus.MISSING)
    # MISSING with no value is valid.
    fv = FieldValue(status=FieldStatus.MISSING)
    assert fv.value is None


def test_field_value_conflict_requires_two_candidates() -> None:
    with pytest.raises(ValidationError):
        FieldValue(
            value="14:11:42",
            status=FieldStatus.CONFLICT,
            candidates=[_confirmed("14:11:42")],
        )
    fv = FieldValue(
        value="14:11:42",
        status=FieldStatus.CONFLICT,
        candidates=[_confirmed("14:11:42"), _confirmed("14:13:00")],
    )
    assert len(fv.candidates) == 2


def test_field_value_confirmed_requires_value() -> None:
    with pytest.raises(ValidationError):
        FieldValue(status=FieldStatus.CONFIRMED)
    assert _confirmed("Engine 1").value == "Engine 1"


def test_confidence_bounds_enforced() -> None:
    with pytest.raises(ValidationError):
        FieldValue(value="x", status=FieldStatus.REVIEW, confidence=1.5)


def test_normalized_incident_round_trips() -> None:
    inc = CadConnectIncident(
        source=CadConnectSource(
            input_format="txt",
            byte_sha256="deadbeef",
            layout_signature="jeffco-v1",
            provenance=CadConnectProvenance(
                source_vendor="local_run_sheet",
                external_incident_id="26-1847",
                ingestion_method=IngestionMethod.PASTE,
                cortex_capability_key="cortex.cad.map",
            ),
        ),
        units=[
            CadConnectUnit(
                designation_raw="E1",
                designation=_confirmed("Engine 1"),
                times={"dispatched": _confirmed("2026-08-13T20:04:00Z")},
            )
        ],
    )
    inc.incident.incident_number = _confirmed("26-1847")
    inc.times.dispatch = _confirmed("2026-08-13T20:04:13Z")
    inc.times.arrived_on_scene = FieldValue(
        value="2026-08-13T20:12:08Z",
        status=FieldStatus.CONFLICT,
        candidates=[
            _confirmed("2026-08-13T20:12:08Z"),
            _confirmed("2026-08-13T20:13:00Z"),
        ],
    )

    dumped = inc.model_dump()
    rebuilt = CadConnectIncident.model_validate(dumped)
    assert rebuilt.units[0].designation_raw == "E1"
    assert rebuilt.units[0].designation.value == "Engine 1"
    assert rebuilt.times.arrived_on_scene.status is FieldStatus.CONFLICT
    assert rebuilt.source.provenance.ingestion_method is IngestionMethod.PASTE
    # JSON schema emits without error.
    assert CadConnectIncident.model_json_schema()["title"] == "CadConnectIncident"


def test_empty_shell_constructs() -> None:
    shell = CadConnectIncident.empty("pdf", IngestionMethod.MANUAL_UPLOAD)
    assert shell.source.input_format == "pdf"
    assert shell.source.provenance.ingestion_method is IngestionMethod.MANUAL_UPLOAD
    assert shell.units == []


def test_source_ref_defaults_redacted() -> None:
    ref = CadConnectSourceRef(cell="DSP", raw_text="DSP 20:04:13")
    assert ref.observed_value_redacted is True


def test_mapping_profile_is_versioned() -> None:
    profile = AgencyCadMappingProfile(
        tenant_id="t-1",
        display_name="Jefferson County CAD run sheet",
        input_type=IngestionMethod.MANUAL_UPLOAD,
        layout_signature="jeffco-v1",
        version=1,
        active=True,
        status=MappingProfileStatus.CONFIRMED,
        field_map=[
            CadFieldMappingRule(canonical_field="times.dispatch", source_locator="DSP")
        ],
        code_map={"111": "FIRE||STRUCTURE_FIRE"},
    )
    assert profile.version == 1
    with pytest.raises(ValidationError):
        AgencyCadMappingProfile(
            tenant_id="t-1",
            display_name="x",
            input_type=IngestionMethod.MANUAL_UPLOAD,
            layout_signature="s",
            version=0,  # must be >= 1
        )


def test_connector_support_status_values() -> None:
    assert ConnectorSupportStatus.PRODUCTION_VERIFIED.value == "production_verified"
    # a registered connector is not "supported" — planned/auth-required exist for that truth
    assert (
        ConnectorSupportStatus.AUTHORIZATION_REQUIRED.value == "authorization_required"
    )


def test_events_defined_but_not_registered_yet() -> None:
    """Event constants exist, but must NOT be in ALL_EVENTS until producers land."""
    from adaptix_contracts.events import registry

    assert len(CAD_CONNECT_EVENT_TYPES) == 7
    for event_type in CAD_CONNECT_EVENT_TYPES:
        assert event_type.startswith("cad_connect.")
        # Deferred registration keeps the producer-drift test green.
        assert event_type not in registry.ALL_EVENTS
