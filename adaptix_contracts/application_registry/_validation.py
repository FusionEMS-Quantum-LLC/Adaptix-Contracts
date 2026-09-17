"""Import-time validation of application and shared-capability definitions."""

from __future__ import annotations

from collections.abc import Iterable

from adaptix_contracts.application_registry._model import (
    ApplicationDefinition,
    ApplicationDomain,
    ApplicationStatus,
    ApplicationVisibility,
    KNOWN_CLIENT_REPOSITORIES,
    PortalDefinition,
    SharedCapabilityDefinition,
    WorkspaceDefinition,
)
from adaptix_contracts.module_registry import (
    ALIAS_INDEX,
    MODULE_REGISTRY,
    normalize_module_id,
)
from adaptix_contracts.service_audiences import KNOWN_SERVICE_AUDIENCES

_ID_PATTERN_DESCRIPTION = "lowercase snake_case starting with a letter"


def _is_valid_id(value: str) -> bool:
    if not value or not value[0].isalpha() or value != value.lower():
        return False
    return all(ch.isalnum() or ch == "_" for ch in value)


def _validate_route(owner: str, route: str, *, allow_query: bool) -> None:
    if not route.startswith("/"):
        raise ValueError(f"{owner}: route {route!r} must start with '/'")
    if any(ch.isspace() for ch in route):
        raise ValueError(f"{owner}: route {route!r} contains whitespace")
    path = route.split("?", 1)[0]
    if path != "/" and path.endswith("/"):
        raise ValueError(f"{owner}: route {route!r} must not end with '/'")
    if "?" in route and not allow_query:
        raise ValueError(f"{owner}: canonical route {route!r} must not carry a query")


def _validate_modules(owner: str, modules: Iterable[str]) -> None:
    for module_id in modules:
        if module_id in MODULE_REGISTRY:
            continue
        canonical = ALIAS_INDEX.get(normalize_module_id(module_id))
        if canonical is not None:
            raise ValueError(
                f"{owner}: module {module_id!r} is an alias of {canonical!r}; "
                "the application registry only references canonical module ids"
            )
        raise ValueError(
            f"{owner}: module {module_id!r} is not a canonical id in "
            "module_registry.MODULE_REGISTRY"
        )


def _validate_services(owner: str, services: Iterable[str]) -> None:
    for audience in services:
        if audience not in KNOWN_SERVICE_AUDIENCES:
            raise ValueError(
                f"{owner}: service {audience!r} is not in "
                "service_audiences.KNOWN_SERVICE_AUDIENCES"
            )


def _validate_workspace(owner: str, workspace: WorkspaceDefinition) -> None:
    label = f"{owner}.{workspace.workspace_id}"
    if not _is_valid_id(workspace.workspace_id):
        raise ValueError(f"{label}: workspace_id must be {_ID_PATTERN_DESCRIPTION}")
    if not workspace.display_name.strip():
        raise ValueError(f"{label}: display_name is empty")
    _validate_route(label, workspace.route, allow_query=True)
    _validate_modules(label, workspace.modules)


def _validate_portal(owner: str, portal: PortalDefinition) -> None:
    label = f"{owner}.{portal.portal_id}"
    if not _is_valid_id(portal.portal_id):
        raise ValueError(f"{label}: portal_id must be {_ID_PATTERN_DESCRIPTION}")
    if not portal.display_name.strip() or not portal.audience.strip():
        raise ValueError(f"{label}: display_name and audience are required")
    _validate_route(label, portal.entry_route, allow_query=False)


def _validate_status_shape(app: ApplicationDefinition) -> None:
    owner = app.canonical_id
    if app.status in (ApplicationStatus.DEFERRED, ApplicationStatus.RETIRED):
        if app.canonical_route is not None or app.workspaces:
            raise ValueError(
                f"{owner}: a {app.status.value} application must not declare a "
                "route or workspaces — it is not navigable"
            )
        return
    if app.canonical_route is None:
        raise ValueError(
            f"{owner}: an {app.status.value} application needs a canonical_route"
        )
    if app.status is ApplicationStatus.ACTIVE and not (
        app.primary_services or app.aggregates
    ):
        raise ValueError(
            f"{owner}: an active application must name primary_services or the "
            "applications it aggregates — 'exists' with no implementation owner "
            "is not allowed"
        )
    if (
        app.status is ApplicationStatus.EXPERIMENTAL
        and app.visibility is ApplicationVisibility.TENANT
    ):
        raise ValueError(
            f"{owner}: an experimental application cannot be tenant-visible; "
            "use ADMIN or FOUNDER visibility"
        )


