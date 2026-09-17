"""WI-LAUNCH-2026.1 application, capability and billing offers (seed data).

Every figure is the founder's locked Wisconsin launch price (AdaptixCore
Wisconsin Domination Plan, Part I sections 7-28, confirmed by Part III sections
248-275). The plan publishes Regional / Enterprise application prices only for
Critical Care Transport and the Adaptix Billing entry price, so every other
Regional price is ``CUSTOM_QUOTE_PRICE`` rather than an invented number.

Wildland is deliberately absent. The plan sets a +$395 / +$795 activation
target but says DO NOT PUBLISH, and neither the application registry nor the
module registry has a Wildland application or entitlement for an offer to
grant. It is added in a later catalog version once the application exists.

Import this module only through ``wi_launch_2026_1``.
"""

from __future__ import annotations

from decimal import Decimal

from adaptix_contracts.commercial.charges import ChargeClass
from adaptix_contracts.commercial.offers import (
    CUSTOM_QUOTE_PRICE,
    NOT_OFFERED_PRICE,
    ApplicationOffer,
    CustomerSegment,
    MonthlyPrice,
    OfferAvailability,
    OfferKind,
    ScalingUnit,
    SegmentPrice,
    fixed_price,
    starting_price,
)
from adaptix_contracts.commercial.usage import UsageMetric, UsageRate, UsageRateBasis

__all__ = ["OFFERS"]

_COMMUNITY = CustomerSegment.COMMUNITY
_STANDARD = CustomerSegment.STANDARD
_REGIONAL = CustomerSegment.REGIONAL_ENTERPRISE

_QUOTED = (CUSTOM_QUOTE_PRICE, CUSTOM_QUOTE_PRICE)


def _prices(
    community: tuple[MonthlyPrice, MonthlyPrice],
    standard: tuple[MonthlyPrice, MonthlyPrice],
    regional: tuple[MonthlyPrice, MonthlyPrice] = _QUOTED,
) -> tuple[SegmentPrice, ...]:
    """(existing-customer add-on, Platform-inclusive standalone) per segment."""

    return (
        SegmentPrice(_COMMUNITY, *community),
        SegmentPrice(_STANDARD, *standard),
        SegmentPrice(_REGIONAL, *regional),
    )


def _application(
    offer_id: str,
    display_name: str,
    grants: frozenset[str],
    prices: tuple[SegmentPrice, ...],
    *,
    notes: str = "",
    excludes: frozenset[str] = frozenset(),
) -> ApplicationOffer:
    """A published application offer that sells the same-named registry application."""

    return ApplicationOffer(
        offer_id=offer_id,
        display_name=display_name,
        kind=OfferKind.APPLICATION,
        charge_class=ChargeClass.APPLICATION_SUBSCRIPTION,
        availability=OfferAvailability.PUBLISHED,
        grants_modules=grants,
        prices=prices,
        application_id=offer_id,
        excludes_offers=excludes,
        notes=notes,
    )


def _asset_module(
    offer_id: str, display_name: str, module_id: str, community: str, standard: str
) -> ApplicationOffer:
    """One Asset Operations component sold on its own (section 17)."""

    return ApplicationOffer(
        offer_id=offer_id,
        display_name=display_name,
        kind=OfferKind.APPLICATION_MODULE,
        charge_class=ChargeClass.APPLICATION_SUBSCRIPTION,
        availability=OfferAvailability.PUBLISHED,
        grants_modules=frozenset({module_id}),
        prices=_prices(
            community=(fixed_price(community), NOT_OFFERED_PRICE),
            standard=(fixed_price(standard), NOT_OFFERED_PRICE),
            regional=(CUSTOM_QUOTE_PRICE, NOT_OFFERED_PRICE),
        ),
        application_id="asset_operations",
        excludes_offers=frozenset({"asset_operations"}),
        notes=(
            "For customers who want only one component; Asset Operations "
            "Complete is the default offer."
        ),
    )


