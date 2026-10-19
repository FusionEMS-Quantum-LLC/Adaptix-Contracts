"""Pin every ``ServiceDefinition.port`` to the port Adaptix-Infra deploys.

Contracts #373: ``schemas.service_registry`` called itself the single source of
truth for ports while 17 of its 49 entries named ports production never used
(8001-8009 and 8040-8047 for services that listen on 8000). Nothing checked
the registry against the deployment, so the drift had no test to fail.

The authority is Adaptix-Infra, read on ``origin/main`` at :data:`INFRA_COMMIT`:

* ``terraform/task_definitions/production/<slug>.json``: the container's
  ``portMappings[].containerPort``;
* ``terraform/task_definitions/production/gateway.json``: the port in the
  gateway's ``<SLUG>_SERVICE_URL`` environment value, which is how the
  gateway actually reaches the service.

Where both exist they agree for every service below. Three services have
neither: ``scheduling`` is a prefix the gateway proxies to Labor
(Adaptix-Gateway ``backend/app/config/routes.py`` at :data:`GATEWAY_COMMIT`),
so it is served on Labor's 8000; ``qhin`` and ``qa`` are not deployed, so their
declared ports cannot be verified and are recorded here as such rather than
silently trusted.

This test is the Contracts side only. A test in Adaptix-Infra that parses the
task definitions and ``gateway.json`` and compares them with this registry is
the other half (the issue's "next action"); it cannot live in this repository,
which does not check out Infra.
"""

from __future__ import annotations

import pytest

from adaptix_contracts.schemas.service_registry import ALL_SERVICES, SERVICE_BY_SLUG

#: Adaptix-Infra ``origin/main`` as read on 2026-10-19.
INFRA_COMMIT = "6f5d90972b494148f4bf3cd68025f4dc25692a6e"
#: Adaptix-Gateway ``origin/main`` as read on 2026-10-19 (the scheduling proxy).
GATEWAY_COMMIT = "02fb20f1a6700e62891b193029c30b8501f91038"

#: How a port was established at :data:`INFRA_COMMIT`.
TASK_DEFINITION_AND_GATEWAY_URL = (
    "task definition containerPort and gateway *_SERVICE_URL"
)
GATEWAY_URL_ONLY = "gateway *_SERVICE_URL (no task definition file under that slug)"
GATEWAY_PROXY_TO_LABOR = (
    "no Infra entry; the gateway proxies the prefix to Labor (8000)"
)
NOT_DEPLOYED = (
    "not deployed: no task definition and no gateway URL; declared value, unverified"
)

