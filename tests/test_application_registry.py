"""Tests for the canonical AdaptixCore application registry.

The load-bearing properties:

* one owner per surface — every route resolves to exactly one application,
  workspace, portal or capability;
* the registry can never mint a second entitlement vocabulary — every module
  reference is a CANONICAL ``module_registry`` id, aliases are rejected;
* lifecycle is enforced, not advisory — deferred / experimental / retired
  applications are structurally unable to reach customer navigation;
* consolidated products are workspaces, not applications — Scheduling, Labor,
  HR, Training, Fleet, Inventory, Medications, Narcotics, CRM, Documents and
  Compliance do not exist as top-level applications;
* the committed JSON catalog is current with the Python registry.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from adaptix_contracts.application_registry import (
    APPLICATION_REGISTRY,
    KNOWN_CLIENT_REPOSITORIES,
    SHARED_CAPABILITY_REGISTRY,
    ApplicationDefinition,
    ApplicationDomain,
    ApplicationStatus,
    ApplicationVisibility,
    PortalDefinition,
    SharedCapabilityDefinition,
    UnknownApplicationError,
    WorkspaceDefinition,
    application_ids,
    applications_in_domain,
    applications_unlocked_by,
    capabilities_unlocked_by,
    customer_navigable_applications,
    export_application_catalog,
    is_application_entitled,
    is_workspace_entitled,
    navigable_applications,
    require_application,
    route_owner,
    sold_products_for_application,
    validate_application_definition,
    validate_shared_capability_definition,
)
from adaptix_contracts.commercial.pricing_catalog import CommercialApplicationKey
from adaptix_contracts.commercial.wisconsin_launch_catalog import WI_LAUNCH_CATALOG
from adaptix_contracts.module_registry import (
    ALIAS_INDEX,
    MODULE_REGISTRY,
    expand_entitlements,
)
from adaptix_contracts.schemas.service_registry import SERVICE_BY_SLUG
from adaptix_contracts.service_audiences import KNOWN_SERVICE_AUDIENCES

REPO_ROOT = Path(__file__).resolve().parents[1]

# Priced products whose catalog entry carries no ``module_canonical_id`` yet.
# They cannot unlock anything until the pricing catalog cross-references an
# entitlement module; this set exists so that wiring one is a visible,
# deliberate change (the test below fails until the key is removed here).
# ``community_paramedicine`` is the notable case: ``module_registry`` already
# has ``mih_community_paramedicine`` and the MIH application is ACTIVE, so the
# only missing link is the catalog entry's cross-reference.
PRICED_WITHOUT_MODULE_ID = frozenset(
    {
        CommercialApplicationKey.QA_CLINICAL_REVIEW,
        CommercialApplicationKey.COMMUNITY_PARAMEDICINE,
        CommercialApplicationKey.PATIENT_PAYMENTS,
        CommercialApplicationKey.THIRD_PARTY_BILLING,
    }
)

# Products the founder directive folds INTO an application. If any of these
# reappears as a top-level application id, the consolidation has regressed.
CONSOLIDATED_INTO_WORKSPACES = frozenset(
    {
        "scheduling",
        "labor",
        "hr",
        "training",
        "fleet",
        "inventory",
        "medications",
        "narcotics",
        "crm",
        "support",
        "documents",
        "compliance",
        "reports",
        "analytics",
        "ask",
        "mdt",
        "crewlink",
        "air_pilot",
        "preplan",
        "hydrant",
        "wildland",
        "neris",
    }
)

# Shared capabilities that must NEVER be promoted to applications, whatever
# repository or service exists for them (directive §11 / §47).
NEVER_APPLICATIONS = frozenset(
    {
        "search",
        "notifications",
        "communications",
        "telephony",
        "voice",
        "rtc",
        "forms",
        "trustsign",
        "audit",
        "calendar",
        "payments",
        "exports",
        "imports",
        "hl7",
        "qhin",
        "terminology",
        "reference_data",
        "patient_identity",
        "nemsis",
        "geo",
        "graph",
        "temporal",
        "ai",
        "bedrock",
        "sagemaker",
        "vision",
        "signalcore",
        "mcp",
        "pricing",
        "cortex",
        "edge",
        "docuseal",
        "officeally",
        "office_ally",
    }
)


def _app(**overrides: object) -> ApplicationDefinition:
    """A valid synthetic ACTIVE application, overridable per test."""

    base: dict[str, object] = {
        "canonical_id": "synthetic_app",
        "display_name": "Synthetic",
        "description": "A synthetic application for tests.",
        "domain": ApplicationDomain.OPERATIONS,
        "status": ApplicationStatus.ACTIVE,
        "canonical_route": "/workspace/synthetic",
        "modules": frozenset({"cad"}),
        "primary_services": frozenset({"adaptix-cad"}),
    }
    base.update(overrides)
    return ApplicationDefinition(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Structural invariants
# ---------------------------------------------------------------------------


def test_registry_is_non_empty_and_keyed_by_canonical_id() -> None:
    assert APPLICATION_REGISTRY
    for key, app in APPLICATION_REGISTRY.items():
        assert key == app.canonical_id


def test_registry_is_read_only() -> None:
    with pytest.raises(TypeError):
        APPLICATION_REGISTRY["x"] = _app()  # type: ignore[index]
    with pytest.raises(TypeError):
        SHARED_CAPABILITY_REGISTRY["x"] = SHARED_CAPABILITY_REGISTRY["search"]  # type: ignore[index]


def test_every_domain_has_at_least_one_application() -> None:
    """The directive's eleven-domain structure is fully populated."""

    for domain in ApplicationDomain:
        assert applications_in_domain(domain), (
            f"domain {domain.value} has no application"
        )