_ASSET_MODULE_OFFER_IDS = frozenset(
    {"fleet_only", "inventory_only", "medications_only", "narcotics_only"}
)

_BILLING_ENCOUNTER_8 = UsageRate(
    UsageMetric.BILLABLE_ENCOUNTER, UsageRateBasis.PER_UNIT, Decimal("8.00")
)
_BILLING_ENCOUNTER_NEGOTIATED = UsageRate(
    UsageMetric.BILLABLE_ENCOUNTER, UsageRateBasis.NEGOTIATED
)
_CARRIER_PASS_THROUGH = (
    UsageRate(UsageMetric.COMMUNICATIONS_CARRIER_USAGE, UsageRateBasis.PASS_THROUGH),
)
_CORTEX_PROVIDER_POLICY = (
    UsageRate(UsageMetric.CORTEX_PROVIDER_USAGE, UsageRateBasis.POLICY_PENDING),
)

_CLINICAL_AND_DISPATCH = (
    _application(
        "epcr",
        "ePCR",
        frozenset({"epcr", "nemsis"}),
        _prices(
            community=(fixed_price("495"), fixed_price("995")),
            standard=(fixed_price("995"), fixed_price("1995")),
        ),
        notes=(
            "Clinical Quality is included with ePCR: the clinical_quality "
            "application opens on the same epcr entitlement. NEMSIS reporting "
            "is part of ePCR as sold, never a separate integration fee, so "
            "nemsis is granted."
        ),
    ),
    _application(
        "cad",
        "CAD",
        frozenset({"cad"}),
        _prices(
            community=(fixed_price("995"), fixed_price("1495")),
            standard=(fixed_price("2495"), fixed_price("3495")),
        ),
        notes=(
            "Operational dispatch and work management. Operations Command opens "
            "on the cad entitlement where the customer's applications provide "
            "its data."
        ),
    ),
    _application(
        "field_operations",
        "Field Operations",
        frozenset({"mdt", "crew", "crewlink"}),
        _prices(
            community=(fixed_price("395"), fixed_price("895")),
            standard=(fixed_price("795"), fixed_price("1795")),
        ),
    ),
    _application(
        "transportlink",
        "TransportLink",
        frozenset({"transport"}),
        _prices(
            community=(fixed_price("295"), fixed_price("795")),
            standard=(fixed_price("595"), fixed_price("1595")),
        ),
        notes=(
            "Grants transport, which implies transportlink: the application "
            "gates on transportlink, and its primary service adaptix-transport "
            "is reached through transport."
        ),
    ),
    ApplicationOffer(
        offer_id="cct",
        display_name="Critical Care Transport",
        kind=OfferKind.APPLICATION,
        charge_class=ChargeClass.APPLICATION_SUBSCRIPTION,
        availability=OfferAvailability.ACTIVATION_PENDING,
        grants_modules=frozenset(),
        prices=_prices(
            community=(fixed_price("395"), fixed_price("1395")),
            standard=(fixed_price("795"), fixed_price("2795")),
            regional=(starting_price("1495"), CUSTOM_QUOTE_PRICE),
        ),
        application_id="cct",
        standalone_includes_offers=frozenset({"epcr"}),
        standalone_display_name="CCT Clinical",
        availability_reason=(
            "The cct application is deferred: it has no entitlement module, no "
            "routed operator workspace, and its service is not deployed. The "
            "price is decided; CCT-ACTIVATE-001 must deliver the application "
            "before it is sold."
        ),
        notes=(
            "CCT Clinical is the Platform-inclusive entry price and includes "
            "ePCR and Clinical Quality."
        ),
    ),
    _application(
        "mih_community_paramedicine",
        "MIH / Community Paramedicine",
        frozenset({"mih_community_paramedicine"}),
        _prices(
            community=(fixed_price("295"), fixed_price("795")),
            standard=(fixed_price("595"), fixed_price("1595")),
        ),
    ),
    ApplicationOffer(
        offer_id="hospital_facility_operations",
        display_name="Hospital / Facility Operations",
        kind=OfferKind.APPLICATION,
        charge_class=ChargeClass.APPLICATION_SUBSCRIPTION,
        availability=OfferAvailability.PUBLISHED,
        grants_modules=frozenset({"hospital"}),
        prices=(
            SegmentPrice(
                _COMMUNITY,
                CUSTOM_QUOTE_PRICE,
                NOT_OFFERED_PRICE,
                additional_unit=CUSTOM_QUOTE_PRICE,
            ),
            SegmentPrice(
                _STANDARD,
                fixed_price("995"),
                fixed_price("1995"),
                additional_unit=fixed_price("395"),
            ),
            SegmentPrice(
                _REGIONAL,
                CUSTOM_QUOTE_PRICE,
                CUSTOM_QUOTE_PRICE,
                additional_unit=CUSTOM_QUOTE_PRICE,
            ),
        ),
        application_id="hospital_facility_operations",
        scaling_unit=ScalingUnit.FACILITY,
        notes=(
            "Prices are for the first facility; each additional facility is "
            "priced separately. Large health systems are quoted."
        ),
    ),
    ApplicationOffer(
        offer_id="air_operations",
        display_name="Air Operations / HEMS",
        kind=OfferKind.APPLICATION,
        charge_class=ChargeClass.APPLICATION_SUBSCRIPTION,
        availability=OfferAvailability.PUBLISHED,
        grants_modules=frozenset({"air"}),
        prices=(
            SegmentPrice(
                _COMMUNITY,
                CUSTOM_QUOTE_PRICE,
                NOT_OFFERED_PRICE,
                additional_unit=CUSTOM_QUOTE_PRICE,
            ),
            SegmentPrice(
                _STANDARD,
                fixed_price("3995"),
                fixed_price("4995"),
                additional_unit=CUSTOM_QUOTE_PRICE,
            ),
            SegmentPrice(
                _REGIONAL,
                CUSTOM_QUOTE_PRICE,
                CUSTOM_QUOTE_PRICE,
                additional_unit=CUSTOM_QUOTE_PRICE,
            ),
        ),
        application_id="air_operations",
        scaling_unit=ScalingUnit.OPERATIONAL_BASE,
        notes=(
            "Prices are for the first operational base. An additional base is "
            "published only inside HEMS Complete; elsewhere it is quoted. Grants "
            "air, not hems_ops: the hems_ops Stripe bundle implies CAD, CrewLink, "
            "MDT, ePCR and Billing and does not open Air Operations."
        ),
    ),
)

