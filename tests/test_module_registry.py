"""Tests for the canonical Adaptix module/product identifier registry.

The load-bearing property under test is the one the blocker is about:

    for EVERY purchasable module id (canonical id or any sold alias)
        purchased  => allowed
        unpurchased => denied

plus the structural invariants that keep the registry from silently rotting
(duplicate ids, aliases colliding with canonical ids, dangling ``implies``,
runtime gate slugs that no purchase can satisfy).
"""

from __future__ import annotations

import pytest

from adaptix_contracts.module_registry import (
    ALIAS_INDEX,
    MODULE_REGISTRY,
    RUNTIME_GATE_SLUGS,
    SOLD_WITHOUT_SERVICE_MAPPING,
    UnknownModuleError,
    audience_map,
    canonical_module_ids,
    expand_entitlements,
    is_any_module_entitled,
    is_module_entitled,
    module_audiences,
    normalize_module_id,
    purchasable_module_ids,
    require_module_id,
    resolve_module_id,
)
from adaptix_contracts.service_audiences import KNOWN_SERVICE_AUDIENCES


# ---------------------------------------------------------------------------
# Structural invariants
# ---------------------------------------------------------------------------


def test_registry_is_non_empty_and_keyed_by_canonical_id() -> None:
    assert MODULE_REGISTRY
    for key, definition in MODULE_REGISTRY.items():
        assert key == definition.canonical_id


def test_canonical_ids_are_already_normalized() -> None:
    for canonical_id in MODULE_REGISTRY:
        assert canonical_id == normalize_module_id(canonical_id)
        assert canonical_id, "empty canonical id"


def test_aliases_are_normalized_and_never_shadow_a_canonical_id() -> None:
    for alias, canonical in ALIAS_INDEX.items():
        assert alias == normalize_module_id(alias)
        assert alias not in MODULE_REGISTRY, f"alias {alias!r} shadows a canonical id"
        assert canonical in MODULE_REGISTRY


def test_every_implied_module_exists_and_is_not_self_referential() -> None:
    for definition in MODULE_REGISTRY.values():
        for implied in definition.implies:
            assert implied in MODULE_REGISTRY
            assert implied != definition.canonical_id


def test_runtime_gate_slugs_are_canonical() -> None:
    """A slug a live route gates on must be resolvable, or no purchase can satisfy it.

    These are the slugs verified in the workspace-wide
    ``require_module_entitlement(`` sweep. If a new service starts gating on a
    slug, it belongs in ``RUNTIME_GATE_SLUGS`` and in the registry.
    """
    assert RUNTIME_GATE_SLUGS <= canonical_module_ids()


def test_registry_covers_every_shipped_vocabulary_id() -> None:
    """Every id observed in a shipping purchase/entitlement vocabulary resolves.

    Sources (verified 2026-08-02):
      * Adaptix-Web-App  ``app/signup/_lib/types.ts::MODULES``
      * Adaptix-Core     ``core_app/signup_pricing.py::_PLAN_CATALOG``
      * Adaptix-Core     ``core_app/admin/module_toggle.py::MODULE_CATALOG``
      * Adaptix-Core     ``core_app/auth.py::_MODULE_TO_AUDIENCE``
      * Adaptix-Billing  ``billing_app/services/stripe_subscription_service.py``
    """
    web_app_signup = {
        "core",
        "epcr",
        "cad",
        "fire_rms",
        "billing",
        "telephony",
        "mobile_field",
        "nemsis_neris",
    }
    core_signup_pricing = {
        "scheduling",
        "field_app",
        "epcr",
        "billing_automation",
        "fire_response",
        "communications_command",
        "narcotics_dea",
        "cad",
        "labor",
        "crew",
        "inventory",
        "medications",
    }
    core_admin_catalog = {
        "core",
        "cad",
        "epcr",
        "billing",
        "crew",
        "comms",
        "workspace",
        "narcotics",
        "medications",
        "inventory",
        "labor",
        "transport",
        "air",
        "fire",
        "calendar",
        "search",
        "finance",
        "investor",
        "partner",
        "founder",
        "crm",
        "graph",
        "telephony",
        "field",
        "workforce",
        "assetops",
    }
    billing_products = {
        "scheduling",
        "cad",
        "crewlink",
        "mdt",
        "epcr",
        "billing_automation",
        "agency_billing_portal",
        "hems_ops",
        "cct_transport_ops",
        "wisconsin_trip_pack",
        "managed_billing",
        "onboarding",
    }

    unresolved = sorted(
        module_id
        for module_id in web_app_signup
        | core_signup_pricing
        | core_admin_catalog
        | billing_products
        if resolve_module_id(module_id) is None
    )
    assert unresolved == [], f"unregistered shipped module ids: {unresolved}"


