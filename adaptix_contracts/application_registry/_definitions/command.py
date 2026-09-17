"""COMMAND domain applications.

See ``_definitions/__init__.py`` for the evidence rules every entry obeys.
"""

from __future__ import annotations

from adaptix_contracts.application_registry._definitions.shorthand import _FC, _GW, _WEB
from adaptix_contracts.application_registry._model import (
    ApplicationDefinition,
    ApplicationDomain,
    ApplicationVisibility,
    _app,
    _ws,
)

COMMAND_APPLICATIONS: tuple[ApplicationDefinition, ...] = (
    _app(
        "founder_command",
        "Founder Command",
        "Run the AdaptixCore company and supervise the platform from one place.",
        domain=ApplicationDomain.COMMAND,
        canonical_route=_FC,
        visibility=ApplicationVisibility.FOUNDER,
        primary_services=("adaptix-founder",),
        supporting_services=(
            "adaptix-core",
            "adaptix-billing",
            "adaptix-calendar",
            "adaptix-investor",
            "adaptix-nemsis",
        ),
        clients=("Adaptix-Android-Founder-Command",),
        workspaces=(
            _ws(
                "war_room",
                "War Room",
                f"{_FC}/war-room",
                visibility=ApplicationVisibility.FOUNDER,
            ),
            _ws(
                "agencies",
                "Agencies",
                f"{_FC}/agencies",
                visibility=ApplicationVisibility.FOUNDER,
            ),
            _ws(
                "dispatch_outages",
                "Dispatch Outages",
                f"{_FC}/dispatch-outages",
                visibility=ApplicationVisibility.FOUNDER,
            ),
            _ws(
                "revenue",
                "Revenue",
                f"{_FC}/revenue",
                visibility=ApplicationVisibility.FOUNDER,
            ),
            _ws(
                "finance_ledger",
                "Finance Ledger",
                f"{_FC}/finance/ledger",
                visibility=ApplicationVisibility.FOUNDER,
            ),
            _ws(
                "profit_and_loss",
                "P&L",
                f"{_FC}/finance/p-and-l",
                visibility=ApplicationVisibility.FOUNDER,
            ),
            _ws(
                "statements",
                "Statements",
                f"{_FC}/finance/revenue",
                visibility=ApplicationVisibility.FOUNDER,
            ),
            _ws(
                "investors",
                "Investors",
                f"{_FC}/investors",
                visibility=ApplicationVisibility.FOUNDER,
            ),
            _ws(
                "infrastructure",
                "AWS Infrastructure Health",
                f"{_FC}/platform/infrastructure",
                visibility=ApplicationVisibility.FOUNDER,
            ),
            _ws(
                "platform_health",
                "Platform Health",
                f"{_FC}/platform/health",
                visibility=ApplicationVisibility.FOUNDER,
            ),
            _ws(
                "tenant_readiness",
                "Tenant Readiness",
                f"{_FC}/platform/tenant-readiness",
                visibility=ApplicationVisibility.FOUNDER,
            ),
            _ws(
                "realtime",
                "Realtime Status",
                f"{_FC}/realtime",
                visibility=ApplicationVisibility.FOUNDER,
            ),
            _ws(
                "sandbox",
                "Founder Sandbox",
                f"{_FC}/sandbox",
                visibility=ApplicationVisibility.FOUNDER,
            ),
            _ws(
                "qa_testing",
                "QA & Testing",
                f"{_FC}/qa",
                visibility=ApplicationVisibility.FOUNDER,
            ),
            _ws(
                "social_command",
                "Social Command",
                f"{_FC}/social",
                visibility=ApplicationVisibility.FOUNDER,
            ),
            _ws(
                "video_studio",
                "Video Studio",
                f"{_FC}/video-studio",
                visibility=ApplicationVisibility.FOUNDER,
            ),
            _ws(
                "cad_command",
                "CAD Command",
                f"{_FC}/cad",
                visibility=ApplicationVisibility.FOUNDER,
            ),
            _ws(
                "fire_command",
                "Fire Command",
                f"{_FC}/fire",
                visibility=ApplicationVisibility.FOUNDER,
            ),
            _ws(
                "air_command",
                "Air Command",
                f"{_FC}/air",
                visibility=ApplicationVisibility.FOUNDER,
            ),
        ),
        source=(
            f"{_WEB}; {_GW} /api/v1/founder-command -> adaptix-founder + core, "
            "billing, calendar, investor, nemsis; ModuleSwitcher 'Founder' bucket "
            "(20 rows, all founderOnly) — those rows are internal workspaces here"
        ),
    ),
    _app(
        "operations_command",
        "Operations Command",
        "Cross-domain operational oversight: live calls, units, hospitals and revenue signals on one board.",
        domain=ApplicationDomain.COMMAND,
        canonical_route="/workspace/mission-control",
        modules=("cad", "hospital", "billing", "air"),
        aggregates=("cad", "hospital_facility_operations", "billing", "air_operations"),
        supporting_services=(
            "adaptix-cad",
            "adaptix-hospital",
            "adaptix-billing",
            "adaptix-air",
        ),
        source=(
            f"{_WEB}; src/lib/api/missionControl.ts reads /api/v1/cad/units, "
            "/api/v1/cad/incidents, /api/v1/hospital/hospitals, "
            "/api/v1/billing/cortex/insights, /api/v1/billing/revenue/command, "
            "/api/v1/air/adsb/bbox — an aggregation surface that owns no domain "
            "records, so it declares `aggregates` instead of a primary service. "
            "Offered when the tenant holds ANY aggregated product. Deliberately "
            "has no workspaces: it is one board (app/workspace/mission-control/"
            "page.tsx is the only page), not a family of surfaces."
        ),
    ),
)
