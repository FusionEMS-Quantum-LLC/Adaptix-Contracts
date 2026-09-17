"""Consistency checks for a :class:`~adaptix_contracts.commercial.offers.CommercialOfferCatalog`.

``validate_offer_catalog`` checks DATA integrity and the linkage to the
application and module registries; it never computes a customer's price. Every
seeded catalog version runs it at import time, so a mistyped founder price, a
grant that cannot reach a service, or a package that costs more than its parts
fails the build instead of a quote.

This module imports ``application_registry``. It is deliberately not imported
by ``adaptix_contracts.commercial`` itself, because ``application_registry``
imports ``commercial.pricing_catalog``; importing a catalog version module
(``commercial.wi_launch_2026_1``) is what runs it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from decimal import Decimal

from adaptix_contracts.application_registry import (
    APPLICATION_REGISTRY,
    SHARED_CAPABILITY_REGISTRY,
    ApplicationDefinition,
    ApplicationStatus,
    ApplicationVisibility,
    SharedCapabilityDefinition,
    is_application_entitled,
    is_workspace_entitled,
)
from adaptix_contracts.commercial.charges import ChargeClass, is_cent_amount
from adaptix_contracts.commercial.offers import (
    ApplicationOffer,
    CommercialOfferCatalog,
    CustomerSegment,
    MonthlyPrice,
    OfferAvailability,
    OfferKind,
    PackageOffer,
    PackagePrice,
    PriceBasis,
    ScalingUnit,
    SegmentPrice,
)
from adaptix_contracts.commercial.terms import CommercialTerms
from adaptix_contracts.commercial.usage import UsageMetric
from adaptix_contracts.module_registry import (
    expand_entitlements,
    module_audiences,
    resolve_module_id,
)

__all__ = ["validate_offer_catalog"]

_LOWER_WORD = re.compile(r"[a-z0-9]+")
_UPPER_WORD = re.compile(r"[A-Z0-9]+")
_VERSION_NUMBER = re.compile(r"[0-9]{4}\.[0-9]+")
_CURRENCY = re.compile(r"[A-Z]{3}")


def _is_snake_case_id(value: str) -> bool:
    """Lower snake_case: a letter first, then lower-case words joined by single underscores."""

    return value[:1].isalpha() and all(
        _LOWER_WORD.fullmatch(word) for word in value.split("_")
    )


def _is_catalog_version(value: str) -> bool:
    """Upper-case words joined by hyphens, then ``-YYYY.N`` (``WI-LAUNCH-2026.1``)."""

    prefix, separator, number = value.rpartition("-")
    return (
        bool(separator)
        and prefix[:1].isalpha()
        and all(_UPPER_WORD.fullmatch(word) for word in prefix.split("-"))
        and _VERSION_NUMBER.fullmatch(number) is not None
    )


_OFFER_CHARGE_CLASSES = {
    OfferKind.APPLICATION: frozenset({ChargeClass.APPLICATION_SUBSCRIPTION}),
    OfferKind.APPLICATION_MODULE: frozenset({ChargeClass.APPLICATION_SUBSCRIPTION}),
    OfferKind.CAPABILITY: frozenset({ChargeClass.APPLICATION_SUBSCRIPTION}),
    OfferKind.BILLING_SERVICE: frozenset(
        {ChargeClass.APPLICATION_SUBSCRIPTION, ChargeClass.MANAGED_SERVICE}
    ),
}

#: Charge classes the annual-prepay discount may never reach automatically.
_NEVER_PREPAY_DISCOUNTED = frozenset(
    {
        ChargeClass.USAGE,
        ChargeClass.PASS_THROUGH,
        ChargeClass.PROFESSIONAL_SERVICE,
        ChargeClass.MAINTAINED_INTERFACE,
    }
)

_PUBLISHED_PRICE_BASES = frozenset({PriceBasis.FIXED, PriceBasis.STARTING_AT})


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _fixed_amount(price: MonthlyPrice) -> Decimal | None:
    """The amount of a FIXED price; ``None`` for every other basis."""

    return price.amount if price.basis is PriceBasis.FIXED else None


def _validate_identity(catalog: CommercialOfferCatalog) -> None:
    version = catalog.catalog_version
    _require(
        _is_catalog_version(version),
        f"catalog_version {version!r} must look like WI-LAUNCH-2026.1",
    )
    _require(
        _CURRENCY.fullmatch(catalog.currency) is not None,
        f"{version}: currency {catalog.currency!r} must be an ISO 4217 code",
    )
    _require(bool(catalog.jurisdiction.strip()), f"{version}: jurisdiction is required")
    _require(
        catalog.supersedes != version, f"{version}: a catalog cannot supersede itself"
    )


def _validate_grants(owner: str, grants: Iterable[str]) -> None:
    for module_id in sorted(grants):
        _require(
            resolve_module_id(module_id) == module_id,
            f"{owner}: {module_id!r} is not a canonical module_registry id",
        )
        _require(
            bool(module_audiences(module_id)),
            f"{owner}: {module_id!r} reaches no service audience, so granting it "
            "would sell a dark entitlement",
        )


def _validate_segments(
    owner: str, segments: list[CustomerSegment], *, complete: bool
) -> None:
    _require(
        bool(segments) and len(segments) == len(set(segments)),
        f"{owner}: each segment must be priced at most once",
    )
    if complete:
        _require(
            set(segments) == set(CustomerSegment),
            f"{owner}: every CustomerSegment must be priced",
        )


def _validate_platform(catalog: CommercialOfferCatalog) -> None:
    owner = f"{catalog.catalog_version} platform"
    _validate_segments(
        owner, [plan.segment for plan in catalog.platform_plans], complete=True
    )
    for plan in catalog.platform_plans:
        _require(
            plan.monthly.basis in _PUBLISHED_PRICE_BASES,
            f"{owner} [{plan.segment.value}]: the Platform price must be published",
        )
    _require(
        bool(catalog.platform_grants_modules), f"{owner}: Platform must grant modules"
    )
    _validate_grants(owner, catalog.platform_grants_modules)


def _validate_availability(
    owner: str, availability: OfferAvailability, reason: str
) -> None:
    if availability is OfferAvailability.ACTIVATION_PENDING:
        _require(
            bool(reason.strip()),
            f"{owner}: an activation-pending offer must say why it cannot be sold yet",
        )
    else:
        _require(
            not reason.strip(),
            f"{owner}: availability_reason is only for activation-pending offers",
        )


def _validate_offer_target(owner: str, offer: ApplicationOffer) -> None:
    _require(
        offer.charge_class in _OFFER_CHARGE_CLASSES[offer.kind],
        f"{owner}: charge class {offer.charge_class.value!r} does not fit a "
        f"{offer.kind.value} offer",
    )
    if offer.kind is OfferKind.CAPABILITY:
        _require(
            offer.application_id is None
            and offer.capability_id in SHARED_CAPABILITY_REGISTRY,
            f"{owner}: a capability offer names exactly one registered shared capability",
        )
    else:
        _require(
            offer.capability_id is None
            and offer.application_id in APPLICATION_REGISTRY,
            f"{owner}: an {offer.kind.value} offer names exactly one registered application",
        )


def _validate_offer_references(
    owner: str, offer: ApplicationOffer, catalog: CommercialOfferCatalog
) -> None:
    for label, referenced in (
        ("requires_offers", offer.requires_offers),
        ("excludes_offers", offer.excludes_offers),
        ("standalone_includes_offers", offer.standalone_includes_offers),
    ):
        unknown = sorted(ref for ref in referenced if ref not in catalog.offers)
        _require(not unknown, f"{owner}: {label} names unknown offers {unknown}")
        _require(
            offer.offer_id not in referenced, f"{owner}: {label} names the offer itself"
        )
    _require(
        not offer.requires_offers & offer.excludes_offers,
        f"{owner}: an offer cannot both require and exclude the same offer",
    )
    for other in sorted(offer.excludes_offers):
        _require(
            offer.offer_id in catalog.offers[other].excludes_offers,
            f"{owner}: excludes {other!r}, which does not exclude it back",
        )


def _target_application(owner: str, offer: ApplicationOffer) -> ApplicationDefinition:
    application_id = offer.application_id
    if application_id is None or application_id not in APPLICATION_REGISTRY:
        raise ValueError(f"{owner}: no registered target application")
    return APPLICATION_REGISTRY[application_id]


def _target_capability(
    owner: str, offer: ApplicationOffer
) -> SharedCapabilityDefinition:
    capability_id = offer.capability_id
    if capability_id is None or capability_id not in SHARED_CAPABILITY_REGISTRY:
        raise ValueError(f"{owner}: no registered target shared capability")
    return SHARED_CAPABILITY_REGISTRY[capability_id]


def _reached_audiences(grants: Iterable[str]) -> frozenset[str]:
    reached: set[str] = set()
    for module_id in grants:
        reached |= module_audiences(module_id)
    return frozenset(reached)


def _validate_published_capability(owner: str, offer: ApplicationOffer) -> None:
    capability = _target_capability(owner, offer)
    _require(
        capability.visibility is ApplicationVisibility.TENANT,
        f"{owner}: capability {capability.capability_id!r} is not tenant-visible",
    )
    _require(
        bool(capability.modules & expand_entitlements(offer.grants_modules)),
        f"{owner}: grants do not open capability {capability.capability_id!r}",
    )
    missing = sorted(capability.services - _reached_audiences(offer.grants_modules))
    _require(not missing, f"{owner}: grants reach none of services {missing}")


def _validate_published_application(owner: str, offer: ApplicationOffer) -> None:
    app = _target_application(owner, offer)
    app_id = app.canonical_id
    _require(
        app.status is ApplicationStatus.ACTIVE,
        f"{owner}: application {app_id!r} is {app.status.value}, not active",
    )
    _require(
        app.visibility is ApplicationVisibility.TENANT,
        f"{owner}: application {app_id!r} is not tenant-visible",
    )
    _require(
        is_application_entitled(app_id, offer.grants_modules),
        f"{owner}: grants do not satisfy the {app_id!r} application gate",
    )
    if offer.kind is OfferKind.APPLICATION_MODULE:
        return
    dark = [
        workspace.workspace_id
        for workspace in app.workspaces
        if not is_workspace_entitled(
            app_id, workspace.workspace_id, offer.grants_modules
        )
    ]
    _require(not dark, f"{owner}: grants leave {app_id!r} workspaces dark: {dark}")
    missing = sorted(app.primary_services - _reached_audiences(offer.grants_modules))
    _require(not missing, f"{owner}: grants reach none of primary services {missing}")


def _validate_published_offer(owner: str, offer: ApplicationOffer) -> None:
    _require(
        bool(offer.grants_modules), f"{owner}: a published offer must grant modules"
    )
    if offer.kind is OfferKind.CAPABILITY:
        _validate_published_capability(owner, offer)
    else:
        _validate_published_application(owner, offer)


def _validate_additional_unit(
    where: str, scaling_unit: ScalingUnit | None, additional_unit: MonthlyPrice | None
) -> None:
    if scaling_unit is None:
        _require(
            additional_unit is None, f"{where}: additional_unit needs a scaling_unit"
        )
    else:
        _require(
            additional_unit is not None,
            f"{where}: a scaled offer must price additional units "
            "(CUSTOM_QUOTE_PRICE when unpublished)",
        )


def _validate_usage_rates(
    where: str, offer: ApplicationOffer, price: SegmentPrice
) -> None:
    metrics = [rate.metric for rate in price.usage_rates]
    _require(
        len(metrics) == len(set(metrics)), f"{where}: a usage metric is priced once"
    )
    if offer.kind is OfferKind.BILLING_SERVICE:
        _require(
            UsageMetric.BILLABLE_ENCOUNTER in metrics,
            f"{where}: a billing service is priced per billable encounter",
        )
    else:
        _require(
            UsageMetric.BILLABLE_ENCOUNTER not in metrics,
            f"{where}: only a billing service is priced per billable encounter",
        )


def _validate_standalone_floor(
    where: str,
    offer: ApplicationOffer,
    price: SegmentPrice,
    catalog: CommercialOfferCatalog,
) -> None:
    """A Platform-inclusive entry price never undercuts Platform plus its add-ons."""

    parts = [catalog.platform_plan(price.segment).monthly, price.add_on]
    parts.extend(
        catalog.offers[included].price_for(price.segment).add_on
        for included in sorted(offer.standalone_includes_offers)
    )
    standalone = _fixed_amount(price.standalone)
    amounts = [_fixed_amount(part) for part in parts]
    if standalone is None or None in amounts:
        return
    floor = sum((amount for amount in amounts if amount is not None), Decimal(0))
    _require(
        standalone >= floor,
        f"{where}: standalone {standalone} is below Platform plus included add-ons {floor}",
    )


def _validate_platform_netting(
    where: str, price: SegmentPrice, catalog: CommercialOfferCatalog
) -> None:
    """A billing add-on is the entry price net of the Platform the customer pays."""

    platform = _fixed_amount(catalog.platform_plan(price.segment).monthly)
    standalone = _fixed_amount(price.standalone)
    add_on = _fixed_amount(price.add_on)
    if platform is None or standalone is None or add_on is None:
        return
    _require(
        add_on == standalone - platform,
        f"{where}: add-on {add_on} must equal standalone {standalone} minus "
        f"Platform {platform}",
    )


def _validate_offer_prices(
    owner: str, offer: ApplicationOffer, catalog: CommercialOfferCatalog
) -> None:
    _validate_segments(owner, [price.segment for price in offer.prices], complete=True)
    for price in offer.prices:
        where = f"{owner} [{price.segment.value}]"
        _validate_additional_unit(where, offer.scaling_unit, price.additional_unit)
        _validate_usage_rates(where, offer, price)
        _validate_standalone_floor(where, offer, price, catalog)
        if offer.kind is OfferKind.BILLING_SERVICE:
            _validate_platform_netting(where, price, catalog)


def _validate_offer(
    key: str, offer: ApplicationOffer, catalog: CommercialOfferCatalog
) -> None:
    owner = f"offer {key}"
    _require(
        offer.offer_id == key, f"{owner}: stored under a key other than its offer_id"
    )
    _require(_is_snake_case_id(key), f"{owner}: offer ids are lower snake_case")
    _require(bool(offer.display_name.strip()), f"{owner}: display_name is required")
    _validate_grants(owner, offer.grants_modules)
    _validate_offer_target(owner, offer)
    _validate_offer_references(owner, offer, catalog)
    _validate_availability(owner, offer.availability, offer.availability_reason)
    if offer.availability is OfferAvailability.PUBLISHED:
        _validate_published_offer(owner, offer)
    else:
        # Grants are only checked against the registries once an offer is
        # published, and every grant feeds application ``sold_as`` linkage, so an
        # unsellable offer must not carry any.
        _require(
            not offer.grants_modules,
            f"{owner}: an activation-pending offer grants nothing until it is published",
        )
    _validate_offer_prices(owner, offer, catalog)


def _validate_package_composition(
    owner: str, package: PackageOffer, catalog: CommercialOfferCatalog
) -> None:
    unknown = sorted(
        ref for ref in package.includes_offers if ref not in catalog.offers
    )
    _require(not unknown, f"{owner}: includes unknown offers {unknown}")
    for offer_id in sorted(package.includes_offers):
        offer = catalog.offers[offer_id]
        missing = sorted(offer.requires_offers - package.includes_offers)
        _require(not missing, f"{owner}: {offer_id!r} requires {missing}")
        clash = sorted(offer.excludes_offers & package.includes_offers)
        _require(not clash, f"{owner}: {offer_id!r} cannot be combined with {clash}")
    for base_id in sorted(package.builds_on_packages):
        _require(
            base_id != package.package_id and base_id in catalog.packages,
            f"{owner}: builds on unknown package {base_id!r}",
        )
        omitted = sorted(
            catalog.packages[base_id].includes_offers - package.includes_offers
        )
        _require(not omitted, f"{owner}: builds on {base_id!r} but omits {omitted}")
    if package.scaling_unit is not None:
        _require(
            any(
                catalog.offers[offer_id].scaling_unit is package.scaling_unit
                for offer_id in package.includes_offers
            ),
            f"{owner}: scales by {package.scaling_unit.value} but includes no offer that does",
        )


def _validate_package_availability(
    owner: str, package: PackageOffer, catalog: CommercialOfferCatalog
) -> None:
    _validate_availability(owner, package.availability, package.availability_reason)
    if package.availability is OfferAvailability.PUBLISHED:
        pending = sorted(
            offer_id
            for offer_id in package.includes_offers
            if catalog.offers[offer_id].availability is not OfferAvailability.PUBLISHED
        )
        _require(
            not pending,
            f"{owner}: cannot be published while it includes activation-pending "
            f"offers {pending}",
        )


def _validate_package_is_a_discount(
    where: str,
    package: PackageOffer,
    price: PackagePrice,
    catalog: CommercialOfferCatalog,
) -> None:
    """Packages are discounts: never above Platform plus their included add-ons."""

    monthly = _fixed_amount(price.monthly)
    parts = [catalog.platform_plan(price.segment).monthly]
    parts.extend(
        catalog.offers[offer_id].price_for(price.segment).add_on
        for offer_id in sorted(package.includes_offers)
    )
    amounts = [_fixed_amount(part) for part in parts]
    if monthly is None or None in amounts:
        return
    total = sum((amount for amount in amounts if amount is not None), Decimal(0))
    _require(
        monthly <= total,
        f"{where}: package price {monthly} exceeds Platform plus included add-ons {total}",
    )


def _validate_package_exceeds_platform(
    where: str, price: PackagePrice, catalog: CommercialOfferCatalog
) -> None:
    """A package includes Platform and at least one application, so it costs more."""

    monthly = _fixed_amount(price.monthly)
    platform = _fixed_amount(catalog.platform_plan(price.segment).monthly)
    if monthly is None or platform is None:
        return
    _require(
        monthly > platform,
        f"{where}: package price {monthly} does not exceed the Platform price "
        f"{platform} it includes",
    )


def _validate_package_prices(
    owner: str, package: PackageOffer, catalog: CommercialOfferCatalog
) -> None:
    _validate_segments(
        owner, [price.segment for price in package.prices], complete=False
    )
    for price in package.prices:
        where = f"{owner} [{price.segment.value}]"
        _require(
            price.monthly.basis in _PUBLISHED_PRICE_BASES,
            f"{where}: a package publishes its monthly price",
        )
        _validate_additional_unit(where, package.scaling_unit, price.additional_unit)
        _validate_package_is_a_discount(where, package, price, catalog)
        _validate_package_exceeds_platform(where, price, catalog)


def _validate_package(
    key: str, package: PackageOffer, catalog: CommercialOfferCatalog
) -> None:
    owner = f"package {key}"
    _require(
        package.package_id == key,
        f"{owner}: stored under a key other than its package_id",
    )
    _require(_is_snake_case_id(key), f"{owner}: package ids are lower snake_case")
    _require(bool(package.display_name.strip()), f"{owner}: display_name is required")
    _require(
        bool(package.includes_offers), f"{owner}: a package includes at least one offer"
    )
    _validate_package_composition(owner, package, catalog)
    _validate_package_availability(owner, package, catalog)
    _validate_package_prices(owner, package, catalog)


def _validate_rates_and_periods(terms: CommercialTerms) -> None:
    for name, rate in (
        ("annual_prepay_discount_rate", terms.annual_prepay_discount_rate),
        ("month_to_month_premium_rate", terms.month_to_month_premium_rate),
        (
            "multi_year_max_annual_subscription_increase_rate",
            terms.multi_year_max_annual_subscription_increase_rate,
        ),
    ):
        _require(
            isinstance(rate, Decimal) and Decimal(0) < rate < Decimal(1),
            f"terms.{name} must be a Decimal rate between 0 and 1",
        )
    for name, value in (
        ("standard_term_months", terms.standard_term_months),
        ("multi_year_term_months", terms.multi_year_term_months),
        ("strategic_pilot_min_days", terms.strategic_pilot_min_days),
        ("strategic_pilot_max_days", terms.strategic_pilot_max_days),
    ):
        _require(
            isinstance(value, int) and not isinstance(value, bool) and value > 0,
            f"terms.{name} must be a positive integer",
        )
    _require(
        terms.strategic_pilot_min_days <= terms.strategic_pilot_max_days,
        "terms: the shortest strategic pilot cannot exceed the longest",
    )
    _require(
        terms.multi_year_term_months > terms.standard_term_months,
        "terms: a multi-year commitment must be longer than the standard term",
    )


def _validate_terms(terms: CommercialTerms) -> None:
    _validate_rates_and_periods(terms)
    _require(
        is_cent_amount(terms.onsite_daily_rate)
        and is_cent_amount(terms.maintained_interface_monthly_starting_price),
        "terms: onsite and maintained-interface prices must be cent amounts",
    )
    fee = terms.standard_migration_fee
    _require(
        isinstance(fee, Decimal) and (fee == 0 or is_cent_amount(fee)),
        "terms: the standard migration fee must be zero or a cent amount",
    )
    eligible = terms.annual_prepay_eligible_charge_classes
    _require(
        bool(eligible) and not eligible & _NEVER_PREPAY_DISCOUNTED,
        "terms: annual prepay applies to subscription charges only, never usage, "
        "pass-through, professional-service or interface charges",
    )
    _require(
        bool(terms.allowed_discounts), "terms: allowed_discounts must not be empty"
    )


def validate_offer_catalog(catalog: CommercialOfferCatalog) -> None:
    """Validate a catalog's data and its registry linkage. Raises ``ValueError``.

    Checks DATA integrity only: identifiers, canonical grants that reach a
    service, published offers that open an active tenant application with no
    dark workspace, activation-pending offers that grant nothing, complete
    segment pricing, per-encounter usage only on billing services, standalone
    prices against Platform plus add-ons, package prices above Platform and
    never above Platform plus add-ons, billing add-ons net of Platform, and
    terms that never discount usage or pass-through charges. It never computes
    a customer's price.
    """

    _validate_identity(catalog)
    _validate_platform(catalog)
    for key, offer in catalog.offers.items():
        _validate_offer(key, offer, catalog)
    for key, package in catalog.packages.items():
        _validate_package(key, package, catalog)
    _validate_terms(catalog.terms)
