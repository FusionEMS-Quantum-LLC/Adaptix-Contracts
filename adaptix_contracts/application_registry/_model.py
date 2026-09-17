"""Vocabulary and record types of the application registry.

See the package docstring for the taxonomy these types encode.
"""

from __future__ import annotations

import enum
from collections.abc import Iterable
from dataclasses import dataclass, field


class ApplicationDomain(str, enum.Enum):
    """The product domain an application belongs to (global navigation group)."""

    COMMAND = "command"
    OPERATIONS = "operations"
    CLINICAL = "clinical"
    FIRE = "fire"
    REVENUE = "revenue"
    WORKFORCE = "workforce"
    LOGISTICS = "logistics"
    BUSINESS = "business"
    INTELLIGENCE = "intelligence"
    GOVERNANCE = "governance"
    ADMINISTRATION = "administration"


class ApplicationStatus(str, enum.Enum):
    """Lifecycle state. Set explicitly; never inferred from a repository."""

    #: Offered to entitled production users. Requires a real canonical route
    #: and a real implementation owner.
    ACTIVE = "active"
    #: Implementation may exist; the product is not presently offered. Never
    #: shown as a normal production application.
    DEFERRED = "deferred"
    #: Prototype / sandbox surface. Never shown in customer navigation.
    EXPERIMENTAL = "experimental"
    #: Must not be navigable, listed, sold or documented as current.
    RETIRED = "retired"


class ApplicationVisibility(str, enum.Enum):
    """Who a navigation surface OFFERS the entry to. Presentation only."""

    #: Any entitled tenant operator.
    TENANT = "tenant"
    #: Agency admin / super admin / founder.
    ADMIN = "admin"
    #: Founder only (and hidden in founder view-as-tenant QA mode).
    FOUNDER = "founder"


#: Schema version of :func:`export_application_catalog`. Bump on any change to
#: the exported shape so a consumer pinned to an older shape fails loudly.
CATALOG_SCHEMA_VERSION = 1


#: Device / client repositories that may be named in ``clients``. Read from
#: ``Adaptix-Governance/repos/fleet.json`` (observed_at 2026-08-27): every
#: ``Adaptix-Android-*`` repository plus the three non-Android client apps.
#: A client is a device-specific implementation of an application, never an
#: application of its own.
KNOWN_CLIENT_REPOSITORIES: frozenset[str] = frozenset(
    {
        "Adaptix-Android-Air",
        "Adaptix-Android-AirPilot",
        "Adaptix-Android-Command",
        "Adaptix-Android-CrewLink",
        "Adaptix-Android-EPCR",
        "Adaptix-Android-Fire",
        "Adaptix-Android-Founder-Command",
        "Adaptix-Android-Inventory",
        "Adaptix-Android-MDT",
        "Adaptix-Android-Narcotics",
        "Adaptix-Android-Workforce",
        "Adaptix-Citizen-App",
        "Adaptix-Mobile-Shell",
        "Adaptix-Transport-Request-App",
    }
)


# ---------------------------------------------------------------------------
# Definitions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorkspaceDefinition:
    """One focused area inside an application where part of the job is done.

    ``route`` is the real Web-App route that opens the workspace. It may carry
    a query string when the owning application shell selects panels by query
    (``/workspace/workforce?section=ems-schedule``). ``modules`` is an ANY-OF
    entitlement gate for this workspace only; empty means the workspace is
    offered whenever its application is.
    """

    workspace_id: str
    display_name: str
    route: str
    modules: frozenset[str] = field(default_factory=frozenset)
    visibility: ApplicationVisibility = ApplicationVisibility.TENANT
    description: str = ""


@dataclass(frozen=True)
class PortalDefinition:
    """A separate-audience entry surface that shares an application's services.

    A portal stays a separate surface because its audience and trust boundary
    differ from the internal application (a patient, a hospital nurse, a
    transport requester). It is never merged into the internal shell.
    """

    portal_id: str
    display_name: str
    entry_route: str
    audience: str


