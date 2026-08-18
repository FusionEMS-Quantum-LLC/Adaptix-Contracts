"""Necessity domain enums — Play P02 pre-submit medical-necessity linter.

Vocabulary shared by ePCR (producer of the pre-submit linter run) and Billing
(consumer of predicted denials). Kept in a leaf module so nothing in
``adaptix_contracts/necessity/models.py`` or ``events.py`` needs to
cross-import within the subpackage.
"""

from __future__ import annotations

from enum import Enum


class NecessityVerdict(str, Enum):
    """Pre-submit medical-necessity linter verdict.

    The linter runs BEFORE a chart is finalized or a claim is dropped. It
    returns one of three states:

    * ``CLEAR``   — no LCD/NCD or payer-pattern findings; chart lock and claim
      submission may proceed with no additional attestation.
    * ``WARN``    — soft findings that do not block chart lock but must be
      surfaced in the reviewer UI (e.g. weak documentation for a covered
      indication, near-miss modifier).
    * ``BLOCK``   — hard findings that must block chart lock and prevent claim
      submission until resolved (e.g. missing signs/symptoms for the LCD, MAC
      denial pattern with >X% historical denial rate).

    Values are lower-case strings so they serialize stably across the
    ePCR->Billing hop and remain readable in denial-analytics dashboards.
    """

    CLEAR = "clear"
    WARN = "warn"
    BLOCK = "block"


class MacRegion(str, Enum):
    """Medicare Administrative Contractor (MAC) jurisdiction.

    Every Medicare Part B claim is adjudicated by exactly one MAC based on the
    servicing provider's state. Local Coverage Determinations (LCDs) and payer
    denial patterns are MAC-scoped — the same CPT + ICD-10 pair can be covered
    by one MAC and denied by another. The linter routes ``LcdRule`` and
    ``PayerDenialPattern`` lookups by this enum so a Novitas-region agency is
    never assessed against a Palmetto rule.

    Values follow CMS's contractor-name convention (case-sensitive as spelled
    by CMS) so mapping tables imported from CMS's public MAC directory drop in
    without a case-normalisation shim.
    """

    NOVITAS = "Novitas"
    PALMETTO = "Palmetto"
    NGS = "NGS"
    FIRST_COAST = "FirstCoast"
    WPS = "WPS"
    NORIDIAN = "Noridian"


__all__ = [
    "MacRegion",
    "NecessityVerdict",
]
