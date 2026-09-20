"""WI-LAUNCH-2026.2: Platform grants Cortex Core and supporting services.

A new catalog version. ``WI-LAUNCH-2026.1`` stays importable and unchanged
for anything already priced on it. Prices, packages, terms and application
offers are the same as that version. This version only adds the Platform
module grants the founder approved on 2026-09-19:

* ``ai`` — Cortex Core (the command bar calls ``/api/v1/ai``). Not founder-only
  ``cortex``, whose Gateway catch-all and Core toggle stay founder-scoped.
* ``forms``, ``facilities``, ``graph``, ``patient_identity`` — supporting
  services sold applications already call, granted through the same Core
  ``module_entitlements`` / Policy path as every other Platform grant.

``validate_offer_catalog`` runs at import.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from adaptix_contracts.commercial.offer_validation import validate_offer_catalog
from adaptix_contracts.commercial.wi_launch_2026_1 import WI_LAUNCH_2026_1

__all__ = ["WI_LAUNCH_2026_2"]

#: Module ids every Platform subscription on this version provisions, in
#: addition to the 2026.1 foundation set. Canonical ``module_registry`` ids
#: that already reach a live service audience.
_PLATFORM_SUPPORTING_GRANTS = frozenset(
    {
        "ai",
        "forms",
        "facilities",
        "graph",
        "patient_identity",
    }
)

WI_LAUNCH_2026_2 = replace(
    WI_LAUNCH_2026_1,
    catalog_version="WI-LAUNCH-2026.2",
    effective_date=date(2026, 9, 20),
    supersedes=WI_LAUNCH_2026_1.catalog_version,
    platform_grants_modules=(
        WI_LAUNCH_2026_1.platform_grants_modules | _PLATFORM_SUPPORTING_GRANTS
    ),
)

validate_offer_catalog(WI_LAUNCH_2026_2)
