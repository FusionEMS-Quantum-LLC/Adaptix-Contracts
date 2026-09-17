"""WI-LAUNCH-2026.1 packages (seed data).

Packages are discounts over Platform plus the add-ons they contain, never
different versions of the applications inside them (founder Wisconsin launch
plan, sections 27, 252, 253 and 420). Community packages are sold only to
Community-eligible organizations and the Wisconsin "Complete" packages only in
the Standard segment. Every package that contains Critical Care Transport is
activation-pending until CCT itself can be sold.

Import this module only through ``wi_launch_2026_1``.
"""

from __future__ import annotations

from adaptix_contracts.commercial.offers import (
    CustomerSegment,
    MonthlyPrice,
    OfferAvailability,
    PackageOffer,
    PackagePrice,
    ScalingUnit,
    fixed_price,
)

__all__ = ["PACKAGES"]

_CCT_PENDING_REASON = (
    "Includes Critical Care Transport, which is activation-pending; the "
    "package is sold only once CCT is active."
)

#: Community EMS contents besides Platform; Cortex-powered migration and
#: Clinical Quality (with ePCR) come with them. Cortex Core is sold with
#: Platform, but no grant delivers it yet (see ``platform_grants_modules``).
_EMS = frozenset(
    {
        "epcr",
        "field_operations",
        "workforce",
        "asset_operations",
        "governance",
        "intelligence_analytics",
    }
)
#: Community Fire Complete contents besides Platform.
_FIRE = frozenset(
    {
        "fire_operations",
        "community_risk_reduction",
        "workforce",
        "asset_operations",
        "governance",
        "intelligence_analytics",
    }
)
#: Wisconsin EMS Complete adds Finance and Communications software.
_WISCONSIN_EMS = _EMS | {"finance", "communications"}
#: Wisconsin Fire Complete adds Communications software.
_WISCONSIN_FIRE = _FIRE | {"communications"}


def _package(
    package_id: str,
    display_name: str,
    segment: CustomerSegment,
    monthly: MonthlyPrice,
    includes: frozenset[str],
    *,
    builds_on: frozenset[str] = frozenset(),
    pending_reason: str = "",
    notes: str = "",
) -> PackageOffer:
    return PackageOffer(
        package_id=package_id,
        display_name=display_name,
        availability=(
            OfferAvailability.ACTIVATION_PENDING
            if pending_reason
            else OfferAvailability.PUBLISHED
        ),
        includes_offers=includes,
        prices=(PackagePrice(segment, monthly),),
        builds_on_packages=builds_on,
        availability_reason=pending_reason,
        notes=notes,
    )


_COMMUNITY_PACKAGES = (
    _package(
        "community_ems",
        "Community EMS",
        CustomerSegment.COMMUNITY,
        fixed_price("1495"),
        _EMS,
    ),
    _package(
        "community_fire_complete",
        "Community Fire Complete",
        CustomerSegment.COMMUNITY,
        fixed_price("1995"),
        _FIRE,
    ),
    _package(
        "community_fire_ems",
        "Community Fire + EMS",
        CustomerSegment.COMMUNITY,
        fixed_price("2495"),
        _EMS | _FIRE,
        builds_on=frozenset({"community_ems", "community_fire_complete"}),
    ),
    _package(
        "community_fire_ems_cct",
        "Community Fire + EMS + CCT",
        CustomerSegment.COMMUNITY,
        fixed_price("2995"),
        _EMS | _FIRE | {"cct"},
        builds_on=frozenset({"community_fire_ems"}),
        pending_reason=_CCT_PENDING_REASON,
    ),
)

_WISCONSIN_PACKAGES = (
    _package(
        "wisconsin_ems_complete",
        "Wisconsin EMS Complete",
        CustomerSegment.STANDARD,
        fixed_price("4995"),
        _WISCONSIN_EMS,
        notes=(
            "Billing stays optional: an existing Standard Platform customer adds "
            "Adaptix Billing at its add-on price plus per-encounter usage."
        ),
    ),
    _package(
        "wisconsin_fire_complete",
        "Wisconsin Fire Complete",
        CustomerSegment.STANDARD,
        fixed_price("4995"),
        _WISCONSIN_FIRE,
    ),
    _package(
        "wisconsin_fire_ems_complete",
        "Wisconsin Fire + EMS Complete",
        CustomerSegment.STANDARD,
        fixed_price("6995"),
        _WISCONSIN_EMS | _WISCONSIN_FIRE,
        builds_on=frozenset({"wisconsin_ems_complete", "wisconsin_fire_complete"}),
        notes="The full Fire and full EMS operating stack.",
    ),
    _package(
        "wisconsin_fire_ems_cct_complete",
        "Wisconsin Fire + EMS + CCT Complete",
        CustomerSegment.STANDARD,
        fixed_price("7995"),
        _WISCONSIN_EMS | _WISCONSIN_FIRE | {"cct"},
        builds_on=frozenset({"wisconsin_fire_ems_complete"}),
        pending_reason=_CCT_PENDING_REASON,
    ),
    _package(
        "operations_complete",
        "Operations Complete",
        CustomerSegment.STANDARD,
        fixed_price("9995"),
        _WISCONSIN_EMS | _WISCONSIN_FIRE | {"cct", "cad", "transportlink"},
        builds_on=frozenset({"wisconsin_fire_ems_cct_complete"}),
        pending_reason=_CCT_PENDING_REASON,
        notes=(
            "Adds CAD, TransportLink and Operations Command, which opens on the "
            "CAD entitlement. Billing remains usage-priced and separate."
        ),
    ),
    PackageOffer(
        package_id="hems_complete",
        display_name="HEMS Complete",
        availability=OfferAvailability.ACTIVATION_PENDING,
        includes_offers=frozenset(
            {
                "air_operations",
                "epcr",
                "cct",
                "field_operations",
                "workforce",
                "asset_operations",
                "governance",
                "intelligence_analytics",
            }
        ),
        prices=(
            PackagePrice(
                CustomerSegment.STANDARD,
                fixed_price("7995"),
                additional_unit=fixed_price("1495"),
            ),
        ),
        scaling_unit=ScalingUnit.OPERATIONAL_BASE,
        availability_reason=_CCT_PENDING_REASON,
        notes=(
            "Price is for the first operational base; each additional base is "
            "priced separately. Billing can be added separately."
        ),
    ),
)

#: Every package in authoring order.
PACKAGES: tuple[PackageOffer, ...] = (*_COMMUNITY_PACKAGES, *_WISCONSIN_PACKAGES)
