"""NFPA 1620 Pre-Incident Planning — Enumerations.

Play P07. Enums are shared across ``models.py`` and ``events.py`` so
occupancy classification, hazard class, and Knox Box status strings never
drift between the models a service publishes and the events consumers
read.
"""

from __future__ import annotations

from enum import StrEnum


class OccupancyType(StrEnum):
    """NFPA 1620 occupancy classification for a pre-incident planning target.

    Mirrors the broad occupancy groupings NFPA 1620 uses to scope the
    depth and content of a pre-incident plan (staffing, water supply,
    special hazards) rather than the full NFPA 101/5000 occupancy
    taxonomy, so a plan can be classified without a second lookup table.
    """

    ASSEMBLY = "assembly"
    BUSINESS = "business"
    EDUCATIONAL = "educational"
    FACTORY_INDUSTRIAL = "factory_industrial"
    HAZARDOUS = "hazardous"
    HEALTHCARE = "healthcare"
    AMBULATORY_HEALTHCARE = "ambulatory_healthcare"
    DETENTION_CORRECTIONAL = "detention_correctional"
    MERCANTILE = "mercantile"
    RESIDENTIAL = "residential"
    RESIDENTIAL_BOARD_AND_CARE = "residential_board_and_care"
    STORAGE = "storage"
    UTILITY_MISCELLANEOUS = "utility_miscellaneous"
    HIGH_RISE = "high_rise"
    MIXED_USE = "mixed_use"
    OTHER = "other"


class HazardClass(StrEnum):
    """Classification of a hazard recorded against a preplan.

    Aligned to the hazard categories NFPA 1620 directs pre-incident plans
    to capture (process hazards, storage hazards, life-safety hazards,
    and utility hazards) plus the DOT/NFPA 704 hazard classes most
    commonly cross-referenced on a preplan's hazard inventory.
    """

    FLAMMABLE_LIQUID = "flammable_liquid"
    FLAMMABLE_GAS = "flammable_gas"
    COMBUSTIBLE_DUST = "combustible_dust"
    CORROSIVE = "corrosive"
    TOXIC = "toxic"
    OXIDIZER = "oxidizer"
    REACTIVE_UNSTABLE = "reactive_unstable"
    RADIOACTIVE = "radioactive"
    BIOLOGICAL = "biological"
    EXPLOSIVE = "explosive"
    CRYOGENIC = "cryogenic"
    HIGH_VOLTAGE_ELECTRICAL = "high_voltage_electrical"
    CONFINED_SPACE = "confined_space"
    STRUCTURAL_COLLAPSE_RISK = "structural_collapse_risk"
    LIFE_SAFETY_EGRESS = "life_safety_egress"
    WATER_SUPPLY_DEFICIENCY = "water_supply_deficiency"
    ROOFTOP_SOLAR = "rooftop_solar"
    LITHIUM_BATTERY_STORAGE = "lithium_battery_storage"
    OTHER = "other"


class KnoxKeyStatus(StrEnum):
    """Lifecycle status of a Knox Box / rapid-entry key device on a preplan.

    ``INSTALLED`` is the steady state a plan should be in for a target
    with a Knox Box; ``MISSING``, ``INOPERABLE`` and ``LOCKED_OUT``
    surface a gap that should block a plan from being marked
    ``ready_for_response`` until corrected.
    """

    NOT_APPLICABLE = "not_applicable"
    INSTALLED = "installed"
    PENDING_INSTALLATION = "pending_installation"
    MISSING = "missing"
    INOPERABLE = "inoperable"
    LOCKED_OUT = "locked_out"
    REMOVED = "removed"


__all__ = [
    "HazardClass",
    "KnoxKeyStatus",
    "OccupancyType",
]
