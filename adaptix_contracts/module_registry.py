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

Every one of those is a ``canonical_id`` below. That is a hard invariant — see
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
    "UnknownModuleError",
    "canonical_module_ids",
    "expand_entitlements",
    "is_any_module_entitled",
    "is_module_entitled",
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
        display_name: Human label. Presentation only — never an identifier.
        aliases: Legacy / alternate spellings of THIS SAME module. Any of these
            resolve to ``canonical_id``.
        implies: Canonical ids that are additionally granted when this module is
            granted. Directional (implying X does not imply the reverse).
        purchasable: True when the id appears in a customer-facing purchase
            surface (signup wizard, signup pricing catalog, or a Stripe product
            module map). False for platform-internal modules.
        audience: The gateway JWT ``aud`` value for the module's upstream
            service, mirroring Adaptix-Core ``core_app/auth.py::
            _MODULE_TO_AUDIENCE``. ``None`` when the module has no dedicated
            upstream audience (e.g. ``scheduling`` rides the ``adaptix-labor``
            audience).
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
    # ── Platform base ────────────────────────────────────────────────────
    _m(
        "core",
        "Core Platform",
        purchasable=True,
        audience="adaptix-core",
        source="Web-App MODULES; Core MODULE_CATALOG; Core _MODULE_TO_AUDIENCE",
    ),
    # ── Clinical / documentation ─────────────────────────────────────────
    _m(
        "epcr",
        "ePCR & NEMSIS",
        aliases=("epcr_nemsis",),
        purchasable=True,
        audience="adaptix-epcr",
        source="Web-App MODULES; Core signup_pricing; Billing _PRODUCT_MODULE_MAP",
    ),
    # ── Dispatch ─────────────────────────────────────────────────────────
    _m(
        "cad",
        "CAD / Dispatch",
        purchasable=True,
        audience="adaptix-cad",
        source="Web-App MODULES; Core signup_pricing; Billing _PRODUCT_MODULE_MAP",
    ),
    # ── Revenue cycle ────────────────────────────────────────────────────
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
    _m(
        "wisconsin_trip_pack",
        "Adaptix Wisconsin TRIP Pack",
        purchasable=True,
        source="Billing _PRODUCT_MODULE_MAP prod_UEOHlRtTmKGvfo",
    ),
    # ── Fire ─────────────────────────────────────────────────────────────
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
    # ── Air medical ──────────────────────────────────────────────────────
    _m(
        "air",
        "Air Medical",
        purchasable=True,
        audience="adaptix-air",
        source="Core MODULE_CATALOG; Core _MODULE_TO_AUDIENCE; Air-Service gate",
    ),
    _m(
        "hems_ops",
        "Adaptix HEMS Ops",
        purchasable=True,
        source="Billing _PRODUCT_MODULE_MAP prod_UEOHT3EFG7BSxF",
    ),
    _m(
        "cct_transport_ops",
        "Adaptix CCT / Transport Ops",
        purchasable=True,
        source="Billing _PRODUCT_MODULE_MAP prod_UEOHmIlaVBQJMX",
    ),
    # ── Field / mobile ───────────────────────────────────────────────────
    # The crew-facing tablet/phone application. Web-App sells `mobile_field`,
    # Core pricing includes it as `field_app`, Core's admin catalog spells it
    # `field`, and Adaptix-CAD-Service gates the write-back surface on `mdt`.
    _m(
        "mdt",
        "Mobile / Field (MDT)",
        aliases=("mobile_field", "field_app", "field"),
        purchasable=True,
        source="Web-App MODULES ('mobile_field'); Core signup_pricing ('field_app')",
    ),
    _m(
        "crewlink",
        "CrewLink",
        purchasable=True,
        source="Billing _PRODUCT_MODULE_MAP; CAD-Service gate",
    ),
    # ── Workforce / scheduling ───────────────────────────────────────────
    # Mirrors Core auth.py::_MODULE_ENTITLEMENT_ALIASES — `workforce` is the id
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
    _m(
        "scheduling",
        "Workforce Scheduling",
        aliases=("workforce_scheduling",),
        purchasable=True,
        audience=None,  # rides adaptix-labor; intentionally no dedicated audience
        source="Core signup_pricing included_modules; Billing prod_UEOHpA51J37AP2",
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
    # ── Communications ───────────────────────────────────────────────────
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
    # ── Controlled substances / supply ───────────────────────────────────
    _m(
        "narcotics",
        "Narcotics + DEA Compliance",
        aliases=("narcotics_dea",),
        purchasable=True,
        audience="adaptix-narcotics",
        source="Core signup_pricing ('narcotics_dea'); Core MODULE_CATALOG ('narcotics')",
    ),
    _m(
        "medications",
        "Medications",
        purchasable=True,
        audience="adaptix-medications",
        source="Core signup_pricing command_v1; Core MODULE_CATALOG",
    ),
    _m(
        "inventory",
        "Inventory",
        purchasable=True,
        audience="adaptix-inventory",
        source="Core signup_pricing command_v1; Core MODULE_CATALOG",
    ),
    _m(
        "assetops",
        "AdaptixCore AssetOps",
        purchasable=True,
        source="Core MODULE_CATALOG; AssetOps-Service gate",
    ),
    # ── Interoperability exports ─────────────────────────────────────────
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
    # ── Transport ────────────────────────────────────────────────────────
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
    # ── Onboarding / services ────────────────────────────────────────────
    _m(
        "onboarding",
        "Adaptix Launch & Onboarding",
        purchasable=True,
        source="Billing _PRODUCT_MODULE_MAP prod_UVUZSxnp8SNBDc",
    ),
    # ── Platform modules (entitlement-bearing, not individually sold) ─────
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
    _m(
        "device", "Device", audience="adaptix-device", source="Core _MODULE_TO_AUDIENCE"
    ),
    _m(
        "patient_identity",
        "Patient Identity",
        audience="adaptix-patient-identity",
        source="Core _MODULE_TO_AUDIENCE",
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
    _m("workspace", "Workspace", source="Core MODULE_CATALOG"),
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

    Lower-cased and stripped — identical to the normalization the runtime
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
    a read/authorization path — authorization must fail closed by *denying*, not
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
       matching — this function is strictly additive),
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
