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


__all__ = [
    "CctType",
    "CredentialLevel",
    "VentMode",
]
