"""Every offer-catalog invariant fails loudly when broken (COMMERCIAL-CATALOG-002).

Each test starts from the real WI-LAUNCH-2026.1 catalog, breaks exactly one
thing with ``dataclasses.replace``, and asserts ``validate_offer_catalog``
rejects it, so a validator that stopped checking would turn a test red.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal
from types import MappingProxyType

import pytest
from adaptix_contracts.commercial import (
    CUSTOM_QUOTE_PRICE,
    BillableEncounterUsageKey,
    ChargeClass,
    CommercialOfferCatalog,
    CommunityEligibilityDecision,
    CommunityEligibilityOutcome,
    CustomerSegment,
    MonthlyPrice,
    OfferAvailability,
    OfferKind,
    PackageOffer,
    PackagePrice,
    PriceBasis,
    ScalingUnit,
    SegmentPrice,
    UsageMetric,
    UsageRate,
    UsageRateBasis,
    fixed_price,
)
from adaptix_contracts.commercial.offer_validation import validate_offer_catalog
from adaptix_contracts.commercial.offers import ApplicationOffer
from adaptix_contracts.commercial.wi_launch_2026_1 import WI_LAUNCH_2026_1

CATALOG = WI_LAUNCH_2026_1
STANDARD = CustomerSegment.STANDARD
COMMUNITY = CustomerSegment.COMMUNITY


def _with_offer(
    offer: ApplicationOffer, *, key: str | None = None
) -> CommercialOfferCatalog:
    offers = dict(CATALOG.offers)
    offers[key or offer.offer_id] = offer
    return replace(CATALOG, offers=MappingProxyType(offers))


def _with_package(package: PackageOffer) -> CommercialOfferCatalog:
    packages = dict(CATALOG.packages)
    packages[package.package_id] = package
    return replace(CATALOG, packages=MappingProxyType(packages))


def _replace_price(
    offer: ApplicationOffer, segment: CustomerSegment, **changes: object
) -> ApplicationOffer:
    prices = tuple(
        replace(price, **changes) if price.segment is segment else price  # type: ignore[arg-type]
        for price in offer.prices
    )
    return replace(offer, prices=prices)


def _rejects(catalog: CommercialOfferCatalog, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        validate_offer_catalog(catalog)


def test_the_seeded_catalog_is_valid() -> None:
    validate_offer_catalog(CATALOG)


class TestValueObjects:
    @pytest.mark.parametrize(
        "amount", [Decimal("0"), Decimal("-1"), Decimal("9.999"), Decimal("NaN")]
    )
    def test_monthly_price_rejects_non_cent_amounts(self, amount: Decimal) -> None:
        with pytest.raises(ValueError, match="cent precision"):
            MonthlyPrice(PriceBasis.FIXED, amount)

    def test_monthly_price_rejects_float_and_missing_amounts(self) -> None:
        with pytest.raises(ValueError, match="cent precision"):
            MonthlyPrice(PriceBasis.FIXED, 495.0)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="cent precision"):
            MonthlyPrice(PriceBasis.STARTING_AT)

    def test_quoted_and_unsold_prices_carry_no_amount(self) -> None:
        with pytest.raises(ValueError, match="must not carry an amount"):
            MonthlyPrice(PriceBasis.CUSTOM_QUOTE, Decimal("100"))
        with pytest.raises(ValueError, match="must not carry an amount"):
            MonthlyPrice(PriceBasis.NOT_OFFERED, Decimal("100"))

    def test_usage_rates(self) -> None:
        with pytest.raises(ValueError, match="per-unit rate"):
            UsageRate(UsageMetric.BILLABLE_ENCOUNTER, UsageRateBasis.PER_UNIT)
        with pytest.raises(ValueError, match="must not carry a unit_price"):
            UsageRate(
                UsageMetric.BILLABLE_ENCOUNTER, UsageRateBasis.NEGOTIATED, Decimal("8")
            )

    def test_usage_key_is_a_value_that_deduplicates(self) -> None:
        first = BillableEncounterUsageKey(
            "tenant-a", "encounter-1", UsageMetric.BILLABLE_ENCOUNTER
        )
        retry = BillableEncounterUsageKey(
            "tenant-a", "encounter-1", UsageMetric.BILLABLE_ENCOUNTER
        )
        other_tenant = BillableEncounterUsageKey(
            "tenant-b", "encounter-1", UsageMetric.BILLABLE_ENCOUNTER
        )
        assert len({first, retry, other_tenant}) == 2
        with pytest.raises(ValueError, match="tenant_id"):
            BillableEncounterUsageKey(
                " ", "encounter-1", UsageMetric.BILLABLE_ENCOUNTER
            )
        with pytest.raises(ValueError, match="billable_encounter_id"):
            BillableEncounterUsageKey("tenant-a", "", UsageMetric.BILLABLE_ENCOUNTER)

    def test_community_eligibility_decision_needs_reason_and_reviewer(self) -> None:
        with pytest.raises(ValueError, match="written reason"):
            CommunityEligibilityDecision(
                CommunityEligibilityOutcome.APPROVED, " ", "reviewer", date(2026, 9, 17)
            )
        with pytest.raises(ValueError, match="reviewer"):
            CommunityEligibilityDecision(
                CommunityEligibilityOutcome.DENIED,
                "regional service",
                "",
                date(2026, 9, 17),
            )


class TestCatalogIdentity:
    def test_version_shape(self) -> None:
        _rejects(replace(CATALOG, catalog_version="wi launch"), "must look like")

    @pytest.mark.parametrize(
        "version",
        [
            "wi-launch-2026.1",
            "WI--LAUNCH-2026.1",
            "-WI-2026.1",
            "1WI-2026.1",
            "WI-LAUNCH-26.1",
            "WI-LAUNCH-2026",
            "WI-LAUNCH-2026.1\n",
            "WI-LAUNCH-2026.1a",
        ],
    )
    def test_version_shape_is_exact(self, version: str) -> None:
        _rejects(replace(CATALOG, catalog_version=version), "must look like")

    def test_currency_code_is_exact(self) -> None:
        _rejects(replace(CATALOG, currency="USD\n"), "ISO 4217")

    def test_cannot_supersede_itself(self) -> None:
        _rejects(
            replace(CATALOG, supersedes=CATALOG.catalog_version), "supersede itself"
        )

    def test_currency_code(self) -> None:
        _rejects(replace(CATALOG, currency="usd"), "ISO 4217")

    def test_platform_prices_every_segment(self) -> None:
        _rejects(
            replace(CATALOG, platform_plans=CATALOG.platform_plans[:2]),
            "every CustomerSegment",
        )

    def test_platform_grants_must_be_canonical(self) -> None:
        _rejects(
            replace(
                CATALOG,
                platform_grants_modules=CATALOG.platform_grants_modules | {"comms"},
            ),
            "not a canonical module_registry id",
        )


class TestOffers:
    def test_offer_stored_under_its_own_id(self) -> None:
        _rejects(
            _with_offer(CATALOG.offer("cad"), key="dispatch"),
            "key other than its offer_id",
        )

    @pytest.mark.parametrize(
        "offer_id", ["CAD", "_cad", "cad_", "cad__pro", "1cad", "cad-pro", "cad\n"]
    )
    def test_offer_id_is_exact_lower_snake_case(self, offer_id: str) -> None:
        _rejects(
            _with_offer(replace(CATALOG.offer("cad"), offer_id=offer_id)),
            "lower snake_case",
        )

    def test_grant_must_be_a_canonical_id(self) -> None:
        _rejects(
            _with_offer(
                replace(
                    CATALOG.offer("epcr"),
                    grants_modules=frozenset({"epcr", "fire_rms"}),
                )
            ),
            "canonical",
        )

    def test_unknown_grant_is_rejected(self) -> None:
        _rejects(
            _with_offer(
                replace(
                    CATALOG.offer("epcr"), grants_modules=frozenset({"not_a_module"})
                )
            ),
            "canonical",
        )

    def test_published_offer_must_grant_modules(self) -> None:
        _rejects(
            _with_offer(replace(CATALOG.offer("finance"), grants_modules=frozenset())),
            "must grant modules",
        )

    def test_published_offer_cannot_sell_a_deferred_application(self) -> None:
        cct = replace(
            CATALOG.offer("cct"),
            availability=OfferAvailability.PUBLISHED,
            availability_reason="",
            grants_modules=frozenset({"epcr"}),
        )
        _rejects(_with_offer(cct), "not active")

    def test_published_offer_cannot_leave_a_workspace_dark(self) -> None:
        workforce = replace(
            CATALOG.offer("workforce"), grants_modules=frozenset({"workforce"})
        )
        _rejects(_with_offer(workforce), "workspaces dark")

    def test_published_offer_must_open_its_application(self) -> None:
        _rejects(
            _with_offer(
                replace(CATALOG.offer("finance"), grants_modules=frozenset({"cad"}))
            ),
            "application gate",
        )

    def test_published_offer_must_reach_primary_services(self) -> None:
        # transportlink opens the application gate but not adaptix-transport.
        transportlink = replace(
            CATALOG.offer("transportlink"), grants_modules=frozenset({"transportlink"})
        )
        _rejects(_with_offer(transportlink), "primary services")

    def test_pending_offer_must_say_why(self) -> None:
        _rejects(
            _with_offer(replace(CATALOG.offer("cct"), availability_reason=" ")),
            "must say why",
        )

    def test_pending_offer_grants_nothing(self) -> None:
        # A pending grant is never checked against the registries, yet it would
        # still list the offer in an application's sold_as.
        _rejects(
            _with_offer(
                replace(CATALOG.offer("cct"), grants_modules=frozenset({"epcr"}))
            ),
            "grants nothing until it is published",
        )

    def test_published_offer_carries_no_pending_reason(self) -> None:
        _rejects(
            _with_offer(replace(CATALOG.offer("cad"), availability_reason="later")),
            "only for activation-pending",
        )

    def test_capability_offer_names_a_capability(self) -> None:
        communications = replace(
            CATALOG.offer("communications"), capability_id=None, application_id="cad"
        )
        _rejects(_with_offer(communications), "registered shared capability")

    def test_charge_class_fits_the_kind(self) -> None:
        _rejects(
            _with_offer(
                replace(CATALOG.offer("cad"), charge_class=ChargeClass.MANAGED_SERVICE)
            ),
            "does not fit",
        )

    def test_references_must_exist(self) -> None:
        _rejects(
            _with_offer(
                replace(
                    CATALOG.offer("community_risk_reduction"),
                    requires_offers=frozenset({"fire"}),
                )
            ),
            "unknown offers",
        )

    def test_exclusion_must_be_mutual(self) -> None:
        _rejects(
            _with_offer(
                replace(
                    CATALOG.offer("billing"),
                    excludes_offers=frozenset({"managed_billing", "cad"}),
                )
            ),
            "does not exclude it back",
        )

    def test_every_segment_is_priced(self) -> None:
        _rejects(
            _with_offer(
                replace(CATALOG.offer("cad"), prices=CATALOG.offer("cad").prices[:2])
            ),
            "every CustomerSegment",
        )

    def test_additional_unit_requires_a_scaling_unit(self) -> None:
        _rejects(
            _with_offer(
                _replace_price(
                    CATALOG.offer("cad"), STANDARD, additional_unit=fixed_price("100")
                )
            ),
            "needs a scaling_unit",
        )

    def test_scaled_offer_prices_additional_units(self) -> None:
        _rejects(
            _with_offer(
                _replace_price(
                    CATALOG.offer("hospital_facility_operations"),
                    STANDARD,
                    additional_unit=None,
                )
            ),
            "must price additional units",
        )

    def test_billing_service_is_priced_per_encounter(self) -> None:
        _rejects(
            _with_offer(
                _replace_price(CATALOG.offer("billing"), STANDARD, usage_rates=())
            ),
            "per billable encounter",
        )

    def test_only_billing_services_are_priced_per_encounter(self) -> None:
        per_encounter = UsageRate(
            UsageMetric.BILLABLE_ENCOUNTER, UsageRateBasis.PER_UNIT, Decimal("8.00")
        )
        _rejects(
            _with_offer(
                _replace_price(
                    CATALOG.offer("cad"), STANDARD, usage_rates=(per_encounter,)
                )
            ),
            "only a billing service",
        )

    def test_standalone_never_undercuts_platform_plus_add_on(self) -> None:
        _rejects(
            _with_offer(
                _replace_price(
                    CATALOG.offer("epcr"), STANDARD, standalone=fixed_price("1500")
                )
            ),
            "below Platform",
        )

    def test_billing_add_on_nets_platform(self) -> None:
        _rejects(
            _with_offer(
                _replace_price(
                    CATALOG.offer("billing"), COMMUNITY, add_on=fixed_price("295")
                )
            ),
            "minus Platform",
        )


class TestPackages:
    @pytest.mark.parametrize(
        "package_id", ["Community_EMS", "community__ems", "community_ems_"]
    )
    def test_package_id_is_exact_lower_snake_case(self, package_id: str) -> None:
        _rejects(
            _with_package(
                replace(CATALOG.package("community_ems"), package_id=package_id)
            ),
            "lower snake_case",
        )

    def test_package_includes_known_offers(self) -> None:
        _rejects(
            _with_package(
                replace(
                    CATALOG.package("community_ems"),
                    includes_offers=frozenset({"epcr", "qa"}),
                )
            ),
            "unknown offers",
        )

    def test_required_offer_must_be_included(self) -> None:
        package = CATALOG.package("community_fire_complete")
        _rejects(
            _with_package(
                replace(
                    package,
                    includes_offers=package.includes_offers - {"fire_operations"},
                )
            ),
            "requires",
        )

    def test_excluded_offers_cannot_be_combined(self) -> None:
        package = CATALOG.package("wisconsin_ems_complete")
        _rejects(
            _with_package(
                replace(
                    package,
                    includes_offers=package.includes_offers
                    | {"billing", "managed_billing"},
                )
            ),
            "cannot be combined",
        )

    def test_builds_on_must_be_a_superset(self) -> None:
        package = CATALOG.package("community_fire_ems")
        _rejects(
            _with_package(
                replace(
                    package, includes_offers=package.includes_offers - {"governance"}
                )
            ),
            "omits",
        )

    def test_published_package_cannot_include_a_pending_offer(self) -> None:
        package = CATALOG.package("community_ems")
        _rejects(
            _with_package(
                replace(package, includes_offers=package.includes_offers | {"cct"})
            ),
            "activation-pending",
        )

    def test_package_is_a_discount(self) -> None:
        package = CATALOG.package("community_ems")
        expensive = replace(
            package, prices=(PackagePrice(COMMUNITY, fixed_price("4000")),)
        )
        _rejects(_with_package(expensive), "exceeds Platform")

    def test_package_costs_more_than_platform(self) -> None:
        package = CATALOG.package("community_ems")
        at_platform = replace(
            package, prices=(PackagePrice(COMMUNITY, fixed_price("495")),)
        )
        _rejects(_with_package(at_platform), "does not exceed the Platform price")

    def test_package_publishes_its_price(self) -> None:
        package = CATALOG.package("community_ems")
        _rejects(
            _with_package(
                replace(package, prices=(PackagePrice(COMMUNITY, CUSTOM_QUOTE_PRICE),))
            ),
            "publishes its monthly price",
        )

    def test_package_scaling_needs_a_scaled_offer(self) -> None:
        package = replace(
            CATALOG.package("wisconsin_fire_complete"),
            scaling_unit=ScalingUnit.FACILITY,
            prices=(
                PackagePrice(
                    STANDARD, fixed_price("4995"), additional_unit=fixed_price("100")
                ),
            ),
        )
        _rejects(_with_package(package), "includes no offer that does")

    def test_package_segment_priced_once(self) -> None:
        package = CATALOG.package("community_ems")
        twice = (
            PackagePrice(COMMUNITY, fixed_price("1495")),
            PackagePrice(COMMUNITY, fixed_price("1495")),
        )
        _rejects(_with_package(replace(package, prices=twice)), "at most once")


class TestTerms:
    def test_annual_prepay_never_reaches_usage(self) -> None:
        terms = replace(
            CATALOG.terms,
            annual_prepay_eligible_charge_classes=CATALOG.terms.annual_prepay_eligible_charge_classes
            | {ChargeClass.USAGE},
        )
        _rejects(replace(CATALOG, terms=terms), "subscription charges only")

    def test_annual_prepay_never_reaches_the_managed_billing_fee(self) -> None:
        terms = replace(
            CATALOG.terms,
            annual_prepay_eligible_charge_classes=CATALOG.terms.annual_prepay_eligible_charge_classes
            | {ChargeClass.MANAGED_SERVICE},
        )
        _rejects(replace(CATALOG, terms=terms), "subscription charges only")

    @pytest.mark.parametrize(
        "field_name",
        ["standalone_price_max_applications", "quote_validity_calendar_days"],
    )
    @pytest.mark.parametrize("value", [0, -30, True, 30.0, "30", None])
    def test_quote_counts_are_positive_integers(
        self, field_name: str, value: object
    ) -> None:
        _rejects(
            replace(CATALOG, terms=replace(CATALOG.terms, **{field_name: value})),
            f"terms.{field_name} must be a positive integer",
        )

    @pytest.mark.parametrize("value", ["additive", None, 1])
    def test_discount_stacking_must_be_the_enum(self, value: object) -> None:
        _rejects(
            replace(CATALOG, terms=replace(CATALOG.terms, discount_stacking=value)),
            "terms.discount_stacking must be a DiscountStacking",
        )

    @pytest.mark.parametrize("value", ["first_clearinghouse_acceptance", None])
    def test_usage_recognition_must_be_the_enum(self, value: object) -> None:
        _rejects(
            replace(
                CATALOG,
                terms=replace(CATALOG.terms, billable_encounter_recognition=value),
            ),
            "terms.billable_encounter_recognition must be a UsageRecognitionPoint",
        )

    def test_rates_are_between_zero_and_one(self) -> None:
        _rejects(
            replace(
                CATALOG,
                terms=replace(
                    CATALOG.terms, month_to_month_premium_rate=Decimal("1.5")
                ),
            ),
            "between 0 and 1",
        )

    def test_pilot_bounds_are_ordered(self) -> None:
        _rejects(
            replace(
                CATALOG, terms=replace(CATALOG.terms, strategic_pilot_min_days=200)
            ),
            "cannot exceed",
        )

    @pytest.mark.parametrize(
        "fee",
        [
            Decimal("0.125"),
            Decimal("-1.00"),
            Decimal("NaN"),
            Decimal("sNaN"),
            Decimal("-0"),
        ],
    )
    def test_migration_fee_is_zero_or_a_cent_amount(self, fee: Decimal) -> None:
        _rejects(
            replace(CATALOG, terms=replace(CATALOG.terms, standard_migration_fee=fee)),
            "zero or a cent amount",
        )


def test_offer_kinds_cover_every_seeded_offer() -> None:
    assert {offer.kind for offer in CATALOG.offers.values()} == set(OfferKind)


def test_segment_price_type_is_exported() -> None:
    assert isinstance(CATALOG.offer("cad").price_for(STANDARD), SegmentPrice)
