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

Relationship to the commercial catalogs
---------------------------------------
The current SOLD vocabulary is the offer catalog (``commercial.offers``,
seeded as ``commercial.wi_launch_2026_1``). The chain is one direction with no
copies::

    offer (offer catalog)  --grants_modules-->
    entitlement module (module_registry)  --modules / workspace.modules-->
    application or workspace (this registry)  --services-->
    running service (gateway audience)

:func:`applications_unlocked_by` answers "a tenant who holds exactly this
module — where do they go?" and :func:`offers_selling_application` answers the
reverse. ``commercial.offer_validation`` refuses to publish an offer whose
grants leave its application gated, a workspace dark, or a primary service
unreached: a customer charged for a product with no place in the product is
the navigation analogue of ``module_registry``'s billable-but-dark SKU.

The superseded pricing catalog (``commercial.pricing_catalog``,
``wi-launch-v1``) keeps its own linkage: ``CommercialApplicationKey`` follows
``module_canonical_id`` into :func:`applications_unlocked_by`, and
:func:`sold_products_for_application` answers the reverse for anything still
priced on that version.

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

from adaptix_contracts.application_registry._export import (
    export_application_catalog,
)
from adaptix_contracts.application_registry._model import (
    ApplicationDefinition,
    ApplicationDomain,
    ApplicationStatus,
    ApplicationVisibility,
    CATALOG_SCHEMA_VERSION,
    KNOWN_CLIENT_REPOSITORIES,
    PortalDefinition,
    SharedCapabilityDefinition,
    UnknownApplicationError,
    WorkspaceDefinition,
)
from adaptix_contracts.application_registry._registry import (
    APPLICATION_REGISTRY,
    RouteOwner,
    SHARED_CAPABILITY_REGISTRY,
    application_ids,
    applications_in_domain,
    applications_unlocked_by,
    capabilities_unlocked_by,
    customer_navigable_applications,
    is_application_entitled,
    is_workspace_entitled,
    navigable_applications,
    offers_selling_application,
    require_application,
    route_owner,
    sold_products_for_application,
)
from adaptix_contracts.application_registry._validation import (
    validate_application_definition,
    validate_shared_capability_definition,
)

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
    "offers_selling_application",
    "require_application",
    "route_owner",
    "sold_products_for_application",
    "validate_application_definition",
    "validate_shared_capability_definition",
]
