"""WI-LAUNCH-2026.1 carries the founder's locked Wisconsin prices exactly (COMMERCIAL-CATALOG-002).

Every expected figure below is typed from the founder's Wisconsin launch plan
(Part I sections 5-28, Part III sections 248-275 and 420), independently of the
seed modules, so a mistyped seed price fails here as well as in validation.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
from decimal import Decimal
from pathlib import Path

import pytest
from adaptix_contracts.application_registry import (
    APPLICATION_REGISTRY,
    ApplicationStatus,
    ApplicationVisibility,
    UnknownApplicationError,
    export_application_catalog,
    is_workspace_entitled,
    offers_selling_application,
)
from adaptix_contracts.commercial import (
    ANNUAL_DISCOUNT_RATE,
    CUSTOM_QUOTE_PRICE,
    DISCOUNTS_REQUIRING_FOUNDER_APPROVAL,
    NOT_OFFERED_PRICE,
    ChargeClass,
    CustomerSegment,
    DiscountType,
    MonthlyPrice,
    OfferAvailability,
    OfferKind,
    ScalingUnit,
    UnknownCommercialOfferError,
    UsageMetric,
    UsageRate,
    UsageRateBasis,
    fixed_price,
    starting_price,
)
from adaptix_contracts.commercial.offer_catalogs import (
    COMMERCIAL_OFFER_CATALOGS,
    UnknownCommercialCatalogVersionError,
    export_offer_catalog,
    get_offer_catalog,
)
from adaptix_contracts.commercial.pricing_catalog import validate_catalog
from adaptix_contracts.commercial.wi_launch_2026_1 import WI_LAUNCH_2026_1
from adaptix_contracts.commercial.wisconsin_launch_catalog import WI_LAUNCH_CATALOG
from adaptix_contracts.module_registry import expand_entitlements, module_audiences

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG = WI_LAUNCH_2026_1
COMMUNITY = CustomerSegment.COMMUNITY
STANDARD = CustomerSegment.STANDARD
REGIONAL = CustomerSegment.REGIONAL_ENTERPRISE
QUOTED = CUSTOM_QUOTE_PRICE
NOT_SOLD = NOT_OFFERED_PRICE

#: (offer, segment, existing-customer add-on, Platform-inclusive standalone).
OFFER_PRICES: list[tuple[str, CustomerSegment, MonthlyPrice, MonthlyPrice]] = [
    ("epcr", COMMUNITY, fixed_price("495"), fixed_price("995")),
    ("epcr", STANDARD, fixed_price("995"), fixed_price("1995")),
    ("cad", COMMUNITY, fixed_price("995"), fixed_price("1495")),
    ("cad", STANDARD, fixed_price("2495"), fixed_price("3495")),
    ("field_operations", COMMUNITY, fixed_price("395"), fixed_price("895")),
    ("field_operations", STANDARD, fixed_price("795"), fixed_price("1795")),
    ("transportlink", COMMUNITY, fixed_price("295"), fixed_price("795")),
    ("transportlink", STANDARD, fixed_price("595"), fixed_price("1595")),
    ("fire_operations", COMMUNITY, fixed_price("595"), fixed_price("1095")),
    ("fire_operations", STANDARD, fixed_price("1295"), fixed_price("2295")),
    ("cct", COMMUNITY, fixed_price("395"), fixed_price("1395")),
    ("cct", STANDARD, fixed_price("795"), fixed_price("2795")),
    ("cct", REGIONAL, starting_price("1495"), QUOTED),
    ("community_risk_reduction", COMMUNITY, fixed_price("195"), NOT_SOLD),
    ("community_risk_reduction", STANDARD, fixed_price("395"), NOT_SOLD),
    ("mih_community_paramedicine", COMMUNITY, fixed_price("295"), fixed_price("795")),
    ("mih_community_paramedicine", STANDARD, fixed_price("595"), fixed_price("1595")),
    ("workforce", COMMUNITY, fixed_price("395"), fixed_price("895")),
    ("workforce", STANDARD, fixed_price("795"), fixed_price("1795")),
    ("asset_operations", COMMUNITY, fixed_price("495"), fixed_price("995")),
    ("asset_operations", STANDARD, fixed_price("995"), fixed_price("1995")),
    ("fleet_only", COMMUNITY, fixed_price("195"), NOT_SOLD),
    ("fleet_only", STANDARD, fixed_price("295"), NOT_SOLD),
    ("inventory_only", COMMUNITY, fixed_price("295"), NOT_SOLD),
    ("inventory_only", STANDARD, fixed_price("395"), NOT_SOLD),
    ("medications_only", COMMUNITY, fixed_price("195"), NOT_SOLD),
    ("medications_only", STANDARD, fixed_price("295"), NOT_SOLD),
    ("narcotics_only", COMMUNITY, fixed_price("595"), NOT_SOLD),
    ("narcotics_only", STANDARD, fixed_price("795"), NOT_SOLD),
    ("finance", COMMUNITY, fixed_price("295"), fixed_price("795")),
    ("finance", STANDARD, fixed_price("595"), fixed_price("1595")),
    ("governance", COMMUNITY, fixed_price("195"), fixed_price("695")),
    ("governance", STANDARD, fixed_price("395"), fixed_price("1395")),
    ("intelligence_analytics", COMMUNITY, fixed_price("295"), fixed_price("795")),
    ("intelligence_analytics", STANDARD, fixed_price("595"), fixed_price("1595")),
    ("communications", COMMUNITY, fixed_price("195"), fixed_price("695")),
    ("communications", STANDARD, fixed_price("395"), fixed_price("1395")),
    ("cortex_pro", COMMUNITY, fixed_price("295"), NOT_SOLD),
    ("cortex_pro", STANDARD, fixed_price("595"), NOT_SOLD),
    ("hospital_facility_operations", COMMUNITY, QUOTED, NOT_SOLD),
    ("hospital_facility_operations", STANDARD, fixed_price("995"), fixed_price("1995")),
    ("air_operations", COMMUNITY, QUOTED, NOT_SOLD),
    ("air_operations", STANDARD, fixed_price("3995"), fixed_price("4995")),
    ("billing", COMMUNITY, fixed_price("300"), fixed_price("795")),
    ("billing", STANDARD, fixed_price("500"), fixed_price("1495")),
    ("billing", REGIONAL, QUOTED, starting_price("2995")),
    ("managed_billing", COMMUNITY, fixed_price("1500"), fixed_price("1995")),
    ("managed_billing", STANDARD, fixed_price("2000"), fixed_price("2995")),
    ("managed_billing", REGIONAL, QUOTED, QUOTED),
]

#: (package, the only segment it is sold in, monthly price, additional unit).
PACKAGE_PRICES: list[tuple[str, CustomerSegment, MonthlyPrice, MonthlyPrice | None]] = [
    ("community_ems", COMMUNITY, fixed_price("1495"), None),
    ("community_fire_complete", COMMUNITY, fixed_price("1995"), None),
    ("community_fire_ems", COMMUNITY, fixed_price("2495"), None),
    ("community_fire_ems_cct", COMMUNITY, fixed_price("2995"), None),
    ("wisconsin_ems_complete", STANDARD, fixed_price("4995"), None),
    ("wisconsin_fire_complete", STANDARD, fixed_price("4995"), None),
    ("wisconsin_fire_ems_complete", STANDARD, fixed_price("6995"), None),
    ("wisconsin_fire_ems_cct_complete", STANDARD, fixed_price("7995"), None),
    ("operations_complete", STANDARD, fixed_price("9995"), None),
    ("hems_complete", STANDARD, fixed_price("7995"), fixed_price("1495")),
]

PUBLISHED_OFFERS = {
    "epcr",
    "cad",
    "field_operations",
    "transportlink",
    "mih_community_paramedicine",
    "hospital_facility_operations",
    "air_operations",
    "fire_operations",
    "community_risk_reduction",
    "workforce",
    "asset_operations",
    "fleet_only",
    "inventory_only",
    "medications_only",
    "narcotics_only",
    "finance",
    "governance",
    "intelligence_analytics",
    "communications",
    "billing",
    "managed_billing",
}
PENDING_OFFERS = {"cct", "cortex_pro"}
CCT_PACKAGES = {
    "community_fire_ems_cct",
    "wisconsin_fire_ems_cct_complete",
    "operations_complete",
    "hems_complete",
}


def _amount(price: MonthlyPrice) -> Decimal:
    assert price.amount is not None, price
    return price.amount


class TestFounderPrices:
    def test_platform_is_paid_once_per_segment(self) -> None:
        assert CATALOG.platform_plan(COMMUNITY).monthly == fixed_price("495")
        assert CATALOG.platform_plan(STANDARD).monthly == fixed_price("995")
        assert CATALOG.platform_plan(REGIONAL).monthly == starting_price("2495")

    @pytest.mark.parametrize(
        ("offer_id", "segment", "add_on", "standalone"), OFFER_PRICES
    )
    def test_offer_prices(
        self,
        offer_id: str,
        segment: CustomerSegment,
        add_on: MonthlyPrice,
        standalone: MonthlyPrice,
    ) -> None:
        price = CATALOG.offer(offer_id).price_for(segment)
        assert price.add_on == add_on
        assert price.standalone == standalone

    def test_every_offer_and_segment_is_pinned_or_quoted(self) -> None:
        """Regional prices the plan never published are quoted, never invented."""

        pinned = {(offer_id, segment) for offer_id, segment, _, _ in OFFER_PRICES}
        for offer in CATALOG.offers.values():
            for price in offer.prices:
                if (offer.offer_id, price.segment) in pinned:
                    continue
                assert price.segment is REGIONAL, (offer.offer_id, price.segment)
                assert price.add_on == QUOTED, offer.offer_id
                assert price.standalone in (QUOTED, NOT_SOLD), offer.offer_id

    @pytest.mark.parametrize(
        ("package_id", "segment", "monthly", "additional"), PACKAGE_PRICES
    )
    def test_package_prices_and_segments(
        self,
        package_id: str,
        segment: CustomerSegment,
        monthly: MonthlyPrice,
        additional: MonthlyPrice | None,
    ) -> None:
        package = CATALOG.package(package_id)
        assert [price.segment for price in package.prices] == [segment]
        assert package.price_for(segment).monthly == monthly
        assert package.price_for(segment).additional_unit == additional

    def test_packages_cover_exactly_the_published_price_card(self) -> None:
        assert set(CATALOG.packages) == {row[0] for row in PACKAGE_PRICES}

    def test_billing_usage_is_per_billable_encounter(self) -> None:
        def rates(offer_id: str, segment: CustomerSegment) -> tuple[UsageRate, ...]:
            return CATALOG.offer(offer_id).price_for(segment).usage_rates

        encounter = UsageMetric.BILLABLE_ENCOUNTER
        per_unit = UsageRateBasis.PER_UNIT
        assert rates("billing", COMMUNITY) == (
            UsageRate(encounter, per_unit, Decimal("8")),
        )
        assert rates("billing", STANDARD) == (
            UsageRate(encounter, per_unit, Decimal("8")),
        )
        assert rates("managed_billing", COMMUNITY) == (
            UsageRate(encounter, per_unit, Decimal("30")),
        )
        assert rates("managed_billing", STANDARD) == (
            UsageRate(encounter, per_unit, Decimal("35")),
        )
        negotiated = (UsageRate(encounter, UsageRateBasis.NEGOTIATED),)
        assert rates("billing", REGIONAL) == negotiated
        assert rates("managed_billing", REGIONAL) == negotiated

    def test_carrier_and_ai_usage_are_never_folded_into_a_price(self) -> None:
        for price in CATALOG.offer("communications").prices:
            assert price.usage_rates == (
                UsageRate(
                    UsageMetric.COMMUNICATIONS_CARRIER_USAGE,
                    UsageRateBasis.PASS_THROUGH,
                ),
            )
        for price in CATALOG.offer("cortex_pro").prices:
            assert price.usage_rates == (
                UsageRate(
                    UsageMetric.CORTEX_PROVIDER_USAGE, UsageRateBasis.POLICY_PENDING
                ),
            )

    def test_additional_hospital_facility_and_hems_base(self) -> None:
        hospital = CATALOG.offer("hospital_facility_operations")
        assert hospital.scaling_unit is ScalingUnit.FACILITY
        assert hospital.price_for(STANDARD).additional_unit == fixed_price("395")
        assert hospital.price_for(COMMUNITY).additional_unit == QUOTED
        air = CATALOG.offer("air_operations")
        assert air.scaling_unit is ScalingUnit.OPERATIONAL_BASE
        assert all(price.additional_unit == QUOTED for price in air.prices)
        assert (
            CATALOG.package("hems_complete").scaling_unit
            is ScalingUnit.OPERATIONAL_BASE
        )

    def test_terms(self) -> None:
        terms = CATALOG.terms
        assert terms.standard_term_months == 12
        assert terms.annual_prepay_discount_rate is ANNUAL_DISCOUNT_RATE
        assert terms.annual_prepay_discount_rate == Decimal("0.10")
        assert terms.annual_prepay_eligible_charge_classes == {
            ChargeClass.PLATFORM_SUBSCRIPTION,
            ChargeClass.APPLICATION_SUBSCRIPTION,
            ChargeClass.PACKAGE_SUBSCRIPTION,
        }
        assert terms.month_to_month_premium_rate == Decimal("0.15")
        assert terms.multi_year_term_months == 36
        assert terms.multi_year_max_annual_subscription_increase_rate == Decimal("0.03")
        assert (terms.strategic_pilot_min_days, terms.strategic_pilot_max_days) == (
            90,
            180,
        )
        assert terms.onsite_daily_rate == Decimal("2000")
        assert terms.maintained_interface_monthly_starting_price == Decimal("195")
        assert terms.standard_migration_fee == Decimal("0")
        assert terms.allowed_discounts == set(DiscountType)
        assert DISCOUNTS_REQUIRING_FOUNDER_APPROVAL == {
            DiscountType.FOUNDER_APPROVED_EXCEPTION
        }
        assert terms.standard_users_unlimited
        assert terms.standard_remote_onboarding_included
        assert terms.standard_support_included
        assert terms.patient_payments_software_included_with_billing

    @pytest.mark.parametrize(
        ("encounters", "expected_annual"),
        [(500, Decimal("21940")), (2000, Decimal("33940")), (5000, Decimal("57940"))],
    )
    def test_founder_billing_examples_reproduce(
        self, encounters: int, expected_annual: Decimal
    ) -> None:
        """Plan sections 257-259: Standard Adaptix Billing base x 12 + encounters x $8."""

        price = CATALOG.offer("billing").price_for(STANDARD)
        rate = price.usage_rates[0].unit_price
        assert rate is not None
        assert _amount(price.standalone) * 12 + rate * encounters == expected_annual

    def test_founder_managed_billing_example_reproduces(self) -> None:
        """Plan section 260: Standard Managed Billing, 2,000 encounters = $105,940."""

        price = CATALOG.offer("managed_billing").price_for(STANDARD)
        rate = price.usage_rates[0].unit_price
        assert rate is not None
        assert _amount(price.standalone) * 12 + rate * 2000 == Decimal("105940")

    def test_founder_annual_prepay_examples_reproduce(self) -> None:
        """Plan sections 312 and 126: 10% off twelve months of a subscription."""

        factor = 12 * (1 - CATALOG.terms.annual_prepay_discount_rate)
        fire = _amount(CATALOG.offer("fire_operations").price_for(STANDARD).standalone)
        assert fire * factor == Decimal("24786")
        fire_ems = _amount(
            CATALOG.package("community_fire_ems").price_for(COMMUNITY).monthly
        )
        assert fire_ems * factor == Decimal("26946")


class TestAvailability:
    def test_published_and_pending_offers(self) -> None:
        published = {
            offer.offer_id
            for offer in CATALOG.offers.values()
            if offer.availability is OfferAvailability.PUBLISHED
        }
        assert published == PUBLISHED_OFFERS
        assert set(CATALOG.offers) == PUBLISHED_OFFERS | PENDING_OFFERS

    def test_pending_offers_say_why_and_grant_nothing(self) -> None:
        for offer_id in PENDING_OFFERS:
            offer = CATALOG.offer(offer_id)
            assert offer.availability is OfferAvailability.ACTIVATION_PENDING
            assert offer.availability_reason.strip()
            assert offer.grants_modules == frozenset()

    def test_every_package_containing_cct_is_pending(self) -> None:
        for package in CATALOG.packages.values():
            pending = package.availability is OfferAvailability.ACTIVATION_PENDING
            assert pending == (package.package_id in CCT_PACKAGES), package.package_id
            assert pending == ("cct" in package.includes_offers), package.package_id

    def test_wildland_is_not_sold(self) -> None:
        assert not any("wildland" in offer_id for offer_id in CATALOG.offers)
        assert not any("wildland" in package_id for package_id in CATALOG.packages)


class TestEntitlements:
    def test_platform_grants(self) -> None:
        # No "cortex" yet: which grants deliver the Cortex Core sold with
        # Platform is decided separately (see platform_grants_modules).
        assert CATALOG.platform_grants_modules == {
            "core",
            "onboarding",
            "device",
            "integration",
            "hl7",
            "imports",
            "exports",
            "search",
        }

    def test_package_entitlements_are_platform_plus_offer_grants_only(self) -> None:
        for package in CATALOG.packages.values():
            expected = set(CATALOG.platform_grants_modules)
            for offer_id in package.includes_offers:
                expected |= CATALOG.offer(offer_id).grants_modules
            assert CATALOG.package_entitlements(package.package_id) == expected
            assert package.package_id not in expected

    def test_packages_never_name_modules(self) -> None:
        field_names = {
            field.name for field in dataclasses.fields(CATALOG.package("community_ems"))
        }
        assert not any("module" in name for name in field_names)

    def test_hems_complete_grants_air_not_the_hems_ops_bundle(self) -> None:
        granted = CATALOG.package_entitlements("hems_complete")
        assert "air" in granted
        assert granted.isdisjoint({"hems_ops", "cad", "billing"})

    def test_cct_clinical_entry_includes_epcr(self) -> None:
        assert CATALOG.offer_entitlements("cct") == frozenset()
        standalone = CATALOG.standalone_entitlements("cct")
        assert CATALOG.offer("epcr").grants_modules <= standalone
        assert CATALOG.offer("cct").standalone_display_name == "CCT Clinical"

    def test_every_published_application_offer_opens_every_workspace(self) -> None:
        for offer in CATALOG.offers.values():
            if offer.availability is not OfferAvailability.PUBLISHED or offer.kind in (
                OfferKind.CAPABILITY,
                OfferKind.APPLICATION_MODULE,
            ):
                continue
            app = APPLICATION_REGISTRY[str(offer.application_id)]
            for workspace in app.workspaces:
                assert is_workspace_entitled(
                    app.canonical_id, workspace.workspace_id, offer.grants_modules
                ), (offer.offer_id, workspace.workspace_id)

    def test_every_grant_reaches_a_service(self) -> None:
        for offer in CATALOG.offers.values():
            for module_id in offer.grants_modules:
                assert module_audiences(module_id), (offer.offer_id, module_id)

    def test_transportlink_reaches_its_primary_service_through_transport(self) -> None:
        offer = CATALOG.offer("transportlink")
        assert offer.grants_modules == {"transport"}
        assert "transportlink" in expand_entitlements(offer.grants_modules)
        assert "adaptix-transport" in module_audiences("transport")

    def test_billing_and_managed_billing_are_alternatives(self) -> None:
        assert CATALOG.offer("billing").excludes_offers == {"managed_billing"}
        assert CATALOG.offer("managed_billing").excludes_offers == {"billing"}

    def test_unknown_lookups_raise_key_errors(self) -> None:
        with pytest.raises(UnknownCommercialOfferError):
            CATALOG.offer("wildland")
        with pytest.raises(UnknownCommercialOfferError):
            CATALOG.package("fire_lite")
        with pytest.raises(UnknownCommercialOfferError):
            CATALOG.package("community_ems").price_for(STANDARD)
        assert issubclass(UnknownCommercialOfferError, KeyError)


class TestApplicationRegistryLinkage:
    def test_every_active_tenant_application_is_sold(self) -> None:
        published = [
            offer
            for offer in CATALOG.offers.values()
            if offer.availability is OfferAvailability.PUBLISHED
        ]
        for app in APPLICATION_REGISTRY.values():
            if (
                app.status is ApplicationStatus.ACTIVE
                and app.visibility is ApplicationVisibility.TENANT
            ):
                assert offers_selling_application(app.canonical_id, published), (
                    app.canonical_id
                )

    @pytest.mark.parametrize(
        ("application_id", "offers"),
        [
            ("air_operations", ("air_operations",)),
            ("mih_community_paramedicine", ("mih_community_paramedicine",)),
            ("community_risk_reduction", ("community_risk_reduction",)),
            ("finance", ("finance",)),
            ("clinical_quality", ("epcr",)),
            ("billing", ("billing", "managed_billing")),
            (
                "operations_command",
                (
                    "air_operations",
                    "billing",
                    "cad",
                    "hospital_facility_operations",
                    "managed_billing",
                ),
            ),
            ("cct", ()),
            ("founder_command", ()),
        ],
    )
    def test_offers_selling_application(
        self, application_id: str, offers: tuple[str, ...]
    ) -> None:
        assert (
            offers_selling_application(application_id, CATALOG.offers.values())
            == offers
        )

    def test_offers_selling_an_unknown_application_raises(self) -> None:
        with pytest.raises(UnknownApplicationError):
            offers_selling_application("no_such_app", CATALOG.offers.values())


class TestVersioning:
    def test_carried_versions(self) -> None:
        assert set(COMMERCIAL_OFFER_CATALOGS) == {"WI-LAUNCH-2026.1"}
        assert get_offer_catalog("WI-LAUNCH-2026.1") is CATALOG

    def test_unknown_version_raises(self) -> None:
        with pytest.raises(UnknownCommercialCatalogVersionError):
            get_offer_catalog("WI-LAUNCH-2099.1")
        assert issubclass(UnknownCommercialCatalogVersionError, KeyError)

    def test_supersedes_the_unchanged_v1_catalog(self) -> None:
        assert CATALOG.supersedes == WI_LAUNCH_CATALOG.catalog_version == "wi-launch-v1"
        validate_catalog(WI_LAUNCH_CATALOG)

    def test_catalog_is_immutable(self) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            CATALOG.catalog_version = "changed"  # type: ignore[misc]
        with pytest.raises(TypeError):
            CATALOG.offers["epcr"] = CATALOG.offer("cad")  # type: ignore[index]


class TestExports:
    def test_offer_catalog_export_is_deterministic_json(self) -> None:
        first = export_offer_catalog(CATALOG)
        assert first == export_offer_catalog(CATALOG)
        assert json.loads(json.dumps(first, sort_keys=True)) == first

    def test_export_writes_money_as_exact_strings(self) -> None:
        exported = export_offer_catalog(CATALOG)
        epcr = next(
            record for record in exported["offers"] if record["offer_id"] == "epcr"
        )  # type: ignore[union-attr,index]
        community = epcr["prices"][0]
        assert community["segment"] == "community"
        assert community["add_on"] == {"basis": "fixed", "amount": "495.00"}
        assert community["standalone"] == {"basis": "fixed", "amount": "995.00"}
        assert exported["terms"]["standard_migration_fee"] == "0.00"  # type: ignore[index]

    def test_export_refuses_a_fraction_of_a_cent_instead_of_rounding(self) -> None:
        sub_cent = dataclasses.replace(
            CATALOG,
            terms=dataclasses.replace(
                CATALOG.terms, standard_migration_fee=Decimal("0.125")
            ),
        )
        with pytest.raises(ValueError, match="finer than a cent"):
            export_offer_catalog(sub_cent)

    def test_committed_commercial_catalog_json_is_current(self) -> None:
        """``adaptix_contracts/commercial_catalog.json`` must be regenerated with every
        catalog change: ``uv run python scripts/export_commercial_catalog.py``."""

        script = REPO_ROOT / "scripts" / "export_commercial_catalog.py"
        spec = importlib.util.spec_from_file_location(
            "export_commercial_catalog", script
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        raw = (REPO_ROOT / "adaptix_contracts" / "commercial_catalog.json").read_bytes()
        assert b"\r\n" not in raw, "commercial_catalog.json must be LF-only"
        assert raw.decode("utf-8") == module.render_catalog(), (
            "commercial_catalog.json is stale — run "
            "`uv run python scripts/export_commercial_catalog.py`"
        )

    def test_application_catalog_export_uses_offer_ids(self) -> None:
        exported = export_application_catalog(
            contracts_version="0", offer_catalog=CATALOG
        )
        assert exported["pricing_catalog_version"] == "WI-LAUNCH-2026.1"
        by_id = {record["canonical_id"]: record for record in exported["applications"]}  # type: ignore[union-attr]
        assert by_id["billing"]["sold_as"] == ["billing", "managed_billing"]
        assert by_id["cct"]["sold_as"] == []

    def test_application_catalog_export_refuses_two_catalogs(self) -> None:
        with pytest.raises(ValueError, match="not both"):
            export_application_catalog(
                contracts_version="0",
                pricing_catalog=WI_LAUNCH_CATALOG,
                offer_catalog=CATALOG,
            )