def test_every_module_reference_is_canonical_never_an_alias() -> None:
    for app in APPLICATION_REGISTRY.values():
        for module_id in app.modules:
            assert module_id in MODULE_REGISTRY, (app.canonical_id, module_id)
            assert module_id not in ALIAS_INDEX
        for workspace in app.workspaces:
            for module_id in workspace.modules:
                assert module_id in MODULE_REGISTRY, (
                    app.canonical_id,
                    workspace.workspace_id,
                    module_id,
                )
    for capability in SHARED_CAPABILITY_REGISTRY.values():
        for module_id in capability.modules:
            assert module_id in MODULE_REGISTRY, (capability.capability_id, module_id)


def test_an_alias_spelling_is_rejected_with_the_canonical_id_named() -> None:
    with pytest.raises(ValueError, match="alias of 'billing'"):
        validate_application_definition(_app(modules=frozenset({"billing_automation"})))


def test_an_unknown_module_is_rejected() -> None:
    with pytest.raises(ValueError, match="not a canonical id"):
        validate_application_definition(_app(modules=frozenset({"fake-billing-new"})))


def test_every_service_reference_is_a_known_live_audience() -> None:
    for app in APPLICATION_REGISTRY.values():
        for audience in app.primary_services | app.supporting_services:
            assert audience in KNOWN_SERVICE_AUDIENCES, (app.canonical_id, audience)
    for capability in SHARED_CAPABILITY_REGISTRY.values():
        for audience in capability.services:
            assert audience in KNOWN_SERVICE_AUDIENCES, (
                capability.capability_id,
                audience,
            )


def test_an_unknown_service_is_rejected() -> None:
    with pytest.raises(ValueError, match="KNOWN_SERVICE_AUDIENCES"):
        validate_application_definition(
            _app(primary_services=frozenset({"adaptix-made-up"}))
        )


def test_every_client_reference_is_a_known_client_repository() -> None:
    for app in APPLICATION_REGISTRY.values():
        assert app.clients <= KNOWN_CLIENT_REPOSITORIES, app.canonical_id


def test_no_client_repository_is_claimed_by_two_applications() -> None:
    """A device app ships exactly one application family."""

    seen: dict[str, str] = {}
    for app in APPLICATION_REGISTRY.values():
        for client in app.clients:
            assert client not in seen, (
                f"{client} claimed by {seen[client]} and {app.canonical_id}"
            )
            seen[client] = app.canonical_id


def test_an_application_id_is_never_a_service_slug_or_repository_name() -> None:
    """A service or repository existing does not make it an application."""

    for app_id in application_ids():
        assert not app_id.startswith("adaptix"), app_id
        assert "-" not in app_id, app_id
    # The one deliberate overlap with a service slug is CAD/ePCR/Billing/etc.
    # where the human job and the service share a name; that is a cross-
    # reference, not a service being promoted. Everything in the service
    # registry that is NOT such a job must stay out.
    service_slugs = set(SERVICE_BY_SLUG)
    for slug in (
        "search",
        "calendar",
        "documents",
        "policy",
        "legal",
        "audit",
        "graph",
        "terminology",
        "device",
        "app-management",
        "integrations",
        "pricing",
        "marketing",
        "partner",
        "investor",
        "office",
        "customer-success",
        "operations",
        "imports",
        "exports",
        "analytics",
        "compliance",
        "hr",
        "training",
        "labor",
        "scheduling",
        "crew",
        "fleet",
        "inventory",
        "medications",
        "narcotics",
        "telephony",
        "communications",
    ):
        assert slug in service_slugs, (
            f"test fixture stale: {slug} left the service registry"
        )
        assert slug.replace("-", "_") not in APPLICATION_REGISTRY, (
            f"service {slug!r} is registered as an application; it is a "
            "workspace or capability"
        )