_FIRE = (
    _application(
        "fire_operations",
        "Fire Operations",
        frozenset({"fire", "neris"}),
        _prices(
            community=(fixed_price("595"), fixed_price("1095")),
            standard=(fixed_price("1295"), fixed_price("2295")),
        ),
        notes=(
            "Incident operations and command, NERIS reporting, stations and "
            "apparatus, preplans, occupancies and hazards, hydrants and flow "
            "tests, prevention and inspections, hose and readiness, station "
            "alerting and normal Fire analytics are features of Fire "
            "Operations, never separate charges."
        ),
    ),
    ApplicationOffer(
        offer_id="community_risk_reduction",
        display_name="Community Risk Reduction",
        kind=OfferKind.APPLICATION,
        charge_class=ChargeClass.APPLICATION_SUBSCRIPTION,
        availability=OfferAvailability.PUBLISHED,
        grants_modules=frozenset({"crr"}),
        prices=_prices(
            community=(fixed_price("195"), NOT_OFFERED_PRICE),
            standard=(fixed_price("395"), NOT_OFFERED_PRICE),
            regional=(CUSTOM_QUOTE_PRICE, NOT_OFFERED_PRICE),
        ),
        application_id="community_risk_reduction",
        requires_offers=frozenset({"fire_operations"}),
        notes="Requires Fire Operations; no standalone entry price is published.",
    ),
)

