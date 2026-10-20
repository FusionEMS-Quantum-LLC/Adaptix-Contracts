"""NEMSIS 3.5.1 eDispatch.05 "Dispatch Priority (Patient Acuity)": the one shared code list.

Why this exists
----------------

Medicare decides whether an ambulance response was an emergency by the call as
it was dispatched: "the nature of the call at the time of dispatch is the
determining factor" (Medicare Benefit Policy Manual, Chapter 10, 30.1.1,
"Emergency Response"). eDispatch.05 is the charted fact that records that
dispatch triage. Owner decision T1 (2026-10-05) makes it the structured source
Billing uses for the emergency indicator (Adaptix-Billing-Service #1620).

Adaptix-EPCR-Service carries the chart's ``ChartDispatch.dispatch_priority_code``
on the billing snapshot's transport block
(``EpcrBillingTransportBlock.dispatch_priority_code``) and Adaptix-Billing-Service
reads it there. Both sides, and Adaptix-Terminology-Service's autocoder (#226),
must agree on which code is an emergency dispatch, so the list is declared once,
here.

Source
------

Transcribed from the official NEMSIS 3.5.1 schema, ``eDispatch_v3.xsd``,
``simpleType name="DispatchPriority"`` (in Adaptix-EPCR-Service at
``backend/epcr_app/nemsis_resources/official/raw/xsd_ems/eDispatch_v3.xsd``):
four codes, each with the label the schema documents. Which two count as an
emergency dispatch follows Terminology #226: Critical and Emergent are, Lower
Acuity and Non-Acute are not.

What this module does not do
----------------------------

It never selects a service level. A dispatch priority says whether the response
was emergent, not whether the care was BLS or ALS: a high priority cannot turn
a BLS service into ALS1. It also does not treat an unknown code as anything:
:func:`is_emergency_dispatch` answers ``None`` for a code this list does not
hold.
"""

from __future__ import annotations

from typing import Final

#: The NEMSIS element these codes belong to.
DISPATCH_PRIORITY_ELEMENT: Final = "eDispatch.05"

CRITICAL: Final = "2305001"
EMERGENT: Final = "2305003"
LOWER_ACUITY: Final = "2305005"
NON_ACUTE: Final = "2305007"

#: Every code of ``DispatchPriority`` with the label the schema documents.
DISPATCH_PRIORITY_LABELS: Final[dict[str, str]] = {
    CRITICAL: "Critical",
    EMERGENT: "Emergent",
    LOWER_ACUITY: "Lower Acuity",
    NON_ACUTE: "Non-Acute [e.g., Scheduled Transfer or Standby]",
}

#: The two codes that record an emergency dispatch.
EMERGENCY_DISPATCH_PRIORITY_CODES: Final[frozenset[str]] = frozenset(
    {CRITICAL, EMERGENT}
)

#: The two codes that record a non-emergency dispatch.
NON_EMERGENCY_DISPATCH_PRIORITY_CODES: Final[frozenset[str]] = frozenset(
    {LOWER_ACUITY, NON_ACUTE}
)


def is_emergency_dispatch(dispatch_priority_code: str | None) -> bool | None:
    """Return whether an eDispatch.05 code records an emergency dispatch.

    Args:
        dispatch_priority_code: The raw eDispatch.05 value as charted, or
            ``None`` when the chart carries none. Surrounding whitespace is
            ignored; nothing else is normalised.

    Returns:
        ``True`` for Critical or Emergent, ``False`` for Lower Acuity or
        Non-Acute, and ``None`` for every other value: an unknown code, an
        empty string or ``None``. A caller must never read ``None`` as either
        answer.
    """
    if dispatch_priority_code is None:
        return None
    code = dispatch_priority_code.strip()
    if code in EMERGENCY_DISPATCH_PRIORITY_CODES:
        return True
    if code in NON_EMERGENCY_DISPATCH_PRIORITY_CODES:
        return False
    return None


__all__ = [
    "CRITICAL",
    "DISPATCH_PRIORITY_ELEMENT",
    "DISPATCH_PRIORITY_LABELS",
    "EMERGENCY_DISPATCH_PRIORITY_CODES",
    "EMERGENT",
    "LOWER_ACUITY",
    "NON_ACUTE",
    "NON_EMERGENCY_DISPATCH_PRIORITY_CODES",
    "is_emergency_dispatch",
]
