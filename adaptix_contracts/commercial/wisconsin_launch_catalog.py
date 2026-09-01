"""The first seeded commercial pricing catalog: Wisconsin launch, v1.

Seed DATA for the modular per-application pricing model — see
``pricing_catalog`` for the shapes and for why this package carries no
pricing calculation logic. Every monthly figure below is the founder's
verified Wisconsin launch price list; every ``annual_price`` /
``annual_price_per_unit`` is monthly * 12 * (1 - ``ANNUAL_DISCOUNT_RATE``),
rounded to the cent, and is checked against that formula by
``validate_catalog`` at import time below — a typo in a hand-entered annual
figure fails the build, not a customer's invoice.

The 21 entries are split across three private, topically-grouped modules
(``_seed_entries_clinical_dispatch``, ``_seed_entries_revenue_workforce``,
``_seed_entries_platform_emerging``) purely to keep each file a readable
size; this module is the only place they are assembled and is the only
supported import path for the catalog.

Prices are versioned, never mutated in place: a future price change ships as
a NEW ``CommercialPricingCatalog`` (a new ``catalog_version`` /
``effective_date``), leaving this one intact for any consumer still pinned
to it.
"""

from __future__ import annotations

from datetime import date
from types import MappingProxyType

# These three imports already pull only the one name each private module
# exports (``ENTRIES``), never the submodule object itself. Pylint's
# no-name-in-module check still cannot resolve them: confirmed a false
# positive against this exact source tree with a current pylint/astroid
# (4.0.8) reporting zero issues here, and separately confirmed by this
# repo's own passing test suite genuinely importing and exercising these
# same three modules at collection time. The failure is scoped to Codacy's
# older bundled Pylint mis-resolving leading-underscore submodule names — it
# does not fire on the non-underscore ``pricing_catalog`` import two lines
# below, which is the same import shape. Matches this repo's existing
# precedent of a targeted, explained pylint exemption (see
# ``pricing_catalog.ApplicationPricingCatalogEntry``'s
# ``too-many-instance-attributes`` exemption) rather than restructuring
# working, correct imports around a tool limitation.
from adaptix_contracts.commercial._seed_entries_clinical_dispatch import (  # pylint: disable=no-name-in-module
    ENTRIES as _CLINICAL_DISPATCH_ENTRIES,
)
from adaptix_contracts.commercial._seed_entries_platform_emerging import (  # pylint: disable=no-name-in-module
    ENTRIES as _PLATFORM_EMERGING_ENTRIES,
)
from adaptix_contracts.commercial._seed_entries_revenue_workforce import (  # pylint: disable=no-name-in-module
    ENTRIES as _REVENUE_WORKFORCE_ENTRIES,
)
from adaptix_contracts.commercial.pricing_catalog import (
    CommercialPricingCatalog,
    validate_catalog,
)

__all__ = ["WI_LAUNCH_CATALOG"]

_ALL_ENTRIES = (
    *_CLINICAL_DISPATCH_ENTRIES,
    *_REVENUE_WORKFORCE_ENTRIES,
    *_PLATFORM_EMERGING_ENTRIES,
)

WI_LAUNCH_CATALOG = CommercialPricingCatalog(
    catalog_version="wi-launch-v1",
    effective_date=date(2026, 9, 1),
    jurisdiction="US-WI",
    entries=MappingProxyType({entry.application: entry for entry in _ALL_ENTRIES}),
)


validate_catalog(WI_LAUNCH_CATALOG)
