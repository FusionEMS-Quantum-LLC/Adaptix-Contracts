"""Canonical Adaptix product / module identifier registry.

SINGLE SOURCE OF TRUTH for "what is a module id" across the Adaptix polyrepo.

Why this exists
---------------
Five independent vocabularies for the same products had drifted apart, and the
runtime entitlement gate does **exact** normalized string matching. A tenant
could therefore pay for a module and still be denied it. Verified drift at the
time this registry was written:

===============================  ==========================================================
Vocabulary (file)                Ids it uses
===============================  ==========================================================
Adaptix-Web-App signup wizard    ``core epcr cad fire_rms billing telephony mobile_field
``app/signup/_lib/types.ts:56``  nemsis_neris``
(``MODULES``, line 66)

Adaptix-Core signup pricing      ``scheduling field_app epcr billing_automation
``core_app/signup_pricing.py``   fire_response communications_command narcotics_dea cad
(``_PLAN_CATALOG``, line 67)     labor crew inventory medications``

Adaptix-Core audience map        ``core billing epcr cad fire air ... communications
``core_app/auth.py:124``         telephony ... nemsis neris ...``
(``_MODULE_TO_AUDIENCE``)

Adaptix-Core admin toggle        ``core cad epcr billing crew comms workspace narcotics
``core_app/admin/module_toggle`` medications inventory labor transport air fire calendar
(``MODULE_CATALOG``, line 51)    search finance investor partner founder crm graph
                                 telephony field workforce assetops``

Adaptix-Billing Stripe products  ``scheduling cad crewlink mdt epcr billing_automation
``billing_app/services/          agency_billing_portal hems_ops cct_transport_ops
stripe_subscription_service.py`` wisconsin_trip_pack managed_billing onboarding``
(``_PRODUCT_MODULE_MAP``, l.59)
===============================  ==========================================================

Runtime gates (verified by sweeping ``require_module_entitlement(`` across the
workspace on 2026-08-02) enforce only these slugs::

    air  assetops  billing  cad  crewlink  epcr  fire  mdt  scheduling

Every one of those is a ``canonical_id`` below. That is a hard invariant â€” see
``tests/test_module_registry.py::test_runtime_gate_slugs_are_canonical``.

Design contract
---------------
* **Nothing customer-visible is renamed.** Canonical ids are the slugs the
  runtime already enforces; every other spelling is registered as an explicit
  legacy ``alias``.
* **Resolution is additive, never narrowing.** :func:`expand_entitlements`
  always returns the caller's own normalized ids *plus* their canonical
  resolutions *plus* transitively implied ids. An id that is entitled today
  stays entitled after this registry is consumed. Unknown ids pass through
  untouched, so an id that has not been registered yet cannot be silently
  dropped.
* **Two distinct relations**, deliberately not merged:

  ``aliases``
      Exact synonyms for the *same* product (``billing_automation`` and
      ``billing`` are one module with two spellings).
  ``implies``
      A purchase that additionally grants a *different* module (buying
      ``workforce`` also grants ``labor`` and ``scheduling``; buying the
      ``nemsis_neris`` bundle grants both ``nemsis`` and ``neris``).

  Collapsing ``implies`` into ``aliases`` would destroy the ability to gate a
  route on the narrower module later, so they stay separate.

Usage
-----
Gate side (does this caller hold the required module?)::

    from adaptix_contracts.module_registry import is_module_entitled

    if is_module_entitled("billing", tenant_entitlements):
        ...

Provisioning side (what should be persisted / minted for this purchase?)::

    from adaptix_contracts.module_registry import expand_entitlements

    granted = expand_entitlements(purchased_module_ids)
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

__all__ = [
    "ModuleDefinition",
    "MODULE_REGISTRY",
    "ALIAS_INDEX",
    "RUNTIME_GATE_SLUGS",
    "SOLD_WITHOUT_SERVICE_MAPPING",
    "UnknownModuleError",
    "audience_map",
    "canonical_module_ids",
    "expand_entitlements",
    "is_any_module_entitled",
    "is_module_entitled",
    "module_audiences",
    "normalize_module_id",
    "purchasable_module_ids",
    "resolve_module_id",
    "require_module_id",
]


# ---------------------------------------------------------------------------
# Definition
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModuleDefinition:
    """One canonical Adaptix module.

    Attributes:
        canonical_id: The authoritative slug. This is what routes gate on and
            what SHOULD be persisted going forward. Never renamed without an
            alias covering the old spelling.
        display_name: Human label. Presentation only â€” never an identifier.
        aliases: Legacy / alternate spellings of THIS SAME module. Any of these
            resolve to ``canonical_id``.
        implies: Canonical ids that are additionally granted when this module is
            granted. Directional (implying X does not imply the reverse).
        purchasable: True when the id appears in a customer-facing purchase
            surface (signup wizard, signup pricing catalog, or a Stripe product
            module map). False for platform-internal modules.
        audience: The gateway JWT ``aud`` value for the module's upstream
            service â€” the value the ``RouteEntry`` for that module's prefix
            declares in ``Adaptix-Gateway/backend/app/config/routes.py``. This
            is the SOURCE for Adaptix-Core ``core_app/auth.py::
            _MODULE_TO_AUDIENCE``, which is derived from this field.

            Two modules MAY share one audience when they are served by the same
            upstream (``mdt`` and ``crewlink`` both resolve to ``adaptix-cad``
            because both routers are mounted inside Adaptix-CAD-Service). That
            is correct and is not drift.

            ``None`` means "this id confers no service reachability at all".
            It must ONLY be used for a module whose whole surface is served by
            Core itself (``adaptix-core`` is always in every session ``aud``),
            or for a non-purchasable grouping id. A **purchasable** module with
            ``audience=None`` and no ``implies`` that reaches an audience is a
            billable-but-dark SKU: the tenant pays, the gate mints no audience,
            and the gateway returns 403 ``jwt_audience_mismatch`` on every
            request. ``tests/test_module_registry.py::
            test_every_purchasable_module_resolves_to_an_audience`` fails on
            exactly that condition â€” see ``SOLD_WITHOUT_SERVICE_MAPPING`` for
            the only sanctioned exceptions.
        source: Where each spelling was observed. Documentation only; keeps the
            registry auditable against the repos it unifies.
    """

    canonical_id: str
    display_name: str
    aliases: frozenset[str] = field(default_factory=frozenset)
    implies: frozenset[str] = field(default_factory=frozenset)
    purchasable: bool = False
    audience: str | None = None
    source: str = ""


def _m(
    canonical_id: str,
    display_name: str,
    *,
    aliases: Iterable[str] = (),
    implies: Iterable[str] = (),
    purchasable: bool = False,
    audience: str | None = None,
    source: str = "",
) -> ModuleDefinition:
    return ModuleDefinition(
        canonical_id=canonical_id,
        display_name=display_name,
        aliases=frozenset(aliases),
        implies=frozenset(implies),
        purchasable=purchasable,
        audience=audience,
        source=source,
    )


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------
#
# Ordering below groups by "sold as a module" first, then platform modules that
# are entitlement-bearing but not individually sold.
#
# EVERY alias listed here was read out of a real file; the ``source`` field
# names it. Do not add an alias that is not observed in a shipping vocabulary.

_DEFINITIONS: tuple[ModuleDefinition, ...] = (
    # â”€â”€ Platform base â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    _m(
        "core",
        "Core Platform",
        purchasable=True,
        audience="adaptix-core",
        source="Web-App MODULES; Core MODULE_CATALOG; Core _MODULE_TO_AUDIENCE",
    ),
    # â”€â”€ Clinical / documentation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    _m(
        "epcr",
        "ePCR & NEMSIS",
        aliases=("epcr_nemsis",),
        purchasable=True,
        audience="adaptix-epcr",
        source="Web-App MODULES; Core signup_pricing; Billing _PRODUCT_MODULE_MAP",
    ),
    # â”€â”€ Dispatch â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    _m(
        "cad",
        "CAD / Dispatch",
        purchasable=True,
        audience="adaptix-cad",
        source="Web-App MODULES; Core signup_pricing; Billing _PRODUCT_MODULE_MAP",
    ),
    # â”€â”€ Revenue cycle â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # `billing_automation` is the Stripe product "Adaptix Billing Command
    # Automation" (Core signup_pricing.py:83,111; Billing seed_v2_stripe_prices
    # .py:56). It is the SAME module Adaptix-Billing-Service gates on as
    # `billing` (billing_app/main.py:968). Without this alias, every agency that
    # bought Billing Automation was denied /api/v1/billing/* with 402
    # module_not_entitled.
    _m(
        "billing",
        "Billing",
        aliases=("billing_automation",),
        purchasable=True,
        audience="adaptix-billing",
        source="Web-App MODULES ('billing'); Core signup_pricing ('billing_automation')",
    ),
    _m(
        "agency_billing_portal",
        "Agency Billing Portal",
        implies=("billing",),
        purchasable=True,
        source="Billing _PRODUCT_MODULE_MAP (Growth/Enterprise/Managed Billing)",
    ),
    _m(
        "managed_billing",
        "Adaptix Managed Billing",
        implies=("billing", "agency_billing_portal"),
        purchasable=True,
        source="Billing _PRODUCT_MODULE_MAP prod_UVUZCL2pqFvptr",
    ),
    # implies: the Stripe product ships ``enabled_modules = ["wisconsin_trip_pack",
    # "billing_automation"]`` and carries ``requires_product_id =
    # prod_UEOH2V8H1u39rY`` (Billing Command Automation), i.e. the TRIP Pack is
    # a Wisconsin payer/claim ruleset INSIDE Billing and is never sold alone.
    # Recording the bundle here is what the SKU already sells â€” it grants
    # nothing the purchaser is not already charged for.
    _m(
        "wisconsin_trip_pack",
        "Adaptix Wisconsin TRIP Pack",
        implies=("billing",),
        purchasable=True,
        source=(
            "Billing _PRODUCT_MODULE_MAP prod_UEOHlRtTmKGvfo "
            "(enabled_modules: wisconsin_trip_pack + billing_automation)"
        ),
    ),
    # â”€â”€ Fire â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Three spellings of one product: Web-App sells `fire_rms`, Core pricing
    # sells `fire_response`, Adaptix-Fire-Service gates on `fire`.
    _m(
        "fire",
        "Fire / NFIRS RMS",
        aliases=("fire_rms", "fire_response"),
        purchasable=True,
        audience="adaptix-fire",
        source="Web-App MODULES ('fire_rms'); Core signup_pricing ('fire_response')",
    ),
    _m(
        "crr",
        "Community Risk Reduction",
        aliases=("vision2020",),
        purchasable=True,
        audience="adaptix-fire",
        implies=("fire",),
        source="adaptix-crr",
    ),
    # â”€â”€ Air medical â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    _m(
        "air",
        "Air Medical",
        purchasable=True,
        audience="adaptix-air",
        source="Core MODULE_CATALOG; Core _MODULE_TO_AUDIENCE; Air-Service gate",
    ),
    # ``hems_ops`` and ``cct_transport_ops`` are BUNDLE MARKER ids, not
    # standalone products: no ``/api/v1/hems`` or ``/api/v1/cct`` RouteEntry
    # exists and no service gates on either slug. What the customer actually
    # buys is the module list the Stripe product ships, read verbatim from
    # Adaptix-Billing ``stripe_subscription_service.py::_PRODUCT_MODULE_MAP``:
    #
    #   prod_UEOHT3EFG7BSxF "Adaptix HEMS Ops"  ($750/mo, HEMS_OPS_V1_MONTHLY)
    #     enabled_modules = [hems_ops, cad, crewlink, mdt, epcr, billing_automation]
    #   prod_UEOHmIlaVBQJMX "Adaptix CCT / Transport Ops"
    #     enabled_modules = [cct_transport_ops, cad, crewlink, mdt, epcr, billing_automation]
    #
    # The ``implies`` below is exactly that list, so it grants nothing the
    # purchaser is not already charged for â€” it only makes the marker id
    # self-sufficient when a plan surface (e.g. the live $999 ``enterprise``
    # tier of GET /api/v1/billing/plans) lists it.
    #
    # Deliberately NOT implying ``air`` or ``transport``: the Stripe map does
    # not ship those, and mapping a SKU to a service on the strength of its
    # NAME would hand every enterprise-tier agency the whole Air / Transport
    # product. That is a pricing decision, not an inference.
    _m(
        "hems_ops",
        "Adaptix HEMS Ops",
        implies=("cad", "crewlink", "mdt", "epcr", "billing"),
        purchasable=True,
        source="Billing _PRODUCT_MODULE_MAP prod_UEOHT3EFG7BSxF enabled_modules",
    ),
    _m(
        "cct_transport_ops",
        "Adaptix CCT / Transport Ops",
        implies=("cad", "crewlink", "mdt", "epcr", "billing"),
        purchasable=True,
        source="Billing _PRODUCT_MODULE_MAP prod_UEOHmIlaVBQJMX enabled_modules",
    ),
    # â”€â”€ Field / mobile â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # The crew-facing tablet/phone application. Web-App sells `mobile_field`,
    # Core pricing includes it as `field_app`, Core's admin catalog spells it
    # `field`, and Adaptix-CAD-Service gates the write-back surface on `mdt`.
    # audience: the /api/v1/mdt RouteEntry declares ``adaptix-cad`` (the
    # mdt_operations_router / mdt_fatigue_router are mounted INSIDE
    # Adaptix-CAD-Service, same ECS task as /api/v1/cad). Registering the
    # audience here does NOT hand a buyer the CAD product: CAD-Service mounts
    # those routers under ``Depends(require_module_entitlement("cad"))``
    # (cad_app/main.py), so the module gate still applies after the audience
    # gate. See PLAN-AUDIENCE-MATRIX in tests/test_module_registry.py.
    _m(
        "mdt",
        "Mobile / Field (MDT)",
        aliases=("mobile_field", "field_app", "field"),
        purchasable=True,
        audience="adaptix-cad",
        source=(
            "Web-App MODULES ('mobile_field'); Core signup_pricing ('field_app'); "
            "Gateway ROUTE_TABLE /api/v1/mdt -> cad_service_url audience=adaptix-cad"
        ),
    ),
    # audience: /api/v1/crewlink routes to cad_service_url with audience
    # ``adaptix-cad`` (the crewlink_router lives in Adaptix-CAD-Service). Every
    # operational crewlink route carries its OWN
    # ``Depends(require_module_entitlement("crewlink"))``
    # (cad_app/api/crewlink_router.py) and the crewlink router is included
    # WITHOUT the cad gate, so a crewlink buyer reaches crewlink and nothing
    # else. Verified in prod 2026-08-04: a token holding adaptix-cad but NOT
    # the crewlink module got 403 MODULE_NOT_ENTITLED on /api/v1/crewlink/pages
    # â€” the module gate, not the audience, is what protects this surface.
    _m(
        "crewlink",
        "CrewLink",
        purchasable=True,
        audience="adaptix-cad",
        source=(
            "Billing _PRODUCT_MODULE_MAP; CAD-Service gate; "
            "Gateway ROUTE_TABLE /api/v1/crewlink -> cad_service_url audience=adaptix-cad"
        ),
    ),
    # â”€â”€ Workforce / scheduling â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Mirrors Core auth.py::_MODULE_ENTITLEMENT_ALIASES â€” `workforce` is the id
    # Core historically persists, but the scheduling engine is served by
    # Labor-Service behind the `labor` / `scheduling` entitlements.
    _m(
        "workforce",
        "Workforce",
        implies=("labor", "scheduling"),
        purchasable=True,
        audience="adaptix-workforce",
        source="Core DEFAULT_AGENCY_MODULE_ENTITLEMENTS; Core _MODULE_ENTITLEMENT_ALIASES",
    ),
    # ``scheduling`` is included in EVERY Core signup plan (starter_v1,
    # operations_v1, command_v1) and in every live /api/v1/billing/plans tier,
    # i.e. 100% of paying agencies hold it. Its runtime is Labor-Service, and
    # the gateway declares audience ``adaptix-labor`` on /api/v1/scheduling,
    # /api/v1/labor and the /api/v1/workforce/{shifts,open-shifts,coverage,...}
    # scheduling sub-prefixes.
    #
    # This was previously ``audience=None`` with the note "rides adaptix-labor".
    # It does not ride anything: nothing else in a scheduling-only entitlement
    # set produces adaptix-labor, so `_session_audiences` minted no such
    # audience and the gateway refused every scheduling request. RUNTIME-PROVEN
    # in prod 2026-08-04T14:18:47Z with a real agency_admin token whose
    # module_entitlements contained "scheduling":
    #     GET /api/v1/workforce/shifts    -> 403 jwt_audience_mismatch
    #                                        expected "adaptix-labor"
    #     GET /api/v1/labor/shifts        -> 403 jwt_audience_mismatch
    #     GET /api/v1/cad/units/available -> 200 (same token, same minute)
    # The 200 control proves the token was valid and the tenant reachable; the
    # missing audience was the whole defect.
    #
    # Granting the audience grants NO additional module entitlement â€” the
    # `labor` module (sold separately in command_v1) stays unheld, so this is
    # not a widening of the entitlement set, only of transport reachability to
    # the service that serves the product the agency already bought.
    _m(
        "scheduling",
        "Workforce Scheduling",
        aliases=("workforce_scheduling",),
        purchasable=True,
        audience="adaptix-labor",
        source=(
            "Core signup_pricing included_modules; Billing prod_UEOHpA51J37AP2; "
            "Gateway ROUTE_TABLE /api/v1/scheduling -> labor_service_url audience=adaptix-labor"
        ),
    ),
    _m(
        "labor",
        "Labor",
        purchasable=True,
        audience="adaptix-labor",
        source="Core signup_pricing command_v1; Core MODULE_CATALOG",
    ),
    _m(
        "crew",
        "Crew",
        purchasable=True,
        audience="adaptix-crew",
        source="Core signup_pricing command_v1; Core MODULE_CATALOG",
    ),
    # â”€â”€ Communications â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    _m(
        "communications",
        "Communications Command",
        aliases=("comms", "communications_command"),
        purchasable=True,
        audience="adaptix-communications",
        source="Core signup_pricing ('communications_command'); Core MODULE_CATALOG ('comms')",
    ),
    _m(
        "telephony",
        "Telephony",
        purchasable=True,
        audience="adaptix-telephony",
        source="Web-App MODULES; Core MODULE_CATALOG; Core _MODULE_TO_AUDIENCE",
    ),
    # â”€â”€ Controlled substances / supply â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # alias ``narcotic`` (singular): the gateway ROUTE_TABLE carries BOTH
    # prefix="/api/v1/narcotic" (routes.py:2287) and prefix="/api/v1/narcotics"
    # as separate entries, and ``_extract_module_id`` takes the first path
    # segment verbatim â€” so the singular route produced module_id "narcotic",
    # which matched no registered module and was not in the tenant's
    # entitlements (Core persists the plural ``narcotics``) -> 403
    # MODULE_NOT_ENTITLED on a controlled-substances surface for a tenant that
    # holds the module. Denying narcotics access to an entitled agency blocks
    # DEA chain-of-custody work, so this is not a cosmetic spelling issue.
    _m(
        "narcotics",
        "Narcotics + DEA Compliance",
        aliases=("narcotics_dea", "narcotic"),
        purchasable=True,
        audience="adaptix-narcotics",
        source=(
            "Core signup_pricing ('narcotics_dea'); Core MODULE_CATALOG ('narcotics'); "
            "Gateway ROUTE_TABLE /api/v1/narcotic ('narcotic')"
        ),
    ),
    _m(
        "medications",
        "Medications",
        purchasable=True,
        audience="adaptix-medications",
        source="Core signup_pricing command_v1; Core MODULE_CATALOG",
    ),
    # Social (MagicPost) and Vision are live routed services with audiences in
    # KNOWN_SERVICE_AUDIENCES and gateway ROUTE_TABLE entries, but were missing
    # module-registry rows. Provisioning could persist ``social`` / ``vision``
    # entitlements while Core's token mint skipped those audiences
    # (``_MODULE_TO_AUDIENCE.get`` miss) â†’ live 403 jwt_audience_mismatch on
    # /api/v1/social and Vision requests missing gateway identity headers.
    # Observed 2026-08-24 with a provisioned session that listed both modules
    # in module_entitlements but not in JWT aud.
    _m(
        "social",
        "Social / MagicPost",
        aliases=("magicpost",),
        purchasable=True,
        audience="adaptix-social",
        source=(
            "Gateway ROUTE_TABLE /api/v1/social audience=adaptix-social; "
            "Adaptix-Social-Service; KNOWN_SERVICE_AUDIENCES"
        ),
    ),
    _m(
        "vision",
        "Adaptix Vision",
        purchasable=True,
        audience="adaptix-vision",
        source=(
            "Gateway ROUTE_TABLE /api/v1/vision audience=adaptix-vision; "
            "Adaptix-Vision-Service; KNOWN_SERVICE_AUDIENCES"
        ),
    ),
    _m(
        "inventory",
        "Inventory",
        purchasable=True,
        audience="adaptix-inventory",
        source="Core signup_pricing command_v1; Core MODULE_CATALOG",
    ),
    # AssetOps is a live metered SKU ($29/vehicle/month, Stripe lookup_key
    # ``assetops_per_vehicle``) and is already grantable through Core's admin
    # MODULE_CATALOG â€” but with no audience row a granted tenant's token could
    # never reach the service, so the SKU was billable and dark. The gateway
    # routes /api/v1/assetops to assetops_service_url with audience
    # ``adaptix-assetops`` (present in KNOWN_SERVICE_AUDIENCES) and
    # Adaptix-AssetOps-Service enforces its own
    # ``require_module_entitlement(ASSETOPS_ENTITLEMENT_SLUG)`` where
    # ASSETOPS_ENTITLEMENT_SLUG == "assetops" (assetops_app/auth.py), so the
    # audience is not the only gate.
    _m(
        "assetops",
        "AdaptixCore AssetOps",
        purchasable=True,
        audience="adaptix-assetops",
        source=(
            "Core MODULE_CATALOG; AssetOps-Service gate; "
            "Gateway ROUTE_TABLE /api/v1/assetops -> assetops_service_url audience=adaptix-assetops"
        ),
    ),
    # â”€â”€ Interoperability exports â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Web-App sells one combined "NEMSIS / NERIS" SKU; Core carries two
    # separate audiences. The bundle implies both.
    _m(
        "nemsis_neris",
        "NEMSIS / NERIS",
        implies=("nemsis", "neris"),
        purchasable=True,
        source="Web-App MODULES",
    ),
    _m(
        "nemsis",
        "NEMSIS",
        audience="adaptix-nemsis",
        source="Core _MODULE_TO_AUDIENCE",
    ),
    _m(
        "neris",
        "NERIS",
        audience="adaptix-neris",
        source="Core _MODULE_TO_AUDIENCE",
    ),
    # â”€â”€ Transport â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Mirrors Core auth.py::_MODULE_ENTITLEMENT_ALIASES: TransportLink is the
    # user-facing route tree, `transport` is the persisted id, and both carry
    # their own gateway audience.
    _m(
        "transport",
        "Transport",
        implies=("transportlink",),
        purchasable=True,
        audience="adaptix-transport",
        source="Core DEFAULT_AGENCY_MODULE_ENTITLEMENTS; Core MODULE_CATALOG",
    ),
    _m(
        "transportlink",
        "TransportLink",
        audience="adaptix-transportlink",
        source="Core _MODULE_TO_AUDIENCE; Core _MODULE_ENTITLEMENT_ALIASES",
    ),
    # â”€â”€ Onboarding / services â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # audience: the onboarding surface is served by Core itself â€” the gateway
    # routes /api/v1/onboarding to auth_service_url with audience
    # ``adaptix-core``. Stating it explicitly (rather than leaving None and
    # relying on adaptix-core always being present in a session aud) keeps the
    # "purchasable module must name the service it unlocks" invariant honest.
    _m(
        "onboarding",
        "Adaptix Launch & Onboarding",
        purchasable=True,
        audience="adaptix-core",
        source=(
            "Billing _PRODUCT_MODULE_MAP prod_UVUZSxnp8SNBDc; "
            "Gateway ROUTE_TABLE /api/v1/onboarding -> auth_service_url audience=adaptix-core"
        ),
    ),
    # â”€â”€ Platform modules (entitlement-bearing, not individually sold) â”€â”€â”€â”€â”€
    _m(
        "calendar",
        "Calendar",
        audience="adaptix-calendar",
        source="Core _MODULE_TO_AUDIENCE",
    ),
    _m(
        "compliance",
        "Compliance",
        audience="adaptix-compliance",
        source="Core _MODULE_TO_AUDIENCE",
    ),
    _m(
        "documents",
        "Documents",
        audience="adaptix-documents",
        source="Core _MODULE_TO_AUDIENCE",
    ),
    _m(
        "exports",
        "Exports",
        audience="adaptix-exports",
        source="Core _MODULE_TO_AUDIENCE",
    ),
    _m(
        "imports",
        "Imports",
        audience="adaptix-imports",
        source="Core _MODULE_TO_AUDIENCE",
    ),
    _m("fleet", "Fleet", audience="adaptix-fleet", source="Core _MODULE_TO_AUDIENCE"),
    _m(
        "hospital",
        "Hospital",
        audience="adaptix-hospital",
        source="Core _MODULE_TO_AUDIENCE",
    ),
    _m(
        "analytics",
        "Analytics",
        audience="adaptix-analytics",
        source="Core _MODULE_TO_AUDIENCE",
    ),
    _m(
        "search", "Search", audience="adaptix-search", source="Core _MODULE_TO_AUDIENCE"
    ),
    _m("graph", "Graph", audience="adaptix-graph", source="Core _MODULE_TO_AUDIENCE"),
    _m(
        "terminology",
        "Terminology",
        audience="adaptix-terminology",
        source="Core _MODULE_TO_AUDIENCE",
    ),
    # alias ``devices`` (plural): the gateway derives module_id from the FIRST
    # path segment verbatim (Adaptix-Gateway backend/app/middleware/entitlements.py
    # ``_extract_module_id``), and ROUTE_TABLE carries BOTH spellings as separate
    # entries â€” prefix="/api/v1/devices" (routes.py:2771) alongside
    # prefix="/api/v1/device" (routes.py:2777). The canonical module id Core
    # persists and mints is the singular ``device``, so a request to
    # /api/v1/devices/* produced module_id "devices", which resolved to nothing
    # and was not in the tenant's entitlements -> 403 MODULE_NOT_ENTITLED for a
    # tenant that genuinely holds ``device``. Same defect class as the
    # ``patient-identity`` alias below, found by sweeping every ROUTE_TABLE slug
    # against this registry rather than fixing the one that was reported.
    _m(
        "device",
        "Device",
        aliases=("devices",),
        audience="adaptix-device",
        source="Core _MODULE_TO_AUDIENCE; Gateway ROUTE_TABLE /api/v1/devices ('devices')",
    ),
    # alias ``patient-identity`` (hyphen): the canonical module id Core persists
    # and mints is ``patient_identity`` (underscore, from Core
    # _MODULE_TO_AUDIENCE), but the SERVICE that owns the surface is slugged
    # ``patient-identity`` â€” ``adaptix_contracts.schemas.service_registry
    # .PATIENT_IDENTITY_SERVICE`` (slug="patient-identity",
    # route_prefix="/api/v1/patient-identity") â€” and the gateway RouteEntry for
    # /api/v1/patient-identity carries audience ``adaptix-patient-identity``.
    # A route/service guard declared with the hyphen spelling
    # (require_module_entitlement("patient-identity")) therefore did NOT resolve
    # against a token carrying ``patient_identity`` under the registry's exact
    # normalized match, so an entitled tenant got 402/403 MODULE_NOT_ENTITLED on
    # the identity surface even though the ``adaptix-patient-identity`` audience
    # was minted. Registering the hyphen spelling as an alias of the SAME module
    # makes both sides resolve to one canonical id. Non-widening: an alias is a
    # synonym for the same product (collision-checked at import â€” it can never
    # shadow a canonical id or map to two canonicals), so this grants no
    # additional module; it only unifies two spellings of one.
    _m(
        "patient_identity",
        "Patient Identity",
        aliases=("patient-identity",),
        audience="adaptix-patient-identity",
        source=(
            "Core _MODULE_TO_AUDIENCE ('patient_identity'); "
            "service_registry PATIENT_IDENTITY_SERVICE slug + gateway "
            "ROUTE_TABLE /api/v1/patient-identity ('patient-identity')"
        ),
    ),
    _m("hl7", "HL7", audience="adaptix-hl7", source="Core _MODULE_TO_AUDIENCE"),
    _m(
        "bedrock",
        "Bedrock",
        audience="adaptix-bedrock",
        source="Core _MODULE_TO_AUDIENCE",
    ),
    _m(
        "cortex", "Cortex", audience="adaptix-cortex", source="Core _MODULE_TO_AUDIENCE"
    ),
    _m(
        "finance",
        "Finance",
        audience="adaptix-finance",
        source="Core _MODULE_TO_AUDIENCE",
    ),
    _m("crm", "CRM", audience="adaptix-crm", source="Core _MODULE_TO_AUDIENCE"),
    _m(
        "investor",
        "Investor",
        audience="adaptix-investor",
        source="Core _MODULE_TO_AUDIENCE",
    ),
    _m(
        "partner",
        "Partner",
        audience="adaptix-partner",
        source="Core _MODULE_TO_AUDIENCE",
    ),
    _m(
        "founder",
        "Founder",
        audience="adaptix-founder",
        source="Core _MODULE_TO_AUDIENCE",
    ),
    # audience: /api/v1/workspace routes to auth_service_url (Core) with
    # audience "adaptix-core" â€” the workspace lock/state surface is Core's own.
    _m(
        "workspace",
        "Workspace",
        audience="adaptix-core",
        source=(
            "Core MODULE_CATALOG; "
            "Gateway ROUTE_TABLE /api/v1/workspace -> auth_service_url audience=adaptix-core"
        ),
    ),
    # -----------------------------------------------------------------
    # Routed-but-unregistered surfaces (added 2026-08-03).
    #
    # Each of these has a live RouteEntry in the gateway ROUTE_TABLE and a
    # real <ModuleGateBoundary> in the web app, but existed in no backend
    # vocabulary. That combination is not "misconfigured", it is
    # unreachable: provisioning only ever writes canonical ids and Core's
    # admin toggle 422s on unknown ones, so nothing could put these into
    # module_entitlements and every one of those routes was
    # permanently dark for every non-founder tenant. It went unseen
    # because useModuleEntitlements returns True unconditionally for a
    # founder, so no amount of founder click-through could surface it.
    #
    # Registered from the gateway ROUTE_TABLE â€” the routing source of
    # truth â€” rather than from the web spelling, and deliberately NOT as
    # aliases of an existing module: aliasing would hand these routes to
    # every tenant already holding the aliased module, granting access
    # under an entitlement they may never have bought. As separate
    # canonical ids they start ungranted for everyone, so this change
    # takes nothing away and gives nothing away; it only makes them
    # grantable.
    #
    # purchasable stays False: none appears in the signup wizard, the
    # signup pricing catalog, or a Stripe product map, so granting is an
    # explicit admin action rather than something a plan silently confers.
    # audience is None for the four whose surfaces are served by Core itself
    # (adaptix-core is unconditionally present in every session aud, so those
    # ids need no additional audience). Only integration and training have
    # their own upstream service and audience. Because all six are
    # purchasable=False they are outside the scope of the
    # billable-but-dark test.
    # -----------------------------------------------------------------
    _m(
        "intelligence",
        "Cortex Intelligence",
        audience="adaptix-core",
        source="Gateway ROUTE_TABLE /api/v1/intelligence; Web-App app/workspace/intelligence",
    ),
    _m(
        "ai-infrastructure",
        "AI Infrastructure",
        audience="adaptix-core",
        source="Gateway ROUTE_TABLE /api/v1/ai-infrastructure; Web-App app/ai-infrastructure",
    ),
    _m(
        "command-intelligence",
        "Command Intelligence",
        audience="adaptix-core",
        source="Gateway ROUTE_TABLE /api/v1/command-intelligence; Web-App app/command-intelligence",
    ),
    _m(
        "interoperability",
        "Interoperability",
        audience="adaptix-core",
        source="Gateway ROUTE_TABLE /api/v1/interoperability; Web-App app/interoperability",
    ),
    # alias ``integrations`` (plural): the canonical module id Core persists and
    # mints is ``integration`` (singular, matching Core MODULE_CATALOG), but the
    # SERVICE is slugged ``integrations`` â€” ``adaptix_contracts.schemas
    # .service_registry.INTEGRATIONS_SERVICE`` (slug="integrations",
    # route_prefix="/api/v1/integrations") â€” and the gateway RouteEntry for
    # /api/v1/integrations carries audience ``adaptix-integrations``. A
    # route/service guard declared with the plural spelling
    # (require_module_entitlement("integrations")) did NOT resolve against a
    # token carrying ``integration`` under exact normalized match, so an entitled
    # tenant got 402/403 MODULE_NOT_ENTITLED on the integrations surface even
    # though the ``adaptix-integrations`` audience was minted. Same fix + same
    # safety as ``patient-identity`` above: one canonical module, two spellings.
    _m(
        "integration",
        "Integrations",
        aliases=("integrations",),
        audience="adaptix-integrations",
        source=(
            "Core MODULE_CATALOG ('integration'); service_registry "
            "INTEGRATIONS_SERVICE slug + gateway ROUTE_TABLE /api/v1/integrations "
            "('integrations')"
        ),
    ),
    _m(
        "training",
        "Training",
        audience="adaptix-training",
        source="Gateway ROUTE_TABLE /api/v1/training; Web-App app/workspace/training",
    ),
    # â”€â”€ Forms â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Adaptix-Forms-Service is a live upstream with its own gateway route and
    # audience, but the module had NO row here â€” so audience_map() lacked a
    # ``forms`` key, Core's _MODULE_TO_AUDIENCE never mapped it, and
    # _session_audiences could not add ``adaptix-forms`` to any non-founder
    # tenant's token. The gateway's AudienceEnforcementMiddleware then 403'd
    # (jwt_audience_mismatch) EVERY /api/v1/forms request for every tenant.
    # Adding the mapping makes the module reachable for entitled tenants on
    # Core's next deploy. purchasable=False: forms is granted through the admin
    # module toggle (Core MODULE_CATALOG), not a signup-pricing SKU â€” same
    # shape as ``integration`` / ``training`` above.
    _m(
        "forms",
        "Forms",
        audience="adaptix-forms",
        source=(
            "Gateway ROUTE_TABLE /api/v1/forms -> forms_service_url "
            "audience=adaptix-forms; Core MODULE_CATALOG"
        ),
    ),
    # â”€â”€ HR â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Identical defect to ``forms`` above, runtime-proven in production on
    # 2026-08-13: Adaptix-HR-Service is deployed and healthy
    # (adaptix-production-hr), the gateway routes /api/v1/hr to it behind
    # audience ``adaptix-hr`` â€” but no module row existed here, so
    # audience_map() had no ``hr`` key, Core's _MODULE_TO_AUDIENCE never mapped
    # it, and _session_audiences could not put ``adaptix-hr`` in ANY tenant's
    # token. Probed with a real agency_admin session carrying all 55 entitled
    # modules:
    #
    #     GET /api/v1/hr/employees    -> 403 jwt_audience_mismatch
    #     GET /api/v1/hr/pto          -> 403 jwt_audience_mismatch
    #     GET /api/v1/hr/credentials  -> 403 jwt_audience_mismatch
    #
    # i.e. the whole HR service was unreachable for every tenant, always.
    # purchasable=False: HR is granted through the admin module toggle (Core
    # MODULE_CATALOG), not a signup-pricing SKU â€” same shape as ``forms``.
    _m(
        "hr",
        "HR",
        audience="adaptix-hr",
        source=(
            "Gateway ROUTE_TABLE /api/v1/hr -> hr_service_url "
            "audience=adaptix-hr; ECS adaptix-production-hr"
        ),
    ),
    # â”€â”€ Office â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Same defect and same runtime proof as ``hr`` above: Adaptix-Office-Service
    # runs as adaptix-production-office and the gateway routes /api/v1/office to
    # it behind audience ``adaptix-office``, with no module row here.
    #
    #     GET /api/v1/office          -> 403 jwt_audience_mismatch
    #     GET /api/v1/office/health   -> 403 jwt_audience_mismatch
    #
    # NOTE: ``officeally`` is a DIFFERENT service (the Office Ally clearinghouse
    # upstream, audience ``adaptix-officeally``) and is deliberately not added
    # here â€” provider policy pins Office Ally to MIGRATION_ONLY.
    _m(
        "office",
        "Office",
        audience="adaptix-office",
        source=(
            "Gateway ROUTE_TABLE /api/v1/office -> office_service_url "
            "audience=adaptix-office; ECS adaptix-production-office"
        ),
    ),
    # â”€â”€ Facilities â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Same defect and same runtime proof as ``hr`` and ``office`` above:
    # Adaptix-Facility-Registry-Service runs as adaptix-production-facilities
    # and the gateway routes /api/v1/facilities to it behind audience
    # ``adaptix-facilities`` (Gateway routes.py:3554), but there was no module
    # row here â€” so a tenant could carry ``facilities`` in
    # ``metadata_json["module_entitlements"]``, and Core's ``_session_audiences``
    # would mint NO ``adaptix-facilities`` audience for it, leaving every
    # facilities request 403 ``jwt_audience_mismatch``.
    #
    # Runtime-proven 2026-08-14T02:5xZ against api.adaptixcore.com with a real
    # provisioned agency_admin session whose module_entitlements included
    # "facilities":
    #
    #     POST /api/v1/facilities  -> 403 jwt_audience_mismatch
    #       {"expected":"adaptix-facilities",
    #        "actual":["adaptix-billing","adaptix-core","adaptix-epcr",
    #                  "adaptix-patient-identity","adaptix-trustsign"]}
    #
    # adaptix-facilities is in service_audiences.KNOWN_SERVICE_AUDIENCES, so
    # test_every_declared_audience_is_a_known_live_service_audience passes.
    #
    # Non-purchasable / no ``implies``, matching hr and office: the facility
    # registry is a shared platform directory, not an individually sold SKU.
    # Whether a base plan should auto-grant it (via ``implies``) so every ePCR/
    # CAD tenant can resolve transport destinations without a separate line item
    # is a product decision left to the founder; this row makes the entitlement
    # GRANTABLE and the audience MINTABLE, which is what unblocks the 403.
    _m(
        "facilities",
        "Facilities",
        aliases=("facility", "facility_registry"),
        audience="adaptix-facilities",
        source=(
            "Gateway ROUTE_TABLE /api/v1/facilities -> facilities_service_url "
            "audience=adaptix-facilities (routes.py:3554); "
            "ECS adaptix-production-facilities"
        ),
    ),
    # -- Realtime -------------------------------------------------------------
    # Adaptix-Gateway routes.py declares this RouteEntry with the comment "RTC
    # -- real-time comms (WebRTC/SFU signalling) shared service" (prefix
    # "/api/v1/rtc", upstream_url=settings.rtc_service_url,
    # audience="adaptix-rtc"), and "adaptix-rtc" is already listed in
    # ``service_audiences.KNOWN_SERVICE_AUDIENCES`` -- so the gateway and the
    # audience registry both already agree this service exists. What was
    # missing is this row: with no module here, ``audience_map()`` had no
    # ``rtc`` key, so Core's ``_MODULE_TO_AUDIENCE`` never mapped it and no
    # tenant's session ``aud`` could ever carry ``adaptix-rtc`` -- every
    # /api/v1/rtc request 403'd ``jwt_audience_mismatch`` for every tenant,
    # including Cortex Live's demo pool, whose live voice session opens a room
    # via ``POST /api/v1/rtc/rooms`` and cannot reach it without this audience.
    # Same defect class as ``forms`` / ``hr`` / ``office`` / ``facilities``
    # above: a live routed upstream with no module-registry row.
    #
    # purchasable=False: rtc is a platform control plane (room signalling for
    # a feature, not a product a tenant buys on its own), granted the same way
    # as forms/hr/office/facilities -- through entitlement, not a signup SKU.
    # No ``implies``: nothing else genuinely depends on holding this module,
    # and nothing else should be silently granted by holding it.
    _m(
        "rtc",
        "Realtime Room Control Plane",
        audience="adaptix-rtc",
        source=(
            "Gateway ROUTE_TABLE /api/v1/rtc -> rtc_service_url "
            'audience=adaptix-rtc ("RTC -- real-time comms (WebRTC/SFU '
            'signalling) shared service"); service_audiences.'
            "KNOWN_SERVICE_AUDIENCES"
        ),
    ),
)


def _build_registry() -> Mapping[str, ModuleDefinition]:
    registry: dict[str, ModuleDefinition] = {}
    for definition in _DEFINITIONS:
        if definition.canonical_id in registry:
            raise ValueError(
                f"duplicate canonical module id: {definition.canonical_id!r}"
            )
        registry[definition.canonical_id] = definition
    return MappingProxyType(registry)


MODULE_REGISTRY: Mapping[str, ModuleDefinition] = _build_registry()


def _build_alias_index() -> Mapping[str, str]:
    index: dict[str, str] = {}
    for definition in MODULE_REGISTRY.values():
        for alias in definition.aliases:
            if alias in MODULE_REGISTRY:
                raise ValueError(
                    f"alias {alias!r} on {definition.canonical_id!r} collides with a canonical id"
                )
            existing = index.get(alias)
            if existing is not None and existing != definition.canonical_id:
                raise ValueError(
                    f"alias {alias!r} maps to both {existing!r} and {definition.canonical_id!r}"
                )
            index[alias] = definition.canonical_id
    return MappingProxyType(index)


#: Legacy/alternate spelling -> canonical id. Aliases never collide with a
#: canonical id, and never map to two different canonical ids (enforced above,
#: at import time).
ALIAS_INDEX: Mapping[str, str] = _build_alias_index()


#: Module slugs that a live ``require_module_entitlement(...)`` call currently
#: enforces somewhere in the platform. Every one of these MUST be a canonical
#: id, otherwise a purchase can never satisfy the gate.
RUNTIME_GATE_SLUGS: frozenset[str] = frozenset(
    {
        "air",
        "assetops",
        "billing",
        "cad",
        "crewlink",
        "epcr",
        "fire",
        "mdt",
        "scheduling",
    }
)


#: Purchasable module ids that are sold on a live price surface but have NO
#: known upstream service, and therefore resolve to no audience.
#:
#: This is a QUARANTINE LIST, not an exemption to be grown. Every id here is a
#: SKU a customer can be charged for that grants no reachable product, and each
#: needs a founder/product decision recording which service it unlocks. Once
#: that decision exists, give the module an ``audience`` (or an ``implies``
#: reaching one) and DELETE the id from this set.
#:
#: **This set is empty and must stay empty.** Every purchasable module in the
#: registry currently reaches at least one service audience, so there is no
#: SKU a customer can be charged for that grants nothing.
#:
#: It exists as a named, documented landing place so that a future change which
#: genuinely cannot map a SKU to a service has to declare that fact in source â€”
#: with the founder/product decision written down â€” instead of silently
#: shipping a billable-but-dark module. Adding an id here should be rare and
#: temporary; ``test_quarantined_modules_are_real_purchasable_ids_with_no_audience``
#: forces the id back out again the moment it gains an audience.
SOLD_WITHOUT_SERVICE_MAPPING: frozenset[str] = frozenset()


def _validate_relations() -> None:
    for definition in MODULE_REGISTRY.values():
        for implied in definition.implies:
            if implied not in MODULE_REGISTRY:
                raise ValueError(
                    f"module {definition.canonical_id!r} implies unknown module {implied!r}"
                )
            if implied == definition.canonical_id:
                raise ValueError(f"module {definition.canonical_id!r} implies itself")
    missing_gates = sorted(RUNTIME_GATE_SLUGS - set(MODULE_REGISTRY))
    if missing_gates:
        raise ValueError(
            "RUNTIME_GATE_SLUGS not present as canonical module ids: "
            + ", ".join(missing_gates)
        )


_validate_relations()


class UnknownModuleError(KeyError):
    """Raised by :func:`require_module_id` for an unregistered module id."""


# ---------------------------------------------------------------------------
# Resolution API
# ---------------------------------------------------------------------------


def normalize_module_id(value: object) -> str:
    """Return the canonical *string form* of a module id (no alias resolution).

    Lower-cased and stripped â€” identical to the normalization the runtime
    entitlement gates already apply, so this never changes matching behaviour on
    its own.
    """
    if value is None:
        return ""
    return str(value).strip().lower()


def resolve_module_id(value: object) -> str | None:
    """Resolve any known spelling of a module to its canonical id.

    Returns ``None`` when the id is not registered. Callers that must not lose
    unknown ids should fall back to :func:`normalize_module_id` (which is what
    :func:`expand_entitlements` does).

    >>> resolve_module_id("Billing_Automation")
    'billing'
    >>> resolve_module_id("fire_rms")
    'fire'
    >>> resolve_module_id("not_a_module") is None
    True
    """
    slug = normalize_module_id(value)
    if not slug:
        return None
    if slug in MODULE_REGISTRY:
        return slug
    return ALIAS_INDEX.get(slug)


def require_module_id(value: object) -> str:
    """Like :func:`resolve_module_id` but raises for an unregistered id.

    Use in provisioning/admin write paths that should reject typos. Never use on
    a read/authorization path â€” authorization must fail closed by *denying*, not
    by raising an unhandled error.
    """
    resolved = resolve_module_id(value)
    if resolved is None:
        raise UnknownModuleError(
            f"{normalize_module_id(value)!r} is not a registered Adaptix module id. "
            f"Known canonical ids: {sorted(MODULE_REGISTRY)}"
        )
    return resolved


def expand_entitlements(values: Iterable[object] | None) -> frozenset[str]:
    """Expand raw granted module ids into the full set of ids they satisfy.

    The result contains, for every input value:

    1. the normalized input id itself (so nothing that matches today stops
       matching â€” this function is strictly additive),
    2. its canonical id, when the id is a registered alias,
    3. every id transitively reachable through ``implies``.

    Unregistered ids are preserved verbatim (normalized) rather than dropped.

    >>> sorted(expand_entitlements(["billing_automation"]))
    ['billing', 'billing_automation']
    >>> sorted(expand_entitlements(["workforce"]))
    ['labor', 'scheduling', 'workforce']
    """
    if not values:
        return frozenset()

    resolved: set[str] = set()
    pending: list[str] = []

    for raw in values:
        slug = normalize_module_id(raw)
        if not slug:
            continue
        resolved.add(slug)
        canonical = resolve_module_id(slug)
        if canonical is not None and canonical not in resolved:
            resolved.add(canonical)
        if canonical is not None:
            pending.append(canonical)

    # Transitive closure over ``implies``. The registry forbids self-implication
    # and the ``resolved`` guard makes cycles terminate.
    while pending:
        current = pending.pop()
        definition = MODULE_REGISTRY.get(current)
        if definition is None:
            continue
        for implied in definition.implies:
            if implied not in resolved:
                resolved.add(implied)
                pending.append(implied)

    return frozenset(resolved)


def is_module_entitled(required: object, granted: Iterable[object] | None) -> bool:
    """True when ``granted`` satisfies ``required`` under canonical resolution.

    Both sides are resolved, so a tenant holding ``billing_automation`` passes a
    ``billing`` gate, and a tenant holding ``billing`` passes a legacy
    ``billing_automation`` gate.

    >>> is_module_entitled("billing", ["billing_automation", "epcr"])
    True
    >>> is_module_entitled("billing", ["epcr"])
    False
    """
    required_slug = normalize_module_id(required)
    if not required_slug:
        return False
    required_canonical = resolve_module_id(required_slug) or required_slug
    granted_set = expand_entitlements(granted)
    if not granted_set:
        return False
    return required_slug in granted_set or required_canonical in granted_set


def is_any_module_entitled(
    required: Iterable[object], granted: Iterable[object] | None
) -> bool:
    """True when ``granted`` satisfies AT LEAST ONE of ``required``."""
    return any(is_module_entitled(item, granted) for item in required)


def canonical_module_ids() -> frozenset[str]:
    """Every canonical module id in the registry."""
    return frozenset(MODULE_REGISTRY)


def purchasable_module_ids() -> frozenset[str]:
    """Canonical ids that appear on a customer-facing purchase surface."""
    return frozenset(d.canonical_id for d in MODULE_REGISTRY.values() if d.purchasable)


def module_audiences(value: object) -> frozenset[str]:
    """Every service audience a single granted module id confers.

    Resolves aliases, then unions the module's own ``audience`` with the
    audience of every id it transitively ``implies``. Returns an empty set for
    an unregistered id and for a module that reaches no upstream service.

    This is the function that answers "can a tenant holding exactly this
    module reach the product it paid for?" â€” an empty result for a
    ``purchasable`` module means the SKU is billable but dark.

    >>> sorted(module_audiences("billing_automation"))
    ['adaptix-billing']
    >>> sorted(module_audiences("workforce"))
    ['adaptix-labor', 'adaptix-workforce']
    >>> sorted(module_audiences("not_a_module"))
    []
    """
    canonical = resolve_module_id(value)
    if canonical is None:
        return frozenset()
    return frozenset(
        definition.audience
        for slug in expand_entitlements([canonical])
        if (definition := MODULE_REGISTRY.get(slug)) is not None and definition.audience
    )


def audience_map() -> Mapping[str, str]:
    """Canonical module id -> its own dedicated service audience.

    The authoritative source for Adaptix-Core
    ``core_app/auth.py::_MODULE_TO_AUDIENCE``. Core derives its table from this
    mapping so the two repos cannot drift; a module added here with an audience
    becomes reachable for entitled tenants on Core's next deploy, and a module
    added WITHOUT one is caught by the purchasable-module test.

    Only modules with their own ``audience`` appear. ``implies`` relationships
    are intentionally NOT flattened here â€” Core walks ``implies`` itself while
    expanding entitlements, so flattening would double-apply it.
    """
    return MappingProxyType(
        {d.canonical_id: d.audience for d in MODULE_REGISTRY.values() if d.audience}
    )
