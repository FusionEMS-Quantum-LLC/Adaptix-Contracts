"""Commercial vocabulary: the offer catalog and the earlier pricing catalog.

Current model (COMMERCIAL-CATALOG-002): Platform + Applications + Packages +
Usage. ``offers`` holds the shapes, ``charges``, ``usage`` and ``terms`` the
supporting vocabulary, and ``wi_launch_2026_1`` the first seeded version
(``WI-LAUNCH-2026.1``). ``offer_catalogs`` resolves any carried version and
exports the JSON form. Those catalog modules import ``application_registry``
for validation and are therefore imported explicitly, never from this package
root, because ``application_registry`` imports ``pricing_catalog``.

Superseded model (Phase B, still importable and unchanged for anything priced
on it): ``pricing_catalog`` and ``wisconsin_launch_catalog`` (``wi-launch-v1``),
independently priced applications by operational volume.
"""

from __future__ import annotations

from adaptix_contracts.commercial.charges import (
    ChargeClass,
    PassThroughChargeType,
    is_cent_amount,
)
from adaptix_contracts.commercial.offers import (
    CUSTOM_QUOTE_PRICE,
    NOT_OFFERED_PRICE,
    ApplicationOffer,
    CommercialOfferCatalog,
    CustomerSegment,
    MonthlyPrice,
    OfferAvailability,
    OfferKind,
    PackageOffer,
    PackagePrice,
    PlatformPlan,
    PriceBasis,
    QuoteSection,
    ScalingUnit,
    SegmentPrice,
    UnknownCommercialOfferError,
    fixed_price,
    starting_price,
)
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
from adaptix_contracts.commercial.terms import (
    DISCOUNTS_REQUIRING_FOUNDER_APPROVAL,
    CommercialTerms,
    CommunityEligibilityCriterion,
    CommunityEligibilityDecision,
    CommunityEligibilityOutcome,
    DiscountType,
)
from adaptix_contracts.commercial.usage import (
    USAGE_LEDGER_STATES_REQUIRING_REASON,
    BillableEncounterUsageKey,
    SameEncounterActivity,
    UsageLedgerState,
    UsageMetric,
    UsageRate,
    UsageRateBasis,
)

__all__ = [
    "ANNUAL_DISCOUNT_RATE",
    "CUSTOM_QUOTE_PRICE",
    "DISCOUNTS_REQUIRING_FOUNDER_APPROVAL",
    "NOT_OFFERED_PRICE",
    "USAGE_LEDGER_STATES_REQUIRING_REASON",
    "ApplicationDependency",
    "ApplicationOffer",
    "ApplicationPricingCatalogEntry",
    "BillableEncounterUsageKey",
    "CatalogEntryStatus",
    "ChargeClass",
    "CommercialApplicationKey",
    "CommercialOfferCatalog",
    "CommercialPricingCatalog",
    "CommercialTerms",
    "CommunityEligibilityCriterion",
    "CommunityEligibilityDecision",
    "CommunityEligibilityOutcome",
    "CustomerSegment",
    "DiscountType",
    "MonthlyPrice",
    "OfferAvailability",
    "OfferKind",
    "PackageOffer",
    "PackagePrice",
    "PassThroughChargeType",
    "PlatformPlan",
    "PriceBasis",
    "PricingBand",
    "PricingMechanic",
    "QuoteSection",
    "SameEncounterActivity",
    "ScalingUnit",
    "SegmentPrice",
    "UnitRateFormula",
    "UnknownCommercialApplicationError",
    "UnknownCommercialOfferError",
    "UsageLedgerState",
    "UsageMetric",
    "UsageRate",
    "UsageRateBasis",
    "fixed_price",
    "is_cent_amount",
    "starting_price",
    "validate_catalog",
]
