"""LOGISTICS domain applications.

See ``_definitions/__init__.py`` for the evidence rules every entry obeys.
"""

from __future__ import annotations

from adaptix_contracts.application_registry._definitions.shorthand import _GW, _WEB
from adaptix_contracts.application_registry._model import (
    ApplicationDefinition,
    ApplicationDomain,
    _app,
    _ws,
)

LOGISTICS_APPLICATIONS: tuple[ApplicationDefinition, ...] = (
    _app(
        "asset_operations",
        "Asset Operations",
        "Physical operational assets: fleet, inventory, medications, narcotics, work orders, purchasing and audits.",
        domain=ApplicationDomain.LOGISTICS,
        canonical_route="/workspace/operations",
        modules=("assetops", "fleet", "inventory", "medications", "narcotics"),
        primary_services=("adaptix-assetops",),
        supporting_services=(
            "adaptix-fleet",
            "adaptix-inventory",
            "adaptix-medications",
            "adaptix-narcotics",
        ),
        clients=("Adaptix-Android-Inventory", "Adaptix-Android-Narcotics"),
        workspaces=(
            _ws(
                "asset_register",
                "Asset Register",
                "/workspace/operations/asset-register",
                modules=("assetops",),
            ),
            _ws("dvir", "DVIR", "/workspace/operations/dvir", modules=("assetops",)),
            _ws(
                "work_orders",
                "Work Orders",
                "/workspace/operations/work-orders",
                modules=("assetops",),
            ),
            _ws(
                "purchase_orders",
                "Purchase Orders",
                "/workspace/operations/purchase-orders",
                modules=("assetops",),
            ),
            _ws(
                "vendors",
                "Vendors",
                "/workspace/operations/vendors",
                modules=("assetops",),
            ),
            _ws(
                "audit_cycles",
                "Audit Cycles",
                "/workspace/operations/audit-cycles",
                modules=("assetops",),
            ),
            _ws(
                "cost_analytics",
                "Cost Analytics",
                "/workspace/operations/analytics",
                modules=("assetops",),
            ),
            _ws("fleet", "Fleet", "/workspace/fleet", modules=("fleet",)),
            _ws(
                "inventory", "Inventory", "/workspace/inventory", modules=("inventory",)
            ),
            _ws(
                "medications",
                "Medications",
                "/workspace/medications",
                modules=("medications",),
            ),
            _ws(
                "narcotics", "Narcotics", "/workspace/narcotics", modules=("narcotics",)
            ),
            _ws(
                "narcotics_vault",
                "Vault Inventory",
                "/workspace/narcotics/inventory",
                modules=("narcotics",),
            ),
            _ws(
                "narcotics_par_levels",
                "Par Levels",
                "/workspace/narcotics/par-levels",
                modules=("narcotics",),
            ),
            _ws(
                "narcotics_chain_of_custody",
                "Chain of Custody",
                "/workspace/narcotics/chain-of-custody",
                modules=("narcotics",),
            ),
            _ws(
                "narcotics_witness",
                "Witness",
                "/workspace/narcotics/witness",
                modules=("narcotics",),
            ),
            _ws(
                "narcotics_waste",
                "Waste",
                "/workspace/narcotics/waste",
                modules=("narcotics",),
            ),
            _ws(
                "narcotics_discrepancies",
                "Discrepancies",
                "/workspace/narcotics/discrepancies",
                modules=("narcotics",),
            ),
        ),
        source=(
            f"{_WEB} (app/workspace/operations/page.tsx: 'AdaptixCore-AssetOps "
            "hub', reads /api/v1/assetops x37); "
            f"{_GW} /api/v1/assetops -> adaptix-assetops, /api/v1/fleet -> "
            "adaptix-fleet, /api/v1/inventory -> adaptix-inventory, "
            "/api/v1/medications -> adaptix-medications, /api/v1/narcotics -> "
            "adaptix-narcotics. AssetOps orchestrates; each domain service keeps "
            "its own truth (no second inventory, narcotics log or vehicle "
            "registry). Device management is Administration's, referenced here."
        ),
    ),
)