# ---------------------------------------------------------------------------
# STEP 3 â€” purchased => allowed, unpurchased => denied, for EVERY purchasable id
# ---------------------------------------------------------------------------


def _purchasable_spellings() -> list[tuple[str, str]]:
    """(canonical_id, spelling) for every purchasable module and each alias."""
    pairs: list[tuple[str, str]] = []
    for definition in MODULE_REGISTRY.values():
        if not definition.purchasable:
            continue
        pairs.append((definition.canonical_id, definition.canonical_id))
        for alias in sorted(definition.aliases):
            pairs.append((definition.canonical_id, alias))
    return sorted(pairs)


PURCHASABLE_SPELLINGS = _purchasable_spellings()


def test_there_is_at_least_one_purchasable_module() -> None:
    assert purchasable_module_ids()
    assert PURCHASABLE_SPELLINGS


@pytest.mark.parametrize(("canonical_id", "spelling"), PURCHASABLE_SPELLINGS)
def test_purchased_module_is_allowed(canonical_id: str, spelling: str) -> None:
    """Buying a module under ANY sold spelling satisfies the canonical gate."""
    purchased = ["core", spelling]
    assert is_module_entitled(canonical_id, purchased) is True
    # The gate may also (legacy) be declared with the sold spelling itself.
    assert is_module_entitled(spelling, purchased) is True
    # Case / whitespace noise on the wire must not change the decision.
    assert is_module_entitled(canonical_id.upper(), [f"  {spelling.upper()}  "]) is True


@pytest.mark.parametrize(("canonical_id", "spelling"), PURCHASABLE_SPELLINGS)
def test_unpurchased_module_is_denied(canonical_id: str, spelling: str) -> None:
    """A tenant that did not buy the module is denied under every spelling.

    The "other tenant" holds every purchasable module EXCEPT this one and
    everything that implies it â€” so the denial is proven against a realistically
    large entitlement set, not against an empty list.
    """
    definition = MODULE_REGISTRY[canonical_id]
    excluded = {canonical_id, spelling} | set(definition.aliases)
    # Anything that transitively grants this module must also be withheld,
    # otherwise the tenant legitimately HAS it.
    for other in MODULE_REGISTRY.values():
        if canonical_id in expand_entitlements([other.canonical_id]) - {
            other.canonical_id
        }:
            excluded.add(other.canonical_id)
            excluded |= set(other.aliases)

    granted = sorted(purchasable_module_ids() - excluded)
    assert canonical_id not in expand_entitlements(granted)
    assert is_module_entitled(canonical_id, granted) is False
    assert is_module_entitled(spelling, granted) is False


@pytest.mark.parametrize(("canonical_id", "spelling"), PURCHASABLE_SPELLINGS)
def test_empty_entitlements_deny_every_purchasable_module(
    canonical_id: str, spelling: str
) -> None:
    for granted in ([], None, [""], ["   "]):
        assert is_module_entitled(canonical_id, granted) is False
        assert is_module_entitled(spelling, granted) is False


# ---------------------------------------------------------------------------
# The specific verified drift pairs from the blocker
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sold_as", "gated_as"),
    [
        # Adaptix-Core signup_pricing sells these; the runtime gates on the right.
        ("billing_automation", "billing"),
        ("fire_response", "fire"),
        ("field_app", "mdt"),
        ("communications_command", "communications"),
        ("narcotics_dea", "narcotics"),
        # Adaptix-Web-App signup wizard sells these.
        ("fire_rms", "fire"),
        ("mobile_field", "mdt"),
        # Adaptix-Core admin catalog spelling.
        ("field", "mdt"),
        ("comms", "communications"),
    ],
)
def test_sold_identifier_satisfies_the_gate_identifier(
    sold_as: str, gated_as: str
) -> None:
    assert resolve_module_id(sold_as) == gated_as
    assert is_module_entitled(gated_as, ["core", sold_as]) is True


