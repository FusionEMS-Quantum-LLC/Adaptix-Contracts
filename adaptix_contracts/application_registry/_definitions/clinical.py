"""CLINICAL domain applications.

See ``_definitions/__init__.py`` for the evidence rules every entry obeys.
"""

from __future__ import annotations

from adaptix_contracts.application_registry._definitions.shorthand import _GW, _WEB
from adaptix_contracts.application_registry._model import (
    ApplicationDefinition,
    ApplicationDomain,
    ApplicationStatus,
    _app,
    _ws,
)

CLINICAL_APPLICATIONS: tuple[ApplicationDefinition, ...] = (
    _app(
        "epcr",
        "ePCR",
        "Document, validate, sign and submit the patient care record.",
        domain=ApplicationDomain.CLINICAL,
        canonical_route="/workspace/epcr",
        modules=("epcr",),
        primary_services=("adaptix-epcr",),
        supporting_services=(
            "adaptix-nemsis",
            "adaptix-patient-identity",
            "adaptix-trustsign",
        ),
        clients=("Adaptix-Android-EPCR",),
        workspaces=(
            _ws("charts", "Charts", "/workspace/epcr/charts"),
            _ws("new_chart", "New Chart", "/workspace/epcr/charts/new"),
            _ws("my_work", "My Work", "/workspace/epcr/my-work"),
            _ws("worklist", "Worklist", "/workspace/epcr/worklist"),
            _ws("queue", "Queue", "/workspace/epcr/queue"),
            _ws("validation", "Validation", "/workspace/epcr/validation"),
            _ws("sign", "Signatures", "/workspace/epcr/sign"),
            _ws("amendments", "Amendments", "/workspace/epcr/amendments"),
            _ws("submissions", "Submissions", "/workspace/epcr/submissions"),
            _ws("qa", "QA", "/workspace/epcr/qa"),
            _ws("reports", "Reports", "/workspace/epcr/reports"),
            _ws("analytics", "Analytics", "/workspace/epcr/analytics"),
            _ws(
                "interoperability",
                "Interoperability",
                "/workspace/epcr/interoperability",
            ),
            _ws("settings", "Settings", "/workspace/epcr/settings"),
        ),
        source=f"{_WEB}; {_GW} /api/v1/epcr -> adaptix-epcr; module_registry epcr",
    ),
    _app(
        "mih_community_paramedicine",
        "MIH / Community Paramedicine",
        "Mobile integrated healthcare: enrolled people, programs, visits, escalations and follow-up.",
        domain=ApplicationDomain.CLINICAL,
        canonical_route="/workspace/mih",
        modules=("mih_community_paramedicine",),
        primary_services=("adaptix-mih",),
        source=(
            f"{_WEB} (layout gates module 'mih_community_paramedicine'; "
            "_components read /api/v1/mih/escalations, /thresholds, "
            "/utilization via useModuleData — real data binding, no placeholders); "
            "gateway mih_route.py -> adaptix-mih; production "
            "GET /api/v1/mih/healthz 200 on 2026-09-17. Runtime operator journey "
            "not yet proven by this registry — status reflects route, gate and "
            "live backend, not Tier-5 evidence."
        ),
    ),
    _app(
        "clinical_quality",
        "Clinical Quality",
        "Chart review, peer review, medical-director oversight and quality-improvement trends.",
        domain=ApplicationDomain.CLINICAL,
        canonical_route="/quality",
        modules=("epcr",),
        primary_services=("adaptix-epcr",),
        supporting_services=("adaptix-qa",),
        workspaces=(
            _ws("qa", "QA", "/quality/qa"),
            _ws("qa_cases", "Cases", "/quality/qa/cases"),
            _ws("peer_review", "Peer Review", "/quality/qa/peer-review"),
            _ws("triggers", "Triggers", "/quality/qa/triggers"),
            _ws("chart_review", "Chart Review", "/quality/qa/chart"),
            _ws("medical_director", "Medical Director", "/quality/medical-director"),
            _ws(
                "review_queue", "Review Queue", "/quality/medical-director/review-queue"
            ),
            _ws("protocols", "Protocols", "/quality/medical-director/protocols"),
            _ws("variances", "Variances", "/quality/medical-director/variances"),
            _ws("qi", "Quality Improvement", "/quality/qi"),
            _ws("initiatives", "Initiatives", "/quality/qi/initiatives"),
            _ws("trends", "Trends", "/quality/qi/trends"),
            _ws("accreditation", "Accreditation", "/quality/qi/accreditation"),
        ),
        source=(
            f"{_WEB} (app/quality reads /api/v1/quality x17 and /api/v1/epcr x12; "
            "routes registry gates /quality on the epcr entitlement — there is no "
            f"'quality' module id); {_GW} /api/v1/quality AND /api/v1/qa -> "
            "adaptix-epcr. Adaptix-QA-Service (adaptix-qa) consumes finalized-"
            "chart events; it is not the surface's routed backend."
        ),
    ),
    _app(
        "cct",
        "Critical Care Transport",
        "Critical care transport operations. Backend contracts exist; no operator surface is offered yet.",
        domain=ApplicationDomain.CLINICAL,
        status=ApplicationStatus.DEFERRED,
        canonical_route=None,
        source=(
            f"No app/ route on {_WEB}; {_GW} routes no /api/v1/cct prefix "
            "(adaptix-cct is a declared audience only); production "
            "GET /api/v1/cct/healthz -> 401 at the gateway edge. "
            "module_registry cct_transport_ops is a Stripe bundle marker, not an "
            "application entitlement. Activation requires route, gateway route, "
            "server authorization, deployment and runtime proof."
        ),
    ),
    _app(
        "citizen_patient",
        "Citizen / Patient",
        "A separate patient- and community-facing application. Not built or deployed.",
        domain=ApplicationDomain.CLINICAL,
        status=ApplicationStatus.DEFERRED,
        canonical_route=None,
        clients=("Adaptix-Citizen-App",),
        source=(
            "Adaptix-Citizen-App exists in the fleet inventory; no web route, no "
            "gateway route, no audience. Patient-Identity-Service is NOT this "
            "application. The patient billing portal is Billing's portal, not this."
        ),
    ),
)
