"""Platform + Applications + Packages + Usage: the commercial offer vocabulary.

COMMERCIAL-CATALOG-002. The founder's Wisconsin launch model (locked
2026-09-17) replaces the earlier independently priced, volume-banded
application model -- still available, unchanged, as ``pricing_catalog`` /
``wisconsin_launch_catalog`` (``wi-launch-v1``) -- with one commercial
architecture::

    Platform (paid once) + Applications + Packages (discounts)
        + Usage (only where usage drives cost or value)

This module holds the DATA SHAPES of that model. Like ``pricing_catalog`` it
carries no price calculation: quotes, annual-prepay arithmetic, discounts,
proration and invoice totals belong to the pricing/billing service. The shapes
here describe list prices, which purchase path each price belongs to, what each
purchase entitles, and whether an offer may be sold yet.

Three separations are deliberate
--------------------------------
* **Pricing is not entitlement.** ``grants_modules`` names the canonical
  ``module_registry`` ids a purchase provisions. Runtime gates never read
  prices, segments, offers or packages; they read module entitlements through
  ``module_registry.expand_entitlements``. A capability included at no extra
  charge still has an explicit grant.
* **Packages are discounts, not products.** A :class:`PackageOffer` lists the
  offers it contains and never names a module itself, so a package can never
  become a second authorization system. Its entitlements are exactly Platform
  plus its offers' grants (:meth:`CommercialOfferCatalog.package_entitlements`).
* **Segment is economics, not capability.** :class:`CustomerSegment` changes
  what an organization pays. Community customers get the same applications
  and the same security as Standard customers.

Availability
------------
:attr:`OfferAvailability.PUBLISHED` means the price is decided AND the
application registry can deliver what the offer grants (see
``offer_validation``). It is not a production-readiness claim: public
"available" wording stays governed by the marketing claims-evidence registry.
:attr:`OfferAvailability.ACTIVATION_PENDING` means the price is decided but the
product cannot be provisioned yet; it must never be sold as available.

``grants_modules`` and ``module_registry.purchasable``
------------------------------------------------------
``purchasable`` records the ids that appear in the legacy purchase surfaces
(signup wizard, Stripe product module maps). ``grants_modules`` are
entitlement ids and may include ids those surfaces only confer through a bundle
(``nemsis``, ``neris``) or that are granted by an administrator today (``hr``,
``training``, ``finance`` ...). Every granted id must be canonical and must
reach a service audience; ``offer_validation`` enforces both.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from adaptix_contracts.commercial.charges import ChargeClass, is_cent_amount
from adaptix_contracts.commercial.terms import CommercialTerms
from adaptix_contracts.commercial.usage import UsageRate

__all__ = [
    "CUSTOM_QUOTE_PRICE",
    "NOT_OFFERED_PRICE",
    "ApplicationOffer",
    "CommercialOfferCatalog",
    "CustomerSegment",
    "MonthlyPrice",
    "OfferAvailability",
    "OfferKind",
    "PackageOffer",
    "PackagePrice",
    "PlatformPlan",
    "PriceBasis",
    "QuoteSection",
    "ScalingUnit",
    "SegmentPrice",
    "UnknownCommercialOfferError",
    "fixed_price",
    "starting_price",
]


class UnknownCommercialOfferError(KeyError):
    """A catalog has no offer, package, plan or segment price for the request."""


class CustomerSegment(str, enum.Enum):
    """The commercial segment of a customer organization.

    Decides list prices and commercial defaults only, never permissions.
    """

    COMMUNITY = "community"
    STANDARD = "standard"
    REGIONAL_ENTERPRISE = "regional_enterprise"


class PriceBasis(str, enum.Enum):
    """How a :class:`MonthlyPrice` is published."""

    #: The published monthly list price.
    FIXED = "fixed"
    #: A published floor ("starting at"); the contracted price is quoted.
    STARTING_AT = "starting_at"
    #: Sold, but no number is published; always quoted.
    CUSTOM_QUOTE = "custom_quote"
    #: This purchase path is not sold in this segment.
    NOT_OFFERED = "not_offered"


_AMOUNT_BASES = frozenset({PriceBasis.FIXED, PriceBasis.STARTING_AT})


@dataclass(frozen=True)
class MonthlyPrice:
    """A monthly price in the catalog currency for one purchase path."""

    basis: PriceBasis
    amount: Decimal | None = None

    def __post_init__(self) -> None:
        if self.basis in _AMOUNT_BASES:
            if not is_cent_amount(self.amount):
                raise ValueError(
                    f"a {self.basis.value} price needs a positive Decimal amount "
                    f"with at most cent precision, got {self.amount!r}"
                )
        elif self.amount is not None:
            raise ValueError(
                f"a {self.basis.value} price must not carry an amount, "
                f"got {self.amount!r}"
            )


def fixed_price(amount: str) -> MonthlyPrice:
    """A published monthly list price, from its exact decimal text."""

    return MonthlyPrice(PriceBasis.FIXED, Decimal(amount))


def starting_price(amount: str) -> MonthlyPrice:
    """A published "starting at" monthly price, from its exact decimal text."""

    return MonthlyPrice(PriceBasis.STARTING_AT, Decimal(amount))


#: Sold in the segment, with the price always quoted.
CUSTOM_QUOTE_PRICE = MonthlyPrice(PriceBasis.CUSTOM_QUOTE)
#: Not sold through this purchase path in the segment.
NOT_OFFERED_PRICE = MonthlyPrice(PriceBasis.NOT_OFFERED)


class OfferKind(str, enum.Enum):
    """What an :class:`ApplicationOffer` sells."""

    #: A customer application from the application registry.
    APPLICATION = "application"
    #: One component of an application sold on its own (Fleet only, ...).
    APPLICATION_MODULE = "application_module"
    #: A shared capability sold as an add-on (Communications, Cortex Pro).
    CAPABILITY = "capability"
    #: Adaptix Billing or Adaptix Managed Billing: a base plus per-encounter usage.
    BILLING_SERVICE = "billing_service"


class OfferAvailability(str, enum.Enum):
    """Whether an offer or package may be sold."""

    #: Price decided and the registry can deliver what the offer grants.
    PUBLISHED = "published"
    #: Price decided; the product cannot be provisioned yet. Never sold as available.
    ACTIVATION_PENDING = "activation_pending"


class ScalingUnit(str, enum.Enum):
    """A unit that is priced again beyond the first one included."""

    OPERATIONAL_BASE = "operational_base"
    FACILITY = "facility"


class QuoteSection(str, enum.Enum):
    """The sections a quote presents its lines in (sections 71 and 337)."""

    PLATFORM = "platform"
    APPLICATIONS = "applications"
    PACKAGE_ADJUSTMENT = "package_adjustment"
    USAGE = "usage"
    PASS_THROUGH = "pass_through"


@dataclass(frozen=True)
class SegmentPrice:
    """One segment's prices for an :class:`ApplicationOffer`.

    ``add_on`` is what an organization that already pays Platform adds.
    ``standalone`` is the Platform-inclusive entry price a new customer sees.
    ``additional_unit`` prices each operational base or facility beyond the
    first, and is set only on offers with a ``scaling_unit``.
    """

    segment: CustomerSegment
    add_on: MonthlyPrice
    standalone: MonthlyPrice
    additional_unit: MonthlyPrice | None = None
    usage_rates: tuple[UsageRate, ...] = ()


@dataclass(frozen=True)
class ApplicationOffer:  # pylint: disable=too-many-instance-attributes
    """One sellable application, application module, capability or billing service."""

    offer_id: str
    display_name: str
    kind: OfferKind
    charge_class: ChargeClass
    availability: OfferAvailability
    #: Canonical ``module_registry`` ids a purchase provisions. Gates read
    #: these, never the price.
    grants_modules: frozenset[str]
    #: Exactly one entry per :class:`CustomerSegment`.
    prices: tuple[SegmentPrice, ...]
    #: The registry application this offer sells (every kind but CAPABILITY).
    application_id: str | None = None
    #: The registry shared capability this offer sells (CAPABILITY only).
    capability_id: str | None = None
    scaling_unit: ScalingUnit | None = None
    #: Offers that must also be held (CRR requires Fire Operations).
    requires_offers: frozenset[str] = field(default_factory=frozenset)
    #: Offers that cannot be held together with this one.
    excludes_offers: frozenset[str] = field(default_factory=frozenset)
    #: Offers the standalone price already includes besides Platform.
    standalone_includes_offers: frozenset[str] = field(default_factory=frozenset)
    #: The public name of the standalone entry product when it differs.
    standalone_display_name: str | None = None
    #: Why an ACTIVATION_PENDING offer cannot be sold yet; empty when PUBLISHED.
    availability_reason: str = ""
    notes: str = ""

    def price_for(self, segment: CustomerSegment) -> SegmentPrice:
        """This offer's prices in ``segment``."""

        for price in self.prices:
            if price.segment is segment:
                return price
        raise UnknownCommercialOfferError(
            f"offer {self.offer_id!r} has no price for segment {segment.value!r}"
        )