def test_consolidated_products_are_workspaces_not_applications() -> None:
    assert not (CONSOLIDATED_INTO_WORKSPACES & application_ids())


def test_shared_capabilities_are_never_applications() -> None:
    assert not (NEVER_APPLICATIONS & application_ids())
    assert not (set(APPLICATION_REGISTRY) & set(SHARED_CAPABILITY_REGISTRY))


def test_docuseal_is_absent_everywhere() -> None:
    source = (REPO_ROOT / "adaptix_contracts" / "application_registry.py").read_text(
        encoding="utf-8"
    )
    assert "docuseal" not in source.lower()
    catalog = json.dumps(export_application_catalog(contracts_version="0"))
    assert "docuseal" not in catalog.lower()


# ---------------------------------------------------------------------------
# Routes: one owner per surface
# ---------------------------------------------------------------------------


def test_every_active_application_has_exactly_one_canonical_route() -> None:
    routes: dict[str, str] = {}
    for app in navigable_applications():
        assert app.canonical_route is not None, app.canonical_id
        assert app.canonical_route not in routes, (
            app.canonical_id,
            routes[app.canonical_route],
        )
        routes[app.canonical_route] = app.canonical_id


def test_canonical_routes_are_workspace_roots_or_named_exceptions() -> None:
    """Directive §20: one canonical entry per application under /workspace.

    ``/quality`` and ``/transportlink`` are the two roots that live at the top
    level on current main; a third exception is a decision, not a drift.
    """

    allowed_top_level = {"/quality", "/transportlink"}
    for app in navigable_applications():
        route = app.canonical_route or ""
        assert route.startswith("/workspace/") or route in allowed_top_level, (
            app.canonical_id,
            route,
        )


def test_no_route_has_two_owners() -> None:
    """Every registered path resolves to exactly the surface that declared it."""

    claimed: dict[str, str] = {}
    for app in APPLICATION_REGISTRY.values():
        candidates = []
        if app.canonical_route:
            candidates.append((app.canonical_route, app.canonical_id))
        for workspace in app.workspaces:
            path = workspace.route.split("?", 1)[0]
            if path != app.canonical_route:
                candidates.append(
                    (path, f"{app.canonical_id}.{workspace.workspace_id}")
                )
        for portal in app.portals:
            candidates.append(
                (portal.entry_route, f"{app.canonical_id}.{portal.portal_id}")
            )
        for path, owner in candidates:
            assert path not in claimed, f"{path} owned by {claimed[path]} and {owner}"
            claimed[path] = owner
    for capability in SHARED_CAPABILITY_REGISTRY.values():
        if capability.route:
            assert capability.route not in claimed, capability.capability_id
            claimed[capability.route] = capability.capability_id


def test_a_duplicate_route_across_applications_is_rejected_at_build() -> None:
    """The import-time index refuses two owners for one path."""

    from adaptix_contracts import application_registry as module

    original = module._APPLICATIONS
    duplicate = _app(canonical_id="synthetic_dup", canonical_route="/workspace/billing")
    try:
        module._APPLICATIONS = (*original, duplicate)
        registry = module._build_application_registry()
        module.APPLICATION_REGISTRY = registry
        with pytest.raises(ValueError, match="exactly one owner"):
            module._route_index()
    finally:
        module._APPLICATIONS = original
        module.APPLICATION_REGISTRY = module._build_application_registry()
        module._ROUTE_INDEX = module._route_index()


@pytest.mark.parametrize(
    ("pathname", "kind", "application_id", "surface_id"),
    [
        ("/workspace/billing", "application", "billing", "billing"),
        ("/workspace/billing?section=claims", "application", "billing", "billing"),
        ("/workspace/billing/claims/abc-123", "workspace", "billing", "claims"),
        ("/workspace/fire", "application", "fire_operations", "fire_operations"),
        (
            "/workspace/fire/crr",
            "application",
            "community_risk_reduction",
            "community_risk_reduction",
        ),
        (
            "/workspace/fire/crr/iso-package",
            "workspace",
            "community_risk_reduction",
            "iso_package",
        ),
        ("/workspace/fire-x", None, None, None),
        (
            "/workspace/workforce?section=labor-overview",
            "application",
            "workforce",
            "workforce",
        ),
        ("/workspace/hr/employees/42", "workspace", "workforce", "hr"),
        ("/workspace/search", "capability", None, "search"),
        ("/patient-portal/invoices", "portal", "billing", "patient_billing_portal"),
        ("/quality/qa/cases/9", "workspace", "clinical_quality", "qa_cases"),
        ("/workspace/nowhere", None, None, None),
        ("/", None, None, None),
    ],
)
def test_route_owner_resolves_by_longest_prefix(
    pathname: str, kind: str | None, application_id: str | None, surface_id: str | None
) -> None:
    owner = route_owner(pathname)
    if kind is None:
        assert owner is None
        return
    assert owner is not None
    assert (owner.kind, owner.application_id, owner.surface_id) == (
        kind,
        application_id,
        surface_id,
    )