def _validate_umbrella_workspaces(app: ApplicationDefinition) -> None:
    """A multi-product umbrella may not let a workspace inherit its ANY-OF gate.

    Inheriting is harmless for a single-module application (the workspace gate
    would equal the application gate anyway). For an umbrella opened by any of
    several products it is a silent widening: a tenant holding only one
    product would be offered every ungated workspace of the others. So every
    workspace of a multi-module application must state its own gate — even
    when that gate is deliberately the umbrella's full set.
    """

    if len(app.modules) < 2:
        return
    ungated = [w.workspace_id for w in app.workspaces if not w.modules]
    if ungated:
        raise ValueError(
            f"{app.canonical_id}: workspaces {ungated} declare no modules inside a "
            f"multi-module umbrella {sorted(app.modules)}; state each workspace's "
            "gate explicitly so consolidation cannot widen what a tenant is offered"
        )


def validate_application_definition(
    app: ApplicationDefinition, *, known_application_ids: Iterable[str] = ()
) -> None:
    """Validate one definition in isolation. Raises ``ValueError``.

    ``known_application_ids`` is the id set ``aggregates`` may reference; the
    registry passes every registered id, a test may pass a synthetic set.
    """

    _validate_identity(app)
    if app.canonical_route is not None:
        _validate_route(app.canonical_id, app.canonical_route, allow_query=False)
    _validate_status_shape(app)
    _validate_modules(app.canonical_id, app.modules)
    _validate_ownership(app, known_application_ids)
    _validate_children(app)


def _validate_identity(app: ApplicationDefinition) -> None:
    owner = app.canonical_id
    if not _is_valid_id(owner):
        raise ValueError(f"{owner!r}: canonical_id must be {_ID_PATTERN_DESCRIPTION}")
    if not app.display_name.strip() or not app.description.strip():
        raise ValueError(f"{owner}: display_name and description are required")
    if not isinstance(app.domain, ApplicationDomain):
        raise ValueError(f"{owner}: domain must be an ApplicationDomain")
    if not isinstance(app.status, ApplicationStatus):
        raise ValueError(f"{owner}: status must be an ApplicationStatus")
    if not isinstance(app.visibility, ApplicationVisibility):
        raise ValueError(f"{owner}: visibility must be an ApplicationVisibility")


def _validate_ownership(
    app: ApplicationDefinition, known_application_ids: Iterable[str]
) -> None:
    """Services, aggregates and clients: who implements and ships the application."""

    owner = app.canonical_id
    _validate_services(owner, app.primary_services)
    _validate_services(owner, app.supporting_services)
    overlap = app.primary_services & app.supporting_services
    if overlap:
        raise ValueError(
            f"{owner}: services listed as both primary and supporting: {sorted(overlap)}"
        )
    if app.aggregates and app.primary_services:
        raise ValueError(
            f"{owner}: an aggregation surface owns no domain records — declare "
            "aggregates OR primary_services, not both"
        )
    known = set(known_application_ids)
    for aggregated in app.aggregates:
        if aggregated == owner:
            raise ValueError(f"{owner}: aggregates itself")
        if aggregated not in known:
            raise ValueError(f"{owner}: aggregates unknown application {aggregated!r}")
    for client in app.clients:
        if client not in KNOWN_CLIENT_REPOSITORIES:
            raise ValueError(
                f"{owner}: client {client!r} is not in KNOWN_CLIENT_REPOSITORIES"
            )


def _validate_children(app: ApplicationDefinition) -> None:
    """Workspaces and portals: unique ids, valid routes, explicit umbrella gates."""

    owner = app.canonical_id
    seen_workspace_ids: set[str] = set()
    for workspace in app.workspaces:
        if workspace.workspace_id in seen_workspace_ids:
            raise ValueError(
                f"{owner}: duplicate workspace id {workspace.workspace_id!r}"
            )
        seen_workspace_ids.add(workspace.workspace_id)
        _validate_workspace(owner, workspace)
    _validate_umbrella_workspaces(app)
    seen_portal_ids: set[str] = set()
    for portal in app.portals:
        if portal.portal_id in seen_portal_ids:
            raise ValueError(f"{owner}: duplicate portal id {portal.portal_id!r}")
        seen_portal_ids.add(portal.portal_id)
        _validate_portal(owner, portal)


def validate_shared_capability_definition(
    capability: SharedCapabilityDefinition,
) -> None:
    """Validate one shared-capability definition in isolation. Raises ``ValueError``."""

    owner = capability.capability_id
    if not _is_valid_id(owner):
        raise ValueError(f"{owner!r}: capability_id must be {_ID_PATTERN_DESCRIPTION}")
    if not capability.display_name.strip() or not capability.description.strip():
        raise ValueError(f"{owner}: display_name and description are required")
    if capability.route is not None:
        _validate_route(owner, capability.route, allow_query=False)
    _validate_modules(owner, capability.modules)
    _validate_services(owner, capability.services)
    if not capability.services:
        raise ValueError(
            f"{owner}: a shared capability must name the service(s) that implement it"
        )
