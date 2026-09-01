"""Commercial pricing / application catalog vocabulary (Phase B).

Shared shapes for the modular per-application pricing model: every
independently-usable Adaptix customer application is priced and sold
separately, by real operational volume, never by user seat count. See
``pricing_catalog`` for the types and ``wisconsin_launch_catalog`` for the
first seeded catalog version.
"""

from __future__ import annotations

from adaptix_contracts.commercial.pricing_catalog import (
    ANNUAL_DISCOUNT_RATE as ANNUAL_DISCOUNT_RATE,
    ApplicationDependency as ApplicationDependency,
    ApplicationPricingCatalogEntry as ApplicationPricingCatalogEntry,
    CatalogEntryStatus as CatalogEntryStatus,
    CommercialApplicationKey as CommercialApplicationKey,
    CommercialPricingCatalog as CommercialPricingCatalog,
    PricingBand as PricingBand,
    PricingMechanic as PricingMechanic,
    UnitRateFormula as UnitRateFormula,
    UnknownCommercialApplicationError as UnknownCommercialApplicationError,
    validate_catalog as validate_catalog,
)
