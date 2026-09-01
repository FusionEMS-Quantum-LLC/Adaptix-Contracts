"""Contract tests for the commercial pricing catalog (Phase B, modular pricing)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import MappingProxyType

import pytest
from adaptix_contracts.commercial.pricing_catalog import (
    ApplicationPricingCatalogEntry,
    CatalogEntryStatus,
    CommercialApplicationKey,
    CommercialPricingCatalog,
    PricingBand,
    PricingMechanic,
    UnitRateFormula,
    validate_catalog,
)
from adaptix_contracts.commercial.wisconsin_launch_catalog import WI_LAUNCH_CATALOG
from adaptix_contracts.module_registry import MODULE_REGISTRY


def _minimal_catalog(
    entries: dict[CommercialApplicationKey, ApplicationPricingCatalogEntry],
) -> CommercialPricingCatalog:
    return CommercialPricingCatalog(
        catalog_version="test",
        effective_date=date(2026, 1, 1),
        jurisdiction="US-WI",
        entries=MappingProxyType(entries),
    )


def _complete_starting_price_entries() -> dict[
    CommercialApplicationKey, ApplicationPricingCatalogEntry
]:
    """One valid, minimal entry per application key -- a baseline for defect tests."""

    return {
        key: ApplicationPricingCatalogEntry(
            application=key,
            display_name=key.value,
            mechanic=PricingMechanic.STARTING_PRICE_BANDS_TBD,
            volume_dimension="test dimension",
            starting_monthly_prices=(Decimal("1"),),
        )
        for key in CommercialApplicationKey
    }


class TestCatalogIntegrity:
    def test_every_application_key_has_exactly_one_entry(self) -> None:
        assert set(WI_LAUNCH_CATALOG.entries) == set(CommercialApplicationKey)

    def test_each_entry_is_stored_under_its_own_key(self) -> None:
        for key, entry in WI_LAUNCH_CATALOG.entries.items():
            assert entry.application is key

    def test_every_set_module_canonical_id_is_a_real_canonical_module(self) -> None:
        """An unresolvable module id would silently disagree with the entitlement gate."""

        for entry in WI_LAUNCH_CATALOG.entries.values():
            if entry.module_canonical_id is not None:
                assert entry.module_canonical_id in MODULE_REGISTRY, entry.application

    def test_dependencies_are_currently_empty(self) -> None:
        """No true technical dependency is confirmed among the 20 launch applications.

        This mirrors ``module_registry.SOLD_WITHOUT_SERVICE_MAPPING``'s
        documented-empty-invariant pattern. If this ever fails, a real
        dependency was added -- verify it is a genuine technical dependency,
        not a sales/bundling relationship (which belongs in
        ``module_registry.implies`` instead).
        """

        assert WI_LAUNCH_CATALOG.dependencies == ()

    def test_the_catalog_entries_mapping_is_read_only(self) -> None:
        with pytest.raises(TypeError):
            WI_LAUNCH_CATALOG.entries[CommercialApplicationKey.EPCR] = None  # type: ignore[index]

    def test_the_catalog_object_itself_is_frozen(self) -> None:
        with pytest.raises(Exception):  # noqa: B017 - dataclasses.FrozenInstanceError
            WI_LAUNCH_CATALOG.catalog_version = "mutated"  # type: ignore[misc]

    def test_the_seed_module_already_self_validated_at_import(self) -> None:
        """Re-running validate_catalog against the imported singleton must still pass."""

        validate_catalog(WI_LAUNCH_CATALOG)


class TestModuleReuseNotDuplication:
    """Every application that already has a module_registry canonical id reuses it."""

    @pytest.mark.parametrize(
        ("application", "expected_module_id"),
        [
            (CommercialApplicationKey.EPCR, "epcr"),
            (CommercialApplicationKey.CAD, "cad"),
            (CommercialApplicationKey.MDT, "mdt"),
            (CommercialApplicationKey.CREWLINK, "crewlink"),
            (CommercialApplicationKey.TRANSPORTLINK, "transportlink"),
            (CommercialApplicationKey.HOSPITAL, "hospital"),
            (CommercialApplicationKey.FIRE, "fire"),
            (CommercialApplicationKey.BILLING_TECHNOLOGY, "billing"),
            (CommercialApplicationKey.SCHEDULING, "scheduling"),
            (CommercialApplicationKey.INVENTORY, "inventory"),
            (CommercialApplicationKey.NARCOTICS, "narcotics"),
            (CommercialApplicationKey.FLEET, "fleet"),
            (CommercialApplicationKey.HEMS, "hems_ops"),
            (CommercialApplicationKey.CORTEX, "cortex"),
            (CommercialApplicationKey.COMMUNICATIONS, "communications"),
            (CommercialApplicationKey.COMPLIANCE, "compliance"),
            (CommercialApplicationKey.ANALYTICS_INTELLIGENCE, "analytics"),
        ],
    )
    def test_reuses_the_existing_canonical_module_id(
        self, application: CommercialApplicationKey, expected_module_id: str
    ) -> None:
        entry = WI_LAUNCH_CATALOG.entries[application]
        assert entry.module_canonical_id == expected_module_id
        assert application.value == expected_module_id

    @pytest.mark.parametrize(
        "application",
        [
            CommercialApplicationKey.QA_CLINICAL_REVIEW,
            CommercialApplicationKey.COMMUNITY_PARAMEDICINE,
            CommercialApplicationKey.PATIENT_PAYMENTS,
            CommercialApplicationKey.THIRD_PARTY_BILLING,
        ],
    )
    def test_genuinely_new_applications_have_no_module_id_yet(
        self, application: CommercialApplicationKey
    ) -> None:
        """These four have no existing module_registry row -- confirmed, not guessed."""

        entry = WI_LAUNCH_CATALOG.entries[application]
        assert entry.module_canonical_id is None
        assert application.value not in MODULE_REGISTRY


class TestSeedPriceMath:
    """Spot-check the founder's Wisconsin launch figures against the annual formula."""

    def test_epcr_lowest_band(self) -> None:
        band = WI_LAUNCH_CATALOG.entries[CommercialApplicationKey.EPCR].bands[0]
        assert band.min_units == 0
        assert band.max_units == 750
        assert band.monthly_price == Decimal("1250")
        assert band.annual_price == Decimal("13500.00")

    def test_epcr_top_band_is_custom_quote(self) -> None:
        band = WI_LAUNCH_CATALOG.entries[CommercialApplicationKey.EPCR].bands[-1]
        assert band.max_units is None
        assert band.custom_quote is True
        assert band.monthly_price is None

    def test_mdt_unit_formula_matches_the_founder_price_list(self) -> None:
        formula = WI_LAUNCH_CATALOG.entries[CommercialApplicationKey.MDT].unit_formula
        assert formula is not None
        assert formula.per_unit_rate == Decimal("125")
        assert formula.minimum_fee == Decimal("750")
        assert formula.base_fee == Decimal("0")

    def test_fleet_unit_formula_matches_the_founder_price_list(self) -> None:
        formula = WI_LAUNCH_CATALOG.entries[CommercialApplicationKey.FLEET].unit_formula
        assert formula is not None
        assert formula.base_fee == Decimal("495")
        assert formula.per_unit_rate == Decimal("59")

    def test_hems_unit_formula_covers_the_first_base_in_the_base_fee(self) -> None:
        formula = WI_LAUNCH_CATALOG.entries[CommercialApplicationKey.HEMS].unit_formula
        assert formula is not None
        assert formula.base_fee == Decimal("3995")
        assert formula.per_unit_rate == Decimal("1995")
        assert formula.included_units == 1

    def test_hospital_bands_are_per_facility_not_marginal(self) -> None:
        entry = WI_LAUNCH_CATALOG.entries[CommercialApplicationKey.HOSPITAL]
        first = entry.bands[0]
        assert first.min_units == 1
        assert first.max_units == 1
        assert first.monthly_price_per_unit == Decimal("1495")
        assert entry.mechanic is PricingMechanic.PER_UNIT_RATE_BY_BRACKET

    def test_third_party_billing_base_fee_covers_five_agencies(self) -> None:
        entry = WI_LAUNCH_CATALOG.entries[CommercialApplicationKey.THIRD_PARTY_BILLING]
        assert entry.base_fee_monthly == Decimal("7500")
        assert entry.included_units == 5
        assert entry.bands[0].min_units == 6

    def test_cortex_is_candidate_pricing_not_published(self) -> None:
        entry = WI_LAUNCH_CATALOG.entries[CommercialApplicationKey.CORTEX]
        assert entry.status is CatalogEntryStatus.CANDIDATE_NOT_APPROVED_FOR_LAUNCH
        assert entry.starting_monthly_prices == (
            Decimal("1995"),
            Decimal("3995"),
            Decimal("7500"),
        )

    def test_communications_has_no_fabricated_usage_rate(self) -> None:
        entry = WI_LAUNCH_CATALOG.entries[CommercialApplicationKey.COMMUNICATIONS]
        assert entry.status is CatalogEntryStatus.USAGE_RATE_CARD_PENDING
        assert entry.base_fee_monthly == Decimal("595")


