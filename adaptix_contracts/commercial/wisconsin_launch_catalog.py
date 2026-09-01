"""The first seeded commercial pricing catalog: Wisconsin launch, v1.

Seed DATA for the modular per-application pricing model — see
``pricing_catalog`` for the shapes and for why this package carries no
pricing calculation logic. Every monthly figure below is the founder's
verified Wisconsin launch price list; every ``annual_price`` /
``annual_price_per_unit`` is monthly * 12 * (1 - ``ANNUAL_DISCOUNT_RATE``),
rounded to the cent, and is checked against that formula by
``validate_catalog`` at import time below — a typo in a hand-entered annual
figure fails the build, not a customer's invoice.

Prices are versioned, never mutated in place: a future price change ships as
a NEW ``CommercialPricingCatalog`` (a new ``catalog_version`` /
``effective_date``), leaving this one intact for any consumer still pinned
to it.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import MappingProxyType

from adaptix_contracts.commercial.pricing_catalog import (
    ApplicationPricingCatalogEntry,
    CatalogEntryStatus,
    CommercialApplicationKey,
    CommercialPricingCatalog,
    PricingBand,
    PricingMechanic,
    UnitRateFormula,
    validate_catalog,
)


def _band(
    min_units: int,
    max_units: int | None,
    monthly: str,
    annual: str,
    *,
    per_unit: bool = False,
) -> PricingBand:
    """Build one priced (non-custom-quote) band from string literals.

    String literals, not floats, so every figure below is an exact
    ``Decimal`` — floating point has no place in a price list.
    """

    if per_unit:
        return PricingBand(
            min_units=min_units,
            max_units=max_units,
            monthly_price_per_unit=Decimal(monthly),
            annual_price_per_unit=Decimal(annual),
        )
    return PricingBand(
        min_units=min_units,
        max_units=max_units,
        monthly_price=Decimal(monthly),
        annual_price=Decimal(annual),
    )


def _custom_quote_band(min_units: int) -> PricingBand:
    return PricingBand(min_units=min_units, max_units=None, custom_quote=True)


_ENTRIES: tuple[ApplicationPricingCatalogEntry, ...] = (
    ApplicationPricingCatalogEntry(
        application=CommercialApplicationKey.EPCR,
        display_name="EPCR",
        mechanic=PricingMechanic.FLAT_VOLUME_BAND,
        volume_dimension="annual EMS incidents",
        module_canonical_id="epcr",
        bands=(
            _band(0, 750, "1250", "13500.00"),
            _band(751, 2000, "1995", "21546.00"),
            _band(2001, 5000, "2995", "32346.00"),
            _band(5001, 10000, "4495", "48546.00"),
            _band(10001, 20000, "6495", "70146.00"),
            _band(20001, 40000, "8995", "97146.00"),
            _custom_quote_band(40001),
        ),
        notes="Unlimited standard users included at every band.",
    ),
    ApplicationPricingCatalogEntry(
        application=CommercialApplicationKey.CAD,
        display_name="CAD",
        mechanic=PricingMechanic.FLAT_VOLUME_BAND,
        volume_dimension="annual CAD incidents",
        module_canonical_id="cad",
        bands=(
            _band(0, 2500, "2495", "26946.00"),
            _band(2501, 7500, "3995", "43146.00"),
            _band(7501, 15000, "5995", "64746.00"),
            _band(15001, 30000, "8495", "91746.00"),
            _band(30001, 60000, "11995", "129546.00"),
            _custom_quote_band(60001),
        ),
        notes=(
            "Unlimited standard users included. Does NOT auto-include MDT, "
            "EPCR, or CrewLink -- no confirmed technical dependency (see "
            "CommercialPricingCatalog.dependencies, currently empty)."
        ),
    ),
    ApplicationPricingCatalogEntry(
        application=CommercialApplicationKey.MDT,
        display_name="MDT",
        mechanic=PricingMechanic.BASE_PLUS_PER_UNIT,
        volume_dimension="active operational devices",
        module_canonical_id="mdt",
        unit_formula=UnitRateFormula(
            per_unit_rate=Decimal("125"),
            minimum_fee=Decimal("750"),
        ),
        notes=("$125/device/month, $750/month minimum: price = max(125 * devices, 750)."),
    ),
    ApplicationPricingCatalogEntry(
        application=CommercialApplicationKey.CREWLINK,
        display_name="CrewLink",
        mechanic=PricingMechanic.WORKFORCE_HEADCOUNT_BAND,
        volume_dimension="active operational personnel",
        module_canonical_id="crewlink",
        bands=(
            _band(1, 50, "495", "5346.00"),
            _band(51, 150, "750", "8100.00"),
            _band(151, 300, "1250", "13500.00"),
            _band(301, 750, "1995", "21546.00"),
            _custom_quote_band(751),
        ),
        notes="Unlimited standard users included at every band.",
    ),
    ApplicationPricingCatalogEntry(
        application=CommercialApplicationKey.TRANSPORTLINK,
        display_name="TransportLink",
        mechanic=PricingMechanic.FLAT_VOLUME_BAND,
        volume_dimension="annual transports",
        module_canonical_id="transportlink",
        bands=(
            _band(0, 2500, "695", "7506.00"),
            _band(2501, 7500, "1295", "13986.00"),
            _band(7501, 15000, "2295", "24786.00"),
            _custom_quote_band(15001),
        ),
        notes=("Does NOT auto-include EPCR, CAD, or Hospital -- no confirmed technical dependency."),
    ),
    ApplicationPricingCatalogEntry(
        application=CommercialApplicationKey.HOSPITAL,
        display_name="Hospital",
        mechanic=PricingMechanic.PER_UNIT_RATE_BY_BRACKET,
        volume_dimension="facility count",
        module_canonical_id="hospital",
        bands=(
            _band(1, 1, "1495", "16146.00", per_unit=True),
            _band(2, 5, "1295", "13986.00", per_unit=True),
            _band(6, 20, "995", "10746.00", per_unit=True),
            _custom_quote_band(21),
        ),
        notes=(
            "Per-facility, cliff-banded: the bracket rate applies to every "
            "facility once the tenant's total facility count places them in "
            "that bracket -- not graduated/marginal pricing. Users are not "
            "individually licensed by default."
        ),
    ),
    ApplicationPricingCatalogEntry(
        application=CommercialApplicationKey.FIRE,
        display_name="Fire",
        mechanic=PricingMechanic.FLAT_VOLUME_BAND,
        volume_dimension="annual fire incidents",
        module_canonical_id="fire",
        bands=(
            _band(0, 750, "1250", "13500.00"),
            _band(751, 2500, "1995", "21546.00"),
            _band(2501, 7500, "2995", "32346.00"),
            _band(7501, 15000, "4495", "48546.00"),
            _custom_quote_band(15001),
        ),
        notes="Does NOT auto-include CAD or EPCR.",
    ),
    ApplicationPricingCatalogEntry(
        application=CommercialApplicationKey.BILLING_TECHNOLOGY,
        display_name="Billing Technology",
        mechanic=PricingMechanic.FLAT_VOLUME_BAND,
        volume_dimension="annual claims/transports",
        module_canonical_id="billing",
        bands=(
            _band(0, 750, "1495", "16146.00"),
            _band(751, 2000, "2495", "26946.00"),
            _band(2001, 5000, "3495", "37746.00"),
            _band(5001, 10000, "4995", "53946.00"),
            _band(10001, 20000, "6995", "75546.00"),
            _custom_quote_band(20001),
        ),
        notes=(
            "The '0% of collections' headline claim applies ONLY to this "
            "software product, never to Adaptix Managed Billing (a separate "
            "SKU -- module_registry canonical id 'managed_billing'). Does NOT "
            "auto-grant EPCR."
        ),
    ),
    ApplicationPricingCatalogEntry(
        application=CommercialApplicationKey.SCHEDULING,
        display_name="Scheduling",
        mechanic=PricingMechanic.WORKFORCE_HEADCOUNT_BAND,
        volume_dimension="active workforce",
        module_canonical_id="scheduling",
        bands=(
            _band(1, 50, "995", "10746.00"),
            _band(51, 150, "1495", "16146.00"),
            _band(151, 300, "2495", "26946.00"),
            _band(301, 750, "3995", "43146.00"),
            _custom_quote_band(751),
        ),
    ),
    ApplicationPricingCatalogEntry(
        application=CommercialApplicationKey.INVENTORY,
        display_name="Inventory",
        mechanic=PricingMechanic.FLAT_VOLUME_BAND,
        volume_dimension="operational locations",
        module_canonical_id="inventory",
        bands=(
            _band(1, 3, "595", "6426.00"),
            _band(4, 10, "995", "10746.00"),
            _band(11, 25, "1495", "16146.00"),
            _custom_quote_band(26),
        ),
    ),
    ApplicationPricingCatalogEntry(
        application=CommercialApplicationKey.NARCOTICS,
        display_name="Narcotics",
        mechanic=PricingMechanic.FLAT_VOLUME_BAND,
        volume_dimension="controlled locations",
        module_canonical_id="narcotics",
        bands=(
            _band(1, 3, "795", "8586.00"),
            _band(4, 10, "1295", "13986.00"),
            _band(11, 25, "1995", "21546.00"),
            _custom_quote_band(26),
        ),
    ),
    ApplicationPricingCatalogEntry(
        application=CommercialApplicationKey.FLEET,
        display_name="Fleet",
        mechanic=PricingMechanic.BASE_PLUS_PER_UNIT,
        volume_dimension="active vehicles",
        module_canonical_id="fleet",
        unit_formula=UnitRateFormula(
            base_fee=Decimal("495"),
            per_unit_rate=Decimal("59"),
        ),
        notes="price = 495 + 59 * active_vehicles.",
    ),
    ApplicationPricingCatalogEntry(
        application=CommercialApplicationKey.HEMS,
        display_name="HEMS",
        mechanic=PricingMechanic.BASE_PLUS_PER_UNIT,
        volume_dimension="operational bases",
        module_canonical_id="hems_ops",
        unit_formula=UnitRateFormula(
            base_fee=Decimal("3995"),
            per_unit_rate=Decimal("1995"),
            included_units=1,
        ),
        notes=(
            "price = 3995 + 1995 * max(bases - 1, 0). Large multi-base "
            "operations require a custom quote -- the source pricing named no "
            "numeric base-count threshold, so none is fabricated here "
            "(UnitRateFormula.custom_quote_above_units stays unset). Does NOT "
            "auto-grant CAD, MDT, EPCR, Billing, or CrewLink -- no confirmed "
            "technical dependency for THIS standalone volume-banded product. "
            "FLAGGED: module_registry.py's pre-existing 'hems_ops' canonical "
            "id already declares implies=(cad, crewlink, mdt, epcr, billing) "
            "for a different, already-shipping Stripe bundle SKU "
            "(prod_UEOHT3EFG7BSxF, 'Adaptix HEMS Ops'). That implies fact is "
            "an ENTITLEMENT-GRANT relationship for the legacy bundle, not a "
            "pricing dependency of this new standalone HEMS catalog entry -- "
            "it is not changed by this file and needs a founder/product "
            "decision on how the legacy bundle and this new standalone "
            "pricing coexist, which is out of scope for this change."
        ),
    ),
    ApplicationPricingCatalogEntry(
        application=CommercialApplicationKey.CORTEX,
        display_name="Cortex",
        mechanic=PricingMechanic.STARTING_PRICE_BANDS_TBD,
        volume_dimension=("not yet defined -- candidate tiers only, pending real provider-cost measurement"),
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
            "Single starting price only; volume bands TBD. Not registered in "
            "module_registry.py. adaptix_contracts/mih/ exists as a schema "
            "package for Mobile Integrated Health, the same clinical domain "
            "as Community Paramedicine, but MIH has no canonical module id in "
            "module_registry.py today -- cross-referenced here in "
            "documentation only, not reused, since no registered id exists to "
            "reuse."
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
            _band(6, 20, "750", "8100.00", per_unit=True),
            _band(21, 50, "595", "6426.00", per_unit=True),
            _band(51, 100, "495", "5346.00", per_unit=True),
            _custom_quote_band(101),
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


WI_LAUNCH_CATALOG = CommercialPricingCatalog(
    catalog_version="wi-launch-v1",
    effective_date=date(2026, 9, 1),
    jurisdiction="US-WI",
    entries=MappingProxyType({entry.application: entry for entry in _ENTRIES}),
)


validate_catalog(WI_LAUNCH_CATALOG)
