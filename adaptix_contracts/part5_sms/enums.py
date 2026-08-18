"""Enums for Play P14 — Adaptix Part 5 Safety Management System (SMS).

These enums encode the shared vocabulary Part 5 SMS work uses across the
Adaptix platform (Adaptix-Compliance-Service is the canonical producer of the
Part 5 SMS events; see ``adaptix_contracts.part5_sms.events``).

- :class:`Part5Pillar` — the four pillars named in FAA Part 5 / AC 120-92B:
  Safety Policy, Safety Risk Management, Safety Assurance, Safety Promotion.
- :class:`HazardSeverity` — the five-level severity vocabulary from FAA Order
  8000.369C / AC 120-92B Appendix 3 (Catastrophic → Negligible).
- :class:`RiskLevel` — the composite risk classification a Risk Assessment
  produces after combining severity and likelihood on the 5x5 matrix.

Every value is stable and stored — do not rename existing members. Add new
members at the end of each enum.
"""

from __future__ import annotations

from enum import StrEnum


class Part5Pillar(StrEnum):
    """The four pillars of an FAA Part 5 Safety Management System.

    Values match the short codes required by the Play P14 task contract and
    are the persisted representation on ``SmsBinder.pillar`` and on every
    pillar-scoped event payload.
    """

    POLICY = "policy"
    SRM = "srm"
    SA = "sa"
    SP = "sp"


class HazardSeverity(StrEnum):
    """Five-level hazard severity per FAA Order 8000.369C / AC 120-92B.

    Ordering, high to low: ``CATASTROPHIC > HAZARDOUS > MAJOR > MINOR >
    NEGLIGIBLE``. Serialised as the uppercase name so the value is unambiguous
    in JSON payloads and audit records.
    """

    NEGLIGIBLE = "NEGLIGIBLE"
    MINOR = "MINOR"
    MAJOR = "MAJOR"
    HAZARDOUS = "HAZARDOUS"
    CATASTROPHIC = "CATASTROPHIC"


class RiskLevel(StrEnum):
    """Composite risk classification produced by a :class:`RiskAssessment`.

    Aligned with the FAA 5x5 severity-versus-likelihood matrix used in
    AC 120-92B Appendix 3. ``EXTREME`` is the unacceptable-region value used
    when a specific carrier's matrix escalates ``HIGH`` into a fourth,
    stop-work band.
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


__all__ = [
    "HazardSeverity",
    "Part5Pillar",
    "RiskLevel",
]
