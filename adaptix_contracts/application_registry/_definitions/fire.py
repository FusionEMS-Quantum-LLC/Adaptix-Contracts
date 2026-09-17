"""FIRE domain applications.

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

FIRE_APPLICATIONS: tuple[ApplicationDefinition, ...] = (
    _app(
        "fire_operations",
        "Fire Operations",
        "Fire incidents, apparatus, stations, hydrants, preplans, inspections and NERIS reporting.",
        domain=ApplicationDomain.FIRE,
        canonical_route="/workspace/fire",
        modules=("fire",),
        primary_services=("adaptix-fire",),
        supporting_services=("adaptix-neris",),
        clients=("Adaptix-Android-Fire",),
        workspaces=(
            _ws("incidents", "Incidents", "/workspace/fire/incidents"),
            _ws("apparatus", "Apparatus", "/workspace/fire/apparatus"),
            _ws("stations", "Stations", "/workspace/fire/stations"),
            _ws("personnel", "Personnel", "/workspace/fire/personnel"),
            _ws("unit_status", "Unit Status", "/workspace/fire/unit-status"),
            _ws("hydrants", "Hydrants", "/workspace/fire/hydrants"),
            _ws(
                "hydrant_registry",
                "Hydrant Registry",
                "/workspace/fire/hydrant-registry",
            ),
            _ws(
                "hydrant_flow_tests",
                "Hydrant Flow Tests",
                "/workspace/fire/hydrant-flow-tests",
            ),
            _ws("preplans", "Preplans", "/workspace/fire/preplans"),
            _ws("inspections", "Inspections", "/workspace/fire/inspections"),
            _ws("occupancies", "Occupancies", "/workspace/fire/occupancies"),
            _ws("hazards", "Hazards", "/workspace/fire/hazards"),
            _ws("neris", "NERIS", "/workspace/fire/neris"),
            _ws(
                "response_timeline",
                "Response Timeline",
                "/workspace/fire/response-timeline",
            ),
            _ws("cad_connect", "CAD Connect", "/workspace/fire/cad-connect"),
            _ws("code_library", "Code Library", "/workspace/fire/code-library"),
            _ws("enforcement", "Enforcement", "/workspace/fire/enforcement"),
            _ws("notices", "Notices", "/workspace/fire/notices"),
            _ws(
                "station_alerting",
                "Station Alerting",
                "/workspace/fire/station-alerting",
            ),
            _ws("settings", "Settings", "/workspace/fire/settings"),
        ),
        source=(
            f"{_WEB}; {_GW} /api/v1/fire -> adaptix-fire, /api/v1/neris -> "
            "adaptix-neris. Preplan, Hydrant and Wildland services are NOT "
            "gateway-routed (no /api/v1/preplan|hydrant|wildland RouteEntry; "
            "Preplan-Service has no ECS footprint per PREPLAN-SERVICE-NOT-DEPLOYED), "
            "so their surfaces here are served by Fire-Service and they are not "
            "listed as supporting services until they are routed."
        ),
    ),
    _app(
        "community_risk_reduction",
        "Community Risk Reduction",
        "Risk assessments, households, campaigns, interventions and outcomes for community risk reduction.",
        domain=ApplicationDomain.FIRE,
        canonical_route="/workspace/fire/crr",
        modules=("crr",),
        primary_services=("adaptix-fire",),
        workspaces=(
            _ws("iso_package", "ISO Package", "/workspace/fire/crr/iso-package"),
        ),
        source=(
            f"{_WEB} (app/workspace/fire/crr is the only CRR surface); {_GW} "
            "/api/v1/crr -> adaptix-fire; module_registry crr (audience "
            "adaptix-fire, implies fire). Adaptix-CRR-Service has no gateway "
            "audience yet. CRR is a distinct job with its own purchasable module, "
            "so it is a separate application whose root currently lives under the "
            "Fire route tree; route ownership resolves by longest prefix."
        ),
    ),
)
