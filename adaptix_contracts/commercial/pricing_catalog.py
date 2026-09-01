"""Canonical commercial application / pricing-catalog vocabulary.

Phase B of the founder's modular-pricing directive: every independently
purchasable Adaptix customer application is priced and sold separately, by
real operational volume (annual incidents, active vehicles, facility count,
active personnel, ...), never by user seat count. This module is the shared
DATA-SHAPE vocabulary Adaptix-Billing-Service, Adaptix-Core-Service's signup
flow, and Adaptix-Web-App's pricing page import instead of each hand-rolling
its own — the same defect class ``module_registry`` was written to end for
entitlement ids (see that module's docstring for the drift it documents).

Why this is a dataclass registry, not a ``schemas/`` Pydantic contract
------------------------------------------------------------------------
``adaptix_contracts/schemas/*.py`` holds Pydantic wire contracts for API
requests/responses. This module is a canonical VOCABULARY — same family as
``module_registry.py`` and ``auth/capability_registry.py`` (frozen
dataclasses, validated at import, a single authoritative registry) — not a
wire format. It follows their pattern rather than the schemas/ one.

What this module deliberately does NOT do
------------------------------------------
It carries no pricing CALCULATION logic. Per
``adaptix_contracts/AGENTS.md`` ("Do not embed service-specific business
logic into shared contracts") and this repo's own
``BILLING_AND_PACKAGING_RULES.md`` ("Do not embed pricing catalog logic in
non-billing runtime code"), the shapes here describe bands, rates, and
thresholds; the engine that evaluates a tenant's volume against them and
produces a bill lives in Adaptix-Billing-Service. ``validate_catalog`` below
checks internal DATA consistency (band coverage, the annual-discount
arithmetic, cross-references into ``MODULE_REGISTRY``) — it never computes a
customer's price.

Relationship to ``module_registry``
------------------------------------
``CommercialApplicationKey`` values equal the ``module_registry`` canonical
id for every application that already has one — cross-referenced, never
duplicated. ``ApplicationPricingCatalogEntry.module_canonical_id`` records
that cross-reference explicitly and ``validate_catalog`` fails the whole
catalog if it names an id ``MODULE_REGISTRY`` does not recognize. An entry
with ``module_canonical_id=None`` is a genuinely new application with no
existing entitlement-gate identity yet — wiring one is a separate,
later task in ``module_registry.py`` and the services that gate on it, not
this change.

Relationship to Adaptix-Billing-Service
-----------------------------------------
Adaptix-Billing-Service already owns the real subscription/entitlement
tables (``billing_pricing_plans``, ``billing_pricing_tiers`` — which already
carries a ``billing_unit`` enum shaped like ``PricingBand``'s volume
dimension — ``billing_tier_modules``, ``billing_tenant_subscriptions``, and
so on). This module does not replace any of that; it gives the NEXT phase of
that service a shared vocabulary to adopt instead of inventing a sixth one.
"""

from __future__ import annotations

import enum
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from adaptix_contracts.module_registry import MODULE_REGISTRY

__all__ = [
    "ANNUAL_DISCOUNT_RATE",
    "ApplicationDependency",
    "ApplicationPricingCatalogEntry",
    "CatalogEntryStatus",
    "CommercialApplicationKey",
    "CommercialPricingCatalog",
    "PricingBand",
    "PricingMechanic",
    "UnitRateFormula",
    "UnknownCommercialApplicationError",
    "validate_catalog",
]


class UnknownCommercialApplicationError(KeyError):
    """Raised when a catalog references an unregistered application key.

    A ``KeyError`` subclass so existing ``except KeyError`` handlers keep
    working, matching ``module_registry.UnknownModuleError`` and
    ``capability_registry.UnknownCapabilityError``.
    """


