"""NEMSIS 3.5.1 eDisposition.16 "EMS Transport Method": the one shared code list.

Why this exists
----------------

eDisposition.16 is the one charted fact that says whether a patient was moved
by a fixed-wing aircraft, a rotor craft or a ground vehicle. An air ambulance
claim needs exactly that distinction: fixed wing bills HCPCS A0430 with A0435
mileage, rotary wing bills A0431 with A0436 mileage (42 CFR 414.610(c)(3)).

Adaptix-EPCR-Service exports the code on the billing snapshot's transport
block (``EpcrBillingTransportBlock.transport_method_code``) and
Adaptix-Billing-Service reads it there. Both sides must agree on which code
means what. A consumer that restated the list from memory would be one typo
from billing ground ambulances as aircraft (the fixed-wing and ground codes
differ in one digit), so the list is declared once, here.

Source
------

Transcribed from the official NEMSIS 3.5.1 schema, ``eDisposition_v3.xsd``,
``simpleType name="EMSTransportMethod"`` (in Adaptix-EPCR-Service at
``backend/epcr_app/nemsis_resources/official/raw/xsd_ems/eDisposition_v3.xsd``).
The values are transcribed, not reinterpreted: nine codes, each with the
label the schema documents.

What this module does not do
----------------------------

It carries no HCPCS code and no billing rule. Which claim code a transport
method leads to is Billing's decision. It also does not treat an unknown code
as anything: :func:`air_airframe_category` answers ``None`` for a code that is
not one of the two air codes, including a code this list does not hold.
"""

from __future__ import annotations

from typing import Final, Literal

#: The NEMSIS element these codes belong to.
EMS_TRANSPORT_METHOD_ELEMENT: Final = "eDisposition.16"

AIR_MEDICAL_FIXED_WING: Final = "4216001"
AIR_MEDICAL_ROTOR_CRAFT: Final = "4216003"
GROUND_AMBULANCE: Final = "4216005"
GROUND_ATV_OR_RESCUE_VEHICLE: Final = "4216007"
GROUND_BARIATRIC: Final = "4216009"
GROUND_OTHER_NOT_LISTED: Final = "4216011"
GROUND_MASS_CASUALTY_BUS_OR_VEHICLE: Final = "4216013"
GROUND_WHEELCHAIR_VAN: Final = "4216015"
WATER_BOAT: Final = "4216017"

#: Every code of ``EMSTransportMethod`` with the label the schema documents.
EMS_TRANSPORT_METHOD_LABELS: Final[dict[str, str]] = {
    AIR_MEDICAL_FIXED_WING: "Air Medical-Fixed Wing",
    AIR_MEDICAL_ROTOR_CRAFT: "Air Medical-Rotor Craft",
    GROUND_AMBULANCE: "Ground-Ambulance",
    GROUND_ATV_OR_RESCUE_VEHICLE: "Ground-ATV or Rescue Vehicle",
    GROUND_BARIATRIC: "Ground-Bariatric",
    GROUND_OTHER_NOT_LISTED: "Ground-Other Not Listed",
    GROUND_MASS_CASUALTY_BUS_OR_VEHICLE: "Ground-Mass Casualty Bus/Vehicle",
    GROUND_WHEELCHAIR_VAN: "Ground-Wheelchair Van",
    WATER_BOAT: "Water-Boat",
}

#: The two codes that mean the patient was moved by aircraft.
AIR_TRANSPORT_METHOD_CODES: Final[frozenset[str]] = frozenset(
    {AIR_MEDICAL_FIXED_WING, AIR_MEDICAL_ROTOR_CRAFT}
)

AirframeCategory = Literal["fixed_wing", "rotor_craft"]

_AIRFRAME_CATEGORY: Final[dict[str, AirframeCategory]] = {
    AIR_MEDICAL_FIXED_WING: "fixed_wing",
    AIR_MEDICAL_ROTOR_CRAFT: "rotor_craft",
}


def air_airframe_category(transport_method_code: str | None) -> AirframeCategory | None:
    """Return the airframe category an eDisposition.16 code states, if it is an air code.

    Args:
        transport_method_code: The raw eDisposition.16 value as charted, or
            ``None`` when the chart carries none. Surrounding whitespace is
            ignored; nothing else is normalised.

    Returns:
        ``"fixed_wing"`` for ``4216001``, ``"rotor_craft"`` for ``4216003``,
        and ``None`` for every other value: a ground or water code, an
        unknown code, an empty string or ``None``. A caller must never read
        ``None`` as "rotor craft" or as any other default.
    """
    if transport_method_code is None:
        return None
    return _AIRFRAME_CATEGORY.get(transport_method_code.strip())


__all__ = [
    "AIR_MEDICAL_FIXED_WING",
    "AIR_MEDICAL_ROTOR_CRAFT",
    "AIR_TRANSPORT_METHOD_CODES",
    "EMS_TRANSPORT_METHOD_ELEMENT",
    "EMS_TRANSPORT_METHOD_LABELS",
    "GROUND_AMBULANCE",
    "GROUND_ATV_OR_RESCUE_VEHICLE",
    "GROUND_BARIATRIC",
    "GROUND_MASS_CASUALTY_BUS_OR_VEHICLE",
    "GROUND_OTHER_NOT_LISTED",
    "GROUND_WHEELCHAIR_VAN",
    "WATER_BOAT",
    "AirframeCategory",
    "air_airframe_category",
]
