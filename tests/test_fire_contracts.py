from adaptix_contracts.events.registry import (
    ALL_EVENTS,
    FIRE_BENCHMARK_TIMELINE_UPDATED,
    FIRE_INCIDENT_STATUS_UPDATED,
    FIRE_INVESTIGATION_READINESS_UPDATED,
    NERIS_NORMALIZATION_COMPLETED,
    NERIS_SCHEMA_ASSET_REFRESHED,
    NERIS_VALIDATION_COMPLETED,
)
from adaptix_contracts.fire import (
    FIRE_EVENTS,
    FireIncidentType,
    FireUnitStatus,
    NerisReadinessContract,
)
from adaptix_contracts.fire.events import (
    FIRE_BENCHMARK_TIMELINE_UPDATED as FIRE_BENCHMARK_TIMELINE_UPDATED_ALIAS,
)
from adaptix_contracts.fire.events import (
    FIRE_INVESTIGATION_READINESS_UPDATED as FIRE_INVESTIGATION_READINESS_UPDATED_ALIAS,
)
from adaptix_contracts.neris import (
    NERIS_EVENTS,
    NerisNormalizationResult,
    NerisSchemaAsset,
    NerisValidationAudit,
    NerisValidationStatus,
)
from adaptix_contracts.neris.events import (
    NERIS_NORMALIZATION_COMPLETED as NERIS_NORMALIZATION_COMPLETED_ALIAS,
)
from adaptix_contracts.neris.events import (
    NERIS_SCHEMA_ASSET_REFRESHED as NERIS_SCHEMA_ASSET_REFRESHED_ALIAS,
)


def test_fire_contract_package_exports_expected_symbols() -> None:
    readiness = NerisReadinessContract(
        incident_id="incident-1",
        ready=False,
        missing_fields=["incident_type"],
        filled_fields=["incident_number"],
        total_required=2,
        total_filled=1,
    )

    assert readiness.incident_id == "incident-1"
    assert FireIncidentType.STRUCTURE_FIRE.value == "STRUCTURE_FIRE"
    assert FireUnitStatus.AVAILABLE.value == "AVAILABLE"
    assert NerisValidationStatus.VALIDATION_PASSED.value == "VALIDATION_PASSED"


def test_fire_and_neris_events_are_registered() -> None:
    assert "fire.incident.status.updated" in FIRE_EVENTS
    assert FIRE_INCIDENT_STATUS_UPDATED in ALL_EVENTS
    assert NERIS_VALIDATION_COMPLETED in ALL_EVENTS
    assert "neris.validation.completed" in NERIS_EVENTS


def test_directive_event_aliases_are_importable_and_registered() -> None:
    assert FIRE_BENCHMARK_TIMELINE_UPDATED_ALIAS == FIRE_BENCHMARK_TIMELINE_UPDATED
    assert (
        FIRE_INVESTIGATION_READINESS_UPDATED_ALIAS
        == FIRE_INVESTIGATION_READINESS_UPDATED
    )
    assert NERIS_SCHEMA_ASSET_REFRESHED_ALIAS == NERIS_SCHEMA_ASSET_REFRESHED
    assert NERIS_NORMALIZATION_COMPLETED_ALIAS == NERIS_NORMALIZATION_COMPLETED
    assert FIRE_BENCHMARK_TIMELINE_UPDATED in FIRE_EVENTS
    assert FIRE_INVESTIGATION_READINESS_UPDATED in FIRE_EVENTS
    assert NERIS_SCHEMA_ASSET_REFRESHED in NERIS_EVENTS
    assert NERIS_NORMALIZATION_COMPLETED in NERIS_EVENTS
    # source_service is the service-registry slug, not the JWT audience. The
    # audiences "adaptix-fire" / "adaptix-neris" still exist in
    # adaptix_contracts.service_audiences; they are a separate namespace.
    assert ALL_EVENTS[FIRE_BENCHMARK_TIMELINE_UPDATED]["source_service"] == "fire"
    assert ALL_EVENTS[FIRE_INVESTIGATION_READINESS_UPDATED]["source_service"] == "fire"
    assert ALL_EVENTS[NERIS_SCHEMA_ASSET_REFRESHED]["source_service"] == "neris"
    assert ALL_EVENTS[NERIS_NORMALIZATION_COMPLETED]["source_service"] == "neris"


def test_neris_directive_models_preserve_ownership_boundaries() -> None:
    schema_asset = NerisSchemaAsset(
        asset_id="asset-1",
        asset_type="validation-schema",
        version="2026.05",
    )
    normalization_result = NerisNormalizationResult(
        incident_id="incident-1",
        normalized_payload={"incident_number": "F-1"},
    )
    validation_audit = NerisValidationAudit(
        validation_id="validation-1",
        incident_id="incident-1",
        status=NerisValidationStatus.VALIDATION_PASSED,
        handled_at="2026-05-03T00:00:00Z",
    )

    assert schema_asset.asset_type == "validation-schema"
    assert normalization_result.normalization_version == "neris-v1"
    assert validation_audit.owner_service == "adaptix-neris"