class TestValidateCatalogCatchesRealDefects:
    """Every check here fails if the defect it targets is reintroduced."""

    def test_rejects_an_unresolvable_module_canonical_id(self) -> None:
        entries = _complete_starting_price_entries()
        entries[CommercialApplicationKey.EPCR] = ApplicationPricingCatalogEntry(
            application=CommercialApplicationKey.EPCR,
            display_name="EPCR",
            mechanic=PricingMechanic.STARTING_PRICE_BANDS_TBD,
            volume_dimension="test",
            module_canonical_id="not_a_real_module",
            starting_monthly_prices=(Decimal("1"),),
        )
        with pytest.raises(ValueError, match="not a canonical id"):
            validate_catalog(_minimal_catalog(entries))

    def test_rejects_a_catalog_missing_an_application(self) -> None:
        entries = _complete_starting_price_entries()
        del entries[CommercialApplicationKey.FLEET]
        with pytest.raises(ValueError, match="missing entries"):
            validate_catalog(_minimal_catalog(entries))

    def test_rejects_an_annual_price_that_does_not_match_the_discount_formula(
        self,
    ) -> None:
        entries = _complete_starting_price_entries()
        entries[CommercialApplicationKey.CAD] = ApplicationPricingCatalogEntry(
            application=CommercialApplicationKey.CAD,
            display_name="CAD",
            mechanic=PricingMechanic.FLAT_VOLUME_BAND,
            volume_dimension="test",
            bands=(
                PricingBand(
                    min_units=0,
                    max_units=100,
                    monthly_price=Decimal("1000"),
                    annual_price=Decimal("9999.99"),
                ),
                PricingBand(min_units=101, max_units=None, custom_quote=True),
            ),
        )
        with pytest.raises(ValueError, match="annual_price does not match"):
            validate_catalog(_minimal_catalog(entries))

    def test_rejects_bands_that_are_not_contiguous(self) -> None:
        entries = _complete_starting_price_entries()
        entries[CommercialApplicationKey.CAD] = ApplicationPricingCatalogEntry(
            application=CommercialApplicationKey.CAD,
            display_name="CAD",
            mechanic=PricingMechanic.FLAT_VOLUME_BAND,
            volume_dimension="test",
            bands=(
                PricingBand(
                    min_units=0,
                    max_units=100,
                    monthly_price=Decimal("1000"),
                    annual_price=Decimal("10800.00"),
                ),
                # gap: skips 101-149
                PricingBand(min_units=150, max_units=None, custom_quote=True),
            ),
        )
        with pytest.raises(ValueError, match="not contiguous"):
            validate_catalog(_minimal_catalog(entries))

    def test_rejects_a_custom_quote_band_that_also_carries_a_price(self) -> None:
        entries = _complete_starting_price_entries()
        entries[CommercialApplicationKey.CAD] = ApplicationPricingCatalogEntry(
            application=CommercialApplicationKey.CAD,
            display_name="CAD",
            mechanic=PricingMechanic.FLAT_VOLUME_BAND,
            volume_dimension="test",
            bands=(
                PricingBand(
                    min_units=0,
                    max_units=None,
                    monthly_price=Decimal("1000"),
                    annual_price=Decimal("10800.00"),
                    custom_quote=True,
                ),
            ),
        )
        with pytest.raises(ValueError, match="must carry no price"):
            validate_catalog(_minimal_catalog(entries))

    def test_rejects_a_base_plus_per_unit_entry_with_no_formula(self) -> None:
        entries = _complete_starting_price_entries()
        entries[CommercialApplicationKey.FLEET] = ApplicationPricingCatalogEntry(
            application=CommercialApplicationKey.FLEET,
            display_name="Fleet",
            mechanic=PricingMechanic.BASE_PLUS_PER_UNIT,
            volume_dimension="test",
        )
        with pytest.raises(ValueError, match="requires unit_formula"):
            validate_catalog(_minimal_catalog(entries))

    def test_rejects_a_dependency_on_an_unregistered_application(self) -> None:
        from adaptix_contracts.commercial.pricing_catalog import ApplicationDependency

        entries = _complete_starting_price_entries()
        catalog = CommercialPricingCatalog(
            catalog_version="test",
            effective_date=date(2026, 1, 1),
            jurisdiction="US-WI",
            entries=MappingProxyType(entries),
            dependencies=(
                ApplicationDependency(
                    application=CommercialApplicationKey.CAD,
                    requires=frozenset({CommercialApplicationKey.CAD}),
                    reason="self-dependency, must be rejected",
                ),
            ),
        )
        with pytest.raises(ValueError, match="cannot require itself"):
            validate_catalog(catalog)

    def test_accepts_a_fully_valid_minimal_catalog(self) -> None:
        validate_catalog(_minimal_catalog(_complete_starting_price_entries()))


def test_unit_rate_formula_never_fabricates_an_unspecified_custom_quote_threshold() -> (
    None
):
    """HEMS 'large multi-base = custom' named no number; none may be invented here."""

    hems_formula = WI_LAUNCH_CATALOG.entries[CommercialApplicationKey.HEMS].unit_formula
    assert hems_formula is not None
    assert hems_formula.custom_quote_above_units is None


def test_pricing_catalog_module_declares_no_calculation_engine() -> None:
    """Contracts is a shape-only package; the engine lives in Billing-Service."""

    import adaptix_contracts.commercial.pricing_catalog as pricing_catalog_module

    for forbidden in ("compute_price", "calculate_price", "get_price", "quote"):
        assert not hasattr(pricing_catalog_module, forbidden)


class TestUnitRateFormulaShape:
    def test_the_formula_dataclass_is_frozen(self) -> None:
        formula = UnitRateFormula(per_unit_rate=Decimal("1"))
        with pytest.raises(Exception):  # noqa: B017 - dataclasses.FrozenInstanceError
            formula.per_unit_rate = Decimal("2")  # type: ignore[misc]
