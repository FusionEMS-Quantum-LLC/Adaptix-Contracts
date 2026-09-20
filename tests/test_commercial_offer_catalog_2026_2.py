"""WI-LAUNCH-2026.2 adds Platform Cortex Core and supporting grants.

2026.1 stays the locked price list. This version changes only identity and
Platform grants: ``ai`` (Cortex Core), ``forms``, ``facilities``, ``graph``,
and ``patient_identity``. It must never grant founder-only ``cortex``.
"""

from __future__ import annotations

from adaptix_contracts.commercial.offer_catalogs import (
    COMMERCIAL_OFFER_CATALOGS,
    CURRENT_OFFER_CATALOG,
    export_offer_catalogs,
    get_offer_catalog,
)
from adaptix_contracts.commercial.wi_launch_2026_1 import WI_LAUNCH_2026_1
from adaptix_contracts.commercial.wi_launch_2026_2 import WI_LAUNCH_2026_2
from adaptix_contracts.module_registry import resolve_module_id

_FOUNDATION = frozenset(
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
)
_CORTEX_CORE_AND_SUPPORTING = frozenset(
    {
        "ai",
        "forms",
        "facilities",
        "graph",
        "patient_identity",
    }
)


class TestWiLaunch20262:
    def test_is_current_and_carried(self) -> None:
        assert CURRENT_OFFER_CATALOG is WI_LAUNCH_2026_2
        assert get_offer_catalog("WI-LAUNCH-2026.2") is WI_LAUNCH_2026_2
        assert COMMERCIAL_OFFER_CATALOGS["WI-LAUNCH-2026.1"] is WI_LAUNCH_2026_1

    def test_supersedes_2026_1_without_rewriting_it(self) -> None:
        assert WI_LAUNCH_2026_2.catalog_version == "WI-LAUNCH-2026.2"
        assert WI_LAUNCH_2026_2.supersedes == "WI-LAUNCH-2026.1"
        assert WI_LAUNCH_2026_1.catalog_version == "WI-LAUNCH-2026.1"
        assert WI_LAUNCH_2026_1.supersedes == "wi-launch-v1"
        assert WI_LAUNCH_2026_1.platform_grants_modules == _FOUNDATION
        assert "ai" not in WI_LAUNCH_2026_1.platform_grants_modules
        assert "cortex" not in WI_LAUNCH_2026_1.platform_grants_modules

    def test_prices_and_offers_are_the_2026_1_list(self) -> None:
        assert WI_LAUNCH_2026_2.platform_plans == WI_LAUNCH_2026_1.platform_plans
        assert WI_LAUNCH_2026_2.offers == WI_LAUNCH_2026_1.offers
        assert WI_LAUNCH_2026_2.packages == WI_LAUNCH_2026_1.packages
        assert WI_LAUNCH_2026_2.terms == WI_LAUNCH_2026_1.terms
        assert WI_LAUNCH_2026_2.jurisdiction == WI_LAUNCH_2026_1.jurisdiction
        assert WI_LAUNCH_2026_2.currency == WI_LAUNCH_2026_1.currency

    def test_platform_grants_cortex_core_and_supporting_modules(self) -> None:
        granted = WI_LAUNCH_2026_2.platform_grants_modules
        assert granted == _FOUNDATION | _CORTEX_CORE_AND_SUPPORTING
        assert "cortex" not in granted
        for module_id in _CORTEX_CORE_AND_SUPPORTING:
            assert resolve_module_id(module_id) == module_id

    def test_package_entitlements_include_the_new_platform_grants(self) -> None:
        for package in WI_LAUNCH_2026_2.packages.values():
            expected = set(WI_LAUNCH_2026_2.platform_grants_modules)
            for offer_id in package.includes_offers:
                expected |= WI_LAUNCH_2026_2.offer(offer_id).grants_modules
            assert WI_LAUNCH_2026_2.package_entitlements(package.package_id) == expected
            assert _CORTEX_CORE_AND_SUPPORTING <= expected
            assert "cortex" not in expected

    def test_export_names_current_version(self) -> None:
        exported = export_offer_catalogs(contracts_version="0")
        assert exported["current_catalog_version"] == "WI-LAUNCH-2026.2"
        versions = [record["catalog_version"] for record in exported["catalogs"]]
        assert versions == ["WI-LAUNCH-2026.1", "WI-LAUNCH-2026.2"]
        current = next(
            record
            for record in exported["catalogs"]
            if record["catalog_version"] == "WI-LAUNCH-2026.2"
        )
        assert set(current["platform"]["grants_modules"]) == set(
            WI_LAUNCH_2026_2.platform_grants_modules
        )