@pytest.mark.parametrize(
    ("purchased", "also_granted"),
    [
        ("workforce", "labor"),
        ("workforce", "scheduling"),
        ("transport", "transportlink"),
        ("nemsis_neris", "nemsis"),
        ("nemsis_neris", "neris"),
        ("managed_billing", "billing"),
        ("agency_billing_portal", "billing"),
    ],
)
def test_bundle_purchase_grants_its_implied_modules(
    purchased: str, also_granted: str
) -> None:
    assert is_module_entitled(also_granted, ["core", purchased]) is True


def test_implication_is_directional_not_symmetric() -> None:
    """Buying the narrow module must NOT grant the bundle that implies it."""
    assert is_module_entitled("workforce", ["labor", "scheduling"]) is False
    assert is_module_entitled("nemsis_neris", ["nemsis", "neris"]) is False
    assert is_module_entitled("managed_billing", ["billing"]) is False


# ---------------------------------------------------------------------------
# Non-narrowing guarantee
# ---------------------------------------------------------------------------


def test_expansion_never_drops_an_input_id() -> None:
    """Resolution is strictly additive â€” anything entitled today stays entitled."""
    raw = ["billing_automation", "totally_unregistered_module", "EPCR", " cad "]
    expanded = expand_entitlements(raw)
    for value in raw:
        assert normalize_module_id(value) in expanded


def test_unregistered_ids_still_match_themselves() -> None:
    """An id the registry has not learned yet must keep working by exact match."""
    assert resolve_module_id("totally_unregistered_module") is None
    assert (
        is_module_entitled(
            "totally_unregistered_module", ["totally_unregistered_module"]
        )
        is True
    )
    assert is_module_entitled("totally_unregistered_module", ["billing"]) is False


def test_blank_and_none_inputs_are_denied_not_crashing() -> None:
    assert is_module_entitled("", ["billing"]) is False
    assert is_module_entitled(None, ["billing"]) is False
    assert expand_entitlements(None) == frozenset()
    assert expand_entitlements([]) == frozenset()
    assert expand_entitlements([None, "", "  "]) == frozenset()


def test_is_any_module_entitled_matches_one_of_many() -> None:
    assert is_any_module_entitled(["mdt", "crewlink"], ["core", "mobile_field"]) is True
    assert is_any_module_entitled(["mdt", "crewlink"], ["core", "crewlink"]) is True
    assert is_any_module_entitled(["mdt", "crewlink"], ["core", "epcr"]) is False


def test_require_module_id_rejects_unknown_ids() -> None:
    assert require_module_id("Billing_Automation") == "billing"
    with pytest.raises(UnknownModuleError):
        require_module_id("no_such_module")


# ---------------------------------------------------------------------------
# Billable-but-dark regression gate
#
# The defect class this guards against: a tenant pays for a module, Core mints
# a JWT whose ``aud`` list does not cover that module's upstream service, and
# the gateway answers 403 ``jwt_audience_mismatch`` on every request. The
# module is billed and dark, and NOTHING fails â€” not a type check, not a unit
# test, not a health check, not a dashboard.
#
# RUNTIME-PROVEN in production 2026-08-04T14:18:47Z with a real agency_admin
# token for tenant 1460aa33 whose module_entitlements contained "scheduling":
#
#   GET /api/v1/workforce/shifts    -> 403 jwt_audience_mismatch
#                                      expected "adaptix-labor"
#   GET /api/v1/labor/shifts        -> 403 jwt_audience_mismatch
#   GET /api/v1/cad/units/available -> 200  (same token, same minute)
#
# ``scheduling`` is included in every Core signup plan AND every live
# /api/v1/billing/plans tier, so this hit 100% of paying agencies.
# ---------------------------------------------------------------------------


def test_every_purchasable_module_resolves_to_at_least_one_audience() -> None:
    """A SKU a customer can buy MUST reach a service, or it is billed and dark.

    Failing here means someone added or changed a purchasable module without
    giving it an ``audience`` (or an ``implies`` that reaches one). Fix it by
    setting the audience the module's gateway ``RouteEntry`` declares in
    ``Adaptix-Gateway/backend/app/config/routes.py`` â€” never by inventing one,
    and never by adding the id to ``SOLD_WITHOUT_SERVICE_MAPPING`` to silence
    the test unless the owning service genuinely does not exist yet.
    """
    dark = {
        module_id
        for module_id in purchasable_module_ids()
        if not module_audiences(module_id)
    }
    assert dark <= SOLD_WITHOUT_SERVICE_MAPPING, (
        "purchasable modules that resolve to ZERO service audiences â€” a tenant "
        f"can be billed for these and reach nothing: {sorted(dark - SOLD_WITHOUT_SERVICE_MAPPING)}"
    )


