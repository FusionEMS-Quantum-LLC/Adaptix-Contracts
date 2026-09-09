"""Semantic guards for the CAD -> ePCR NEMSIS handoff contract.

This model had no test coverage at all, which is how three separate NEMSIS
mislabels survived in it: eResponse.07 was documented as "Primary Role of the
Unit" and sourced from a requested level of care, mileage was documented as
eDisposition.17 "Transport Distance", and the whole eDispatch section was
shifted by one or more positions.

These tests assert the structural separations that were violated. They are
deliberately about shape and independence rather than description text, so they
keep holding when wording is improved.
"""

from datetime import UTC, datetime

from adaptix_contracts.cad.nemsis_handoff import (
    CadDispatchContext,
    CadNemsisHandoffPayload,
)


def _payload(**overrides):
    base = {
        "handoff_id": "hndff-test",
        "cad_dispatch_id": "disp-test",
        "tenant_id": "tenant-test",
        "transport_type": "INTERFACILITY",
        "level_of_care": "ALS",
        "handoff_created_at": datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
    }
    base.update(overrides)
    return CadNemsisHandoffPayload(**base)


def test_requested_level_and_assigned_capability_are_separate_fields():
    """eResponse.07 describes the unit that responded, not what was requested.

    A CCT unit answering a BLS request must report BLS as the request and
    Critical Care Equipped as the capability. If these ever collapse back into
    one field, this fails.
    """
    payload = _payload(
        level_of_care="BLS",
        assigned_unit_transport_equipment_capability="2207019",
    )

    assert payload.level_of_care == "BLS"
    assert payload.assigned_unit_transport_equipment_capability == "2207019"


def test_assigned_capability_is_not_defaulted_from_requested_level():
    """Requesting a level must never assert a capability CAD has not observed."""
    payload = _payload(level_of_care="ALS")

    assert payload.assigned_unit_transport_equipment_capability is None


def test_unit_callsign_is_carried_separately_from_vehicle_number():
    """eResponse.14 (Call Sign) and eResponse.13 (Vehicle Number) are distinct.

    Both are Mandatory national elements. Agencies often use the same string,
    which is exactly why one must not be inferred from the other.
    """
    payload = _payload(unit_id="VEH-12", assigned_unit_callsign="MEDIC 12")

    assert payload.unit_id == "VEH-12"
    assert payload.assigned_unit_callsign == "MEDIC 12"


def test_dispatch_priority_survives_round_trip():
    """eDispatch.05 must reach ePCR; it was previously unreachable end to end."""
    payload = _payload(dispatch_priority="2305003")

    restored = CadNemsisHandoffPayload.model_validate(payload.model_dump())

    assert restored.dispatch_priority == "2305003"


def test_dispatch_context_carries_the_coded_edispatch_values():
    """CAD emits coded values; the contract must declare all of them.

    Before this, CAD emitted dispatch_reason_code, emd_performed_code,
    emd_determinant, center_id and priority_code while the contract declared
    none of them, so the coded values had no contractual home.
    """
    context = CadDispatchContext(
        call_type="CHEST_PAIN",
        dispatch_reason_code="2301013",
        cad_record_id="disp-test",
        emd_performed_code="2302001",
        emd_determinant="10-D-4",
        center_id="CENTER-1",
        priority_code="2305003",
    )

    restored = CadDispatchContext.model_validate(context.model_dump())

    assert restored.dispatch_reason_code == "2301013"
    assert restored.emd_performed_code == "2302001"
    assert restored.emd_determinant == "10-D-4"
    assert restored.center_id == "CENTER-1"
    assert restored.priority_code == "2305003"


def test_internal_call_type_token_is_kept_apart_from_the_coded_reason():
    """CHEST_PAIN is a CAD token, not an eDispatch.01 value.

    Keeping them in separate fields is what stops an internal token being
    submitted as though it were an official 2301xxx code.
    """
    context = CadDispatchContext(call_type="CHEST_PAIN", dispatch_reason_code="2301013")

    assert context.call_type == "CHEST_PAIN"
    assert context.dispatch_reason_code == "2301013"


def test_mileage_estimate_is_not_presented_as_a_nemsis_element():
    """Mileage is CAD operational context; no eDisposition element carries it."""
    payload = _payload(mileage_estimate=12.4)

    assert payload.mileage_estimate == 12.4
