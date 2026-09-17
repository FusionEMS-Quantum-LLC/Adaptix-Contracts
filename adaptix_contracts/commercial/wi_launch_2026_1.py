"""WI-LAUNCH-2026.1: the Wisconsin launch Platform + Applications + Packages + Usage catalog.

Seed DATA locked by the founder on 2026-09-17 (AdaptixCore Wisconsin Domination
Plan, Parts I-III). It supersedes ``wi-launch-v1`` for new quotes. That catalog
stays importable and unchanged for anything already priced on it: pricing
history is never overwritten, and an existing contract keeps the version it
was signed under until its renewal terms allow otherwise. A price change ships
as a new catalog version, never as an edit to this one.

``validate_offer_catalog`` runs at import, so a mistyped price, a package that
costs more than its parts, or a grant that cannot reach a service fails the
build rather than a quote.

The offers and packages live in two private, topically grouped seed modules to
keep each file a readable size; this module is the only supported import path.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import TypeVar

# Pylint's no-name-in-module check mis-resolves leading-underscore submodules in
# the older pylint bundled by Codacy; see the identical, explained exemption in
# ``wisconsin_launch_catalog``. The imports are exercised by the test suite.
from adaptix_contracts.commercial._wi_launch_2026_1_offers import (  # pylint: disable=no-name-in-module
    OFFERS as _OFFERS,
)
from adaptix_contracts.commercial._wi_launch_2026_1_packages import (  # pylint: disable=no-name-in-module
    PACKAGES as _PACKAGES,
)
from adaptix_contracts.commercial.charges import ChargeClass
from adaptix_contracts.commercial.offer_validation import validate_offer_catalog
from adaptix_contracts.commercial.offers import (
    CommercialOfferCatalog,
    CustomerSegment,
    PlatformPlan,
    fixed_price,
    starting_price,
)
from adaptix_contracts.commercial.pricing_catalog import ANNUAL_DISCOUNT_RATE
from adaptix_contracts.commercial.terms import CommercialTerms, DiscountType

__all__ = ["WI_LAUNCH_2026_1"]

_Item = TypeVar("_Item")


def _index(items: Iterable[_Item], key_of: str) -> Mapping[str, _Item]:
    """A read-only mapping keyed by each item's ``key_of`` attribute; no duplicates."""

    indexed: dict[str, _Item] = {}
    for item in items:
        key = getattr(item, key_of)
        if key in indexed:
            raise ValueError(f"WI-LAUNCH-2026.1: duplicate {key_of} {key!r}")
        indexed[key] = item
    return MappingProxyType(indexed)


WI_LAUNCH_2026_1 = CommercialOfferCatalog(
    catalog_version="WI-LAUNCH-2026.1",
    effective_date=date(2026, 9, 17),
    jurisdiction="US-WI",
    currency="USD",
    supersedes="wi-launch-v1",
    platform_plans=(
        PlatformPlan(
            CustomerSegment.COMMUNITY, "Community Platform", fixed_price("495")
        ),
        PlatformPlan(CustomerSegment.STANDARD, "Standard Platform", fixed_price("995")),
        PlatformPlan(
            CustomerSegment.REGIONAL_ENTERPRISE,
            "Regional / Enterprise Platform",
            starting_price("2495"),
        ),
    ),
    # What every Platform subscription provisions: the Core foundation and
    # onboarding, Administration (devices, integrations, HL7, imports and
    # exports -- imports is also the execution authority for Cortex-powered
    # migration) and search. Notifications is served by Core.
    #
    # Cortex Core is sold as part of Platform, but this version grants no Cortex
    # module: which grants deliver it is decided separately, and both roles of
    # module ``cortex`` bear on that decision. As a token audience it mints
    # ``adaptix-cortex``, whose Gateway ``/api/v1/cortex`` catch-all is
    # founder-only, and Core's module toggle lets only a founder enable it. As
    # the Gateway entitlement key it is also required by tenant routes: Core's
    # ``/api/v1/cortex/route``, ``/capabilities`` and ``/budget``, and, together
    # with ``ai`` (the ``adaptix-ai`` audience), the AI service's
    # ``/api/v1/cortex/acuity-prediction`` and ``/demand-forecast``. The tenant
    # Cortex command bar calls ``/api/v1/ai`` (module ``ai``, which the module
    # registry reserves for explicit provisioning). Until that decision ships, a
    # Platform-only tenant reaches none of those routes.
    platform_grants_modules=frozenset(
        {
            "core",
            "onboarding",
            "device",
            "integration",
            "hl7",
            "imports",
            "exports",
            "search",
        }
    ),
    offers=_index(_OFFERS, "offer_id"),
    packages=_index(_PACKAGES, "package_id"),
    terms=CommercialTerms(
        standard_term_months=12,
        # Encoded once: the same rate the wi-launch-v1 catalog validates against.
        annual_prepay_discount_rate=ANNUAL_DISCOUNT_RATE,
        annual_prepay_eligible_charge_classes=frozenset(
            {
                ChargeClass.PLATFORM_SUBSCRIPTION,
                ChargeClass.APPLICATION_SUBSCRIPTION,
                ChargeClass.PACKAGE_SUBSCRIPTION,
            }
        ),
        month_to_month_premium_rate=Decimal("0.15"),
        multi_year_term_months=36,
        multi_year_max_annual_subscription_increase_rate=Decimal("0.03"),
        strategic_pilot_min_days=90,
        strategic_pilot_max_days=180,
        onsite_daily_rate=Decimal("2000.00"),
        maintained_interface_monthly_starting_price=Decimal("195.00"),
        standard_migration_fee=Decimal("0.00"),
        allowed_discounts=frozenset(DiscountType),
        standard_users_unlimited=True,
        standard_remote_onboarding_included=True,
        standard_support_included=True,
        patient_payments_software_included_with_billing=True,
    ),
)

validate_offer_catalog(WI_LAUNCH_2026_1)
