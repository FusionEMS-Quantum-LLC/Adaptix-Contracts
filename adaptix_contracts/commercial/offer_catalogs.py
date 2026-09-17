"""Every carried commercial offer catalog version, and its JSON export.

A quote records the catalog version it was priced on. This registry resolves
that version for as long as the quote or the contract exists, so the original
proposal stays explainable after prices change (quote compatibility, founder
Wisconsin launch plan sections 128-129 and 314).

:func:`export_offer_catalog` is the machine-readable form committed as
``adaptix_contracts/commercial_catalog.json`` for non-Python consumers. It
serializes catalog DATA only: no annual, prorated or discounted figure is
computed here, because calculation belongs to the pricing/billing service.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from types import MappingProxyType

from adaptix_contracts.commercial.charges import PassThroughChargeType
from adaptix_contracts.commercial.offers import (
    ApplicationOffer,
    CommercialOfferCatalog,
    CustomerSegment,
    MonthlyPrice,
    PackageOffer,
    QuoteSection,
)
from adaptix_contracts.commercial.terms import (
    DISCOUNTS_REQUIRING_FOUNDER_APPROVAL,
    CommercialTerms,
    CommunityEligibilityCriterion,
)
from adaptix_contracts.commercial.usage import (
    SameEncounterActivity,
    UsageLedgerState,
    UsageRate,
)
from adaptix_contracts.commercial.wi_launch_2026_1 import WI_LAUNCH_2026_1

__all__ = [
    "COMMERCIAL_OFFER_CATALOGS",
    "OFFER_CATALOG_SCHEMA_VERSION",
    "UnknownCommercialCatalogVersionError",
    "export_offer_catalogs",
    "export_offer_catalog",
    "get_offer_catalog",
]

#: Version of the exported JSON shape (not of any price list).
OFFER_CATALOG_SCHEMA_VERSION = 1


class UnknownCommercialCatalogVersionError(KeyError):
    """Raised for a catalog version this package does not carry."""


#: Catalog version -> catalog. Read-only; every entry validated at import.
COMMERCIAL_OFFER_CATALOGS: Mapping[str, CommercialOfferCatalog] = MappingProxyType(
    {WI_LAUNCH_2026_1.catalog_version: WI_LAUNCH_2026_1}
)


def get_offer_catalog(catalog_version: str) -> CommercialOfferCatalog:
    """The carried catalog for ``catalog_version``."""

    try:
        return COMMERCIAL_OFFER_CATALOGS[catalog_version]
    except KeyError:
        raise UnknownCommercialCatalogVersionError(
            f"unknown commercial catalog version {catalog_version!r}; carried: "
            f"{sorted(COMMERCIAL_OFFER_CATALOGS)}"
        ) from None


_CENT = Decimal("0.01")


def _money_text(amount: Decimal) -> str:
    """``amount`` as exact text with two decimal places, e.g. ``"1395.00"``.

    A fraction of a cent is refused rather than rounded, so the exported file
    can never state a different price than the catalog it was exported from.
    """

    cents = amount.quantize(_CENT)
    if cents != amount:
        raise ValueError(
            f"money amount {amount!r} is finer than a cent and cannot be exported exactly"
        )
    return str(cents)


def _price(price: MonthlyPrice | None) -> dict[str, str | None] | None:
    if price is None:
        return None
    return {
        "basis": price.basis.value,
        "amount": None if price.amount is None else _money_text(price.amount),
    }


def _usage_rate(rate: UsageRate) -> dict[str, str | None]:
    return {
        "metric": rate.metric.value,
        "basis": rate.basis.value,
        "unit_price": None if rate.unit_price is None else _money_text(rate.unit_price),
    }


def _offer_record(offer: ApplicationOffer) -> dict[str, object]:
    return {
        "offer_id": offer.offer_id,
        "display_name": offer.display_name,
        "kind": offer.kind.value,
        "charge_class": offer.charge_class.value,
        "availability": offer.availability.value,
        "availability_reason": offer.availability_reason,
        "application_id": offer.application_id,
        "capability_id": offer.capability_id,
        "grants_modules": sorted(offer.grants_modules),
        "requires_offers": sorted(offer.requires_offers),
        "excludes_offers": sorted(offer.excludes_offers),
        "standalone_includes_offers": sorted(offer.standalone_includes_offers),
        "standalone_display_name": offer.standalone_display_name,
        "scaling_unit": None
        if offer.scaling_unit is None
        else offer.scaling_unit.value,
        "prices": [
            {
                "segment": price.segment.value,
                "add_on": _price(price.add_on),
                "standalone": _price(price.standalone),
                "additional_unit": _price(price.additional_unit),
                "usage_rates": [_usage_rate(rate) for rate in price.usage_rates],
            }
            for price in offer.prices
        ],
        "notes": offer.notes,
    }


def _package_record(package: PackageOffer) -> dict[str, object]:
    return {
        "package_id": package.package_id,
        "display_name": package.display_name,
        "availability": package.availability.value,
        "availability_reason": package.availability_reason,
        "includes_offers": sorted(package.includes_offers),
        "builds_on_packages": sorted(package.builds_on_packages),
        "scaling_unit": None
        if package.scaling_unit is None
        else package.scaling_unit.value,
        "prices": [
            {
                "segment": price.segment.value,
                "monthly": _price(price.monthly),
                "additional_unit": _price(price.additional_unit),
            }
            for price in package.prices
        ],
        "notes": package.notes,
    }


def _terms_record(terms: CommercialTerms) -> dict[str, object]:
    return {
        "standard_term_months": terms.standard_term_months,
        "annual_prepay_discount_rate": str(terms.annual_prepay_discount_rate),
        "annual_prepay_eligible_charge_classes": sorted(
            charge_class.value
            for charge_class in terms.annual_prepay_eligible_charge_classes
        ),
        "month_to_month_premium_rate": str(terms.month_to_month_premium_rate),
        "multi_year_term_months": terms.multi_year_term_months,
        "multi_year_max_annual_subscription_increase_rate": str(
            terms.multi_year_max_annual_subscription_increase_rate
        ),
        "strategic_pilot_min_days": terms.strategic_pilot_min_days,
        "strategic_pilot_max_days": terms.strategic_pilot_max_days,
        "onsite_daily_rate": _money_text(terms.onsite_daily_rate),
        "maintained_interface_monthly_starting_price": _money_text(
            terms.maintained_interface_monthly_starting_price
        ),
        "standard_migration_fee": _money_text(terms.standard_migration_fee),
        "allowed_discounts": sorted(
            discount.value for discount in terms.allowed_discounts
        ),
        "discounts_requiring_founder_approval": sorted(
            discount.value for discount in DISCOUNTS_REQUIRING_FOUNDER_APPROVAL
        ),
        "standard_users_unlimited": terms.standard_users_unlimited,
        "standard_remote_onboarding_included": terms.standard_remote_onboarding_included,
        "standard_support_included": terms.standard_support_included,
        "patient_payments_software_included_with_billing": (
            terms.patient_payments_software_included_with_billing
        ),
    }


def export_offer_catalog(catalog: CommercialOfferCatalog) -> dict[str, object]:
    """One catalog version as a deterministic, JSON-serialisable record."""

    return {
        "catalog_version": catalog.catalog_version,
        "effective_date": catalog.effective_date.isoformat(),
        "jurisdiction": catalog.jurisdiction,
        "currency": catalog.currency,
        "supersedes": catalog.supersedes,
        "platform": {
            "plans": [
                {
                    "segment": plan.segment.value,
                    "display_name": plan.display_name,
                    "monthly": _price(plan.monthly),
                }
                for plan in catalog.platform_plans
            ],
            "grants_modules": sorted(catalog.platform_grants_modules),
        },
        "offers": [_offer_record(offer) for offer in catalog.offers.values()],
        "packages": [_package_record(package) for package in catalog.packages.values()],
        "terms": _terms_record(catalog.terms),
    }


def export_offer_catalogs(*, contracts_version: str) -> dict[str, object]:
    """Every carried catalog version plus the shared commercial vocabulary."""

    return {
        "schema_version": OFFER_CATALOG_SCHEMA_VERSION,
        "contracts_version": contracts_version,
        "segments": [segment.value for segment in CustomerSegment],
        "quote_sections": [section.value for section in QuoteSection],
        "pass_through_charge_types": [kind.value for kind in PassThroughChargeType],
        "same_encounter_activities": [
            activity.value for activity in SameEncounterActivity
        ],
        "usage_ledger_states": [state.value for state in UsageLedgerState],
        "community_eligibility_criteria": [
            criterion.value for criterion in CommunityEligibilityCriterion
        ],
        "catalogs": [
            export_offer_catalog(catalog)
            for catalog in COMMERCIAL_OFFER_CATALOGS.values()
        ],
    }
