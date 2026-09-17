"""INTELLIGENCE domain applications.

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

INTELLIGENCE_APPLICATIONS: tuple[ApplicationDefinition, ...] = (
    _app(
        "intelligence_analytics",
        "Intelligence & Analytics",
        "Reports, analytics and the governed natural-language console (Ask AdaptixCore).",
        domain=ApplicationDomain.INTELLIGENCE,
        canonical_route="/workspace/reports",
        primary_services=("adaptix-analytics",),
        supporting_services=("adaptix-graph", "adaptix-core"),
        workspaces=(
            _ws(
                "analytics", "Analytics", "/workspace/analytics", modules=("analytics",)
            ),
            _ws("ask", "Ask AdaptixCore", "/workspace/ask", modules=("intelligence",)),
            _ws(
                "intelligence",
                "Cortex Intelligence",
                "/workspace/intelligence",
                modules=("intelligence",),
            ),
        ),
        source=(
            f"{_WEB} (reports reads /api/v1/reports + cross-module report "
            "prefixes; analytics reads /api/v1/analytics x64 + graph; ask carries "
            f"its own ModuleGate 'intelligence'); {_GW} /api/v1/reports AND "
            "/api/v1/intelligence -> adaptix-core, /api/v1/analytics -> "
            "adaptix-analytics, /api/v1/graph -> adaptix-graph. The root is "
            "Reports because it is served by Core and reachable by every tenant; "
            "Analytics is a workspace behind the sold 'analytics' module (its "
            "backend mints no audience without it, so an ungated entry would be a "
            "control that can only fail)."
        ),
    ),
)
