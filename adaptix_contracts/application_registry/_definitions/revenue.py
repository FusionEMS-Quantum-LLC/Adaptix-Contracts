"""REVENUE domain applications.

See ``_definitions/__init__.py`` for the evidence rules every entry obeys.
"""

from __future__ import annotations

from adaptix_contracts.application_registry._definitions.shorthand import _GW, _WEB
from adaptix_contracts.application_registry._model import (
    ApplicationDefinition,
    ApplicationDomain,
    PortalDefinition,
    _app,
    _ws,
)

REVENUE_APPLICATIONS: tuple[ApplicationDefinition, ...] = (
    _app(
        "billing",
        "Billing",
        (
            "EMS revenue cycle: eligibility, coding, claims, clearinghouse, "
            "remittance, denials, appeals and patient balances."
        ),
        domain=ApplicationDomain.REVENUE,
        canonical_route="/workspace/billing",
        modules=("billing",),
        primary_services=("adaptix-billing",),
        supporting_services=("adaptix-payments", "adaptix-trustsign"),
        portals=(
            PortalDefinition(
                portal_id="agency_billing_portal",
                display_name="Agency Billing Portal",
                entry_route="/billing/portal",
                audience="billing_operator",
            ),
            PortalDefinition(
                portal_id="patient_billing_portal",
                display_name="Patient Billing Portal",
                entry_route="/patient-portal",
                audience="patient",
            ),
        ),
        workspaces=(
            _ws("work_queue", "Work Queue", "/workspace/billing/work-queue"),
            _ws("claims", "Claims", "/workspace/billing/claims"),
            _ws("eligibility", "Eligibility", "/workspace/billing/eligibility"),
            _ws("clearinghouse", "Clearinghouse", "/workspace/billing/clearinghouse"),
            _ws("stedi", "Stedi", "/workspace/billing/stedi"),
            _ws("era", "ERA / 835", "/workspace/billing/era"),
            _ws("eob_posting", "EOB Posting", "/workspace/billing/eob-posting"),
            _ws("denials", "Denials", "/workspace/billing/denials"),
            _ws("appeals", "Appeals", "/workspace/billing/appeals"),
            _ws("resubmissions", "Resubmissions", "/workspace/billing/resubmissions"),
            _ws("underpayments", "Underpayments", "/workspace/billing/underpayments"),
            _ws("accounts_receivable", "A/R", "/workspace/billing/ar"),
            _ws("patients", "Patient Balances", "/workspace/billing/patients"),
            _ws("statements", "Statements", "/workspace/billing/statements"),
            _ws("payers", "Payers", "/workspace/billing/payers"),
            _ws(
                "cms1500_studio", "CMS-1500 Studio", "/workspace/billing?section=studio"
            ),
            _ws("readiness", "Go-Live Readiness", "/workspace/billing/readiness"),
            _ws("imports", "Imports", "/workspace/billing/imports"),
            _ws("migration", "Migration", "/workspace/billing/migration"),
            _ws("integrations", "Integrations", "/workspace/billing/integrations"),
            _ws(
                "intelligence",
                "Revenue Intelligence",
                "/workspace/billing/intelligence",
            ),
            _ws("revenue", "Revenue", "/workspace/billing/revenue"),
            _ws(
                "subscription",
                "Subscription",
                "/workspace/billing/settings/subscription",
            ),
        ),
        source=(
            f"{_WEB}; {_GW} /api/v1/billing -> adaptix-billing (+ core), "
            "/api/v1/payments -> adaptix-payments, /api/v1/trustsign -> "
            "adaptix-trustsign. Patient/claim receivables live HERE, never in "
            "Finance. Office Ally is a migration-only adapter and belongs to "
            "Administration imports, not to Billing's live path (Stedi is the "
            "only live clearinghouse)."
        ),
    ),
    _app(
        "finance",
        "Finance",
        "Company financial management: ledger, P&L, budgets, expenses and corporate receivables.",
        domain=ApplicationDomain.REVENUE,
        canonical_route="/workspace/finance",
        modules=("finance",),
        primary_services=("adaptix-finance",),
        workspaces=(_ws("ledger", "General Ledger", "/workspace/finance/ledger"),),
        source=(
            f"{_WEB}; {_GW} /api/v1/finance -> adaptix-finance. Company/"
            "accounting A/R only — patient/claim A/R is Billing's."
        ),
    ),
)