class CommercialApplicationKey(str, enum.Enum):
    """One independently purchasable Adaptix customer application.

    A value equal to a ``module_registry.MODULE_REGISTRY`` canonical id means
    that application is cross-referenced from — not duplicated against — the
    existing entitlement vocabulary; see ``module_canonical_id`` on each
    catalog entry and the collision check in ``validate_catalog``. Do not
    mint a new member for an application that already has a canonical module
    id; reuse that id's string value instead.
    """

    EPCR = "epcr"
    CAD = "cad"
    MDT = "mdt"
    CREWLINK = "crewlink"
    TRANSPORTLINK = "transportlink"
    HOSPITAL = "hospital"
    FIRE = "fire"
    # The software-only revenue-cycle product ("0% of collections"). Reuses
    # module_registry's "billing" canonical id, which is distinct from
    # "agency_billing_portal" / "managed_billing" (the Adaptix Managed
    # Billing SERVICE, sold separately and not part of this 20-application
    # catalog).
    BILLING_TECHNOLOGY = "billing"
    SCHEDULING = "scheduling"
    INVENTORY = "inventory"
    NARCOTICS = "narcotics"
    FLEET = "fleet"
    # Reuses module_registry's "hems_ops" canonical id. See the HEMS catalog
    # entry's ``notes`` for a flagged tension between that id's existing
    # ``implies`` (a legacy bundled Stripe SKU) and this standalone
    # volume-banded HEMS product.
    HEMS = "hems_ops"
    CORTEX = "cortex"
    COMMUNICATIONS = "communications"
    # No canonical module id exists yet for these four — see each entry's
    # ``module_canonical_id=None`` and ``notes``.
    QA_CLINICAL_REVIEW = "qa_clinical_review"
    COMPLIANCE = "compliance"
    ANALYTICS_INTELLIGENCE = "analytics"
    COMMUNITY_PARAMEDICINE = "community_paramedicine"
    PATIENT_PAYMENTS = "patient_payments"
    THIRD_PARTY_BILLING = "third_party_billing"


class PricingMechanic(str, enum.Enum):
    """The shape of the math behind one application's price.

    Genuinely different calculation shapes stay genuinely different mechanics
    rather than being collapsed into one generic "banded price" concept —
    see each value's docstring for which applications use it and why the
    shape differs from its neighbors. No mechanic here computes a price;
    that engine lives in Adaptix-Billing-Service.
    """

    #: A flat monthly price per volume band, applied to the whole tenant
    #: count. EPCR, CAD, Fire, TransportLink, Billing Technology, Inventory,
    #: Narcotics.
    FLAT_VOLUME_BAND = "flat_volume_band"

    #: A flat monthly price per band of active workforce headcount. Same
    #: shape as ``FLAT_VOLUME_BAND`` mathematically; kept as its own value
    #: because the volume dimension is a workforce count, not an operational
    #: incident/asset count — CrewLink, Scheduling.
    WORKFORCE_HEADCOUNT_BAND = "workforce_headcount_band"

    #: A continuous per-unit rate, not a discrete band ladder — see
    #: ``UnitRateFormula``. MDT (per-unit rate with a monthly minimum),
    #: Fleet (base fee plus per-vehicle rate), HEMS (base fee covering the
    #: first operational base plus a per-additional-base rate).
    BASE_PLUS_PER_UNIT = "base_plus_per_unit"

    #: A per-unit rate that changes by which volume bracket the tenant's
    #: total count falls into, applied to the WHOLE priced count within that
    #: bracket — never graduated/marginal across brackets. Hospital
    #: (per-facility, no base fee) and Third-Party Billing (a base fee
    #: covering an included agency count, then the bracket rate applied to
    #: agencies beyond that).
    PER_UNIT_RATE_BY_BRACKET = "per_unit_rate_by_bracket"

    #: A flat platform base fee plus metered usage on top. Communications
    #: (base fee published; usage rate card not yet built).
    BASE_PLUS_METERED_USAGE = "base_plus_metered_usage"

    #: One or more starting monthly prices with the volume dimension and
    #: banded thresholds not yet defined. QA/Clinical Review, Compliance,
    #: Analytics/Intelligence, Community Paramedicine (single starting
    #: price); Cortex (three candidate starting prices, unpublished).
    STARTING_PRICE_BANDS_TBD = "starting_price_bands_tbd"

    #: A flat software fee plus real pass-through costs that are not modeled
    #: as a price band. Patient Payments.
    SOFTWARE_FEE_PLUS_PASSTHROUGH = "software_fee_plus_passthrough"


