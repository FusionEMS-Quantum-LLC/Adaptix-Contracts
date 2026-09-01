"""Commercial pricing / application catalog vocabulary (Phase B).

Shared shapes for the modular per-application pricing model: every
independently-usable Adaptix customer application is priced and sold
separately, by real operational volume, never by user seat count. See
``pricing_catalog`` for the types and ``wisconsin_launch_catalog`` for the
first seeded catalog version.
"""

from __future__ import annotations

from adaptix_contracts.commercial.pricing_catalog import (
    ANNUAL_DISCOUNT_RATE,
    ApplicationDependency,
    ApplicationPricingCatalogEntry,
    CatalogEntryStatus,
    CommercialApplicationKey,
    CommercialPricingCatalog,
    PricingBand,
    PricingMechanic,
    UnitRateFormula,
    UnknownCommercialApplicationError,
    validate_catalog,
)

__all__ = [
    "ANNUAL_DISCOUNT_RATE",
    "ApplicationDependency",
    "ApplicationPricingCatalogEntry",
    "CatalogEntryStatus",
    "CommercialApplicationKey",
    "CommercialPricingCatalog",
    "PricingBand",
    "PricingMechanic",
    "UnitRateFormula",
    "UnknownCommercialApplicationError",
    "validate_catalog",
]
