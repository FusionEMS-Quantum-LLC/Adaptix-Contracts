"""Canonical AdaptixCore application registry.

SINGLE SOURCE OF TRUTH for "what is an AdaptixCore application" — the job a
person performs, the workspaces inside it, the entitlement modules that make it
available, the services that implement it, the device clients that ship it and
the external portals that hang off it.

Why this exists
---------------
The product taxonomy was hand-typed in five independent places in
Adaptix-Web-App and they disagreed with each other (measured on Web-App main
35b4a12e, 2026-09-16):

===========================================  ======================================
Vocabulary (file)                            What it owned
===========================================  ======================================
``src/components/nav/ModuleSwitcher.tsx``    6 buckets, ~55 rows, one row per
``DOMAINS``                                  ROUTE (Workforce / EMS Scheduling /
                                             Labor / HR / Training all top-level)
``src/lib/nav/paletteCatalog.ts``            8 different domain names, its own
``PALETTE_ENTRIES``                          per-route entitlement gates
``src/components/nav/MobileBottomNav.tsx``   pre-2026-08-31 bucket names, NO
``AllLinksSheet``                            entitlement gating at all
``src/lib/nav/operatorRoutes.ts``            10 chords, two of them targeting
``OPERATOR_ROUTES``                          routes with no page
``src/lib/workspace/applications.ts``        home-screen cards, gated on module
``APPLICATIONS``                             ids the backend cannot grant
===========================================  ======================================

Changing one application meant editing five lists, and nothing failed when
they drifted. This registry is the one list; every consumer derives from it.

Relationship to ``module_registry``
-----------------------------------
``module_registry`` answers "which products has this tenant bought?" and is
NOT changed by this module — it stays the entitlement authority, aliases and
all. An application sits ABOVE entitlement: it names one or more canonical
module ids (``modules``) and is offered when the tenant holds ANY of them,
resolved through ``module_registry.expand_entitlements`` so legacy aliases and
bundle implications keep working exactly as they do at a route gate. Every id
here must be a CANONICAL id — an alias is rejected at import, so this registry
can never mint a second entitlement spelling.

Relationship to ``service_audiences`` / the gateway
---------------------------------------------------
Service ownership is recorded as gateway audiences (``adaptix-<slug>``) and
validated against ``service_audiences.KNOWN_SERVICE_AUDIENCES``. Each
application's services were read from Adaptix-Gateway
``backend/app/config/routes.py`` (main 5658fb1c) — the prefix each surface
actually calls, not the service the name suggests. That is why Clinical
Quality's primary service is ``adaptix-epcr`` (``/api/v1/quality`` and
``/api/v1/qa`` both route there) and TransportLink's is ``adaptix-transport``.

Relationship to ``commercial.pricing_catalog``
----------------------------------------------
``CommercialApplicationKey`` is the SOLD product vocabulary. It is not renamed
or replaced. The chain is one direction with no copies::

    sold product (pricing catalog)  --module_canonical_id-->
    entitlement module (module_registry)  --modules / workspace.modules-->
    application or workspace (this registry)  --services-->
    running service (gateway audience)

:func:`applications_unlocked_by` answers "a tenant who bought exactly this
module — where do they go?", :func:`sold_products_for_application` answers
the reverse, and ``tests/test_application_registry.py`` fails when a priced
product unlocks nothing: a customer charged for a product with no place in
the product is the navigation analogue of ``module_registry``'s
billable-but-dark SKU.

What is deliberately NOT an application
---------------------------------------
A backend service, a repository, a module id, or a route is not an
application. Search, Notifications, Calendar, Communications, Telephony,
Voice, TrustSign, Forms, Payments, Audit, NEMSIS, Terminology, Graph, Patient
Identity and Cortex are **shared capabilities** — reusable functions many
applications consume. Those that expose an operator shell surface today are
registered in :data:`SHARED_CAPABILITY_REGISTRY` with that route so navigation
can still reach them; they are not counted as applications. ``Edge`` is
deferred device infrastructure, not an application, and the retired
e-signature vendor is guarded against by its own test — neither appears here.

Visibility is presentation, never authorization
-----------------------------------------------
``visibility`` and ``modules`` decide what a navigation surface OFFERS. They
grant nothing. Every route and API keeps its own server-side authentication,
entitlement and tenant enforcement; hiding an entry is not a security control
and showing one does not bypass a gate.
"""

from __future__ import annotations

import enum
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from adaptix_contracts.commercial.pricing_catalog import (
    CommercialApplicationKey,
    CommercialPricingCatalog,
)
from adaptix_contracts.module_registry import (
    ALIAS_INDEX,
    MODULE_REGISTRY,
    expand_entitlements,
    normalize_module_id,
)
from adaptix_contracts.service_audiences import KNOWN_SERVICE_AUDIENCES