class CatalogEntryStatus(str, enum.Enum):
    """Publication state of one catalog entry — never inferred, always set."""

    #: Real, founder-approved launch pricing.
    PUBLISHED = "published"

    #: Real numbers exist but are candidates only, not approved for public
    #: launch (Cortex: pending real AI-provider-cost measurement).
    CANDIDATE_NOT_APPROVED_FOR_LAUNCH = "candidate_not_approved_for_launch"

    #: Only a starting price exists; the volume dimension and banded
    #: thresholds are not yet defined.
    STARTING_PRICE_ONLY_BANDS_TBD = "starting_price_only_bands_tbd"

    #: A platform base fee is published; the metered-usage rate card is not.
    USAGE_RATE_CARD_PENDING = "usage_rate_card_pending"

    #: A software fee is published; real pass-through costs are not modeled
    #: as a price band.
    PASSTHROUGH_COST_NOT_MODELED = "passthrough_cost_not_modeled"


#: Annual price = monthly price * 12 * (1 - ANNUAL_DISCOUNT_RATE), rounded to
#: the cent. Every ``annual_price`` / ``annual_price_per_unit`` value seeded
#: in ``wisconsin_launch_catalog`` is checked against this formula by
#: ``validate_catalog`` — the discount policy cannot silently drift from a
#: hand-typed seed figure.
ANNUAL_DISCOUNT_RATE: Decimal = Decimal("0.10")


