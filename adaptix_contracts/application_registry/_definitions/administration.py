"""ADMINISTRATION domain applications.

See ``_definitions/__init__.py`` for the evidence rules every entry obeys.
"""

from __future__ import annotations

from adaptix_contracts.application_registry._definitions.shorthand import _GW, _WEB
from adaptix_contracts.application_registry._model import (
    ApplicationDefinition,
    ApplicationDomain,
    ApplicationStatus,
    ApplicationVisibility,
    _app,
    _ws,
)

ADMINISTRATION_APPLICATIONS: tuple[ApplicationDefinition, ...] = (
    _app(
        "administration",
        "Administration",
        (
            "Organization, users, roles, applications and entitlements, devices, "
            "integrations, imports/exports, onboarding and platform configuration."
        ),
        domain=ApplicationDomain.ADMINISTRATION,
        canonical_route="/workspace/admin",
        visibility=ApplicationVisibility.ADMIN,
        primary_services=("adaptix-core",),
        supporting_services=(
            "adaptix-app-management",
            "adaptix-device",
            "adaptix-integrations",
            "adaptix-hl7",
            "adaptix-imports",
            "adaptix-exports",
            "adaptix-officeally",
        ),
        workspaces=(
            _ws(
                "agency",
                "Agency",
                "/workspace/admin/agency",
                visibility=ApplicationVisibility.ADMIN,
            ),
            _ws(
                "organization",
                "Organization",
                "/workspace/admin/organization",
                visibility=ApplicationVisibility.ADMIN,
            ),
            _ws(
                "api_keys",
                "API Keys",
                "/workspace/api-keys",
                visibility=ApplicationVisibility.ADMIN,
            ),
            _ws(
                "integrations",
                "Integrations",
                "/workspace/integrations",
                visibility=ApplicationVisibility.ADMIN,
            ),
            _ws(
                "hl7",
                "HL7 Interface Engine",
                "/workspace/hl7",
                visibility=ApplicationVisibility.ADMIN,
            ),
            _ws(
                "interop",
                "Interop",
                "/workspace/interop",
                visibility=ApplicationVisibility.ADMIN,
            ),
            _ws(
                "interoperability",
                "Interoperability",
                "/workspace/interoperability",
                visibility=ApplicationVisibility.ADMIN,
            ),
            _ws(
                "devices",
                "Devices",
                "/workspace/device",
                modules=("device",),
                visibility=ApplicationVisibility.ADMIN,
            ),
            _ws(
                "onboarding",
                "Onboarding",
                "/workspace/onboarding",
                visibility=ApplicationVisibility.ADMIN,
            ),
            _ws(
                "settings",
                "Settings",
                "/settings",
                visibility=ApplicationVisibility.ADMIN,
            ),
            _ws(
                "ai_administration",
                "AI Administration",
                "/workspace/ai",
                visibility=ApplicationVisibility.ADMIN,
            ),
        ),
        source=(
            f"{_WEB} (admin reads /api/v1/users, core, organization, agency; "
            "api-keys, hl7, integrations, device x51, onboarding x46; "
            "/workspace/ai surfaces founder-command AI telemetry with no gate of "
            f"its own, so it stays ADMIN); {_GW} /api/v1/admin, agency, users, "
            "api-keys, onboarding -> adaptix-core; /api/v1/app-management, device, "
            "integrations, hl7, imports, exports, officeally -> their own "
            "audiences. /workspace/interop and /workspace/interoperability are "
            "both real pages today; consolidating them is Web-App work, not a "
            "registry decision. Office Ally lives here as a historical import "
            "adapter, never as a billing path."
        ),
    ),
    _app(
        "demos",
        "Demos",
        "Founder / development demo launcher. Not a production application.",
        domain=ApplicationDomain.ADMINISTRATION,
        status=ApplicationStatus.EXPERIMENTAL,
        canonical_route="/workspace/demos",
        visibility=ApplicationVisibility.FOUNDER,
        source=(
            f"{_WEB} (app/workspace/demos/page.tsx links founder-command demo "
            "surfaces; no backend calls). Listed so status enforcement has a "
            "real EXPERIMENTAL entry to exclude from customer navigation."
        ),
    ),
)