_OPERATIONS_SUPPORT = (
    _application(
        "workforce",
        "Workforce",
        frozenset({"workforce", "hr", "training"}),
        _prices(
            community=(fixed_price("395"), fixed_price("895")),
            standard=(fixed_price("795"), fixed_price("1795")),
        ),
        notes=(
            "Scheduling, labor, HR and training are Workforce capabilities, not "
            "products. workforce implies scheduling and labor; hr and training "
            "are granted so their workspaces open."
        ),
    ),
    _application(
        "asset_operations",
        "Asset Operations",
        frozenset({"assetops", "fleet", "inventory", "medications", "narcotics"}),
        _prices(
            community=(fixed_price("495"), fixed_price("995")),
            standard=(fixed_price("995"), fixed_price("1995")),
        ),
        excludes=_ASSET_MODULE_OFFER_IDS,
        notes=(
            "Asset Operations Complete. Controlled-substance activation still "
            "follows the tenant's state rules at provisioning."
        ),
    ),
    _asset_module("fleet_only", "Fleet only", "fleet", "195", "295"),
    _asset_module("inventory_only", "Inventory only", "inventory", "295", "395"),
    _asset_module("medications_only", "Medications only", "medications", "195", "295"),
    _asset_module("narcotics_only", "Narcotics only", "narcotics", "595", "795"),
    _application(
        "finance",
        "Finance",
        frozenset({"finance"}),
        _prices(
            community=(fixed_price("295"), fixed_price("795")),
            standard=(fixed_price("595"), fixed_price("1595")),
        ),
    ),
    _application(
        "governance",
        "Governance",
        frozenset({"compliance", "documents"}),
        _prices(
            community=(fixed_price("195"), fixed_price("695")),
            standard=(fixed_price("395"), fixed_price("1395")),
        ),
    ),
    _application(
        "intelligence_analytics",
        "Intelligence & Analytics",
        frozenset({"analytics", "intelligence"}),
        _prices(
            community=(fixed_price("295"), fixed_price("795")),
            standard=(fixed_price("595"), fixed_price("1595")),
        ),
        notes=(
            "The application has no application-level module gate; its "
            "analytics and intelligence workspaces gate on these grants."
        ),
    ),
    ApplicationOffer(
        offer_id="communications",
        display_name="Communications",
        kind=OfferKind.CAPABILITY,
        charge_class=ChargeClass.APPLICATION_SUBSCRIPTION,
        availability=OfferAvailability.PUBLISHED,
        grants_modules=frozenset({"communications", "telephony"}),
        prices=(
            SegmentPrice(
                _COMMUNITY,
                fixed_price("195"),
                fixed_price("695"),
                usage_rates=_CARRIER_PASS_THROUGH,
            ),
            SegmentPrice(
                _STANDARD,
                fixed_price("395"),
                fixed_price("1395"),
                usage_rates=_CARRIER_PASS_THROUGH,
            ),
            SegmentPrice(
                _REGIONAL,
                CUSTOM_QUOTE_PRICE,
                CUSTOM_QUOTE_PRICE,
                usage_rates=_CARRIER_PASS_THROUGH,
            ),
        ),
        capability_id="communications",
        notes=(
            "Software price plus actual carrier usage, passed through "
            "transparently or with a documented markup."
        ),
    ),
    ApplicationOffer(
        offer_id="cortex_pro",
        display_name="Cortex Pro Automation",
        kind=OfferKind.CAPABILITY,
        charge_class=ChargeClass.APPLICATION_SUBSCRIPTION,
        availability=OfferAvailability.ACTIVATION_PENDING,
        grants_modules=frozenset(),
        prices=(
            SegmentPrice(
                _COMMUNITY,
                fixed_price("295"),
                NOT_OFFERED_PRICE,
                usage_rates=_CORTEX_PROVIDER_POLICY,
            ),
            SegmentPrice(
                _STANDARD,
                fixed_price("595"),
                NOT_OFFERED_PRICE,
                usage_rates=_CORTEX_PROVIDER_POLICY,
            ),
            SegmentPrice(
                _REGIONAL,
                CUSTOM_QUOTE_PRICE,
                NOT_OFFERED_PRICE,
                usage_rates=_CORTEX_PROVIDER_POLICY,
            ),
        ),
        capability_id="cortex",
        availability_reason=(
            "No entitlement distinguishes Cortex Pro automation from Cortex "
            "Core, and the grants that deliver Cortex Core are not yet decided, "
            "so a Cortex Pro purchase could not be enforced."
        ),
        notes=(
            "Provider-heavy overages follow a transparent usage policy, metered "
            "internally with administrator warnings instead of a per-operator "
            "token counter."
        ),
    ),
)

