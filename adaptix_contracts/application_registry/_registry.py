"""Registry assembly, the route index and the query API."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from adaptix_contracts.application_registry._definitions import (
    APPLICATIONS as _APPLICATIONS,
    SHARED_CAPABILITIES as _SHARED_CAPABILITIES,
)
from adaptix_contracts.application_registry._model import (
    ApplicationDefinition,
    ApplicationDomain,
    ApplicationStatus,
    ApplicationVisibility,
    SharedCapabilityDefinition,
    UnknownApplicationError,
)
from adaptix_contracts.application_registry._validation import (
    validate_application_definition,
    validate_shared_capability_definition,
)
from adaptix_contracts.commercial.offers import ApplicationOffer
from adaptix_contracts.commercial.pricing_catalog import (
    CommercialApplicationKey,
    CommercialPricingCatalog,
)
from adaptix_contracts.module_registry import expand_entitlements


def _build_application_registry() -> Mapping[str, ApplicationDefinition]:
    registry: dict[str, ApplicationDefinition] = {}
    for app in _APPLICATIONS:
        if app.canonical_id in registry:
            raise ValueError(f"duplicate application id: {app.canonical_id!r}")
        registry[app.canonical_id] = app
    for app in registry.values():
        validate_application_definition(app, known_application_ids=registry)
    return MappingProxyType(registry)


def _build_capability_registry() -> Mapping[str, SharedCapabilityDefinition]:
    registry: dict[str, SharedCapabilityDefinition] = {}
    for capability in _SHARED_CAPABILITIES:
        if capability.capability_id in registry:
            raise ValueError(
                f"duplicate shared capability id: {capability.capability_id!r}"
            )
        validate_shared_capability_definition(capability)
        registry[capability.capability_id] = capability
    return MappingProxyType(registry)


#: Canonical application id -> definition. Read-only; validated at import.
APPLICATION_REGISTRY: Mapping[str, ApplicationDefinition] = (
    _build_application_registry()
)


#: Shared capability id -> definition. Read-only; validated at import.
SHARED_CAPABILITY_REGISTRY: Mapping[str, SharedCapabilityDefinition] = (
    _build_capability_registry()
)


@dataclass(frozen=True)
class RouteOwner:
    """The registered surface a pathname resolves to (see :func:`route_owner`)."""

    kind: str  # "application" | "workspace" | "portal" | "capability"
    application_id: str | None
    surface_id: str
    route: str


def _route_index() -> Mapping[str, RouteOwner]:
    """Every registered route path (query stripped) -> its single owner."""

    index: dict[str, RouteOwner] = {}

    def claim(path: str, owner: RouteOwner) -> None:
        existing = index.get(path)
        if existing is not None:
            raise ValueError(
                f"route {path!r} is claimed by both "
                f"{existing.application_id or existing.surface_id} and "
                f"{owner.application_id or owner.surface_id} — every surface has "
                "exactly one owner"
            )
        index[path] = owner

    for app in APPLICATION_REGISTRY.values():
        if app.canonical_route is not None:
            claim(
                app.canonical_route,
                RouteOwner(
                    "application",
                    app.canonical_id,
                    app.canonical_id,
                    app.canonical_route,
                ),
            )
        for workspace in app.workspaces:
            path = workspace.route.split("?", 1)[0]
            if path == app.canonical_route:
                # A query-selected panel on the application's own root shares
                # the root path by design (``/workspace/billing?section=studio``).
                continue
            claim(
                path,
                RouteOwner(
                    "workspace",
                    app.canonical_id,
                    workspace.workspace_id,
                    workspace.route,
                ),
            )
        for portal in app.portals:
            claim(
                portal.entry_route,
                RouteOwner(
                    "portal", app.canonical_id, portal.portal_id, portal.entry_route
                ),
            )
    for capability in SHARED_CAPABILITY_REGISTRY.values():
        if capability.route is not None:
            claim(
                capability.route,
                RouteOwner(
                    "capability", None, capability.capability_id, capability.route
                ),
            )
    return MappingProxyType(index)


_ROUTE_INDEX: Mapping[str, RouteOwner] = _route_index()


# Shared-capability ids and application ids are one namespace for consumers
# that render both; a collision would make ``route_owner`` ambiguous.
_ID_COLLISIONS = set(APPLICATION_REGISTRY) & set(SHARED_CAPABILITY_REGISTRY)


if _ID_COLLISIONS:
    raise ValueError(
        f"ids used for both an application and a capability: {sorted(_ID_COLLISIONS)}"
    )


# ---------------------------------------------------------------------------
# Query API
# ---------------------------------------------------------------------------


def application_ids() -> frozenset[str]:
    """Every registered application id, regardless of status."""

    return frozenset(APPLICATION_REGISTRY)


def require_application(application_id: str) -> ApplicationDefinition:
    """Return the definition or raise :class:`UnknownApplicationError`."""

    try:
        return APPLICATION_REGISTRY[application_id]
    except KeyError:
        raise UnknownApplicationError(
            f"{application_id!r} is not a registered AdaptixCore application. "
            f"Known ids: {sorted(APPLICATION_REGISTRY)}"
        ) from None


def applications_in_domain(
    domain: ApplicationDomain,
) -> tuple[ApplicationDefinition, ...]:
    """Applications in ``domain``, in registry (presentation) order."""

    return tuple(app for app in APPLICATION_REGISTRY.values() if app.domain is domain)


def navigable_applications() -> tuple[ApplicationDefinition, ...]:
    """Applications a navigation surface may offer at all: ``ACTIVE`` only.

    ``DEFERRED``, ``EXPERIMENTAL`` and ``RETIRED`` never appear here. A founder
    or developer surface that wants experimental entries must ask for them by
    status explicitly, never through this function.
    """

    return tuple(
        app
        for app in APPLICATION_REGISTRY.values()
        if app.status is ApplicationStatus.ACTIVE
    )


def customer_navigable_applications() -> tuple[ApplicationDefinition, ...]:
    """``ACTIVE`` applications offered to an ordinary tenant operator."""

    return tuple(
        app
        for app in navigable_applications()
        if app.visibility is ApplicationVisibility.TENANT
    )


def _any_of_entitled(
    required: frozenset[str], granted: Iterable[object] | None
) -> bool:
    if not required:
        return True
    expanded = expand_entitlements(granted)
    return any(module_id in expanded for module_id in required)


def is_application_entitled(
    application_id: str, granted: Iterable[object] | None
) -> bool:
    """True when ``granted`` satisfies the application's ANY-OF module gate.

    Resolution runs through ``module_registry.expand_entitlements``, so legacy
    aliases and bundle implications behave exactly as at a route gate. An
    application with no ``modules`` is a shell surface and returns ``True``:
    its ``visibility`` and the server decide, not an entitlement. Unknown ids
    raise — a navigation surface asking about an unregistered application is
    a defect, not a denial.

    >>> is_application_entitled("billing", ["billing_automation"])
    True
    >>> is_application_entitled("workforce", ["scheduling"])
    True
    >>> is_application_entitled("workforce", ["billing"])
    False
    """

    return _any_of_entitled(require_application(application_id).modules, granted)


def _workspace_entitled(
    app: ApplicationDefinition, workspace_id: str, granted: Iterable[object] | None
) -> bool:
    """The gate behind :func:`is_workspace_entitled`, on an explicit definition.

    Split out so the application-gate short-circuit can be tested on a
    synthetic definition whose workspace module lies outside its application
    modules — a shape the real registry deliberately never contains.
    """

    if not _any_of_entitled(app.modules, granted):
        return False
    for workspace in app.workspaces:
        if workspace.workspace_id == workspace_id:
            return _any_of_entitled(workspace.modules, granted)
    raise UnknownApplicationError(
        f"{app.canonical_id!r} has no workspace {workspace_id!r}; known: "
        f"{sorted(w.workspace_id for w in app.workspaces)}"
    )


def is_workspace_entitled(
    application_id: str, workspace_id: str, granted: Iterable[object] | None
) -> bool:
    """True when ``granted`` satisfies BOTH the application gate and the workspace gate.

    A workspace with no modules of its own inherits the application's answer
    (only possible in a single-module application — see
    ``_validate_umbrella_workspaces``). Holding ``scheduling`` opens the
    Workforce shell but not its Labor workspace; this is where that
    distinction is enforced.
    """

    return _workspace_entitled(
        require_application(application_id), workspace_id, granted
    )


def applications_unlocked_by(module_id: str) -> tuple[ApplicationDefinition, ...]:
    """The ``ACTIVE`` applications a tenant holding exactly ``module_id`` can open.

    "Open" means the application gate is satisfied AND either the application
    itself is module-gated or at least one of its workspaces is unlocked. A
    shell surface with no module gate anywhere (Founder Command) is not
    "unlocked by" anything and is never returned. Aliases and bundle
    implications resolve through ``module_registry``: ``hems_ops`` unlocks
    CAD, Field Operations, ePCR and Billing because the bundle grants those.
    """

    granted = [module_id]
    unlocked: list[ApplicationDefinition] = []
    for app in navigable_applications():
        if not _any_of_entitled(app.modules, granted):
            continue
        if app.modules or any(
            workspace.modules and _any_of_entitled(workspace.modules, granted)
            for workspace in app.workspaces
        ):
            unlocked.append(app)
    return tuple(unlocked)


def capabilities_unlocked_by(module_id: str) -> tuple[SharedCapabilityDefinition, ...]:
    """The shared capabilities with an operator surface that ``module_id`` opens."""

    granted = [module_id]
    return tuple(
        capability
        for capability in SHARED_CAPABILITY_REGISTRY.values()
        if capability.route is not None
        and capability.modules
        and _any_of_entitled(capability.modules, granted)
    )


def sold_products_for_application(
    application_id: str, catalog: CommercialPricingCatalog
) -> tuple[CommercialApplicationKey, ...]:
    """The priced products in ``catalog`` that unlock this application.

    Follows ``entry.module_canonical_id`` into :func:`applications_unlocked_by`
    — the same resolution a route gate uses — so a product that reaches the
    application only through a bundle implication is still reported. A
    catalog entry with no ``module_canonical_id`` can unlock nothing yet and
    is never reported; see ``tests/test_application_registry.py`` for the
    pinned list of those.
    """

    require_application(application_id)
    sold: list[CommercialApplicationKey] = []
    for key, entry in catalog.entries.items():
        if entry.module_canonical_id is None:
            continue
        if any(
            app.canonical_id == application_id
            for app in applications_unlocked_by(entry.module_canonical_id)
        ):
            sold.append(key)
    return tuple(sold)


def offers_selling_application(
    application_id: str, offers: Iterable[ApplicationOffer]
) -> tuple[str, ...]:
    """The ids of the offers whose grants open this application, sorted.

    The offer-catalog counterpart of :func:`sold_products_for_application`: it
    follows each granted module into :func:`applications_unlocked_by`, the
    same resolution a route gate uses, so an offer that reaches the
    application only through a bundle implication is still reported. An
    activation-pending offer that grants nothing sells nothing.
    """

    require_application(application_id)
    return tuple(
        sorted(
            offer.offer_id
            for offer in offers
            if any(
                app.canonical_id == application_id
                for module_id in offer.grants_modules
                for app in applications_unlocked_by(module_id)
            )
        )
    )


def route_owner(pathname: str) -> RouteOwner | None:
    """Resolve a pathname to its registered owner by longest path prefix.

    Query strings and trailing slashes are ignored. Matching is on path
    segment boundaries, so ``/workspace/fire-x`` does not match
    ``/workspace/fire``. ``/workspace/fire/crr/iso-package`` resolves to
    Community Risk Reduction, not Fire Operations, because the longer
    registered prefix wins. Returns ``None`` for an unregistered path.

    LIMITATION: a workspace addressed only by query on its application's root
    (``/workspace/workforce?section=labor-overview``,
    ``/workspace/billing?section=studio``) resolves to the APPLICATION, because
    the query is dropped before matching. A consumer that needs the
    per-workspace gate for such a panel must read the query itself and call
    :func:`is_workspace_entitled`; ``route_owner`` alone would hand it the
    application-level gate.
    """

    path = pathname.split("?", 1)[0].split("#", 1)[0]
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    best: RouteOwner | None = None
    best_len = -1
    for registered, owner in _ROUTE_INDEX.items():
        if path == registered or path.startswith(registered + "/"):
            if len(registered) > best_len:
                best, best_len = owner, len(registered)
    return best