@dataclass(frozen=True)
class PackagePrice:
    """One segment's monthly price for a :class:`PackageOffer`."""

    segment: CustomerSegment
    monthly: MonthlyPrice
    additional_unit: MonthlyPrice | None = None


@dataclass(frozen=True)
class PackageOffer:  # pylint: disable=too-many-instance-attributes
    """Platform plus a set of application offers, sold as a discount.

    A package is a commercial convenience and never an entitlement authority:
    it names offers, not modules, and is sold only in the segments it prices.
    """

    package_id: str
    display_name: str
    availability: OfferAvailability
    includes_offers: frozenset[str]
    prices: tuple[PackagePrice, ...]
    #: Packages whose contents this one contains in full.
    builds_on_packages: frozenset[str] = field(default_factory=frozenset)
    scaling_unit: ScalingUnit | None = None
    availability_reason: str = ""
    notes: str = ""

    def price_for(self, segment: CustomerSegment) -> PackagePrice:
        """This package's price in ``segment``."""

        for price in self.prices:
            if price.segment is segment:
                return price
        raise UnknownCommercialOfferError(
            f"package {self.package_id!r} is not sold in segment {segment.value!r}"
        )


@dataclass(frozen=True)
class PlatformPlan:
    """The AdaptixCore Platform subscription in one segment, paid once."""

    segment: CustomerSegment
    display_name: str
    monthly: MonthlyPrice


