"""Tenant capability registry — shared platform primitive I.

``module_registry`` answers "which products has this tenant bought?".  This
module answers the finer question every play needs: "may this tenant use *this
capability*?" — where a capability is one shipped feature (ambient capture, the
revenue twin, RSNAT prior authorisation) rather than a whole product.

Why a second layer rather than more module ids
----------------------------------------------
Module ids are the vocabulary the runtime gate, the signup wizard, the pricing
catalogue and the Stripe products all share. Adding a module id per feature would
churn five vocabularies for something that is not separately sold. A capability
therefore *resolves to* a module id and is enforced through the existing
``require_module_entitlement`` gate — one enforcement path, not two.

Why capabilities exist at all
-----------------------------
So a feature flag is not the only thing standing between a tenant and a feature
they have not been provisioned. A capability code is a server-side fact with a
named owning module; hiding a button is not.

Deliberately unregistered
-------------------------
Three capability codes from the platform build spec are **not** registered here,
because no canonical module owns their service yet: ``edge.apparatus``,
``interop.qhin`` and ``agent.protected_execution``. There is no ``edge``,
``qhin`` or ``agent`` module id, and no entry for those services in the service
registry or the ownership manifest. Binding them to an approximate module would
either 403 a tenant who paid or grant one who did not — the exact drift
``module_registry`` was written to end. Each registers in the same change that
gives its service a module.

Resolution is additive
----------------------
:func:`is_capability_entitled` runs the tenant's granted ids through
``expand_entitlements`` first, so aliases and bundle implications resolve exactly
as they do for a module gate: a tenant holding ``nemsis_neris`` is entitled to
``fire.neris`` because that bundle implies ``neris``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from adaptix_contracts.module_registry import (
    MODULE_REGISTRY,
    UnknownModuleError,
    is_module_entitled,
)


@dataclass(frozen=True)
class PlatformCapability:
    """One shipped capability and the module a tenant must hold to use it.

    ``play`` records which build-spec play introduced the capability. It is
    documentation, not behaviour: it makes the registry auditable against the
    programme without a separate spreadsheet.
    """

    capability_code: str
    module_id: str
    display_name: str
    play: str


def _c(
    capability_code: str, module_id: str, display_name: str, play: str
) -> PlatformCapability:
    return PlatformCapability(
        capability_code=capability_code,
        module_id=module_id,
        display_name=display_name,
        play=play,
    )


# Every ``module_id`` below is a canonical id in ``MODULE_REGISTRY``, verified at
# import time by ``_validate_registry()``. Do not add a capability whose owning
# module is a guess — see "Deliberately unregistered" in the module docstring.
_CAPABILITIES: tuple[PlatformCapability, ...] = (
    # ── ePCR ─────────────────────────────────────────────────────────────
    _c("epcr.ambient_capture", "epcr", "Ambient clinical capture", "P01"),
    # ── Billing / revenue ────────────────────────────────────────────────
    _c("billing.revenue_twin", "billing", "Revenue digital twin", "P37"),
    _c(
        "billing.rsnat_prior_auth",
        "billing",
        "Medicare RSNAT prior authorisation",
        "P51",
    ),
    # ── Fire ─────────────────────────────────────────────────────────────
    # Bound to ``neris`` rather than ``fire``: NERIS is its own module with its
    # own audience, sold inside the ``nemsis_neris`` bundle. expand_entitlements
    # resolves that bundle to ``neris``, so a tenant who bought the bundle passes.
    _c("fire.neris", "neris", "NERIS zero-entry reporting", "P06"),
    _c("fire.digital_twin", "fire", "Occupancy digital twin", "P07"),
    _c("fire.crr_outcomes", "crr", "CRR outcome engine", "P08"),
    # ── Air medical ──────────────────────────────────────────────────────
    _c("air.sms", "air", "HEMS Part 5 safety management system", "P14"),
    _c("air.fdm", "air", "Flight data monitoring", "P16"),
    # ── Workforce ────────────────────────────────────────────────────────
    _c("workforce.mou_compiler", "workforce", "MOU / labour rule compiler", "P19"),
    # ── Controlled substances ────────────────────────────────────────────
    _c(
        "narcotics.controlled_substances",
        "narcotics",
        "Controlled substance custody ledger",
        "P21",
    ),
    # ── Intelligence ─────────────────────────────────────────────────────
    _c(
        "intelligence.counterfactual",
        "intelligence",
        "Chief counterfactual lab",
        "P41",
    ),
)


class UnknownCapabilityError(KeyError):
    """Raised when a capability code is not registered.

    A ``KeyError`` subclass so existing ``except KeyError`` handlers keep
    working, matching ``module_registry.UnknownModuleError``.
    """


def _build_registry() -> Mapping[str, PlatformCapability]:
    registry: dict[str, PlatformCapability] = {}
    for capability in _CAPABILITIES:
        if capability.capability_code in registry:
            raise ValueError(
                f"duplicate capability code: {capability.capability_code!r}"
            )
        registry[capability.capability_code] = capability
    return MappingProxyType(registry)


CAPABILITY_REGISTRY: Mapping[str, PlatformCapability] = _build_registry()


def _validate_registry() -> None:
    """Fail at import if any capability names a module that does not exist.

    An unresolvable module id would make the capability permanently unentitled —
    a feature nobody can reach, discovered by a customer rather than by CI.
    """

    for capability in CAPABILITY_REGISTRY.values():
        if capability.module_id not in MODULE_REGISTRY:
            raise ValueError(
                f"capability {capability.capability_code!r} names module "
                f"{capability.module_id!r}, which is not a canonical module id"
            )
        namespace = capability.capability_code.split(".", 1)[0]
        if not namespace:
            raise ValueError(
                f"capability {capability.capability_code!r} has an empty namespace"
            )


_validate_registry()


def capability_codes() -> frozenset[str]:
    """Return every registered capability code."""

    return frozenset(CAPABILITY_REGISTRY)


def resolve_capability(capability_code: str) -> PlatformCapability | None:
    """Return the capability, or ``None`` when it is not registered."""

    return CAPABILITY_REGISTRY.get(capability_code)


def require_capability(capability_code: str) -> PlatformCapability:
    """Return the capability, raising :class:`UnknownCapabilityError` if absent."""

    capability = CAPABILITY_REGISTRY.get(capability_code)
    if capability is None:
        raise UnknownCapabilityError(capability_code)
    return capability


def module_for_capability(capability_code: str) -> str:
    """Return the canonical module id a tenant must hold for this capability."""

    return require_capability(capability_code).module_id


def is_capability_entitled(
    capability_code: str, granted: Iterable[object] | None
) -> bool:
    """Return ``True`` when ``granted`` entitles the tenant to this capability.

    Fails closed on an unregistered capability: a code this registry does not
    know is not entitled. A caller that wants an unregistered code to raise
    should use :func:`module_for_capability` instead.

    ``granted`` accepts whatever the tenant's entitlement claim holds — canonical
    ids, legacy aliases, bundle ids — because ``is_module_entitled`` expands it.
    """

    capability = CAPABILITY_REGISTRY.get(capability_code)
    if capability is None:
        return False
    try:
        return is_module_entitled(capability.module_id, granted)
    except UnknownModuleError:  # pragma: no cover - guarded by _validate_registry
        return False


def capabilities_for_module(module_id: str) -> frozenset[str]:
    """Return every capability code gated on ``module_id``."""

    return frozenset(
        capability.capability_code
        for capability in CAPABILITY_REGISTRY.values()
        if capability.module_id == module_id
    )


__all__ = [
    "CAPABILITY_REGISTRY",
    "PlatformCapability",
    "UnknownCapabilityError",
    "capabilities_for_module",
    "capability_codes",
    "is_capability_entitled",
    "module_for_capability",
    "require_capability",
    "resolve_capability",
]