def test_every_sold_alias_resolves_to_the_same_audiences_as_its_canonical_id() -> None:
    """The spelling a plan sells must reach exactly what the canonical id reaches.

    ``signup_pricing`` persists ``billing_automation`` / ``fire_response`` /
    ``field_app`` verbatim into ``metadata_json["module_entitlements"]``, so
    the SOLD spelling is what Core resolves at token-mint time. An alias that
    resolves to fewer audiences than its canonical id is the same
    billed-and-dark defect wearing a different name.
    """
    for canonical_id, definition in MODULE_REGISTRY.items():
        for alias in definition.aliases:
            assert module_audiences(alias) == module_audiences(canonical_id), (
                f"alias {alias!r} reaches {sorted(module_audiences(alias))} but "
                f"canonical {canonical_id!r} reaches "
                f"{sorted(module_audiences(canonical_id))}"
            )


def test_quarantined_modules_are_real_purchasable_ids_with_no_audience() -> None:
    """``SOLD_WITHOUT_SERVICE_MAPPING`` must not accumulate stale entries.

    Once a quarantined SKU is given its audience, this fails until the id is
    removed from the set â€” so the quarantine list can only shrink, never rot.
    """
    for module_id in SOLD_WITHOUT_SERVICE_MAPPING:
        assert module_id in MODULE_REGISTRY, (
            f"{module_id!r} is quarantined but is not a registered module"
        )
        assert MODULE_REGISTRY[module_id].purchasable, (
            f"{module_id!r} is quarantined but is not purchasable â€” the "
            "quarantine is only for SKUs a customer can be charged for"
        )
        assert not module_audiences(module_id), (
            f"{module_id!r} now resolves to "
            f"{sorted(module_audiences(module_id))} â€” delete it from "
            "SOLD_WITHOUT_SERVICE_MAPPING"
        )


def test_every_declared_audience_is_a_known_live_service_audience() -> None:
    """An audience the gateway does not know is unroutable â€” 403 for everyone."""
    unknown = sorted(set(audience_map().values()) - KNOWN_SERVICE_AUDIENCES)
    assert not unknown, (
        f"module audiences absent from KNOWN_SERVICE_AUDIENCES: {unknown}"
    )


def test_runtime_gated_modules_reach_the_service_that_gates_them() -> None:
    """A slug a service gates on must also mint an audience reaching that service.

    Otherwise the module gate can never even be evaluated: the gateway rejects
    the request on audience before the service sees it. This is precisely the
    ``scheduling`` failure â€” Core gated on the module while the gateway refused
    the audience.
    """
    for slug in sorted(RUNTIME_GATE_SLUGS):
        assert module_audiences(slug), (
            f"{slug!r} is enforced by a live require_module_entitlement() call "
            "but resolves to no audience â€” every request 403s at the gateway "
            "before the gate runs"
        )


def test_scheduling_reaches_labor_service() -> None:
    """Pinned regression for the exact production failure.

    Gateway ``RouteEntry(prefix="/api/v1/scheduling", audience="adaptix-labor")``.
    Holding ``scheduling`` must therefore mint ``adaptix-labor``, and must NOT
    silently confer the separately-sold ``labor`` module entitlement.
    """
    assert "adaptix-labor" in module_audiences("scheduling")
    assert "labor" not in expand_entitlements(["scheduling"])


def test_field_app_and_crewlink_reach_cad_service() -> None:
    """Both routers live inside Adaptix-CAD-Service, so both need adaptix-cad.

    ``field_app`` is the spelling ``signup_pricing`` persists for the mobile
    field product; it resolves to ``mdt``.
    """
    assert module_audiences("field_app") == {"adaptix-cad"}
    assert module_audiences("mdt") == {"adaptix-cad"}
    assert module_audiences("crewlink") == {"adaptix-cad"}
    # Reaching CAD's audience must not confer the CAD module itself â€” CAD
    # mounts /api/v1/cad and /api/v1/mdt under
    # Depends(require_module_entitlement("cad")), which still applies.
    assert "cad" not in expand_entitlements(["mdt"])
    assert "cad" not in expand_entitlements(["crewlink"])


