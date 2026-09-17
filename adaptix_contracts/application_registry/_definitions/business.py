"""BUSINESS domain applications.

See ``_definitions/__init__.py`` for the evidence rules every entry obeys.
"""

from __future__ import annotations

from adaptix_contracts.application_registry._definitions.shorthand import _GW, _WEB
from adaptix_contracts.application_registry._model import (
    ApplicationDefinition,
    ApplicationDomain,
    ApplicationVisibility,
    _app,
    _ws,
)

BUSINESS_APPLICATIONS: tuple[ApplicationDefinition, ...] = (
    _app(
        "business_operations",
        "Business Operations",
        "Internal commercial work: CRM, customer success, partners, marketing, support and office operations.",
        domain=ApplicationDomain.BUSINESS,
        canonical_route="/workspace/crm",
        visibility=ApplicationVisibility.ADMIN,
        primary_services=("adaptix-crm",),
        supporting_services=(
            "adaptix-customer-success",
            "adaptix-partner",
            "adaptix-marketing",
            "adaptix-office",
        ),
        workspaces=(
            _ws("crm", "CRM", "/workspace/crm", visibility=ApplicationVisibility.ADMIN),
            _ws(
                "support",
                "Support",
                "/workspace/support",
                visibility=ApplicationVisibility.ADMIN,
            ),
        ),
        source=(
            f"{_WEB} (app/workspace/crm reads /api/v1/crm x124 + "
            "/api/v1/marketing x9; app/workspace/support); "
            f"{_GW} /api/v1/crm -> adaptix-crm, customer-success, partner, "
            "marketing, office each -> their own audience. Customer Success, "
            "Partner, Marketing and Office have no web surface of their own on "
            "main; they are services this application will host as workspaces. "
            "Visibility stays ADMIN because both rows were admin-only before."
        ),
    ),
)
