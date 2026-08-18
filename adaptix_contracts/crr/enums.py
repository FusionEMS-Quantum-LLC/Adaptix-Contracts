"""Community Risk Reduction (CRR) + Vision 20/20 enum definitions.

Community Risk Reduction is the Vision 20/20 model for prevention: identify the
community's risks, build a program to reduce them, deliver interventions, and
measure the outcome. This subpackage carries the shared contracts for the CRR
Service (Play P08).

Every enum here is a ``StrEnum`` so the wire format is a stable string, matching
the platform convention already used by
``adaptix_contracts.fire.models.FireIncidentType`` and
``adaptix_contracts.neris.models.NerisValidationStatus``.
"""

from __future__ import annotations

from enum import StrEnum


class InterventionType(StrEnum):
    """Category of CRR intervention delivered to a target household or group.

    The four values are the ones the task contract enumerates; they cover the
    canonical Vision 20/20 delivery modes:

    * ``SMOKE_ALARM`` — install / test / replace residential smoke alarms.
    * ``COOKING_SAFETY`` — kitchen-fire prevention (unattended cooking is the
      leading cause of US home structure fires).
    * ``HOME_VISIT`` — an in-person community risk assessment visit that may
      bundle multiple prevention topics for a single household.
    * ``COMMUNITY_ED`` — group / classroom / event-based public education.
    """

    SMOKE_ALARM = "smoke_alarm"
    COOKING_SAFETY = "cooking_safety"
    HOME_VISIT = "home_visit"
    COMMUNITY_ED = "community_ed"


class CrrOutcome(StrEnum):
    """Measured outcome of a CRR intervention or cohort.

    Outcomes are recorded against an ``OutcomeCohort`` (see ``models.py``) and
    are what feeds an ISO Community Risk Reduction credit package. The values
    are deliberately generic across intervention types so a single cohort can
    aggregate smoke-alarm installs and cooking-safety visits under the same
    outcome vocabulary.
    """

    RISK_REDUCED = "risk_reduced"
    NO_CHANGE = "no_change"
    RISK_INCREASED = "risk_increased"
    INCIDENT_PREVENTED = "incident_prevented"
    INCIDENT_OCCURRED = "incident_occurred"
    PARTICIPANT_DECLINED = "participant_declined"
    UNKNOWN = "unknown"


__all__ = [
    "CrrOutcome",
    "InterventionType",
]