@dataclass(frozen=True)
class CommercialOfferCatalog:  # pylint: disable=too-many-instance-attributes
    """One immutable version of the Platform + Applications + Packages + Usage catalog."""

    catalog_version: str
    effective_date: date
    jurisdiction: str
    currency: str
    platform_plans: tuple[PlatformPlan, ...]
    #: Canonical module ids every Platform subscription provisions; identical
    #: in every segment.
    platform_grants_modules: frozenset[str]
    offers: Mapping[str, ApplicationOffer]
    packages: Mapping[str, PackageOffer]
    terms: CommercialTerms
    #: The earlier catalog version this one replaces for new quotes. The
    #: earlier version is never mutated.
    supersedes: str | None = None

    def platform_plan(self, segment: CustomerSegment) -> PlatformPlan:
        """The Platform plan for ``segment``."""

        for plan in self.platform_plans:
            if plan.segment is segment:
                return plan
        raise UnknownCommercialOfferError(
            f"{self.catalog_version}: no Platform plan for segment {segment.value!r}"
        )

    def offer(self, offer_id: str) -> ApplicationOffer:
        """The offer registered as ``offer_id``."""

        try:
            return self.offers[offer_id]
        except KeyError:
            raise UnknownCommercialOfferError(
                f"{self.catalog_version}: unknown offer {offer_id!r}"
            ) from None

    def package(self, package_id: str) -> PackageOffer:
        """The package registered as ``package_id``."""

        try:
            return self.packages[package_id]
        except KeyError:
            raise UnknownCommercialOfferError(
                f"{self.catalog_version}: unknown package {package_id!r}"
            ) from None

    def offer_entitlements(self, offer_id: str) -> frozenset[str]:
        """Module ids an existing Platform customer receives by adding the offer."""

        return self.offer(offer_id).grants_modules

    def standalone_entitlements(self, offer_id: str) -> frozenset[str]:
        """Module ids a new customer receives from the offer's standalone price.

        Platform, the offer, and every offer its standalone price includes.
        """

        offer = self.offer(offer_id)
        granted = set(self.platform_grants_modules) | offer.grants_modules
        for included in offer.standalone_includes_offers:
            granted |= self.offer(included).grants_modules
        return frozenset(granted)

    def package_entitlements(self, package_id: str) -> frozenset[str]:
        """Module ids a package provisions: Platform plus every included offer."""

        granted = set(self.platform_grants_modules)
        for offer_id in self.package(package_id).includes_offers:
            granted |= self.offer(offer_id).grants_modules
        return frozenset(granted)