@dataclass(frozen=True)
class ApplicationDefinition:  # pylint: disable=too-many-instance-attributes
    # Deliberately wide: one exhaustively-typed record per application is the
    # point of a registry, and splitting it would scatter the invariants the
    # validators check. Same precedent as commercial.pricing_catalog
    # .ApplicationPricingCatalogEntry.
    """One AdaptixCore application: a major job a person performs.

    Attributes:
        canonical_id: Stable snake_case identifier. Never a module id, service
            slug or repository name by construction — see the tests.
        canonical_route: The one Web-App root route. ``None`` only for
            ``DEFERRED`` / ``RETIRED`` applications.
        modules: ANY-OF canonical entitlement module ids. Empty means the
            application is a shell surface with no module gate (visibility and
            server-side authorization still apply).
        primary_services: Gateway audiences of the services that own the
            application's domain truth.
        supporting_services: Audiences the application also calls.
        aggregates: Application ids whose state this application composes.
            Only a cross-application command surface uses this instead of
            ``primary_services``; it owns no domain records of its own.
        clients: Repository names from :data:`KNOWN_CLIENT_REPOSITORIES`.
        portals: External-audience entry surfaces.
        visibility: Who navigation offers the entry to. Presentation only.
        source: Where each fact was measured. Documentation, not behaviour.
    """

    canonical_id: str
    display_name: str
    description: str
    domain: ApplicationDomain
    status: ApplicationStatus
    canonical_route: str | None
    workspaces: tuple[WorkspaceDefinition, ...] = ()
    modules: frozenset[str] = field(default_factory=frozenset)
    primary_services: frozenset[str] = field(default_factory=frozenset)
    supporting_services: frozenset[str] = field(default_factory=frozenset)
    aggregates: frozenset[str] = field(default_factory=frozenset)
    clients: frozenset[str] = field(default_factory=frozenset)
    portals: tuple[PortalDefinition, ...] = ()
    visibility: ApplicationVisibility = ApplicationVisibility.TENANT
    source: str = ""


@dataclass(frozen=True)
class SharedCapabilityDefinition:
    """A reusable platform function consumed by many applications.

    Distinct from ``auth.capability_registry.PlatformCapability`` (a shipped
    feature gated on a module, e.g. ``epcr.ambient_capture``): this is the
    product-taxonomy notion — Search, Notifications, Communications — that must
    NOT be presented as an application. ``route`` is set only when the
    capability exposes its own operator shell surface today, so navigation can
    still reach it without promoting it to an application.
    """

    capability_id: str
    display_name: str
    description: str
    route: str | None = None
    modules: frozenset[str] = field(default_factory=frozenset)
    services: frozenset[str] = field(default_factory=frozenset)
    visibility: ApplicationVisibility = ApplicationVisibility.TENANT
    source: str = ""


class UnknownApplicationError(KeyError):
    """Raised for an unregistered application id.

    A ``KeyError`` subclass so existing ``except KeyError`` handlers keep
    working, matching ``module_registry.UnknownModuleError``.
    """


def _ws(
    workspace_id: str,
    display_name: str,
    route: str,
    *,
    modules: Iterable[str] = (),
    visibility: ApplicationVisibility = ApplicationVisibility.TENANT,
    description: str = "",
) -> WorkspaceDefinition:
    return WorkspaceDefinition(
        workspace_id=workspace_id,
        display_name=display_name,
        route=route,
        modules=frozenset(modules),
        visibility=visibility,
        description=description,
    )


def _app(  # pylint: disable=too-many-arguments
    # Keyword-only constructor mirroring ApplicationDefinition one-to-one, so
    # each registry entry reads as a record and every field is named at the
    # call site. Same shape as module_registry._m.
    canonical_id: str,
    display_name: str,
    description: str,
    *,
    domain: ApplicationDomain,
    status: ApplicationStatus = ApplicationStatus.ACTIVE,
    canonical_route: str | None,
    workspaces: Iterable[WorkspaceDefinition] = (),
    modules: Iterable[str] = (),
    primary_services: Iterable[str] = (),
    supporting_services: Iterable[str] = (),
    aggregates: Iterable[str] = (),
    clients: Iterable[str] = (),
    portals: Iterable[PortalDefinition] = (),
    visibility: ApplicationVisibility = ApplicationVisibility.TENANT,
    source: str = "",
) -> ApplicationDefinition:
    return ApplicationDefinition(
        canonical_id=canonical_id,
        display_name=display_name,
        description=description,
        domain=domain,
        status=status,
        canonical_route=canonical_route,
        workspaces=tuple(workspaces),
        modules=frozenset(modules),
        primary_services=frozenset(primary_services),
        supporting_services=frozenset(supporting_services),
        aggregates=frozenset(aggregates),
        clients=frozenset(clients),
        portals=tuple(portals),
        visibility=visibility,
        source=source,
    )


def _cap(
    capability_id: str,
    display_name: str,
    description: str,
    *,
    route: str | None = None,
    modules: Iterable[str] = (),
    services: Iterable[str] = (),
    visibility: ApplicationVisibility = ApplicationVisibility.TENANT,
    source: str = "",
) -> SharedCapabilityDefinition:
    return SharedCapabilityDefinition(
        capability_id=capability_id,
        display_name=display_name,
        description=description,
        route=route,
        modules=frozenset(modules),
        services=frozenset(services),
        visibility=visibility,
        source=source,
    )