#: slug -> (port, how it was established).
EXPECTED_PORTS: dict[str, tuple[int, str]] = {
    "core": (8000, TASK_DEFINITION_AND_GATEWAY_URL),
    "cad": (8000, TASK_DEFINITION_AND_GATEWAY_URL),
    "epcr": (8000, TASK_DEFINITION_AND_GATEWAY_URL),
    "fire": (8000, TASK_DEFINITION_AND_GATEWAY_URL),
    "billing": (8000, TASK_DEFINITION_AND_GATEWAY_URL),
    "crew": (8000, GATEWAY_URL_ONLY),
    "workforce": (8000, TASK_DEFINITION_AND_GATEWAY_URL),
    "transport": (8000, TASK_DEFINITION_AND_GATEWAY_URL),
    "communications": (8000, TASK_DEFINITION_AND_GATEWAY_URL),
    "telephony": (8000, TASK_DEFINITION_AND_GATEWAY_URL),
    "inventory": (8000, TASK_DEFINITION_AND_GATEWAY_URL),
    "medications": (8000, TASK_DEFINITION_AND_GATEWAY_URL),
    "narcotics": (8000, TASK_DEFINITION_AND_GATEWAY_URL),
    "labor": (8000, TASK_DEFINITION_AND_GATEWAY_URL),
    "graph": (8000, TASK_DEFINITION_AND_GATEWAY_URL),
    "air": (8000, TASK_DEFINITION_AND_GATEWAY_URL),
    "scheduling": (8000, GATEWAY_PROXY_TO_LABOR),
    "crm": (8010, TASK_DEFINITION_AND_GATEWAY_URL),
    "investor": (8011, TASK_DEFINITION_AND_GATEWAY_URL),
    "partner": (8012, TASK_DEFINITION_AND_GATEWAY_URL),
    "finance": (8013, TASK_DEFINITION_AND_GATEWAY_URL),
    "calendar": (8014, TASK_DEFINITION_AND_GATEWAY_URL),
    "search": (8015, TASK_DEFINITION_AND_GATEWAY_URL),
    "founder": (8016, TASK_DEFINITION_AND_GATEWAY_URL),
    "documents": (8017, TASK_DEFINITION_AND_GATEWAY_URL),
    "office": (8018, GATEWAY_URL_ONLY),
    "training": (8019, TASK_DEFINITION_AND_GATEWAY_URL),
    "fleet": (8020, TASK_DEFINITION_AND_GATEWAY_URL),
    "hr": (8021, GATEWAY_URL_ONLY),
    "analytics": (8022, GATEWAY_URL_ONLY),
    "compliance": (8023, GATEWAY_URL_ONLY),
    "imports": (8024, GATEWAY_URL_ONLY),
    "exports": (8025, GATEWAY_URL_ONLY),
    "policy": (8026, GATEWAY_URL_ONLY),
    "device": (8027, TASK_DEFINITION_AND_GATEWAY_URL),
    "app-management": (8028, GATEWAY_URL_ONLY),
    "ai": (8029, TASK_DEFINITION_AND_GATEWAY_URL),
    "patient-identity": (8030, TASK_DEFINITION_AND_GATEWAY_URL),
    "legal": (8031, GATEWAY_URL_ONLY),
    "integrations": (8032, GATEWAY_URL_ONLY),
    "terminology": (8033, GATEWAY_URL_ONLY),
    "marketing": (8034, GATEWAY_URL_ONLY),
    "customer-success": (8035, GATEWAY_URL_ONLY),
    "pricing": (8036, GATEWAY_URL_ONLY),
    "operations": (8037, GATEWAY_URL_ONLY),
    "nemsis": (8038, TASK_DEFINITION_AND_GATEWAY_URL),
    "neris": (8039, GATEWAY_URL_ONLY),
    "audit": (8000, TASK_DEFINITION_AND_GATEWAY_URL),
    "qhin": (8048, NOT_DEPLOYED),
    "qa": (8049, NOT_DEPLOYED),
}

#: The 17 entries Contracts #373 found wrong. Every one listens on 8000.
ISSUE_373_SERVICES: frozenset[str] = frozenset(
    {
        "cad",
        "epcr",
        "fire",
        "billing",
        "crew",
        "workforce",
        "transport",
        "communications",
        "telephony",
        "inventory",
        "medications",
        "narcotics",
        "labor",
        "graph",
        "air",
        "scheduling",
        "audit",
    }
)


def test_every_registered_service_has_a_pinned_port() -> None:
    """A new ServiceDefinition must bring its Infra-read port here.

    Otherwise the registry could grow another unverified value.
    """
    assert set(EXPECTED_PORTS) == set(SERVICE_BY_SLUG), (
        "ServiceDefinitions and EXPECTED_PORTS name different services; add the "
        f"Infra-read port for the new entry (Infra {INFRA_COMMIT[:8]})"
    )
    assert len(ALL_SERVICES) == len(EXPECTED_PORTS)


@pytest.mark.parametrize("slug", sorted(EXPECTED_PORTS))
def test_registry_port_matches_infra(slug: str) -> None:
    port, source = EXPECTED_PORTS[slug]
    assert SERVICE_BY_SLUG[slug].port == port, (
        f"{slug}: registry says {SERVICE_BY_SLUG[slug].port}, Adaptix-Infra "
        f"{INFRA_COMMIT[:8]} says {port} ({source})"
    )


def test_issue_373_services_listen_on_8000() -> None:
    """The regression for Contracts #373: these read 8001-8009 / 8040-8047."""
    wrong = {
        slug: SERVICE_BY_SLUG[slug].port
        for slug in sorted(ISSUE_373_SERVICES)
        if SERVICE_BY_SLUG[slug].port != 8000
    }
    assert not wrong, f"ports production never used (Infra {INFRA_COMMIT[:8]}): {wrong}"


def test_unverified_ports_are_named_not_hidden() -> None:
    """Only the two undeployed services carry an unverified port.

    The table says so instead of presenting a plan as production.
    """
    unverified = {
        slug for slug, (_, source) in EXPECTED_PORTS.items() if source == NOT_DEPLOYED
    }
    assert unverified == {"qhin", "qa"}
