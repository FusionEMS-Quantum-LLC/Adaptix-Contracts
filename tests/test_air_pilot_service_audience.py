"""Air-Pilot is a first-class service audience, granted through ``air`` (DEF-031).

Adaptix-Air-Service-Pilot runs as its own ECS service
(``adaptix-production-air-pilot``) behind the gateway prefix
``/api/v1/air-pilot``, but it has always shared Air's audience
``adaptix-air``: the gateway signed ``aud=adaptix-air`` for its routes and its
task definition pinned ``ADAPTIX_GATEWAY_EXPECTED_AUDIENCE=adaptix-air``. Once
the gateway records a distinct Service Power Manager identity for Air-Pilot
(``service_name="adaptix-air-pilot"``), the gateway's own invariant that two
distinct services never share one audience
(``tests/unit/test_identity_header_contract.py::
test_distinct_services_get_distinct_audiences``) requires an audience of its
own. The lockstep split starts here, because:

* the gateway refuses to start with a route audience outside
  ``KNOWN_SERVICE_AUDIENCES`` (``routes.py: KNOWN_AUDIENCES``), and the
  downstream verifier raises ``GatewayVerifierConfigurationError`` when
  ``ADAPTIX_GATEWAY_EXPECTED_AUDIENCE`` names an unknown audience
  (``gateway_signature._expected_audience``);
* Core mints a tenant's ``aud`` from ``audience_map()`` over the tenant's
  expanded entitlements, so an Air-entitled tenant only reaches Air-Pilot on
  the new audience if a module carries it AND ``air`` implies that module.

These tests pin that contract. They are written against the registry as it is
consumed (``expand_entitlements`` / ``module_audiences`` / ``audience_map``),
not against private tables, so a refactor that keeps the contract keeps them.
"""

from __future__ import annotations

from adaptix_contracts.module_registry import (
    MODULE_REGISTRY,
    audience_map,
    expand_entitlements,
    module_audiences,
    purchasable_module_ids,
    resolve_module_id,
)
from adaptix_contracts.service_audiences import (
    KNOWN_SERVICE_AUDIENCES,
    is_known_service_audience,
)

AIR_AUDIENCE = "adaptix-air"
AIR_PILOT_AUDIENCE = "adaptix-air-pilot"
AIR_MODULE = "air"
AIR_PILOT_MODULE = "air-pilot"


def test_air_pilot_is_a_known_service_audience() -> None:
    """The gateway route validator and the downstream pin both read this set."""
    assert AIR_PILOT_AUDIENCE in KNOWN_SERVICE_AUDIENCES
    assert is_known_service_audience(AIR_PILOT_AUDIENCE)
    assert is_known_service_audience(" Adaptix-Air-Pilot ")
    # Air keeps its own audience; the split adds, it does not rename.
    assert AIR_AUDIENCE in KNOWN_SERVICE_AUDIENCES


def test_air_pilot_module_maps_to_its_own_audience() -> None:
    assert resolve_module_id(AIR_PILOT_MODULE) == AIR_PILOT_MODULE
    assert MODULE_REGISTRY[AIR_PILOT_MODULE].audience == AIR_PILOT_AUDIENCE
    assert audience_map()[AIR_PILOT_MODULE] == AIR_PILOT_AUDIENCE
    assert module_audiences(AIR_PILOT_MODULE) == {AIR_PILOT_AUDIENCE}


def test_air_implies_air_pilot_so_an_air_tenant_is_minted_both_audiences() -> None:
    """Core expands entitlements through ``implies`` and then maps each id
    through ``audience_map()``: an ``air`` tenant must come out holding both."""
    assert AIR_PILOT_MODULE in MODULE_REGISTRY[AIR_MODULE].implies
    assert expand_entitlements([AIR_MODULE]) == {AIR_MODULE, AIR_PILOT_MODULE}
    assert module_audiences(AIR_MODULE) == {AIR_AUDIENCE, AIR_PILOT_AUDIENCE}
    minted = {
        audience_map()[module_id] for module_id in expand_entitlements([AIR_MODULE])
    }
    assert minted == {AIR_AUDIENCE, AIR_PILOT_AUDIENCE}


def test_air_keeps_its_own_audience_for_core_floor() -> None:
    """Core's ``_MODULE_TO_AUDIENCE_FLOOR`` pins ``air -> adaptix-air`` and
    requires the derived table to stay a superset of it."""
    assert audience_map()[AIR_MODULE] == AIR_AUDIENCE
    assert MODULE_REGISTRY[AIR_MODULE].audience == AIR_AUDIENCE


def test_implication_is_directional_air_pilot_does_not_grant_air() -> None:
    assert expand_entitlements([AIR_PILOT_MODULE]) == {AIR_PILOT_MODULE}
    assert AIR_MODULE not in MODULE_REGISTRY[AIR_PILOT_MODULE].implies
    assert AIR_AUDIENCE not in module_audiences(AIR_PILOT_MODULE)


def test_air_pilot_is_granted_through_air_not_sold_separately() -> None:
    """No signup wizard, pricing catalog or Stripe product sells it; it is
    reached through the Air SKU, like ``nemsis``/``neris`` through
    ``nemsis_neris``."""
    assert MODULE_REGISTRY[AIR_PILOT_MODULE].purchasable is False
    assert AIR_PILOT_MODULE not in purchasable_module_ids()
    assert AIR_MODULE in purchasable_module_ids()


def test_every_module_audience_is_known_and_the_registries_agree_on_air_pilot() -> None:
    """``audience_map()`` values stay a subset of ``KNOWN_SERVICE_AUDIENCES``
    (the invariant ``test_module_registry`` enforces for every module), and the
    new audience is reachable from exactly one module."""
    declared = frozenset(audience_map().values())
    assert declared <= KNOWN_SERVICE_AUDIENCES
    owners = sorted(m for m, a in audience_map().items() if a == AIR_PILOT_AUDIENCE)
    assert owners == [AIR_PILOT_MODULE]
