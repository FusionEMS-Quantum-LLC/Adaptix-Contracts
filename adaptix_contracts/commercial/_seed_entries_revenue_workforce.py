"""Wisconsin launch seed entries: revenue-cycle, workforce, and fleet applications.

Private to ``wisconsin_launch_catalog.py`` — split out purely to keep each
seed file to a readable, topically-coherent size; see that module for the
assembled catalog. Billing Technology, Scheduling, Inventory, Narcotics,
Fleet, HEMS.
"""

from __future__ import annotations

from decimal import Decimal

from adaptix_contracts.commercial._seed_band_builders import (
    custom_quote_band,
    flat_band,
)
from adaptix_contracts.commercial.pricing_catalog import (
    ApplicationPricingCatalogEntry,
    CommercialApplicationKey,
    PricingMechanic,
    UnitRateFormula,
)

__all__ = ["ENTRIES"]

ENTRIES: tuple[ApplicationPricingCatalogEntry, ...] = (
    ApplicationPricingCatalogEntry(
        application=CommercialApplicationKey.BILLING_TECHNOLOGY,
        display_name="Billing Technology",
        mechanic=PricingMechanic.FLAT_VOLUME_BAND,
        volume_dimension="annual claims/transports",
        module_canonical_id="billing",
        bands=(
            flat_band(0, 750, "1495", "16146.00"),
            flat_band(751, 2000, "2495", "26946.00"),
            flat_band(2001, 5000, "3495", "37746.00"),
            flat_band(5001, 10000, "4995", "53946.00"),
            flat_band(10001, 20000, "6995", "75546.00"),
            custom_quote_band(20001),
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
            flat_band(1, 50, "995", "10746.00"),
            flat_band(51, 150, "1495", "16146.00"),
            flat_band(151, 300, "2495", "26946.00"),
            flat_band(301, 750, "3995", "43146.00"),
            custom_quote_band(751),
        ),
    ),
    ApplicationPricingCatalogEntry(
        application=CommercialApplicationKey.INVENTORY,
        display_name="Inventory",
        mechanic=PricingMechanic.FLAT_VOLUME_BAND,
        volume_dimension="operational locations",
        module_canonical_id="inventory",
        bands=(
            flat_band(1, 3, "595", "6426.00"),
            flat_band(4, 10, "995", "10746.00"),
            flat_band(11, 25, "1495", "16146.00"),
            custom_quote_band(26),
        ),
    ),
    ApplicationPricingCatalogEntry(
        application=CommercialApplicationKey.NARCOTICS,
        display_name="Narcotics",
        mechanic=PricingMechanic.FLAT_VOLUME_BAND,
        volume_dimension="controlled locations",
        module_canonical_id="narcotics",
        bands=(
            flat_band(1, 3, "795", "8586.00"),
            flat_band(4, 10, "1295", "13986.00"),
            flat_band(11, 25, "1995", "21546.00"),
            custom_quote_band(26),
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
)