# ---------------------------------------------------------------------------
# Lifecycle enforcement
# ---------------------------------------------------------------------------


def test_deferred_and_experimental_and_retired_never_reach_navigation() -> None:
    offered = {app.canonical_id for app in navigable_applications()}
    for app in APPLICATION_REGISTRY.values():
        if app.status is not ApplicationStatus.ACTIVE:
            assert app.canonical_id not in offered, app.canonical_id
    customer = {app.canonical_id for app in customer_navigable_applications()}
    for app in APPLICATION_REGISTRY.values():
        if (
            app.status is not ApplicationStatus.ACTIVE
            or app.visibility is not ApplicationVisibility.TENANT
        ):
            assert app.canonical_id not in customer, app.canonical_id


def test_the_deferred_products_are_registered_as_deferred() -> None:
    """CCT and Citizen exist in the registry so nobody re-registers them as
    active on the strength of a repository."""

    assert require_application("cct").status is ApplicationStatus.DEFERRED
    assert require_application("citizen_patient").status is ApplicationStatus.DEFERRED
    assert require_application("demos").status is ApplicationStatus.EXPERIMENTAL
    assert "edge" not in APPLICATION_REGISTRY


def test_founder_and_admin_applications_are_not_customer_navigable() -> None:
    customer = {app.canonical_id for app in customer_navigable_applications()}
    assert "founder_command" not in customer
    assert "administration" not in customer
    assert "business_operations" not in customer
    assert "cad" in customer
    assert "billing" in customer


def test_an_active_application_without_a_route_is_rejected() -> None:
    with pytest.raises(ValueError, match="needs a canonical_route"):
        validate_application_definition(_app(canonical_route=None))


def test_an_active_application_without_an_owner_is_rejected() -> None:
    with pytest.raises(
        ValueError, match="primary_services or the applications it aggregates"
    ):
        validate_application_definition(_app(primary_services=frozenset()))


def test_an_aggregation_surface_may_not_also_claim_domain_ownership() -> None:
    with pytest.raises(ValueError, match="aggregates OR primary_services"):
        validate_application_definition(
            _app(aggregates=frozenset({"cad"})), known_application_ids=["cad"]
        )


def test_an_aggregate_reference_must_exist_and_not_be_self() -> None:
    with pytest.raises(ValueError, match="unknown application"):
        validate_application_definition(
            _app(primary_services=frozenset(), aggregates=frozenset({"nope"})),
            known_application_ids=["cad"],
        )
    with pytest.raises(ValueError, match="aggregates itself"):
        validate_application_definition(
            _app(primary_services=frozenset(), aggregates=frozenset({"synthetic_app"})),
            known_application_ids=["synthetic_app"],
        )


def test_a_deferred_application_may_not_declare_a_route() -> None:
    with pytest.raises(ValueError, match="not navigable"):
        validate_application_definition(_app(status=ApplicationStatus.DEFERRED))


def test_a_retired_application_may_not_declare_a_route() -> None:
    with pytest.raises(ValueError, match="not navigable"):
        validate_application_definition(_app(status=ApplicationStatus.RETIRED))
    # And a retired application with no route validates — retirement is a
    # legal terminal state, it is simply invisible.
    validate_application_definition(
        _app(
            status=ApplicationStatus.RETIRED,
            canonical_route=None,
            primary_services=frozenset(),
        )
    )


def test_an_experimental_application_cannot_be_tenant_visible() -> None:
    with pytest.raises(ValueError, match="cannot be tenant-visible"):
        validate_application_definition(_app(status=ApplicationStatus.EXPERIMENTAL))
    validate_application_definition(
        _app(
            status=ApplicationStatus.EXPERIMENTAL,
            visibility=ApplicationVisibility.FOUNDER,
        )
    )


def test_a_canonical_route_may_not_carry_a_query_but_a_workspace_route_may() -> None:
    with pytest.raises(ValueError, match="must not carry a query"):
        validate_application_definition(
            _app(canonical_route="/workspace/synthetic?tab=x")
        )
    validate_application_definition(
        _app(
            workspaces=(
                WorkspaceDefinition(
                    "panel", "Panel", "/workspace/synthetic?section=panel"
                ),
            )
        )
    )