_BILLING = (
    ApplicationOffer(
        offer_id="billing",
        display_name="Adaptix Billing",
        kind=OfferKind.BILLING_SERVICE,
        charge_class=ChargeClass.APPLICATION_SUBSCRIPTION,
        availability=OfferAvailability.PUBLISHED,
        grants_modules=frozenset({"billing"}),
        prices=(
            SegmentPrice(
                _COMMUNITY,
                fixed_price("300"),
                fixed_price("795"),
                usage_rates=(_BILLING_ENCOUNTER_8,),
            ),
            SegmentPrice(
                _STANDARD,
                fixed_price("500"),
                fixed_price("1495"),
                usage_rates=(_BILLING_ENCOUNTER_8,),
            ),
            SegmentPrice(
                _REGIONAL,
                CUSTOM_QUOTE_PRICE,
                starting_price("2995"),
                usage_rates=(_BILLING_ENCOUNTER_NEGOTIATED,),
            ),
        ),
        application_id="billing",
        excludes_offers=frozenset({"managed_billing"}),
        notes=(
            "The agency performs its own billing. Usage is per accepted billable "
            "encounter and never a percentage of collections. Patient-payment "
            "software is included; processor, card and ACH fees pass through."
        ),
    ),
    ApplicationOffer(
        offer_id="managed_billing",
        display_name="Adaptix Managed Billing",
        kind=OfferKind.BILLING_SERVICE,
        charge_class=ChargeClass.MANAGED_SERVICE,
        availability=OfferAvailability.PUBLISHED,
        grants_modules=frozenset({"managed_billing"}),
        prices=(
            SegmentPrice(
                _COMMUNITY,
                fixed_price("1500"),
                fixed_price("1995"),
                usage_rates=(
                    UsageRate(
                        UsageMetric.BILLABLE_ENCOUNTER,
                        UsageRateBasis.PER_UNIT,
                        Decimal("30.00"),
                    ),
                ),
            ),
            SegmentPrice(
                _STANDARD,
                fixed_price("2000"),
                fixed_price("2995"),
                usage_rates=(
                    UsageRate(
                        UsageMetric.BILLABLE_ENCOUNTER,
                        UsageRateBasis.PER_UNIT,
                        Decimal("35.00"),
                    ),
                ),
            ),
            SegmentPrice(
                _REGIONAL,
                CUSTOM_QUOTE_PRICE,
                CUSTOM_QUOTE_PRICE,
                usage_rates=(_BILLING_ENCOUNTER_NEGOTIATED,),
            ),
        ),
        application_id="billing",
        excludes_offers=frozenset({"billing"}),
        notes=(
            "FusionEMS performs the billing work: 0% of collections, no revenue "
            "share and no success fee. An existing Platform customer's add-on "
            "nets the Platform it already pays; public entry pricing is the "
            "standalone price."
        ),
    ),
)

#: Every offer in authoring order.
OFFERS: tuple[ApplicationOffer, ...] = (
    *_CLINICAL_AND_DISPATCH,
    *_FIRE,
    *_OPERATIONS_SUPPORT,
    *_BILLING,
)