__all__ = [
    "APPLICATION_REGISTRY",
    "ApplicationDefinition",
    "ApplicationDomain",
    "ApplicationStatus",
    "ApplicationVisibility",
    "CATALOG_SCHEMA_VERSION",
    "KNOWN_CLIENT_REPOSITORIES",
    "PortalDefinition",
    "RouteOwner",
    "SHARED_CAPABILITY_REGISTRY",
    "SharedCapabilityDefinition",
    "UnknownApplicationError",
    "WorkspaceDefinition",
    "application_ids",
    "applications_in_domain",
    "applications_unlocked_by",
    "capabilities_unlocked_by",
    "customer_navigable_applications",
    "export_application_catalog",
    "is_application_entitled",
    "is_workspace_entitled",
    "navigable_applications",
    "require_application",
    "route_owner",
    "sold_products_for_application",
    "validate_application_definition",
    "validate_shared_capability_definition",
]


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------


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


# Evidence shorthand used in ``source`` fields below.
_WEB = "Web-App main 35b4a12e app/ route tree"
_GW = "Gateway main 5658fb1c routes.py"

# ---------------------------------------------------------------------------
# The applications
#
# EVERY route below is a real ``page.tsx`` on Web-App main 35b4a12e. EVERY
# service audience was read from the gateway route table for the prefix the
# surface actually calls. Do not add an application because a service or a
# repository exists; add one because a person performs that job.
# ---------------------------------------------------------------------------

_FC = "/workspace/founder-command"
# The gate app/workspace/workforce/layout.tsx applies to everything under it.
_WF_SHELL = ("workforce", "scheduling", "labor")