def test_malformed_routes_and_ids_are_rejected() -> None:
    with pytest.raises(ValueError, match="must start with"):
        validate_application_definition(_app(canonical_route="workspace/synthetic"))
    with pytest.raises(ValueError, match="must not end with"):
        validate_application_definition(_app(canonical_route="/workspace/synthetic/"))
    with pytest.raises(ValueError, match="snake_case"):
        validate_application_definition(_app(canonical_id="Synthetic-App"))
    with pytest.raises(ValueError, match="duplicate workspace id"):
        validate_application_definition(
            _app(
                workspaces=(
                    WorkspaceDefinition("a", "A", "/workspace/synthetic/a"),
                    WorkspaceDefinition("a", "A again", "/workspace/synthetic/b"),
                )
            )
        )
    with pytest.raises(ValueError, match="KNOWN_CLIENT_REPOSITORIES"):
        validate_application_definition(
            _app(clients=frozenset({"Adaptix-Android-Made-Up"}))
        )
    with pytest.raises(ValueError, match="both primary and supporting"):
        validate_application_definition(
            _app(supporting_services=frozenset({"adaptix-cad"}))
        )
    with pytest.raises(ValueError, match="display_name and audience"):
        validate_application_definition(
            _app(portals=(PortalDefinition("p", "Portal", "/p", ""),))
        )


def test_a_shared_capability_must_name_its_service() -> None:
    with pytest.raises(ValueError, match="must name the service"):
        validate_shared_capability_definition(
            SharedCapabilityDefinition("synthetic_cap", "Cap", "A capability.")
        )
    validate_shared_capability_definition(
        SharedCapabilityDefinition(
            "synthetic_cap",
            "Cap",
            "A capability.",
            services=frozenset({"adaptix-search"}),
        )
    )


# ---------------------------------------------------------------------------
# Entitlement resolution — additive, alias-aware, never widening
# ---------------------------------------------------------------------------


def test_application_gate_resolves_legacy_aliases_through_module_registry() -> None:
    assert is_application_entitled("billing", ["billing_automation"]) is True
    assert is_application_entitled("fire_operations", ["fire_rms"]) is True
    assert is_application_entitled("field_operations", ["mobile_field"]) is True


def test_application_gate_is_any_of_and_bundle_aware() -> None:
    assert is_application_entitled("workforce", ["scheduling"]) is True
    assert is_application_entitled("workforce", ["labor"]) is True
    assert is_application_entitled("workforce", ["workforce"]) is True
    assert is_application_entitled("workforce", ["billing"]) is False
    # transport implies transportlink (module_registry), so a transport
    # purchase opens TransportLink.
    assert is_application_entitled("transportlink", ["transport"]) is True
    # hems_ops bundles cad/crewlink/mdt/epcr/billing — never air.
    assert is_application_entitled("field_operations", ["hems_ops"]) is True
    assert is_application_entitled("air_operations", ["hems_ops"]) is False


def test_application_gate_denies_the_empty_and_unrelated_tenant() -> None:
    for granted in ([], None, [""], ["core"]):
        assert is_application_entitled("cad", granted) is False
        assert is_application_entitled("epcr", granted) is False
        assert is_application_entitled("billing", granted) is False


def test_shell_surfaces_with_no_module_gate_return_true_and_rely_on_visibility() -> (
    None
):
    assert require_application("founder_command").modules == frozenset()
    assert is_application_entitled("founder_command", []) is True
    assert (
        require_application("founder_command").visibility
        is ApplicationVisibility.FOUNDER
    )


def test_workspace_gate_never_widens_beyond_the_purchased_module() -> None:
    """Holding scheduling opens the Workforce shell but not Labor, HR or Training."""

    assert is_workspace_entitled("workforce", "schedule", ["scheduling"]) is True
    assert is_workspace_entitled("workforce", "ems_schedule", ["scheduling"]) is True
    assert is_workspace_entitled("workforce", "labor", ["scheduling"]) is False
    assert is_workspace_entitled("workforce", "labor", ["labor"]) is True
    assert is_workspace_entitled("workforce", "hr", ["scheduling"]) is False
    assert is_workspace_entitled("workforce", "hr", ["hr"]) is True
    assert is_workspace_entitled("workforce", "training", ["training"]) is True
    assert is_workspace_entitled("asset_operations", "narcotics", ["narcotics"]) is True
    assert is_workspace_entitled("asset_operations", "narcotics", ["fleet"]) is False
    assert is_workspace_entitled("asset_operations", "fleet", ["narcotics"]) is False


