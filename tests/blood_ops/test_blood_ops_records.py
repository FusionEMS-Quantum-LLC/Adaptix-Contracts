"""Blood Ops records and events (FND-001).

Certification data only: every identifier below is a synthetic certification
value, never a real unit, patient or person.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import BaseModel, ValidationError

from adaptix_contracts.blood_ops import events as blood_events
from adaptix_contracts.blood_ops import models as blood_models
from adaptix_contracts.blood_ops.events import (
    BLOOD_OPS_EVENT_PAYLOADS,
    BLOOD_OPS_EXCURSION_STATE_CHANGED,
    BLOOD_OPS_UNIT_CUSTODY_RECORDED,
    BloodColdChainExcursionStateChangedPayload,
)
from adaptix_contracts.blood_ops.lifecycle import (
    BloodUnitLifecycleState,
    ColdChainExcursionState,
    ColdChainReadingClassification,
)
from adaptix_contracts.blood_ops.models import (
    BloodColdChainExcursion,
    BloodColdChainReading,
    BloodUnit,
    BloodUnitCustodyEvent,
)
from adaptix_contracts.cct.enums import AboGroup, BloodProductType, RhFactor
from adaptix_contracts.events.registry import ALL_EVENTS, producer_of
from adaptix_contracts.inventory_events import InventoryEventType

U = BloodUnitLifecycleState
C = ColdChainExcursionState
NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


def _unit(**overrides: object) -> BloodUnit:
    data: dict[str, object] = {
        "blood_unit_id": "bu-cert-1",
        "tenant_id": "tenant-cert-a",
        "donation_identification_number": "CERT0000000001",
        "product_type": BloodProductType.WHOLE_BLOOD,
        "abo_group": AboGroup.O,
        "rh_factor": RhFactor.POSITIVE,
        "volume_ml": 500,
        "collected_at": NOW - timedelta(days=3),
        "expires_at": NOW + timedelta(days=18),
        "issuing_facility_name": "Certification Blood Bank",
        "received_at": NOW - timedelta(days=2),
        "lifecycle_state": U.AVAILABLE,
        "cold_chain_state": C.NORMAL,
        "storage_location_id": "loc-cert-station-1",
        "version": 3,
        "created_at": NOW - timedelta(days=2),
        "updated_at": NOW,
    }
    data.update(overrides)
    return BloodUnit.model_validate(data)


def test_unit_reuses_the_cct_blood_bank_vocabulary() -> None:
    fields = BloodUnit.model_fields
    assert fields["product_type"].annotation is BloodProductType
    assert fields["abo_group"].annotation is AboGroup
    assert fields["rh_factor"].annotation is RhFactor
    for shared in (
        "isbt128_code",
        "product_code",
        "issuing_facility_name",
        "issuing_facility_id",
    ):
        assert shared in fields


@pytest.mark.parametrize("state", [U.AVAILABLE, U.ASSIGNED])
@pytest.mark.parametrize(
    "cold_chain", [C.EXCURSION_DETECTED, C.SENSOR_FAILURE, C.QUARANTINED, C.DISCARDED]
)
def test_a_usable_unit_never_has_an_open_cold_chain_problem(
    state: BloodUnitLifecycleState, cold_chain: ColdChainExcursionState
) -> None:
    extra = {"assigned_apparatus_id": "apparatus-cert-7"} if state is U.ASSIGNED else {}
    with pytest.raises(ValidationError, match="quarantine it first"):
        _unit(lifecycle_state=state, cold_chain_state=cold_chain, **extra)


def test_a_released_unit_is_usable_again() -> None:
    assert _unit(cold_chain_state=C.RELEASED).cold_chain_state is C.RELEASED


def test_a_transfused_unit_can_carry_a_later_found_excursion() -> None:
    unit = _unit(
        lifecycle_state=U.TRANSFUSED,
        transfused_chart_id="chart-cert-1",
        cold_chain_state=C.EXCURSION_DETECTED,
    )
    assert unit.cold_chain_state is C.EXCURSION_DETECTED


def test_assigned_names_its_apparatus_and_only_assigned_does() -> None:
    with pytest.raises(ValidationError, match="assigned_apparatus_id"):
        _unit(lifecycle_state=U.ASSIGNED)
    with pytest.raises(ValidationError, match="assigned_apparatus_id"):
        _unit(assigned_apparatus_id="apparatus-cert-7")
    assert (
        _unit(
            lifecycle_state=U.ASSIGNED, assigned_apparatus_id="apparatus-cert-7"
        ).assigned_apparatus_id
        == "apparatus-cert-7"
    )


def test_transfused_names_its_chart_and_only_transfused_does() -> None:
    with pytest.raises(ValidationError, match="transfused_chart_id"):
        _unit(lifecycle_state=U.TRANSFUSED)
    with pytest.raises(ValidationError, match="transfused_chart_id"):
        _unit(transfused_chart_id="chart-cert-1")


def test_unit_label_dates_and_strict_scalars() -> None:
    with pytest.raises(ValidationError, match="expires_at must be after collected_at"):
        _unit(expires_at=NOW - timedelta(days=4))
    with pytest.raises(ValidationError):
        _unit(version="3")
    with pytest.raises(ValidationError):
        _unit(volume_ml="500")
    with pytest.raises(ValidationError):
        _unit(volume_ml=float("inf"))
    with pytest.raises(ValidationError, match="timezone"):
        _unit(received_at=datetime(2026, 9, 22, 8, 0))


def test_unit_refuses_patient_demographics() -> None:
    with pytest.raises(ValidationError, match="extra"):
        _unit(patient_name="Certification Patient")


def _custody(**overrides: object) -> BloodUnitCustodyEvent:
    data: dict[str, object] = {
        "custody_event_id": "ce-1",
        "tenant_id": "tenant-cert-a",
        "blood_unit_id": "bu-cert-1",
        "from_state": U.AVAILABLE,
        "to_state": U.ASSIGNED,
        "unit_version": 4,
        "occurred_at": NOW,
        "recorded_at": NOW,
        "actor_user_id": "user-cert-medic-1",
        "from_location_id": "loc-cert-station-1",
        "to_apparatus_id": "apparatus-cert-7",
        "correlation_id": "corr-1",
        "idempotency_key": "ce-1",
    }
    data.update(overrides)
    return BloodUnitCustodyEvent.model_validate(data)


def test_custody_event_refuses_a_forbidden_transition() -> None:
    with pytest.raises(
        ValidationError, match="cannot move from DESTROYED to AVAILABLE"
    ):
        _custody(from_state=U.DESTROYED, to_state=U.AVAILABLE)


def test_receipt_is_the_only_event_without_a_from_state() -> None:
    receipt = _custody(
        from_state=None, to_state=U.RECEIVED, unit_version=1, to_apparatus_id=None
    )
    assert receipt.from_state is None
    with pytest.raises(ValidationError, match="unit_version is 1 exactly"):
        _custody(from_state=None, to_state=U.RECEIVED, unit_version=2)
    with pytest.raises(ValidationError, match="unit_version is 1 exactly"):
        _custody(unit_version=1)


def test_transfusion_names_the_chart_and_a_second_person() -> None:
    base = {"from_state": U.ASSIGNED, "to_state": U.TRANSFUSED, "to_apparatus_id": None}
    with pytest.raises(ValidationError, match="names the chart_id"):
        _custody(**base, witness_user_id="user-cert-medic-2")
    with pytest.raises(ValidationError, match="requires a witness_user_id"):
        _custody(**base, chart_id="chart-cert-1")
    with pytest.raises(ValidationError, match="second person"):
        _custody(**base, chart_id="chart-cert-1", witness_user_id="user-cert-medic-1")
    transfused = _custody(
        **base, chart_id="chart-cert-1", witness_user_id="user-cert-medic-2"
    )
    assert transfused.witness_user_id == "user-cert-medic-2"


def test_assignment_return_quarantine_and_destruction_carry_their_evidence() -> None:
    with pytest.raises(ValidationError, match="to_apparatus_id"):
        _custody(to_apparatus_id=None)
    with pytest.raises(ValidationError, match="to_facility_id"):
        _custody(to_state=U.RETURNED, to_apparatus_id=None)
    for target in (U.QUARANTINED, U.DESTROYED):
        with pytest.raises(ValidationError, match="states its reason"):
            _custody(to_state=target, to_apparatus_id=None)
    assert (
        _custody(
            to_state=U.QUARANTINED,
            to_apparatus_id=None,
            reason="cold-chain review",
            excursion_id="exc-1",
        ).excursion_id
        == "exc-1"
    )


def test_custody_event_identifies_people_by_user_id_only() -> None:
    with pytest.raises(ValidationError, match="extra"):
        _custody(witness_name="Certification Witness")


def _reading(**overrides: object) -> BloodColdChainReading:
    data: dict[str, object] = {
        "reading_id": "rd-1",
        "tenant_id": "tenant-cert-a",
        "storage_location_id": "loc-cert-station-1",
        "sensor_id": "sensor-cert-1",
        "storage_profile_id": "profile-cert-whole-blood",
        "classification": ColdChainReadingClassification.IN_RANGE,
        "temperature_c": 4.2,
        "recorded_at": NOW,
        "idempotency_key": "sensor-cert-1:2026-09-24T12:00:00Z",
    }
    data.update(overrides)
    return BloodColdChainReading.model_validate(data)


def test_a_sensor_failure_reading_has_no_temperature() -> None:
    failed = _reading(
        classification=ColdChainReadingClassification.SENSOR_FAILURE, temperature_c=None
    )
    assert failed.temperature_c is None
    with pytest.raises(
        ValidationError, match="SENSOR_FAILURE reading has no temperature_c"
    ):
        _reading(classification=ColdChainReadingClassification.SENSOR_FAILURE)


@pytest.mark.parametrize(
    "classification",
    [
        ColdChainReadingClassification.IN_RANGE,
        ColdChainReadingClassification.OUT_OF_RANGE,
    ],
)
def test_a_measured_reading_carries_its_temperature(
    classification: ColdChainReadingClassification,
) -> None:
    with pytest.raises(ValidationError, match="carries temperature_c"):
        _reading(classification=classification, temperature_c=None)


def test_a_manual_reading_names_who_took_it_and_cannot_be_a_sensor_failure() -> None:
    with pytest.raises(ValidationError, match="recorded_by_user_id"):
        _reading(sensor_id=None)
    with pytest.raises(ValidationError, match="cannot be a SENSOR_FAILURE"):
        _reading(
            sensor_id=None,
            recorded_by_user_id="user-cert-medic-1",
            classification=ColdChainReadingClassification.SENSOR_FAILURE,
            temperature_c=None,
        )
    assert (
        _reading(sensor_id=None, recorded_by_user_id="user-cert-medic-1").sensor_id
        is None
    )


def test_reading_temperature_is_strict_and_finite() -> None:
    with pytest.raises(ValidationError):
        _reading(temperature_c="4.2")
    with pytest.raises(ValidationError):
        _reading(temperature_c=True)
    with pytest.raises(ValidationError):
        _reading(temperature_c=float("nan"))
    assert _reading(temperature_c=4).temperature_c == 4.0


def _is_threshold_name(name: str) -> bool:
    lowered = name.lower()
    return any(
        token in lowered
        for token in (
            "threshold",
            "min_c",
            "max_c",
            "min_temp",
            "max_temp",
            "band",
            "limit",
        )
    )


def test_no_blood_ops_contract_carries_a_temperature_threshold() -> None:
    for module in (blood_models, blood_events):
        for _, model in inspect.getmembers(module, inspect.isclass):
            if issubclass(model, BaseModel) and model.__module__ == module.__name__:
                offenders = [
                    name for name in model.model_fields if _is_threshold_name(name)
                ]
                assert not offenders, (
                    f"{model.__name__} carries threshold fields {offenders}"
                )
        numeric_constants = {
            name
            for name, value in vars(module).items()
            if name.isupper() and isinstance(value, float)
        }
        assert not numeric_constants, f"{module.__name__} defines {numeric_constants}"


def _episode(**overrides: object) -> BloodColdChainExcursion:
    data: dict[str, object] = {
        "excursion_id": "exc-1",
        "tenant_id": "tenant-cert-a",
        "storage_location_id": "loc-cert-station-1",
        "affected_blood_unit_ids": ("bu-cert-1", "bu-cert-2"),
        "state": C.EXCURSION_DETECTED,
        "detection_reading_id": "rd-9",
        "detected_at": NOW,
        "version": 1,
        "created_at": NOW,
        "updated_at": NOW,
    }
    data.update(overrides)
    return BloodColdChainExcursion.model_validate(data)


def test_an_episode_is_never_normal_and_never_repeats_a_unit() -> None:
    with pytest.raises(ValidationError, match="never NORMAL"):
        _episode(state=C.NORMAL)
    with pytest.raises(ValidationError, match="must not repeat a unit"):
        _episode(affected_blood_unit_ids=("bu-cert-1", "bu-cert-1"))


@pytest.mark.parametrize("state", [C.RELEASED, C.DISCARDED])
def test_an_episode_ends_only_by_a_review(state: ColdChainExcursionState) -> None:
    with pytest.raises(ValidationError, match="reviewed_by_user_id and reviewed_at"):
        _episode(state=state)
    reviewed = _episode(
        state=state,
        reviewed_by_user_id="user-cert-medical-director",
        reviewed_at=NOW + timedelta(hours=1),
    )
    assert reviewed.reviewed_by_user_id == "user-cert-medical-director"


def test_an_open_episode_has_no_review_and_a_discard_names_units() -> None:
    with pytest.raises(ValidationError, match="reviewed_by_user_id and reviewed_at"):
        _episode(reviewed_by_user_id="user-cert-md", reviewed_at=NOW)
    with pytest.raises(ValidationError, match="names the units it discards"):
        _episode(
            state=C.DISCARDED,
            affected_blood_unit_ids=(),
            reviewed_by_user_id="user-cert-md",
            reviewed_at=NOW,
        )
    with pytest.raises(ValidationError, match="reviewed_at precedes detected_at"):
        _episode(
            state=C.RELEASED,
            reviewed_by_user_id="user-cert-md",
            reviewed_at=NOW - timedelta(minutes=1),
        )


def _episode_change(**overrides: object) -> BloodColdChainExcursionStateChangedPayload:
    data: dict[str, object] = {
        "tenant_id": "tenant-cert-a",
        "excursion_id": "exc-1",
        "storage_location_id": "loc-cert-station-1",
        "affected_blood_unit_ids": ("bu-cert-1",),
        "from_state": None,
        "to_state": C.SENSOR_FAILURE,
        "detection_reading_id": "rd-9",
        "excursion_version": 1,
        "occurred_at": NOW,
        "correlation_id": "corr-1",
        "idempotency_key": "exc-1:v1",
    }
    data.update(overrides)
    return BloodColdChainExcursionStateChangedPayload.model_validate(data)


def test_an_episode_opens_by_a_detection_at_version_one() -> None:
    assert _episode_change().to_state is C.SENSOR_FAILURE
    with pytest.raises(
        ValidationError, match="opens as EXCURSION_DETECTED or SENSOR_FAILURE"
    ):
        _episode_change(to_state=C.QUARANTINED)
    with pytest.raises(ValidationError, match="excursion_version 1"):
        _episode_change(excursion_version=2)
    with pytest.raises(ValidationError, match="names detection_reading_id"):
        _episode_change(detection_reading_id=None)


def test_a_later_episode_change_follows_the_state_machine() -> None:
    later = {"from_state": C.EXCURSION_DETECTED, "excursion_version": 2}
    assert _episode_change(**later, to_state=C.QUARANTINED).to_state is C.QUARANTINED
    with pytest.raises(
        ValidationError, match="cannot move from EXCURSION_DETECTED to RELEASED"
    ):
        _episode_change(**later, to_state=C.RELEASED, actor_user_id="user-cert-md")
    with pytest.raises(ValidationError, match="never NORMAL"):
        _episode_change(
            from_state=C.NORMAL, to_state=C.SENSOR_FAILURE, excursion_version=2
        )
    with pytest.raises(ValidationError, match="excursion_version >= 2"):
        _episode_change(
            from_state=C.QUARANTINED, to_state=C.RELEASED, actor_user_id="u"
        )


@pytest.mark.parametrize("target", [C.RELEASED, C.DISCARDED])
def test_release_and_discard_are_a_persons_decision(
    target: ColdChainExcursionState,
) -> None:
    change = {"from_state": C.QUARANTINED, "to_state": target, "excursion_version": 3}
    with pytest.raises(ValidationError, match="person's decision"):
        _episode_change(**change)
    assert (
        _episode_change(**change, actor_user_id="user-cert-md").actor_user_id
        == "user-cert-md"
    )


def test_blood_ops_events_are_registered_to_inventory() -> None:
    for event_type in (
        BLOOD_OPS_UNIT_CUSTODY_RECORDED,
        BLOOD_OPS_EXCURSION_STATE_CHANGED,
    ):
        assert ALL_EVENTS[event_type] == {
            "version": "1.0",
            "source_service": "inventory",
        }
        assert producer_of(event_type).name == "Adaptix-Inventory-Service"
    assert BLOOD_OPS_EVENT_PAYLOADS == {
        "inventory.blood_unit.custody_recorded": BloodUnitCustodyEvent,
        "inventory.blood_excursion.state_changed": BloodColdChainExcursionStateChangedPayload,
    }
    assert (
        BLOOD_OPS_UNIT_CUSTODY_RECORDED
        == InventoryEventType.BLOOD_UNIT_CUSTODY_RECORDED
    )
    assert (
        BLOOD_OPS_EXCURSION_STATE_CHANGED
        == InventoryEventType.BLOOD_EXCURSION_STATE_CHANGED
    )


def test_blood_ops_package_root_reexports_nothing() -> None:
    import adaptix_contracts.blood_ops as package

    public = [name for name in vars(package) if not name.startswith("_")]
    assert sorted(public) == ["events", "lifecycle", "models"]
