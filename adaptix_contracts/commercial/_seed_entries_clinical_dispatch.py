"""Wisconsin launch seed entries: clinical and dispatch applications.

Private to ``wisconsin_launch_catalog.py`` — split out purely to keep each
seed file to a readable, topically-coherent size; see that module for the
assembled catalog. EPCR, CAD, MDT, CrewLink, TransportLink, Hospital, Fire.
"""

from __future__ import annotations

from decimal import Decimal

from adaptix_contracts.commercial._seed_band_builders import (
    custom_quote_band,
    flat_band,
    per_unit_band,
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
        application=CommercialApplicationKey.EPCR,
        display_name="EPCR",
        mechanic=PricingMechanic.FLAT_VOLUME_BAND,
        volume_dimension="annual EMS incidents",
        module_canonical_id="epcr",
        bands=(
            flat_band(0, 750, "1250", "13500.00"),
            flat_band(751, 2000, "1995", "21546.00"),
            flat_band(2001, 5000, "2995", "32346.00"),
            flat_band(5001, 10000, "4495", "48546.00"),
            flat_band(10001, 20000, "6495", "70146.00"),
            flat_band(20001, 40000, "8995", "97146.00"),
            custom_quote_band(40001),
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
            flat_band(0, 2500, "2495", "26946.00"),
            flat_band(2501, 7500, "3995", "43146.00"),
            flat_band(7501, 15000, "5995", "64746.00"),
            flat_band(15001, 30000, "8495", "91746.00"),
            flat_band(30001, 60000, "11995", "129546.00"),
            custom_quote_band(60001),
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
        notes=(
            "$125/device/month, $750/month minimum: price = max(125 * devices, 750)."
        ),
    ),
    ApplicationPricingCatalogEntry(
        application=CommercialApplicationKey.CREWLINK,
        display_name="CrewLink",
        mechanic=PricingMechanic.WORKFORCE_HEADCOUNT_BAND,
        volume_dimension="active operational personnel",
        module_canonical_id="crewlink",
        bands=(
            flat_band(1, 50, "495", "5346.00"),
            flat_band(51, 150, "750", "8100.00"),
            flat_band(151, 300, "1250", "13500.00"),
            flat_band(301, 750, "1995", "21546.00"),
            custom_quote_band(751),
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
            flat_band(0, 2500, "695", "7506.00"),
            flat_band(2501, 7500, "1295", "13986.00"),
            flat_band(7501, 15000, "2295", "24786.00"),
            custom_quote_band(15001),
        ),
        notes=(
            "Does NOT auto-include EPCR, CAD, or Hospital -- no confirmed "
            "technical dependency."
        ),
    ),
    ApplicationPricingCatalogEntry(
        application=CommercialApplicationKey.HOSPITAL,
        display_name="Hospital",
        mechanic=PricingMechanic.PER_UNIT_RATE_BY_BRACKET,
        volume_dimension="facility count",
        module_canonical_id="hospital",
        bands=(
            per_unit_band(1, 1, "1495", "16146.00"),
            per_unit_band(2, 5, "1295", "13986.00"),
            per_unit_band(6, 20, "995", "10746.00"),
            custom_quote_band(21),
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
            flat_band(0, 750, "1250", "13500.00"),
            flat_band(751, 2500, "1995", "21546.00"),
            flat_band(2501, 7500, "2995", "32346.00"),
            flat_band(7501, 15000, "4495", "48546.00"),
            custom_quote_band(15001),
        ),
        notes="Does NOT auto-include CAD or EPCR.",
    ),
)