def test_workspace_without_its_own_gate_inherits_the_application_gate() -> None:
    assert is_workspace_entitled("cad", "dispatch", ["cad"]) is True
    assert is_workspace_entitled("cad", "dispatch", ["epcr"]) is False


def test_application_gate_short_circuits_a_workspace_the_tenant_could_otherwise_open() -> (
    None
):
    """A tenant who cannot open the application cannot open any workspace in it,
    even one whose own module they hold.

    The real registry never contains this shape (a workspace module outside its
    application's modules), so it is proven on a synthetic definition through
    the same gate the public function uses.
    """

    from adaptix_contracts.application_registry import _workspace_entitled

    app = _app(
        modules=frozenset({"cad"}),
        workspaces=(
            WorkspaceDefinition(
                "side", "Side", "/workspace/synthetic/side", frozenset({"epcr"})
            ),
        ),
    )
    assert _workspace_entitled(app, "side", ["epcr"]) is False
    assert _workspace_entitled(app, "side", ["cad"]) is False
    assert _workspace_entitled(app, "side", ["cad", "epcr"]) is True


def test_an_umbrella_may_not_let_a_workspace_inherit_its_any_of_gate() -> None:
    """Regression for the widening a reviewer measured: a training-only tenant
    was offered Workforce's ungated personnel/fatigue/command workspaces."""

    with pytest.raises(ValueError, match="state each workspace's gate explicitly"):
        validate_application_definition(
            _app(
                modules=frozenset({"cad", "epcr"}),
                workspaces=(
                    WorkspaceDefinition("ungated", "Ungated", "/workspace/synthetic/u"),
                ),
            )
        )
    # A single-module application may still inherit — the gates are identical.
    validate_application_definition(
        _app(
            workspaces=(
                WorkspaceDefinition("inherits", "Inherits", "/workspace/synthetic/i"),
            )
        )
    )
    # And in the real registry every multi-module umbrella declares every gate.
    for app in APPLICATION_REGISTRY.values():
        if len(app.modules) >= 2:
            assert all(w.modules for w in app.workspaces), app.canonical_id


def test_a_single_product_tenant_is_not_offered_another_products_ungated_surfaces() -> (
    None
):
    """The measured counterexample, pinned: training alone opens HR-adjacent
    nothing in Workforce except Training itself."""

    for workspace in require_application("workforce").workspaces:
        expected = workspace.workspace_id == "training"
        assert (
            is_workspace_entitled("workforce", workspace.workspace_id, ["training"])
            is expected
        ), workspace.workspace_id
    for workspace in require_application("workforce").workspaces:
        expected = workspace.workspace_id == "hr"
        assert (
            is_workspace_entitled("workforce", workspace.workspace_id, ["hr"])
            is expected
        ), workspace.workspace_id


def test_unknown_application_or_workspace_raises_not_denies() -> None:
    with pytest.raises(UnknownApplicationError):
        is_application_entitled("no_such_app", ["cad"])
    with pytest.raises(UnknownApplicationError):
        is_workspace_entitled("cad", "no_such_workspace", ["cad"])
    assert issubclass(UnknownApplicationError, KeyError)


def test_consolidation_widens_no_entitlement() -> None:
    """Every module an application offers is a module the tenant must hold.

    A consolidated umbrella (Workforce, Asset Operations, Field Operations)
    is opened by ANY of its products, but each product's workspace stays
    behind that product's own module.
    """

    for app in navigable_applications():
        for workspace in app.workspaces:
            if not workspace.modules:
                # Only legal in a single-module application (enforced at import
                # by _validate_umbrella_workspaces), where inheriting cannot widen.
                assert len(app.modules) <= 1, (app.canonical_id, workspace.workspace_id)
                continue
            # Every umbrella product OUTSIDE this workspace's own gate must be
            # denied — unless module_registry says that product bundles one of
            # the workspace's products (workforce implies labor + scheduling).
            for other in app.modules - workspace.modules:
                if expand_entitlements([other]) & workspace.modules:
                    continue
                assert (
                    is_workspace_entitled(
                        app.canonical_id, workspace.workspace_id, [other]
                    )
                    is False
                ), (app.canonical_id, workspace.workspace_id, other)
            # And each of the workspace's own products does open it, so the
            # denial above is a real gate and not a query that matches nothing.
            for own in workspace.modules:
                assert (
                    is_workspace_entitled(
                        app.canonical_id, workspace.workspace_id, [own]
                    )
                    is True
                ), (app.canonical_id, workspace.workspace_id, own)


