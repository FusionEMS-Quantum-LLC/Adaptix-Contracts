"""Critical Care Transport (CCT) enum definitions (Play P05).

Critical Care Transport covers interfacility transports that require a
crew and equipment package beyond standard ALS — ECMO, IABP, high-risk
obstetric, neonatal, adult critical care, and other specialty transports
that must satisfy CAMTS accreditation standards.

Every enum here is a ``StrEnum`` so the wire format is a stable string,
matching the platform convention already used by
``adaptix_contracts.crr.enums.InterventionType`` and
``adaptix_contracts.mih.enums.MihServiceType``.
"""

from __future__ import annotations

from enum import StrEnum


class CctType(StrEnum):
    """The specialty transport category a CCT mission is staffed/equipped for.

    Drives both the required crew credential level and the equipment
    loadout a mission must carry before dispatch.
    """

    ECMO = "ecmo"
    IABP = "iabp"
    HIGH_RISK_OB = "high_risk_ob"
    NEONATAL = "neonatal"
    ADULT_CRITICAL = "adult_critical"
    SPECIALTY = "specialty"


class VentMode(StrEnum):
    """Mechanical ventilator mode in use for a patient during CCT transport.

    Values cover the modes a CCT crew is expected to manage in transit;
    this is deliberately narrower than a full biomedical ventilator
    taxonomy because the contract only needs the modes CAMTS-level crews
    document on interfacility handoff paperwork.
    """

    AC_VC = "ac_vc"
    AC_PC = "ac_pc"
    SIMV = "simv"
    PSV = "psv"
    CPAP = "cpap"
    BIPAP = "bipap"
    HFOV = "hfov"
    APRV = "aprv"
    OTHER = "other"


class CredentialLevel(StrEnum):
    """Minimum crew credential level required/held for a CCT mission.

    Ordered from least to most specialized; ``CCT_RN`` and ``CCT_RT`` are
    the two most common CAMTS-recognized flight/critical-care crew
    credentials layered on top of a paramedic-level base crew.
    """

    PARAMEDIC = "paramedic"
    CRITICAL_CARE_PARAMEDIC = "critical_care_paramedic"
    CCT_RN = "cct_rn"
    CCT_RT = "cct_rt"
    PHYSICIAN = "physician"


class BloodProductType(StrEnum):
    """Blood-product categories tracked through CCT chain-of-custody.

    Values follow AABB / ISBT 128 labeling conventions at the category
    level; the concrete component/product code (E0139, E0141, etc.) is
    carried separately on the ``BloodProduct.product_code`` field so this
    enum stays a stable, small category set that Web/Field apps can
    render as filters.
    """

    PACKED_RBC = "packed_rbc"
    WHOLE_BLOOD = "whole_blood"
    FRESH_FROZEN_PLASMA = "fresh_frozen_plasma"
    PLATELETS = "platelets"
    CRYOPRECIPITATE = "cryoprecipitate"
    FACTOR_CONCENTRATE = "factor_concentrate"
    ALBUMIN = "albumin"
    OTHER = "other"


class AboGroup(StrEnum):
    """ABO blood group on a unit or a patient record."""

    A = "A"
    B = "B"
    AB = "AB"
    O = "O"  # noqa: E741 — canonical single-letter blood-bank code


class RhFactor(StrEnum):
    """Rh (D) factor on a unit or a patient record."""

    POSITIVE = "positive"
    NEGATIVE = "negative"


class BloodProductStatus(StrEnum):
    """Chain-of-custody status of a single blood-product unit in transit.

    A unit is ``ISSUED`` by the sending blood bank, ``ACCEPTED`` when the
    CCT crew signs custody, ``INFUSED`` at bedside, ``RETURNED`` to the
    sending or receiving blood bank unused, or ``WASTED`` when the
    cold-chain or product integrity failed and it cannot be transfused.
    """

    ISSUED = "issued"
    ACCEPTED = "accepted"
    INFUSED = "infused"
    RETURNED = "returned"
    WASTED = "wasted"


class InfusionRunStatus(StrEnum):
    """Lifecycle state of a single medication infusion during transport."""

    ORDERED = "ordered"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    DISCONTINUED = "discontinued"


__all__ = [
    "AboGroup",
    "BloodProductStatus",
    "BloodProductType",
    "CctType",
    "CredentialLevel",
    "InfusionRunStatus",
    "RhFactor",
    "VentMode",
]