_APPLICATIONS: tuple[ApplicationDefinition, ...] = (
    # ── COMMAND ──────────────────────────────────────────────────────────
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
    # ── OPERATIONS ───────────────────────────────────────────────────────
    _app(
        "cad",
        "CAD",
        "Receive work, assign units and follow every response through to close.",
        domain=ApplicationDomain.OPERATIONS,
        canonical_route="/workspace/cad",
        modules=("cad",),
        primary_services=("adaptix-cad",),
        workspaces=(
            _ws("dispatch", "Dispatch Board", "/workspace/cad/dispatch"),
            _ws("incidents", "Incidents", "/workspace/cad/incidents"),
            _ws("intake", "Intake", "/workspace/cad/intake"),
            _ws("units", "Units", "/workspace/cad/units"),
            _ws("map", "Map", "/workspace/cad/map"),
            _ws("tracking", "Tracking", "/workspace/cad/tracking"),
            _ws("communications", "Communications", "/workspace/cad/comms"),
            _ws("facilities", "Facilities", "/workspace/cad/facilities"),
            _ws("hospitals", "Hospitals", "/workspace/cad/hospitals"),
            _ws("premise_hazards", "Premise Hazards", "/workspace/cad/premise-hazards"),
            _ws("transports", "Transports", "/workspace/cad/transports"),
            _ws("analytics", "Analytics", "/workspace/cad/analytics"),
            _ws("settings", "Settings", "/workspace/cad/settings"),
        ),
        source=f"{_WEB}; {_GW} /api/v1/cad -> adaptix-cad; module_registry cad",
    ),
    _app(
        "field_operations",
        "Field Operations",
        "What the crew works from in the unit: status, assignment, navigation, paging and messages.",
        domain=ApplicationDomain.OPERATIONS,
        canonical_route="/workspace/mdt",
        modules=("mdt", "crewlink", "crew"),
        primary_services=("adaptix-cad", "adaptix-crew"),
        supporting_services=("adaptix-field",),
        clients=("Adaptix-Android-MDT", "Adaptix-Android-CrewLink"),
        workspaces=(
            _ws("mdt", "MDT", "/workspace/mdt", modules=("mdt",)),
            _ws("mdt_status", "Unit Status", "/workspace/mdt/status", modules=("mdt",)),
            _ws("mdt_map", "Navigation", "/workspace/mdt/map", modules=("mdt",)),
            _ws(
                "mdt_messages", "Messages", "/workspace/mdt/messages", modules=("mdt",)
            ),
            _ws("crewlink", "CrewLink", "/workspace/crewlink", modules=("crewlink",)),
            _ws(
                "crewlink_roster",
                "Roster",
                "/workspace/crewlink/roster",
                modules=("crewlink",),
            ),
            _ws(
                "crewlink_shifts",
                "Shifts",
                "/workspace/crewlink/shifts",
                modules=("crewlink",),
            ),
            _ws(
                "crewlink_ptt",
                "Push-to-Talk",
                "/workspace/crewlink/ptt",
                modules=("crewlink",),
            ),
            _ws(
                "crewlink_devices",
                "Devices",
                "/workspace/crewlink/devices",
                modules=("crewlink",),
            ),
            _ws("crew", "Crew", "/workspace/crew", modules=("crew",)),
        ),
        source=(
            f"{_WEB}; {_GW} /api/v1/mdt -> adaptix-cad, /api/v1/crewlink -> "
            "adaptix-cad + adaptix-crew, /api/v1/crew -> adaptix-crew, "
            "/api/v1/field -> adaptix-field. The umbrella shell route is the MDT "
            "surface until a dedicated field shell exists; CrewLink and Crew are "
            "workspaces with their own module gates, so consolidation widens no "
            "entitlement."
        ),
    ),
    _app(
        "transportlink",
        "TransportLink",
        "Schedule and run interfacility and non-emergency transports end to end.",
        domain=ApplicationDomain.OPERATIONS,
        canonical_route="/transportlink",
        modules=("transportlink",),
        primary_services=("adaptix-transport",),
        clients=("Adaptix-Transport-Request-App",),
        portals=(
            PortalDefinition(
                portal_id="transport_status_portal",
                display_name="Transport Status Portal",
                entry_route="/transportlink/portal",
                audience="transport_requester",
            ),
        ),
        workspaces=(
            _ws("new_request", "New Request", "/workspace/transportlink/requests/new"),
            _ws("forms", "Forms", "/workspace/transportlink/forms"),
            _ws(
                "intelligence", "Intelligence", "/workspace/transportlink/intelligence"
            ),
            _ws("schedule", "Daily Schedule", "/workspace/transport/schedule"),
            _ws("hazards", "Hazard Reports", "/workspace/transport/hazards"),
            _ws("mci", "MCI Incidents", "/workspace/transport/mci"),
            _ws("rollups", "Status Rollups", "/workspace/transport/analytics"),
        ),
        source=(
            f"{_WEB} (app/transportlink/page.tsx is the navigated root on main; "
            "routes registry PUBLIC product entry); "
            f"{_GW} /api/v1/transport AND /api/v1/transportlink -> adaptix-transport "
            "(module_registry records adaptix-transportlink for the module; the "
            "gateway is the routing truth and is what is recorded here). The "
            "external requester/status portal stays a separate audience surface."
        ),
    ),
    _app(
        "air_operations",
        "Air Operations",
        "Air-medical missions from request through flight following and post-flight.",
        domain=ApplicationDomain.OPERATIONS,
        canonical_route="/workspace/air",
        modules=("air",),
        primary_services=("adaptix-air",),
        clients=("Adaptix-Android-Air", "Adaptix-Android-AirPilot"),
        workspaces=(
            _ws("missions", "Missions", "/workspace/air/missions"),
            _ws("aircraft", "Aircraft", "/workspace/air/aircraft"),
            _ws("weather", "Weather", "/workspace/air/weather"),
            _ws("weight_balance", "Weight & Balance", "/workspace/air/weight-balance"),
            _ws("helipads", "Helipads", "/workspace/air/helipads"),
            _ws(
                "landing_requests",
                "Landing Requests",
                "/workspace/air/landing-requests",
            ),
            _ws("tracking", "Flight Following", "/workspace/air/tracking"),
            _ws("duty_rest", "Duty & Rest", "/workspace/air/duty-rest"),
            _ws("risk", "Risk (FRAT)", "/workspace/air/risk"),
            _ws("maintenance", "Maintenance", "/workspace/air/maintenance"),
            _ws("airworthiness", "Airworthiness", "/workspace/air/airworthiness"),
            _ws("inspections", "Inspections", "/workspace/air/inspections"),
            _ws("post_flight", "Post-Flight", "/workspace/air/post-flight"),
            _ws("pilot_operations", "Pilot Operations", "/workspace/air-pilot"),
        ),
        source=(
            f"{_WEB}; {_GW} /api/v1/air AND /api/v1/air-pilot -> adaptix-air. "
            "Adaptix-Air-Service-Pilot has no gateway audience of its own, so the "
            "pilot surface is a workspace of this application, never a second app."
        ),
    ),
    _app(
        "hospital_facility_operations",
        "Hospital / Facility Operations",
        "Destination capacity, diversion, bed reservations, transfers and patient handoff.",
        domain=ApplicationDomain.OPERATIONS,
        canonical_route="/workspace/hospital",
        modules=("hospital",),
        primary_services=("adaptix-hospital",),
        supporting_services=("adaptix-facilities",),
        portals=(
            PortalDefinition(
                portal_id="hospital_portal",
                display_name="Hospital Portal",
                entry_route="/hospital/login",
                audience="hospital_staff",
            ),
        ),
        workspaces=(
            _ws("handoffs", "Handoffs", "/workspace/hospital/handoffs"),
            _ws("incoming", "Incoming", "/workspace/hospital/incoming"),
            _ws("transfers", "Transfers", "/workspace/hospital/transfers"),
            _ws("capacity", "Capacity", "/workspace/hospital/capacity"),
            _ws(
                "bed_reservations",
                "Bed Reservations",
                "/workspace/hospital/bed-reservations",
            ),
            _ws(
                "facility_registry",
                "Facility Registry",
                "/workspace/hospital/facility-registry",
            ),
            _ws("hie", "HIE", "/workspace/hospital/hie"),
            _ws("analytics", "Analytics", "/workspace/hospital/analytics"),
            _ws("integrations", "Integrations", "/workspace/hospital/integrations"),
            _ws("audit", "Audit", "/workspace/hospital/audit"),
        ),
        source=(
            f"{_WEB} (layout gates module 'hospital'); {_GW} /api/v1/hospital -> "
            "adaptix-hospital, /api/v1/facilities -> adaptix-facilities. "
            "Facility-Registry-Service owns facility data; this is the human "
            "workspace. Hospital staff authenticate through their own portal "
            "session, not the agency JWT."
        ),
    ),
    # ── CLINICAL ─────────────────────────────────────────────────────────
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
    # ── FIRE ─────────────────────────────────────────────────────────────
    _app(
        "fire_operations",
        "Fire Operations",
        "Fire incidents, apparatus, stations, hydrants, preplans, inspections and NERIS reporting.",
        domain=ApplicationDomain.FIRE,
        canonical_route="/workspace/fire",
        modules=("fire",),
        primary_services=("adaptix-fire",),
        supporting_services=("adaptix-neris",),
        clients=("Adaptix-Android-Fire",),
        workspaces=(
            _ws("incidents", "Incidents", "/workspace/fire/incidents"),
            _ws("apparatus", "Apparatus", "/workspace/fire/apparatus"),
            _ws("stations", "Stations", "/workspace/fire/stations"),
            _ws("personnel", "Personnel", "/workspace/fire/personnel"),
            _ws("unit_status", "Unit Status", "/workspace/fire/unit-status"),
            _ws("hydrants", "Hydrants", "/workspace/fire/hydrants"),
            _ws(
                "hydrant_registry",
                "Hydrant Registry",
                "/workspace/fire/hydrant-registry",
            ),
            _ws(
                "hydrant_flow_tests",
                "Hydrant Flow Tests",
                "/workspace/fire/hydrant-flow-tests",
            ),
            _ws("preplans", "Preplans", "/workspace/fire/preplans"),
            _ws("inspections", "Inspections", "/workspace/fire/inspections"),
            _ws("occupancies", "Occupancies", "/workspace/fire/occupancies"),
            _ws("hazards", "Hazards", "/workspace/fire/hazards"),
            _ws("neris", "NERIS", "/workspace/fire/neris"),
            _ws(
                "response_timeline",
                "Response Timeline",
                "/workspace/fire/response-timeline",
            ),
            _ws("cad_connect", "CAD Connect", "/workspace/fire/cad-connect"),
            _ws("code_library", "Code Library", "/workspace/fire/code-library"),
            _ws("enforcement", "Enforcement", "/workspace/fire/enforcement"),
            _ws("notices", "Notices", "/workspace/fire/notices"),
            _ws(
                "station_alerting",
                "Station Alerting",
                "/workspace/fire/station-alerting",
            ),
            _ws("settings", "Settings", "/workspace/fire/settings"),
        ),
        source=(
            f"{_WEB}; {_GW} /api/v1/fire -> adaptix-fire, /api/v1/neris -> "
            "adaptix-neris. Preplan, Hydrant and Wildland services are NOT "
            "gateway-routed (no /api/v1/preplan|hydrant|wildland RouteEntry; "
            "Preplan-Service has no ECS footprint per PREPLAN-SERVICE-NOT-DEPLOYED), "
            "so their surfaces here are served by Fire-Service and they are not "
            "listed as supporting services until they are routed."
        ),
    ),
    _app(
        "community_risk_reduction",
        "Community Risk Reduction",
        "Risk assessments, households, campaigns, interventions and outcomes for community risk reduction.",
        domain=ApplicationDomain.FIRE,
        canonical_route="/workspace/fire/crr",
        modules=("crr",),
        primary_services=("adaptix-fire",),
        workspaces=(
            _ws("iso_package", "ISO Package", "/workspace/fire/crr/iso-package"),
        ),
        source=(
            f"{_WEB} (app/workspace/fire/crr is the only CRR surface); {_GW} "
            "/api/v1/crr -> adaptix-fire; module_registry crr (audience "
            "adaptix-fire, implies fire). Adaptix-CRR-Service has no gateway "
            "audience yet. CRR is a distinct job with its own purchasable module, "
            "so it is a separate application whose root currently lives under the "
            "Fire route tree; route ownership resolves by longest prefix."
        ),
    ),
    # ── REVENUE ──────────────────────────────────────────────────────────
    _app(
        "billing",
        "Billing",
        "EMS revenue cycle: eligibility, coding, claims, clearinghouse, remittance, denials, appeals and patient balances.",
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
    # ── WORKFORCE ────────────────────────────────────────────────────────
    _app(
        "workforce",
        "Workforce",
        "Staff the organization: scheduling, people, labor, HR, training, credentials and availability.",
        domain=ApplicationDomain.WORKFORCE,
        canonical_route="/workspace/workforce",
        modules=("workforce", "scheduling", "labor", "hr", "training"),
        primary_services=("adaptix-workforce", "adaptix-labor"),
        supporting_services=("adaptix-hr", "adaptix-training"),
        clients=("Adaptix-Android-Workforce",),
        workspaces=(
            _ws(
                "schedule",
                "Schedule",
                "/workspace/workforce/schedule",
                modules=("scheduling",),
            ),
            _ws(
                "ems_schedule",
                "EMS Schedule",
                "/workspace/workforce?section=ems-schedule",
                modules=("scheduling",),
            ),
            _ws(
                "shifts",
                "Shifts",
                "/workspace/workforce/shifts",
                modules=("scheduling",),
            ),
            _ws(
                "open_shifts",
                "Open Shifts",
                "/workspace/workforce/open-shifts",
                modules=("scheduling",),
            ),
            _ws(
                "shift_swaps",
                "Shift Swaps",
                "/workspace/workforce/shift-swaps",
                modules=("scheduling",),
            ),
            _ws(
                "time_off",
                "Time Off",
                "/workspace/workforce/time-off",
                modules=("scheduling",),
            ),
            _ws(
                "labor",
                "Labor",
                "/workspace/workforce?section=labor-overview",
                modules=("labor",),
            ),
            _ws(
                "overtime",
                "Overtime",
                "/workspace/workforce/overtime",
                modules=("labor",),
            ),
            _ws(
                "timecards",
                "Timecards",
                "/workspace/workforce/timecards",
                modules=("labor",),
            ),
            _ws(
                "time_clock",
                "Time Clock",
                "/workspace/workforce/time-clock",
                modules=("labor",),
            ),
            _ws(
                "payroll", "Payroll", "/workspace/workforce/payroll", modules=("labor",)
            ),
            # These live under app/workspace/workforce/layout.tsx, whose own gate
            # is ANY-OF workforce/scheduling/labor. They carry that gate
            # explicitly rather than inheriting the umbrella's (which also
            # admits hr and training for the two workspaces that live outside
            # the shell) — an HR-only tenant must not be offered the shell's
            # personnel, fatigue or command surfaces.
            _ws(
                "people", "People", "/workspace/workforce/directory", modules=_WF_SHELL
            ),
            _ws(
                "credentials",
                "Credentials",
                "/workspace/workforce/credentials",
                modules=_WF_SHELL,
            ),
            _ws(
                "certifications",
                "Certifications",
                "/workspace/workforce/certifications",
                modules=_WF_SHELL,
            ),
            _ws(
                "availability",
                "Availability",
                "/workspace/workforce/availability",
                modules=_WF_SHELL,
            ),
            _ws(
                "fatigue", "Fatigue", "/workspace/workforce/fatigue", modules=_WF_SHELL
            ),
            _ws(
                "readiness",
                "Readiness",
                "/workspace/workforce/readiness",
                modules=_WF_SHELL,
            ),
            _ws(
                "mission_command",
                "Mission Command",
                "/workspace/workforce/mission-command",
                modules=_WF_SHELL,
            ),
            _ws("hr", "HR", "/workspace/hr", modules=("hr",)),
            _ws("training", "Training", "/workspace/training", modules=("training",)),
        ),
        source=(
            f"{_WEB} (app/workspace/workforce/layout.tsx gates ANY-OF "
            "workforce/scheduling/labor; /workspace/training gates 'training'); "
            f"{_GW} /api/v1/workforce -> adaptix-workforce + adaptix-labor, "
            "/api/v1/scheduling AND /api/v1/labor -> adaptix-labor, /api/v1/hr -> "
            "adaptix-hr, /api/v1/training -> adaptix-training. The application "
            "is offered when ANY of its products is held (an HR-only tenant has "
            "/workspace/hr today and must still find it); entitlements stay "
            "separate per workspace: a scheduling-only tenant sees the Schedule "
            "workspaces, never Labor, HR or Training (module_registry: "
            "scheduling implies none of them)."
        ),
    ),
    # ── LOGISTICS ────────────────────────────────────────────────────────
    _app(
        "asset_operations",
        "Asset Operations",
        "Physical operational assets: fleet, inventory, medications, narcotics, work orders, purchasing and audits.",
        domain=ApplicationDomain.LOGISTICS,
        canonical_route="/workspace/operations",
        modules=("assetops", "fleet", "inventory", "medications", "narcotics"),
        primary_services=("adaptix-assetops",),
        supporting_services=(
            "adaptix-fleet",
            "adaptix-inventory",
            "adaptix-medications",
            "adaptix-narcotics",
        ),
        clients=("Adaptix-Android-Inventory", "Adaptix-Android-Narcotics"),
        workspaces=(
            _ws(
                "asset_register",
                "Asset Register",
                "/workspace/operations/asset-register",
                modules=("assetops",),
            ),
            _ws("dvir", "DVIR", "/workspace/operations/dvir", modules=("assetops",)),
            _ws(
                "work_orders",
                "Work Orders",
                "/workspace/operations/work-orders",
                modules=("assetops",),
            ),
            _ws(
                "purchase_orders",
                "Purchase Orders",
                "/workspace/operations/purchase-orders",
                modules=("assetops",),
            ),
            _ws(
                "vendors",
                "Vendors",
                "/workspace/operations/vendors",
                modules=("assetops",),
            ),
            _ws(
                "audit_cycles",
                "Audit Cycles",
                "/workspace/operations/audit-cycles",
                modules=("assetops",),
            ),
            _ws(
                "cost_analytics",
                "Cost Analytics",
                "/workspace/operations/analytics",
                modules=("assetops",),
            ),
            _ws("fleet", "Fleet", "/workspace/fleet", modules=("fleet",)),
            _ws(
                "inventory", "Inventory", "/workspace/inventory", modules=("inventory",)
            ),
            _ws(
                "medications",
                "Medications",
                "/workspace/medications",
                modules=("medications",),
            ),
            _ws(
                "narcotics", "Narcotics", "/workspace/narcotics", modules=("narcotics",)
            ),
            _ws(
                "narcotics_vault",
                "Vault Inventory",
                "/workspace/narcotics/inventory",
                modules=("narcotics",),
            ),
            _ws(
                "narcotics_par_levels",
                "Par Levels",
                "/workspace/narcotics/par-levels",
                modules=("narcotics",),
            ),
            _ws(
                "narcotics_chain_of_custody",
                "Chain of Custody",
                "/workspace/narcotics/chain-of-custody",
                modules=("narcotics",),
            ),
            _ws(
                "narcotics_witness",
                "Witness",
                "/workspace/narcotics/witness",
                modules=("narcotics",),
            ),
            _ws(
                "narcotics_waste",
                "Waste",
                "/workspace/narcotics/waste",
                modules=("narcotics",),
            ),
            _ws(
                "narcotics_discrepancies",
                "Discrepancies",
                "/workspace/narcotics/discrepancies",
                modules=("narcotics",),
            ),
        ),
        source=(
            f"{_WEB} (app/workspace/operations/page.tsx: 'AdaptixCore-AssetOps "
            "hub', reads /api/v1/assetops x37); "
            f"{_GW} /api/v1/assetops -> adaptix-assetops, /api/v1/fleet -> "
            "adaptix-fleet, /api/v1/inventory -> adaptix-inventory, "
            "/api/v1/medications -> adaptix-medications, /api/v1/narcotics -> "
            "adaptix-narcotics. AssetOps orchestrates; each domain service keeps "
            "its own truth (no second inventory, narcotics log or vehicle "
            "registry). Device management is Administration's, referenced here."
        ),
    ),
    # ── BUSINESS ─────────────────────────────────────────────────────────
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
    # ── INTELLIGENCE ─────────────────────────────────────────────────────
    _app(
        "intelligence_analytics",
        "Intelligence & Analytics",
        "Reports, analytics and the governed natural-language console (Ask AdaptixCore).",
        domain=ApplicationDomain.INTELLIGENCE,
        canonical_route="/workspace/reports",
        primary_services=("adaptix-analytics",),
        supporting_services=("adaptix-graph", "adaptix-core"),
        workspaces=(
            _ws(
                "analytics", "Analytics", "/workspace/analytics", modules=("analytics",)
            ),
            _ws("ask", "Ask AdaptixCore", "/workspace/ask", modules=("intelligence",)),
            _ws(
                "intelligence",
                "Cortex Intelligence",
                "/workspace/intelligence",
                modules=("intelligence",),
            ),
        ),
        source=(
            f"{_WEB} (reports reads /api/v1/reports + cross-module report "
            "prefixes; analytics reads /api/v1/analytics x64 + graph; ask carries "
            f"its own ModuleGate 'intelligence'); {_GW} /api/v1/reports AND "
            "/api/v1/intelligence -> adaptix-core, /api/v1/analytics -> "
            "adaptix-analytics, /api/v1/graph -> adaptix-graph. The root is "
            "Reports because it is served by Core and reachable by every tenant; "
            "Analytics is a workspace behind the sold 'analytics' module (its "
            "backend mints no audience without it, so an ungated entry would be a "
            "control that can only fail)."
        ),
    ),
    # ── GOVERNANCE ───────────────────────────────────────────────────────
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
    # ── ADMINISTRATION ───────────────────────────────────────────────────
    _app(
        "administration",
        "Administration",
        "Organization, users, roles, applications and entitlements, devices, integrations, imports/exports, onboarding and platform configuration.",
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
    # ── EXPERIMENTAL ─────────────────────────────────────────────────────
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


# ---------------------------------------------------------------------------
# Shared capabilities (not applications)
# ---------------------------------------------------------------------------

_SHARED_CAPABILITIES: tuple[SharedCapabilityDefinition, ...] = (
    _cap(
        "search",
        "Search",
        "Tenant-scoped search across indexed records.",
        route="/workspace/search",
        services=("adaptix-search",),
        source=f"{_WEB}; {_GW} /api/v1/search -> adaptix-search",
    ),
    _cap(
        "notifications",
        "Notifications",
        "A person's own notifications and alerts.",
        route="/workspace/notifications",
        services=("adaptix-core",),
        source=f"{_WEB}; {_GW} /api/v1/notifications -> adaptix-core",
    ),
    _cap(
        "calendar",
        "Calendar",
        "Platform calendar events, reminders and booking.",
        route="/workspace/calendar",
        services=("adaptix-calendar",),
        source=f"{_WEB}; {_GW} /api/v1/calendar -> adaptix-calendar",
    ),
    _cap(
        "communications",
        "Communications",
        "Phone, SMS, email, fax, voicemail, templates and consent across applications.",
        route="/workspace/communications",
        modules=("communications",),
        services=("adaptix-communications", "adaptix-telephony"),
        source=(
            f"{_WEB} (reads /api/v1/communications x37, telephony x17, templates, "
            f"consent, communications-hub); {_GW} all -> adaptix-communications / "
            "adaptix-telephony"
        ),
    ),
    _cap(
        "telephony",
        "Telephony",
        "Call queues, presence, scripts and voicemail.",
        route="/workspace/telephony",
        modules=("telephony",),
        services=("adaptix-telephony",),
        source=f"{_WEB}; {_GW} /api/v1/telephony -> adaptix-telephony",
    ),
    _cap(
        "voice",
        "Voice",
        "Real-time voice rooms tied to incidents and cases.",
        route="/workspace/voice",
        modules=("communications",),
        services=("adaptix-voice",),
        source=(
            f"{_WEB}; routes registry gates /voice on the communications "
            f"entitlement; {_GW} /api/v1/voice -> adaptix-voice"
        ),
    ),
    _cap(
        "trustsign",
        "TrustSign",
        "AdaptixCore's signature authority: signing requests, verification and the signed archive.",
        route="/workspace/trustsign",
        services=("adaptix-trustsign",),
        source=f"{_WEB}; {_GW} /api/v1/trustsign AND /api/v1/verifications -> adaptix-trustsign",
    ),
    _cap(
        "nemsis",
        "NEMSIS",
        "NEMSIS dataset registry, validation and state submission plumbing.",
        route="/workspace/nemsis",
        modules=("nemsis",),
        services=("adaptix-nemsis",),
        source=f"{_WEB}; {_GW} /api/v1/nemsis AND /api/v1/wards -> adaptix-nemsis",
    ),
    _cap(
        "terminology",
        "Terminology",
        "Reference terminology, code sets and concept governance.",
        route="/workspace/terminology/concepts",
        services=("adaptix-terminology",),
        source=(
            f"{_WEB} (app/workspace/terminology has NO root page.tsx — only "
            "concepts, mappings, review and sources; concepts is the entry); "
            f"{_GW} /api/v1/terminology -> adaptix-terminology"
        ),
    ),
    _cap(
        "graph",
        "Graph",
        "Microsoft Graph integration surfaces (mail, calendar, files).",
        route="/workspace/graph",
        services=("adaptix-graph",),
        source=f"{_WEB}; {_GW} /api/v1/graph -> adaptix-graph",
    ),
    _cap(
        "cortex",
        "Cortex",
        "Cross-platform AI assistance consumed by every application; this is its own operator surface.",
        route="/workspace/cortex-ai",
        modules=("ai", "cortex"),
        services=("adaptix-ai", "adaptix-cortex", "adaptix-bedrock"),
        source=(
            f"{_WEB} (app/workspace/cortex-ai reads /api/v1/ai x38); {_GW} "
            "/api/v1/ai -> adaptix-ai, /api/v1/cortex -> adaptix-cortex + core; "
            "the pricing catalog sells Cortex as module 'cortex' and the runtime "
            "grant is 'ai', so either opens the surface. Cortex is an "
            "intelligence layer, never a business application; founder-only "
            "Cortex administration is Administration's workspace."
        ),
    ),
    _cap(
        "forms",
        "Forms",
        "Structured forms consumed by Documents, ePCR and TransportLink.",
        services=("adaptix-forms",),
        source=f"{_GW} /api/v1/forms -> adaptix-forms; surfaced inside Governance/Documents",
    ),
    _cap(
        "payments",
        "Payments",
        "Payment handling consumed by Billing, Finance, portals and subscriptions. Never a second money ledger.",
        services=("adaptix-payments",),
        source=f"{_GW} /api/v1/payments -> adaptix-payments",
    ),
    _cap(
        "audit",
        "Audit",
        "Immutable cross-service audit trails and the evidence graph.",
        services=("adaptix-audit",),
        source=f"{_GW} /api/v1/audit -> adaptix-audit + core",
    ),
    _cap(
        "patient_identity",
        "Patient Identity",
        "Master patient index and matching consumed by clinical applications.",
        services=("adaptix-patient-identity",),
        source="module_registry patient_identity (audience adaptix-patient-identity)",
    ),
)


# ---------------------------------------------------------------------------
# Validation (import time)
# ---------------------------------------------------------------------------

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

    if app.canonical_route is not None:
        _validate_route(owner, app.canonical_route, allow_query=False)
    _validate_status_shape(app)
    _validate_modules(owner, app.modules)
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


# ---------------------------------------------------------------------------
# Machine-readable export
# ---------------------------------------------------------------------------


def _workspace_record(workspace: WorkspaceDefinition) -> dict[str, object]:
    return {
        "workspace_id": workspace.workspace_id,
        "display_name": workspace.display_name,
        "route": workspace.route,
        "modules": sorted(workspace.modules),
        "visibility": workspace.visibility.value,
        "description": workspace.description,
    }


def _portal_record(portal: PortalDefinition) -> dict[str, object]:
    return {
        "portal_id": portal.portal_id,
        "display_name": portal.display_name,
        "entry_route": portal.entry_route,
        "audience": portal.audience,
    }


def _application_record(
    app: ApplicationDefinition, position: int, catalog: CommercialPricingCatalog | None
) -> dict[str, object]:
    sold_as = (
        sorted(
            key.value
            for key in sold_products_for_application(app.canonical_id, catalog)
        )
        if catalog is not None and app.status is ApplicationStatus.ACTIVE
        else []
    )
    return {
        "canonical_id": app.canonical_id,
        "display_name": app.display_name,
        "description": app.description,
        "domain": app.domain.value,
        "status": app.status.value,
        "visibility": app.visibility.value,
        "canonical_route": app.canonical_route,
        "modules": sorted(app.modules),
        "primary_services": sorted(app.primary_services),
        "supporting_services": sorted(app.supporting_services),
        "aggregates": sorted(app.aggregates),
        "clients": sorted(app.clients),
        "workspaces": [_workspace_record(w) for w in app.workspaces],
        "portals": [_portal_record(p) for p in app.portals],
        # Priced products (pricing-catalog keys) that unlock this application.
        "sold_as": sold_as,
        # Presentation order inside the domain. Explicit so a consumer sorting
        # by id does not reorder the founder's intended navigation.
        "position": position,
        "source": app.source,
    }


def _capability_record(
    capability: SharedCapabilityDefinition, position: int
) -> dict[str, object]:
    return {
        "capability_id": capability.capability_id,
        "display_name": capability.display_name,
        "description": capability.description,
        "route": capability.route,
        "modules": sorted(capability.modules),
        "services": sorted(capability.services),
        "visibility": capability.visibility.value,
        "position": position,
        "source": capability.source,
    }


def export_application_catalog(
    *, contracts_version: str, pricing_catalog: CommercialPricingCatalog | None = None
) -> dict[str, object]:
    """The registry as a deterministic, JSON-serialisable catalog.

    This is what ``adaptix_contracts/application_catalog.json`` contains and
    what Adaptix-Web-App mirrors into its generated TypeScript. It carries the
    schema version and the producing package version; the generator records
    the source repository. Ordering is registry order (presentation), recorded
    as ``position`` so consumers never have to guess it. When a pricing
    catalog is supplied each application also lists the products it is
    ``sold_as``; the pricing catalog version is recorded alongside so the
    linkage is attributable.
    """

    return {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "contracts_version": contracts_version,
        "pricing_catalog_version": (
            None if pricing_catalog is None else pricing_catalog.catalog_version
        ),
        "domains": [
            {"domain": domain.value, "position": index}
            for index, domain in enumerate(ApplicationDomain)
        ],
        "statuses": [status.value for status in ApplicationStatus],
        "visibilities": [visibility.value for visibility in ApplicationVisibility],
        "applications": [
            _application_record(app, index, pricing_catalog)
            for index, app in enumerate(APPLICATION_REGISTRY.values())
        ],
        "shared_capabilities": [
            _capability_record(capability, index)
            for index, capability in enumerate(SHARED_CAPABILITY_REGISTRY.values())
        ],
        "client_repositories": sorted(KNOWN_CLIENT_REPOSITORIES),
    }
