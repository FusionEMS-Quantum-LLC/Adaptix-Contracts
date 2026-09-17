"""GOVERNANCE domain applications.

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

GOVERNANCE_APPLICATIONS: tuple[ApplicationDefinition, ...] = (
    _app(
        "governance",
        "Governance",
        "Compliance, documents, policies, legal and audit evidence.",
        domain=ApplicationDomain.GOVERNANCE,
        canonical_route="/workspace/compliance",
        modules=("compliance", "documents"),
        primary_services=("adaptix-compliance", "adaptix-documents"),
        supporting_services=(
            "adaptix-policy",
            "adaptix-legal",
            "adaptix-audit",
            "adaptix-forms",
        ),
        workspaces=(
            _ws(
                "documents", "Documents", "/workspace/documents", modules=("documents",)
            ),
            # Core-served (/api/v1/admin) and admin-only; stated as the
            # umbrella's own gate so the any-of is explicit, not inherited.
            _ws(
                "audit_logs",
                "Audit Logs",
                "/workspace/audit-logs",
                modules=("compliance", "documents"),
                visibility=ApplicationVisibility.ADMIN,
            ),
        ),
        source=(
            f"{_WEB} (compliance reads /api/v1/compliance x205; documents reads "
            "/api/v1/forms x68 + /api/v1/documents x36; audit-logs reads "
            f"/api/v1/admin); {_GW} /api/v1/compliance -> adaptix-compliance (+ "
            "core), /api/v1/documents -> adaptix-documents, /api/v1/policy, "
            "/api/v1/legal, /api/v1/audit, /api/v1/forms -> their own audiences. "
            "Audit-Service is a capability this application reads; it is not the "
            "application."
        ),
    ),
)