# ---------------------------------------------------------------------------
# Directive pins (the specific ownership decisions)
# ---------------------------------------------------------------------------


def test_patient_receivables_belong_to_billing_not_finance() -> None:
    billing = require_application("billing")
    finance = require_application("finance")
    assert any(w.workspace_id == "patients" for w in billing.workspaces)
    assert any(p.audience == "patient" for p in billing.portals)
    assert not any("patient" in w.workspace_id for w in finance.workspaces)


def test_clinical_quality_is_gated_on_epcr_and_owned_by_epcr_service() -> None:
    quality = require_application("clinical_quality")
    assert quality.modules == frozenset({"epcr"})
    assert quality.primary_services == frozenset({"adaptix-epcr"})


def test_transportlink_keeps_its_external_portal_separate() -> None:
    transport = require_application("transportlink")
    assert any(p.audience == "transport_requester" for p in transport.portals)
    assert route_owner("/transportlink/portal") is not None
    assert route_owner("/transportlink/portal").kind == "portal"  # type: ignore[union-attr]


def test_office_ally_is_administration_never_billing() -> None:
    assert (
        "adaptix-officeally" not in require_application("billing").supporting_services
    )
    assert (
        "adaptix-officeally"
        in require_application("administration").supporting_services
    )


def test_device_management_is_owned_by_administration_only() -> None:
    owners = [
        app.canonical_id
        for app in APPLICATION_REGISTRY.values()
        if any(w.route.startswith("/workspace/device") for w in app.workspaces)
    ]
    assert owners == ["administration"]


def test_android_clients_are_clients_of_application_families_not_applications() -> None:
    claimed = set().union(*(app.clients for app in APPLICATION_REGISTRY.values()))
    assert claimed <= KNOWN_CLIENT_REPOSITORIES
    assert require_application("air_operations").clients == {
        "Adaptix-Android-Air",
        "Adaptix-Android-AirPilot",
    }
    assert require_application("field_operations").clients == {
        "Adaptix-Android-MDT",
        "Adaptix-Android-CrewLink",
    }
    for repo in KNOWN_CLIENT_REPOSITORIES:
        assert repo.lower().replace("-", "_") not in APPLICATION_REGISTRY


# ---------------------------------------------------------------------------
# Pricing linkage — every sold product has a home in the product
# ---------------------------------------------------------------------------


def test_every_priced_product_with_a_module_unlocks_a_surface() -> None:
    """A customer charged for a product must have somewhere to go.

    Resolution follows the same path a route gate uses (aliases + bundle
    implications), so ``hems_ops`` — a bundle marker — passes because the
    bundle grants CAD, Field Operations, ePCR and Billing.
    """

    homeless = []
    for key, entry in WI_LAUNCH_CATALOG.entries.items():
        if entry.module_canonical_id is None:
            continue
        module_id = entry.module_canonical_id
        if not applications_unlocked_by(module_id) and not capabilities_unlocked_by(
            module_id
        ):
            homeless.append((key.value, module_id))
    assert homeless == [], (
        f"priced products that unlock no application or capability: {homeless}"
    )


def test_priced_products_without_a_module_id_are_exactly_the_pinned_set() -> None:
    """The gap list can only shrink: wiring a cross-reference must delete the key here."""

    without = {
        key
        for key, entry in WI_LAUNCH_CATALOG.entries.items()
        if entry.module_canonical_id is None
    }
    assert without == PRICED_WITHOUT_MODULE_ID


@pytest.mark.parametrize(
    ("module_id", "expected"),
    [
        ("cad", {"cad", "operations_command"}),
        ("epcr", {"epcr", "clinical_quality"}),
        ("mdt", {"field_operations"}),
        ("crewlink", {"field_operations"}),
        ("scheduling", {"workforce"}),
        ("labor", {"workforce"}),
        ("hr", {"workforce"}),
        ("fleet", {"asset_operations"}),
        ("narcotics", {"asset_operations"}),
        ("hospital", {"hospital_facility_operations", "operations_command"}),
        ("fire", {"fire_operations"}),
        ("crr", {"fire_operations", "community_risk_reduction"}),
        ("billing", {"billing", "operations_command"}),
        ("billing_automation", {"billing", "operations_command"}),
        ("analytics", {"intelligence_analytics"}),
        ("intelligence", {"intelligence_analytics"}),
        ("compliance", {"governance"}),
        ("mih_community_paramedicine", {"mih_community_paramedicine"}),
        (
            "hems_ops",
            {
                "cad",
                "field_operations",
                "epcr",
                "clinical_quality",
                "billing",
                "operations_command",
            },
        ),
        ("workforce", {"workforce"}),
        ("transport", {"transportlink"}),
        ("not_a_module", set()),
        ("core", set()),
    ],
)
def test_applications_unlocked_by_module(module_id: str, expected: set[str]) -> None:
    assert {app.canonical_id for app in applications_unlocked_by(module_id)} == expected


