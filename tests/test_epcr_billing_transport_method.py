"""The billing snapshot carries NEMSIS eDisposition.16, and its codes have one home.

Air vendor gap register 2026-10-03, defect 12. A fixed-wing air ambulance
transport bills HCPCS A0430/A0435 and a rotary-wing one A0431/A0436. The only
charted fact that separates them is eDisposition.16 "EMS Transport Method".
Adaptix-EPCR-Service exports it as ``transport_method_code`` (#924), but
``EpcrBillingTransportBlock`` had no such field, so pydantic's default
``extra="ignore"`` dropped the key and Billing never saw it. It could then
code an air transport only from free text.

These tests pin two things:

* the block types and round-trips ``transport_method_code``, and a legacy
  event without it still validates;
* ``adaptix_contracts.epcr.transport_method`` holds exactly the nine codes of
  the NEMSIS 3.5.1 ``EMSTransportMethod`` list, with the schema's labels, and
  answers "fixed wing" or "rotor craft" for the two air codes only.
"""

from __future__ import annotations

import pytest

from adaptix_contracts.epcr import transport_method as tm
from adaptix_contracts.schemas import EpcrBillingTransportBlock, EpcrChartFinalizedEvent


def _event_with_transport(transport: dict[str, str | None]) -> dict[str, object]:
    return {
        "chart_id": "18ab537c",
        "tenant_id": "0149677b",
        "call_number": "E2E-EPCR-AIR-001",
        "finalized_at": "2026-10-03T00:00:00+00:00",
        "billing_snapshot": {"transport": transport},
    }


# ---------------------------------------------------------------------------
# The block carries the field
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "code",
    [tm.AIR_MEDICAL_FIXED_WING, tm.AIR_MEDICAL_ROTOR_CRAFT, tm.GROUND_AMBULANCE],
)
def test_transport_method_code_is_no_longer_dropped(code: str) -> None:
    """The producer's key reaches the consumer, verbatim."""
    event = EpcrChartFinalizedEvent.model_validate(
        _event_with_transport(
            {"destination_name": "General Hospital", "transport_method_code": code}
        )
    )
    snapshot = event.billing_snapshot
    assert snapshot is not None
    assert snapshot.transport is not None
    assert snapshot.transport.transport_method_code == code
    # It survives serialization too, so a relayed event keeps it.
    dumped = event.model_dump(mode="json")
    assert dumped["billing_snapshot"]["transport"]["transport_method_code"] == code


def test_an_event_without_the_code_still_validates_and_reads_none() -> None:
    """A chart with no eDisposition.16 is absence, not a default."""
    event = EpcrChartFinalizedEvent.model_validate(
        _event_with_transport({"destination_name": "General Hospital"})
    )
    assert event.billing_snapshot is not None
    assert event.billing_snapshot.transport is not None
    assert event.billing_snapshot.transport.transport_method_code is None


def test_the_code_is_a_raw_string_and_is_not_normalised() -> None:
    """Like every other value in the block: passed through, never coerced."""
    block = EpcrBillingTransportBlock(transport_method_code="4216001")
    assert block.transport_method_code == "4216001"
    assert isinstance(block.transport_method_code, str)


# ---------------------------------------------------------------------------
# The one shared code list
# ---------------------------------------------------------------------------


def test_the_list_is_the_nemsis_3_5_1_ems_transport_method_enumeration() -> None:
    """Transcribed from eDisposition_v3.xsd, simpleType EMSTransportMethod."""
    assert tm.EMS_TRANSPORT_METHOD_ELEMENT == "eDisposition.16"
    assert tm.EMS_TRANSPORT_METHOD_LABELS == {
        "4216001": "Air Medical-Fixed Wing",
        "4216003": "Air Medical-Rotor Craft",
        "4216005": "Ground-Ambulance",
        "4216007": "Ground-ATV or Rescue Vehicle",
        "4216009": "Ground-Bariatric",
        "4216011": "Ground-Other Not Listed",
        "4216013": "Ground-Mass Casualty Bus/Vehicle",
        "4216015": "Ground-Wheelchair Van",
        "4216017": "Water-Boat",
    }


def test_the_named_constants_match_their_labels() -> None:
    assert (
        tm.EMS_TRANSPORT_METHOD_LABELS[tm.AIR_MEDICAL_FIXED_WING]
        == "Air Medical-Fixed Wing"
    )
    assert (
        tm.EMS_TRANSPORT_METHOD_LABELS[tm.AIR_MEDICAL_ROTOR_CRAFT]
        == "Air Medical-Rotor Craft"
    )
    assert tm.EMS_TRANSPORT_METHOD_LABELS[tm.GROUND_AMBULANCE] == "Ground-Ambulance"
    assert tm.EMS_TRANSPORT_METHOD_LABELS[tm.WATER_BOAT] == "Water-Boat"


def test_only_the_two_air_codes_are_air() -> None:
    assert tm.AIR_TRANSPORT_METHOD_CODES == frozenset({"4216001", "4216003"})
    air_labelled = {
        code
        for code, label in tm.EMS_TRANSPORT_METHOD_LABELS.items()
        if label.startswith("Air ")
    }
    assert air_labelled == tm.AIR_TRANSPORT_METHOD_CODES


def test_air_airframe_category_separates_fixed_wing_from_rotor_craft() -> None:
    assert tm.air_airframe_category("4216001") == "fixed_wing"
    assert tm.air_airframe_category("4216003") == "rotor_craft"
    # Surrounding whitespace is the only normalisation.
    assert tm.air_airframe_category(" 4216003 ") == "rotor_craft"


@pytest.mark.parametrize(
    "code",
    [
        # Every ground and water code. 4216005 and 4216007 differ from the air
        # codes in one digit, which is exactly the slip this list exists to stop.
        "4216005",
        "4216007",
        "4216009",
        "4216011",
        "4216013",
        "4216015",
        "4216017",
        # Not in the list at all.
        "4216019",
        "4216002",
        "HEMS",
        "",
        "   ",
        None,
    ],
)
def test_air_airframe_category_is_none_for_everything_else(code: str | None) -> None:
    """Never a default: an unknown or ground code is not "rotor craft"."""
    assert tm.air_airframe_category(code) is None