def _expected_annual(monthly: Decimal) -> Decimal:
    """The annual price a ``monthly`` figure must match under the discount policy."""

    return (monthly * 12 * (Decimal("1") - ANNUAL_DISCOUNT_RATE)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


@dataclass(frozen=True)
class PricingBand:
    """One volume bracket inside a banded pricing mechanic.

    Exactly one of ``monthly_price`` (a flat price for the whole tier) or
    ``monthly_price_per_unit`` (a rate applied per unit in the tenant's
    priced count) is set for a real, priced band — matching whether the
    owning entry bills the tier flat or per-unit. Both stay ``None`` only
    when ``custom_quote=True``: a band with no price, routed to a manual
    quote workflow instead of a catalog lookup.

    ``annual_price`` / ``annual_price_per_unit`` are the corresponding
    figure under ``ANNUAL_DISCOUNT_RATE`` — hand-authored alongside the
    monthly figure and checked, not derived at import time, so a typo cannot
    silently ship as the annual price.

    ``max_units is None`` marks the open-ended top band.
    """

    min_units: int
    max_units: int | None
    monthly_price: Decimal | None = None
    annual_price: Decimal | None = None
    monthly_price_per_unit: Decimal | None = None
    annual_price_per_unit: Decimal | None = None
    custom_quote: bool = False


@dataclass(frozen=True)
class UnitRateFormula:
    """A continuous per-unit price, not a discrete band ladder.

    Conceptually: ``price = max(base_fee + per_unit_rate *
    max(units - included_units, 0), minimum_fee or 0)``. This module does not
    evaluate that formula (see the module docstring) — the fields exist so
    Billing-Service's engine can, from one shape, reproduce every
    ``BASE_PLUS_PER_UNIT`` application in the launch catalog:

    * Fleet: base_fee=495, per_unit_rate=59, included_units=0,
      minimum_fee=None -> price = 495 + 59 * vehicles
    * MDT: base_fee=0, per_unit_rate=125, included_units=0,
      minimum_fee=750 -> price = max(125 * devices, 750)
    * HEMS: base_fee=3995, per_unit_rate=1995, included_units=1,
      minimum_fee=None -> price = 3995 + 1995 * max(bases - 1, 0)

    ``custom_quote_above_units`` documents a spec-stated ceiling above which
    the seller quotes manually instead of applying the formula (e.g. HEMS
    "large multi-base = custom"). It stays ``None`` when the source pricing
    named no numeric threshold — a threshold has never been fabricated here.
    """

    per_unit_rate: Decimal
    base_fee: Decimal = Decimal("0")
    included_units: int = 0
    minimum_fee: Decimal | None = None
    custom_quote_above_units: int | None = None


@dataclass(frozen=True)
class ApplicationPricingCatalogEntry:  # pylint: disable=too-many-instance-attributes
    """One application's complete pricing shape inside one catalog version.

    Deliberately wide: a single ``PricingMechanic`` value selects which
    subset of these fields is populated (enforced by
    ``_validate_mechanic_shape``), so one shape covers all seven mechanics
    instead of Billing-Service having to import seven near-identical
    per-mechanic types. Matches this repo's existing precedent of exempting
    a genuinely wide, exhaustively-typed data holder from pylint's
    generic attribute-count default (see
    ``schemas/signup_contracts.py``'s ``too-few-public-methods`` exemption
    for the same class of reason, inverted).
    """

    application: CommercialApplicationKey
    display_name: str
    mechanic: PricingMechanic
    volume_dimension: str
    status: CatalogEntryStatus = CatalogEntryStatus.PUBLISHED

    #: Cross-reference into ``module_registry.MODULE_REGISTRY``. ``None``
    #: means this application has no canonical entitlement-module id yet —
    #: wiring one is separate, later work, not this change.
    module_canonical_id: str | None = None

    #: Populated for ``FLAT_VOLUME_BAND``, ``WORKFORCE_HEADCOUNT_BAND`` and
    #: ``PER_UNIT_RATE_BY_BRACKET`` mechanics.
    bands: tuple[PricingBand, ...] = ()

    #: Populated for ``BASE_PLUS_PER_UNIT``.
    unit_formula: UnitRateFormula | None = None

    #: Populated for ``BASE_PLUS_METERED_USAGE`` and
    #: ``SOFTWARE_FEE_PLUS_PASSTHROUGH``.
    base_fee_monthly: Decimal | None = None

    #: For ``PER_UNIT_RATE_BY_BRACKET`` only: units covered by
    #: ``base_fee_monthly`` before the bracket rate applies (e.g.
    #: Third-Party Billing's base fee includes 5 client agencies before the
    #: per-agency bracket rate starts). Zero for an entry with no base fee
    #: (e.g. Hospital).
    included_units: int = 0

    #: Populated for ``STARTING_PRICE_BANDS_TBD``: one figure for a single
    #: starting price, more than one only for Cortex's three unpublished
    #: candidate tiers. Never used to fabricate band thresholds that were
    #: not given in the source pricing.
    starting_monthly_prices: tuple[Decimal, ...] = ()

    notes: str = ""


@dataclass(frozen=True)
class ApplicationDependency:
    """A TRUE technical dependency of one application on others.

    Never a sales/bundling relationship — ``module_registry.implies`` already
    exists for "buying X also grants Y" and is out of scope here. This shape
    exists so a genuine technical dependency (one application's runtime
    cannot function without another's) can be recorded when one is
    confirmed. As of this catalog version, zero true dependencies are
    confirmed among the twenty-one applications it prices — see
    ``CommercialPricingCatalog.dependencies``.
    """

    application: CommercialApplicationKey
    requires: frozenset[CommercialApplicationKey] = field(default_factory=frozenset)
    reason: str = ""


@dataclass(frozen=True)
class CommercialPricingCatalog:
    """One versioned, effective-dated commercial pricing catalog.

    Prices are versioned, never silently mutated in place: a price change
    ships as a new ``catalog_version`` / ``effective_date``, not an edit to
    an existing one's ``entries``.
    """

    catalog_version: str
    effective_date: date
    jurisdiction: str
    entries: Mapping[CommercialApplicationKey, ApplicationPricingCatalogEntry]

    #: Empty and must stay empty until a founder/product decision confirms a
    #: real technical dependency — mirrors the documented-empty-invariant
    #: pattern in ``module_registry.SOLD_WITHOUT_SERVICE_MAPPING``. Adding an
    #: entry here should be rare and deliberate, not a default.
    dependencies: tuple[ApplicationDependency, ...] = ()


def _validate_band_ordering(
    application: CommercialApplicationKey, bands: tuple[PricingBand, ...]
) -> list[PricingBand]:
    ordered = sorted(bands, key=lambda band: band.min_units)
    if list(ordered) != list(bands):
        raise ValueError(f"{application.value}: bands are not in ascending order")
    return ordered


def _validate_open_ended_band(
    application: CommercialApplicationKey, ordered: list[PricingBand]
) -> None:
    open_ended = [band for band in ordered if band.max_units is None]
    if len(open_ended) != 1:
        raise ValueError(
            f"{application.value}: expected exactly one open-ended top band, "
            f"found {len(open_ended)}"
        )
    if ordered[-1].max_units is not None:
        raise ValueError(f"{application.value}: the open-ended band must be last")


def _validate_band_contiguity(
    application: CommercialApplicationKey,
    band: PricingBand,
    previous_max: int | None,
) -> None:
    if previous_max is not None and band.min_units != previous_max + 1:
        raise ValueError(
            f"{application.value}: bands are not contiguous around "
            f"min_units={band.min_units}"
        )


def _validate_band_bounds(
    application: CommercialApplicationKey,
    band: PricingBand,
    previous_max: int | None,
) -> None:
    if band.min_units < 0:
        raise ValueError(f"{application.value}: min_units must be >= 0")
    if band.max_units is not None and band.max_units < band.min_units:
        raise ValueError(f"{application.value}: band max_units below its own min_units")
    _validate_band_contiguity(application, band, previous_max)


def _validate_band_flat_annual_price(
    application: CommercialApplicationKey, band: PricingBand
) -> None:
    if band.monthly_price is not None and band.annual_price != _expected_annual(
        band.monthly_price
    ):
        raise ValueError(
            f"{application.value}: annual_price does not match "
            f"monthly_price {band.monthly_price} at ANNUAL_DISCOUNT_RATE "
            f"(expected {_expected_annual(band.monthly_price)}, got {band.annual_price})"
        )


def _validate_band_per_unit_annual_price(
    application: CommercialApplicationKey, band: PricingBand
) -> None:
    if (
        band.monthly_price_per_unit is not None
        and band.annual_price_per_unit != _expected_annual(band.monthly_price_per_unit)
    ):
        raise ValueError(
            f"{application.value}: annual_price_per_unit does not match "
            f"monthly_price_per_unit {band.monthly_price_per_unit} at "
            f"ANNUAL_DISCOUNT_RATE (expected "
            f"{_expected_annual(band.monthly_price_per_unit)}, "
            f"got {band.annual_price_per_unit})"
        )


def _validate_band_annual_price(
    application: CommercialApplicationKey, band: PricingBand
) -> None:
    _validate_band_flat_annual_price(application, band)
    _validate_band_per_unit_annual_price(application, band)


def _validate_custom_quote_band_price(
    application: CommercialApplicationKey, band: PricingBand, priced: bool
) -> None:
    if priced:
        raise ValueError(
            f"{application.value}: a custom_quote band must carry no price"
        )


def _validate_priced_band_shape(
    application: CommercialApplicationKey, band: PricingBand, priced: bool
) -> None:
    if not priced:
        raise ValueError(
            f"{application.value}: a non-custom-quote band must carry a price"
        )
    if band.monthly_price is not None and band.monthly_price_per_unit is not None:
        raise ValueError(
            f"{application.value}: a band cannot set both monthly_price and "
            "monthly_price_per_unit"
        )
    _validate_band_annual_price(application, band)


def _validate_band_price(
    application: CommercialApplicationKey, band: PricingBand
) -> None:
    priced = band.monthly_price is not None or band.monthly_price_per_unit is not None
    if band.custom_quote:
        _validate_custom_quote_band_price(application, band, priced)
        return
    _validate_priced_band_shape(application, band, priced)


def _validate_band_sequence(
    application: CommercialApplicationKey, bands: tuple[PricingBand, ...]
) -> None:
    if not bands:
        return
    ordered = _validate_band_ordering(application, bands)
    _validate_open_ended_band(application, ordered)

    previous_max: int | None = None
    for band in ordered:
        _validate_band_bounds(application, band, previous_max)
        previous_max = band.max_units
        _validate_band_price(application, band)


def _validate_banded_mechanic_shape(
    application: CommercialApplicationKey,
    mechanic: PricingMechanic,
    entry: ApplicationPricingCatalogEntry,
) -> None:
    if not entry.bands:
        raise ValueError(f"{application.value}: {mechanic.value} requires bands")
    if entry.unit_formula is not None:
        raise ValueError(
            f"{application.value}: {mechanic.value} must not set unit_formula"
        )
    if entry.starting_monthly_prices:
        raise ValueError(
            f"{application.value}: {mechanic.value} must not set "
            "starting_monthly_prices"
        )


def _validate_unit_formula_shape(
    application: CommercialApplicationKey,
    mechanic: PricingMechanic,
    entry: ApplicationPricingCatalogEntry,
) -> None:
    if entry.unit_formula is None:
        raise ValueError(f"{application.value}: {mechanic.value} requires unit_formula")
    if entry.bands:
        raise ValueError(f"{application.value}: {mechanic.value} must not set bands")


def _validate_starting_price_shape(
    application: CommercialApplicationKey,
    mechanic: PricingMechanic,
    entry: ApplicationPricingCatalogEntry,
) -> None:
    if not entry.starting_monthly_prices:
        raise ValueError(
            f"{application.value}: {mechanic.value} requires starting_monthly_prices"
        )
    if entry.bands:
        raise ValueError(f"{application.value}: {mechanic.value} must not set bands")


def _validate_base_fee_shape(
    application: CommercialApplicationKey,
    mechanic: PricingMechanic,
    entry: ApplicationPricingCatalogEntry,
) -> None:
    if entry.base_fee_monthly is None:
        raise ValueError(
            f"{application.value}: {mechanic.value} requires base_fee_monthly"
        )
    if entry.bands:
        raise ValueError(f"{application.value}: {mechanic.value} must not set bands")


#: One shape-validator per mechanic. A dict dispatch, not an if/elif chain, so
#: adding a mechanic cannot silently grow this into an unmaintainable branch
#: ladder — see ``_MECHANIC_SHAPE_VALIDATORS`` used in ``_validate_mechanic_shape``.
_MechanicShapeValidator = Callable[
    [CommercialApplicationKey, PricingMechanic, ApplicationPricingCatalogEntry], None
]
_MECHANIC_SHAPE_VALIDATORS: Mapping[PricingMechanic, _MechanicShapeValidator] = {
    PricingMechanic.FLAT_VOLUME_BAND: _validate_banded_mechanic_shape,
    PricingMechanic.WORKFORCE_HEADCOUNT_BAND: _validate_banded_mechanic_shape,
    PricingMechanic.PER_UNIT_RATE_BY_BRACKET: _validate_banded_mechanic_shape,
    PricingMechanic.BASE_PLUS_PER_UNIT: _validate_unit_formula_shape,
    PricingMechanic.STARTING_PRICE_BANDS_TBD: _validate_starting_price_shape,
    PricingMechanic.BASE_PLUS_METERED_USAGE: _validate_base_fee_shape,
    PricingMechanic.SOFTWARE_FEE_PLUS_PASSTHROUGH: _validate_base_fee_shape,
}


def _validate_included_units_usage(
    application: CommercialApplicationKey,
    mechanic: PricingMechanic,
    entry: ApplicationPricingCatalogEntry,
) -> None:
    if (
        mechanic is not PricingMechanic.PER_UNIT_RATE_BY_BRACKET
        and entry.included_units
    ):
        raise ValueError(
            f"{application.value}: included_units is only meaningful for "
            f"{PricingMechanic.PER_UNIT_RATE_BY_BRACKET.value}"
        )
    if entry.included_units and entry.base_fee_monthly is None:
        raise ValueError(
            f"{application.value}: included_units without base_fee_monthly makes "
            "no sense"
        )


def _validate_mechanic_shape(
    application: CommercialApplicationKey, entry: ApplicationPricingCatalogEntry
) -> None:
    """Every entry populates only the fields its own mechanic uses.

    Catches the class of defect where an entry is authored under one
    mechanic but the wrong shape is filled in (or the right shape is left
    empty) — e.g. a ``BASE_PLUS_PER_UNIT`` entry with no ``unit_formula``
    would silently price as "nothing", not fail loudly.
    """

    mechanic = entry.mechanic
    validator = _MECHANIC_SHAPE_VALIDATORS.get(mechanic)
    if (
        validator is None
    ):  # pragma: no cover - exhaustiveness guard for future mechanics
        raise ValueError(f"{application.value}: unhandled mechanic {mechanic.value}")
    validator(application, mechanic, entry)
    _validate_included_units_usage(application, mechanic, entry)


def _validate_catalog_coverage(catalog: CommercialPricingCatalog) -> None:
    missing = [key for key in CommercialApplicationKey if key not in catalog.entries]
    if missing:
        raise ValueError(
            "catalog is missing entries for: "
            + ", ".join(sorted(key.value for key in missing))
        )


def _validate_catalog_entry(
    key: CommercialApplicationKey, entry: ApplicationPricingCatalogEntry
) -> None:
    if entry.application is not key:
        raise ValueError(
            f"entries[{key.value!r}].application is {entry.application.value!r}, "
            "not the mapping key it is stored under"
        )
    if (
        entry.module_canonical_id is not None
        and entry.module_canonical_id not in MODULE_REGISTRY
    ):
        raise ValueError(
            f"{key.value}: module_canonical_id {entry.module_canonical_id!r} "
            "is not a canonical id in module_registry.MODULE_REGISTRY"
        )
    _validate_band_sequence(key, entry.bands)
    _validate_mechanic_shape(key, entry)


def _validate_dependency(
    dependency: ApplicationDependency, catalog: CommercialPricingCatalog
) -> None:
    if dependency.application in dependency.requires:
        raise ValueError(f"{dependency.application.value}: cannot require itself")
    unknown = [
        required.value
        for required in dependency.requires
        if required not in catalog.entries
    ]
    if unknown:
        raise ValueError(
            f"{dependency.application.value}: requires unregistered "
            "application(s): " + ", ".join(sorted(unknown))
        )


def _validate_catalog_dependencies(catalog: CommercialPricingCatalog) -> None:
    for dependency in catalog.dependencies:
        _validate_dependency(dependency, catalog)


def validate_catalog(catalog: CommercialPricingCatalog) -> None:
    """Validate a catalog for internal consistency. Raises ``ValueError``.

    This checks DATA integrity only — coverage, cross-references, the
    annual-discount arithmetic, band contiguity — never a computed price.
    See the module docstring for why pricing calculation stays out of this
    package entirely.
    """

    _validate_catalog_coverage(catalog)
    for key, entry in catalog.entries.items():
        _validate_catalog_entry(key, entry)
    _validate_catalog_dependencies(catalog)
