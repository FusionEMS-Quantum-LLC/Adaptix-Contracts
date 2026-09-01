"""Wisconsin launch seed entries: platform and emerging applications.

Private to ``wisconsin_launch_catalog.py`` — split out purely to keep each
seed file to a readable, topically-coherent size; see that module for the
assembled catalog. Cortex, Communications, QA/Clinical Review, Compliance,
Analytics/Intelligence, Community Paramedicine, Patient Payments,
Third-Party Billing.
"""

from __future__ import annotations

from decimal import Decimal

from adaptix_contracts.commercial._seed_band_builders import (
    custom_quote_band,
    per_unit_band,
)
from adaptix_contracts.commercial.pricing_catalog import (
    ApplicationPricingCatalogEntry,
    CatalogEntryStatus,
    CommercialApplicationKey,
    PricingMechanic,
)

__all__ = ["ENTRIES"]

ENTRIES: tuple[ApplicationPricingCatalogEntry, ...] = (
    ApplicationPricingCatalogEntry(
        application=CommercialApplicationKey.CORTEX,
        display_name="Cortex",
        mechanic=PricingMechanic.STARTING_PRICE_BANDS_TBD,
        volume_dimension=(
            "not yet defined -- candidate tiers only, pending real "
            "provider-cost measurement"
        ),
        status=CatalogEntryStatus.CANDIDATE_NOT_APPROVED_FOR_LAUNCH,
        module_canonical_id="cortex",
        starting_monthly_prices=(
            Decimal("1995"),
            Decimal("3995"),
            Decimal("7500"),
        ),
        notes=(
            "NOT approved for public launch. Candidate figures only, pending "
            "real AI-provider-cost measurement. A fourth open-ended 'custom' "
            "tier is expected at launch (matching every other application "
            "below) but no numeric threshold was specified for it -- none is "
            "fabricated here. Do not sell against these numbers."
        ),
    ),
    ApplicationPricingCatalogEntry(
        application=CommercialApplicationKey.COMMUNICATIONS,
        display_name="Communications",
        mechanic=PricingMechanic.BASE_PLUS_METERED_USAGE,
        volume_dimension="platform base plus metered usage (rate card pending)",
        status=CatalogEntryStatus.USAGE_RATE_CARD_PENDING,
        module_canonical_id="communications",
        base_fee_monthly=Decimal("595"),
        notes=(
            "Platform base fee only. Per-unit usage rate card (minutes, "
            "messages, etc.) is not yet built; no metered rate is published. "
            "Do not compute a usage-based price from this entry until a rate "
            "card is added in a later catalog version."
        ),
    ),
    ApplicationPricingCatalogEntry(
        application=CommercialApplicationKey.QA_CLINICAL_REVIEW,
        display_name="QA / Clinical Review",
        mechanic=PricingMechanic.STARTING_PRICE_BANDS_TBD,
        volume_dimension="not yet defined -- volume bands TBD",
        status=CatalogEntryStatus.STARTING_PRICE_ONLY_BANDS_TBD,
        starting_monthly_prices=(Decimal("995"),),
        notes=(
            "Single starting price only; the volume dimension and banded "
            "thresholds are not yet defined. Not registered in "
            "module_registry.py -- this is a genuinely new application with "
            "no existing canonical module id; entitlement wiring is separate, "
            "later work."
        ),
    ),
    ApplicationPricingCatalogEntry(
        application=CommercialApplicationKey.COMPLIANCE,
        display_name="Compliance",
        mechanic=PricingMechanic.STARTING_PRICE_BANDS_TBD,
        volume_dimension="not yet defined -- volume bands TBD",
        status=CatalogEntryStatus.STARTING_PRICE_ONLY_BANDS_TBD,
        module_canonical_id="compliance",
        starting_monthly_prices=(Decimal("795"),),
        notes=(
            "Single starting price only; volume bands TBD. module_registry.py "
            "already registers 'compliance' (audience adaptix-compliance) but "
            "purchasable=False today -- flipping that flag, if desired, is a "
            "module_registry.py change left to later, separate work."
        ),
    ),
    ApplicationPricingCatalogEntry(
        application=CommercialApplicationKey.ANALYTICS_INTELLIGENCE,
        display_name="Analytics / Intelligence",
        mechanic=PricingMechanic.STARTING_PRICE_BANDS_TBD,
        volume_dimension="not yet defined -- volume bands TBD",
        status=CatalogEntryStatus.STARTING_PRICE_ONLY_BANDS_TBD,
        module_canonical_id="analytics",
        starting_monthly_prices=(Decimal("995"),),
        notes=(
            "Single starting price only; volume bands TBD. Reuses "
            "module_registry.py canonical id 'analytics' (audience "
            "adaptix-analytics). module_registry.py separately registers "
            "'intelligence' (Cortex Intelligence, audience adaptix-core) and "
            "'ai' (Cortex AI Runtime) -- those are NOT assumed to be the same "
            "product as this entry. If the founder intends 'Analytics/"
            "Intelligence' pricing to gate the Cortex Intelligence surface "
            "instead of (or in addition to) the Analytics service, that "
            "mapping needs explicit founder confirmation before "
            "Billing-Service wires entitlement -- flagged, not resolved, by "
            "this change."
        ),
    ),
    ApplicationPricingCatalogEntry(
        application=CommercialApplicationKey.COMMUNITY_PARAMEDICINE,
        display_name="Community Paramedicine",
        mechanic=PricingMechanic.STARTING_PRICE_BANDS_TBD,
        volume_dimension="not yet defined -- volume bands TBD",
        status=CatalogEntryStatus.STARTING_PRICE_ONLY_BANDS_TBD,
        starting_monthly_prices=(Decimal("995"),),
        notes=(
            "Single starting price only; volume bands TBD. The entitlement this "
            "application confers is module_registry canonical id "
            "mih_community_paramedicine (audience adaptix-mih), the same "
            "clinical domain as adaptix_contracts/mih/. The catalog key stays "
            "community_paramedicine: renaming a sold key is a contract change "
            "for every consumer, so the mapping is documented here rather than "
            "made by equality."
        ),
    ),
    ApplicationPricingCatalogEntry(
        application=CommercialApplicationKey.PATIENT_PAYMENTS,
        display_name="Patient Payments",
        mechanic=PricingMechanic.SOFTWARE_FEE_PLUS_PASSTHROUGH,
        volume_dimension="software fee plus pass-through processing cost",
        status=CatalogEntryStatus.PASSTHROUGH_COST_NOT_MODELED,
        base_fee_monthly=Decimal("495"),
        notes=(
            "Software fee only; real payment-processing pass-through costs "
            "are not modeled as a price band and vary by processor and "
            "transaction mix. Not registered in module_registry.py as its own "
            "module id."
        ),
    ),
    ApplicationPricingCatalogEntry(
        application=CommercialApplicationKey.THIRD_PARTY_BILLING,
        display_name="Third-Party Billing",
        mechanic=PricingMechanic.PER_UNIT_RATE_BY_BRACKET,
        volume_dimension="active client agency count (billing-company customer type)",
        base_fee_monthly=Decimal("7500"),
        included_units=5,
        bands=(
            per_unit_band(6, 20, "750", "8100.00"),
            per_unit_band(21, 50, "595", "6426.00"),
            per_unit_band(51, 100, "495", "5346.00"),
            custom_quote_band(101),
        ),
        notes=(
            "Billing-company customer type (a billing company reselling "
            "services to multiple client agencies) -- distinct from a single "
            "agency's own Billing Technology or Managed Billing purchase. "
            "Base fee $7,500/month includes up to 5 client agencies; the "
            "per-unit bracket rate applies to agencies beyond that included "
            "5, selected by which bracket the tenant's TOTAL client-agency "
            "count falls into -- not graduated/marginal across brackets, "
            "matching the Hospital entry's convention. Not registered in "
            "module_registry.py as its own module id; this is a distinct "
            "commercial customer type from 'agency_billing_portal' / "
            "'managed_billing'."
        ),
    ),
)