def test_assetops_reaches_its_own_service() -> None:
    """Live $29/vehicle/month SKU; gateway routes /api/v1/assetops to it."""
    assert module_audiences("assetops") == {"adaptix-assetops"}


def test_audience_map_is_consistent_with_the_registry() -> None:
    """``audience_map()`` is what Core derives ``_MODULE_TO_AUDIENCE`` from."""
    mapping = audience_map()
    for module_id, audience in mapping.items():
        assert MODULE_REGISTRY[module_id].audience == audience
    for module_id, definition in MODULE_REGISTRY.items():
        if definition.audience:
            assert mapping[module_id] == definition.audience
        else:
            assert module_id not in mapping


# ---------------------------------------------------------------------------
# Module-id canonicalization drift (underscore/hyphen, singular/plural).
#
# Core persists + mints the canonical module id (``patient_identity`` underscore,
# ``integration`` singular); the owning service is slugged with the drifted
# spelling (``patient-identity`` hyphen, ``integrations`` plural â€” see
# ``service_registry`` + the gateway ROUTE_TABLE), so a guard declared with the
# service spelling denied an entitled tenant under exact match. These pin the
# alias resolution so the drift cannot silently return.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("service_spelling", "canonical"),
    [
        ("patient-identity", "patient_identity"),
        ("integrations", "integration"),
    ],
)
def test_service_spelling_resolves_to_the_canonical_module(
    service_spelling: str, canonical: str
) -> None:
    assert resolve_module_id(service_spelling) == canonical
    # A guard declared with the service spelling is satisfied by a token that
    # carries the canonical id (the real production shape), and vice-versa.
    assert is_module_entitled(service_spelling, ["core", canonical]) is True
    assert is_module_entitled(canonical, ["core", service_spelling]) is True
    # Same reachable audience under either spelling.
    assert module_audiences(service_spelling) == module_audiences(canonical)
    assert module_audiences(service_spelling), (
        "drifted module must reach a service audience"
    )


@pytest.mark.parametrize("service_spelling", ["patient-identity", "integrations"])
def test_service_spelling_does_not_widen_entitlement(service_spelling: str) -> None:
    """The alias unifies spellings of ONE module; it grants no other module."""
    # A tenant that holds only an unrelated module is still denied.
    assert is_module_entitled(service_spelling, ["core", "epcr"]) is False
    assert is_module_entitled(service_spelling, ["core"]) is False
    # The drifted spelling never leaks into ``audience_map()`` keys â€” Core keys
    # ``_MODULE_TO_AUDIENCE`` by canonical id, so an alias key there would be a
    # dead audience row.
    assert service_spelling not in audience_map()


def test_facilities_reaches_its_own_service() -> None:
    """The facility registry gateway route is behind audience adaptix-facilities.

    Regression pin for the gap proven live 2026-08-14: the gateway enforced
    adaptix-facilities on /api/v1/facilities, but no module entitlement mapped
    to it, so no tenant JWT could ever carry that audience and every facilities
    request 403'd jwt_audience_mismatch. Removing the ``facilities`` registry
    row turns this RED.
    """
    assert module_audiences("facilities") == {"adaptix-facilities"}
    # The drifted spellings a caller might send resolve to the same audience.
    assert module_audiences("facility") == {"adaptix-facilities"}
    assert module_audiences("facility_registry") == {"adaptix-facilities"}


def test_rtc_reaches_its_own_service() -> None:
    """The realtime room control plane gateway route is behind adaptix-rtc.

    Regression pin for the gap this module row closes: the gateway already
    routes /api/v1/rtc to its own upstream with audience ``adaptix-rtc``, and
    ``adaptix-rtc`` was already in ``KNOWN_SERVICE_AUDIENCES`` -- but with no
    module-registry row, ``audience_map()`` had no ``rtc`` key, so no tenant's
    session (including a Cortex Live demo tenant) could ever carry the
    ``adaptix-rtc`` audience, and every /api/v1/rtc request 403'd
    jwt_audience_mismatch. Removing the ``rtc`` registry row turns this RED.
    """
    assert module_audiences("rtc") == {"adaptix-rtc"}
    assert audience_map()["rtc"] == "adaptix-rtc"