def test_capabilities_unlocked_by_module() -> None:
    assert {c.capability_id for c in capabilities_unlocked_by("communications")} == {
        "communications",
        "voice",
    }
    assert {c.capability_id for c in capabilities_unlocked_by("cortex")} == {"cortex"}
    assert {c.capability_id for c in capabilities_unlocked_by("ai")} == {"cortex"}
    assert capabilities_unlocked_by("billing") == ()


def test_sold_products_for_application_follows_the_catalog() -> None:
    assert set(sold_products_for_application("billing", WI_LAUNCH_CATALOG)) == {
        CommercialApplicationKey.BILLING_TECHNOLOGY,
        CommercialApplicationKey.HEMS,
    }
    assert set(sold_products_for_application("workforce", WI_LAUNCH_CATALOG)) == {
        CommercialApplicationKey.SCHEDULING,
    }
    assert set(
        sold_products_for_application("asset_operations", WI_LAUNCH_CATALOG)
    ) == {
        CommercialApplicationKey.FLEET,
        CommercialApplicationKey.INVENTORY,
        CommercialApplicationKey.NARCOTICS,
    }
    assert sold_products_for_application("founder_command", WI_LAUNCH_CATALOG) == ()
    with pytest.raises(UnknownApplicationError):
        sold_products_for_application("no_such_app", WI_LAUNCH_CATALOG)


def test_export_records_sold_as_and_pricing_catalog_version() -> None:
    catalog = export_application_catalog(
        contracts_version="0", pricing_catalog=WI_LAUNCH_CATALOG
    )
    assert catalog["pricing_catalog_version"] == WI_LAUNCH_CATALOG.catalog_version
    by_id = {record["canonical_id"]: record for record in catalog["applications"]}  # type: ignore[index]
    assert by_id["billing"]["sold_as"] == ["billing", "hems_ops"]
    assert by_id["cct"]["sold_as"] == []
    bare = export_application_catalog(contracts_version="0")
    assert bare["pricing_catalog_version"] is None
    assert all(record["sold_as"] == [] for record in bare["applications"])  # type: ignore[index]


# ---------------------------------------------------------------------------
# Export / drift
# ---------------------------------------------------------------------------


def test_export_is_deterministic_and_json_serialisable() -> None:
    first = export_application_catalog(contracts_version="1.2.3")
    second = export_application_catalog(contracts_version="1.2.3")
    assert first == second
    assert json.loads(json.dumps(first, sort_keys=True)) == first
    assert first["schema_version"] == 1
    assert first["contracts_version"] == "1.2.3"
    ids = [record["canonical_id"] for record in first["applications"]]  # type: ignore[index]
    assert ids == list(APPLICATION_REGISTRY)
    positions = [record["position"] for record in first["applications"]]  # type: ignore[index]
    assert positions == list(range(len(ids)))


def test_export_domain_order_matches_the_directive() -> None:
    catalog = export_application_catalog(contracts_version="0")
    assert [d["domain"] for d in catalog["domains"]] == [  # type: ignore[index]
        "command",
        "operations",
        "clinical",
        "fire",
        "revenue",
        "workforce",
        "logistics",
        "business",
        "intelligence",
        "governance",
        "administration",
    ]


def test_committed_catalog_json_is_current() -> None:
    """``adaptix_contracts/application_catalog.json`` must be regenerated with
    every registry change: ``uv run python scripts/export_application_catalog.py``."""

    script = REPO_ROOT / "scripts" / "export_application_catalog.py"
    spec = importlib.util.spec_from_file_location("export_application_catalog", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    raw = (REPO_ROOT / "adaptix_contracts" / "application_catalog.json").read_bytes()
    assert b"\r\n" not in raw, (
        "application_catalog.json must be LF-only on every platform"
    )
    assert raw.decode("utf-8") == module.render_catalog(), (
        "application_catalog.json is stale — run "
        "`uv run python scripts/export_application_catalog.py`"
    )


def test_committed_catalog_carries_source_identity() -> None:
    catalog = json.loads(
        (REPO_ROOT / "adaptix_contracts" / "application_catalog.json").read_text(
            encoding="utf-8"
        )
    )
    assert catalog["source_repository"] == "FusionEMS-Quantum-LLC/Adaptix-Contracts"
    assert catalog["schema_version"] == 1
    from adaptix_contracts import __version__

    assert catalog["contracts_version"] == __version__
