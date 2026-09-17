"""Machine-readable export of the registry (``application_catalog.json``)."""

from __future__ import annotations

from adaptix_contracts.application_registry._model import (
    ApplicationDefinition,
    ApplicationDomain,
    ApplicationStatus,
    ApplicationVisibility,
    CATALOG_SCHEMA_VERSION,
    KNOWN_CLIENT_REPOSITORIES,
    PortalDefinition,
    SharedCapabilityDefinition,
    WorkspaceDefinition,
)
from adaptix_contracts.application_registry._registry import (
    APPLICATION_REGISTRY,
    SHARED_CAPABILITY_REGISTRY,
    sold_products_for_application,
)
from adaptix_contracts.commercial.pricing_catalog import CommercialPricingCatalog


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
