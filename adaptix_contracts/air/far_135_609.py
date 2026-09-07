"""Single numeric authority for the 14 CFR 135.609 VFR weather minimums shared
by Adaptix-Air-Service and Adaptix-Air-Service-Pilot.

Why this exists
----------------

Both HEMS engines independently declared the same twelve-row federal table:

* ``Adaptix-Air-Service/backend/air_app/far_135_609.py`` -- the reference
  transcription, module-level ``_TABLE`` and ``resolve`` / ``stricter_of``.
* ``Adaptix-Air-Service-Pilot/backend/air_pilot_app/aviation/engine.py`` --
  the same twelve rows declared inline as ``_CFR_135_609_TABLE`` with its own
  ``resolve_regulatory_minimum`` wrapper, whose own comment already says this
  table belongs in ``adaptix_contracts.air.far_135_609`` once that module
  exists.

Verified 2026-09-06: every one of the twelve rows and both scalar constants
(``LOCAL_FLYING_AREA_MAX_NM``, ``LOCAL_AREA_EXAM_VALIDITY_MONTHS``) agreed
between the two copies. Agreement was not guaranteed -- nothing prevented one
file from being corrected (a transcription fix, a CFR amendment) without the
other being touched, and the two HEMS engines on this platform must never
disagree about how much ceiling and visibility federal law requires under a
given terrain / area / lighting combination. This module is the one place the
table is declared; both services import it.

This is a deduplication fix, not a policy change. The values are transcribed,
not reinterpreted.

``air_settings``/``AviationSafetyPolicy`` on each consuming service stores
exactly one ceiling and one visibility per tenant. The regulation is not one
pair -- it is a table whose value depends on three independent axes:

* terrain            -- mountainous or nonmountainous
* flying area        -- inside the certificate holder's designated local
                         flying area, or outside it
* lighting/equipment -- day, night, or night using approved NVIS or HTAWS

A single stored pair cannot express that. An agency configured at 800 ft / 3
sm reads as compliant for a nonmountainous local day flight and is 700 ft
below the floor for a mountainous night non-local flight. Each consuming
engine scores the FRAT/weather gate against the *stricter* of the agency's
declared minimum and the regulatory floor from this module.

An operator may always be more restrictive than the regulation. It may never
be less. That asymmetry is the whole contract of :func:`stricter_of`.

Authority
---------

14 CFR 135.609, table in paragraph (a); 50 nm local-flying-area cap in
(b)(1); 12-calendar-month local-area familiarity examination in (c). Values
transcribed from the GPO print of the CFR (CFR-2016-title14-vol3-sec135-609),
verified 2026-08-15 by Adaptix-Air-Service and confirmed unchanged
2026-09-06 when this module was published. Do not change any value without
confirming the corresponding CFR text has actually changed -- this is not a
tunable.

Scope limits -- deliberately not inferred here
-----------------------------------------------

This module answers only "what does 135.609 require for these conditions". It
does NOT decide terrain class or local-area membership; those are properties
of the route and the certificate holder's OpsSpec-designated areas, which
neither consuming service holds independently of the caller. Callers pass
them in. When a caller cannot state them, :func:`resolve` returns ``None``
and the caller must surface that as an unverified regulatory floor rather
than assume compliance -- 135.609(a) itself begins "unless otherwise
specified in the certificate holder's operations specifications", so a
silently-assumed floor would be doubly wrong.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

__all__ = [
    "LOCAL_FLYING_AREA_MAX_NM",
    "LOCAL_AREA_EXAM_VALIDITY_MONTHS",
    "LightingCondition",
    "RegulatoryMinimum",
    "TerrainClass",
    "lighting_condition",
    "resolve",
    "stricter_of",
]

#: 135.609(b)(1) -- a designated local flying area may not exceed 50 nm in any
#: direction from its designated location.
LOCAL_FLYING_AREA_MAX_NM: int = 50

#: 135.609(c) -- the local-area familiarity examination is valid for 12
#: calendar months.
LOCAL_AREA_EXAM_VALIDITY_MONTHS: int = 12


class TerrainClass(str, enum.Enum):
    """Terrain classification for the route of flight."""

    NONMOUNTAINOUS = "nonmountainous"
    MOUNTAINOUS = "mountainous"


class LightingCondition(str, enum.Enum):
    """Lighting condition combined with approved night vision equipage."""

    DAY = "day"
    NIGHT = "night"
    NIGHT_NVIS_HTAWS = "night_nvis_htaws"
    """Night using an approved NVIS or HTAWS, which the table credits."""


@dataclass(frozen=True)
class RegulatoryMinimum:
    """The ceiling and visibility floor 135.609 imposes for one set of conditions."""

    ceiling_ft: int
    visibility_sm: float
    terrain: TerrainClass
    local_flying_area: bool
    lighting: LightingCondition

    @property
    def citation(self) -> str:
        """Human-readable citation naming the exact row applied."""
        area = "local" if self.local_flying_area else "non-local"
        return (
            f"14 CFR 135.609 -- {self.terrain.value} {area} flying area, "
            f"{self.lighting.value}: {self.ceiling_ft} ft ceiling, "
            f"{self.visibility_sm} sm visibility"
        )


#: The 135.609(a) table, keyed by (terrain, is_local_flying_area, lighting).
#: Values are (ceiling_ft, visibility_statute_miles) exactly as printed.
_TABLE: dict[tuple[TerrainClass, bool, LightingCondition], tuple[int, float]] = {
    # --- Nonmountainous, local flying areas --------------------------------
    (TerrainClass.NONMOUNTAINOUS, True, LightingCondition.DAY): (800, 2.0),
    (TerrainClass.NONMOUNTAINOUS, True, LightingCondition.NIGHT): (1000, 3.0),
    (TerrainClass.NONMOUNTAINOUS, True, LightingCondition.NIGHT_NVIS_HTAWS): (800, 3.0),
    # --- Nonmountainous, non-local flying areas ---------------------------
    (TerrainClass.NONMOUNTAINOUS, False, LightingCondition.DAY): (800, 3.0),
    (TerrainClass.NONMOUNTAINOUS, False, LightingCondition.NIGHT): (1000, 5.0),
    (TerrainClass.NONMOUNTAINOUS, False, LightingCondition.NIGHT_NVIS_HTAWS): (
        1000,
        3.0,
    ),
    # --- Mountainous, local flying areas ----------------------------------
    (TerrainClass.MOUNTAINOUS, True, LightingCondition.DAY): (800, 3.0),
    (TerrainClass.MOUNTAINOUS, True, LightingCondition.NIGHT): (1500, 3.0),
    (TerrainClass.MOUNTAINOUS, True, LightingCondition.NIGHT_NVIS_HTAWS): (1000, 3.0),
    # --- Mountainous, non-local flying areas ------------------------------
    (TerrainClass.MOUNTAINOUS, False, LightingCondition.DAY): (1000, 3.0),
    (TerrainClass.MOUNTAINOUS, False, LightingCondition.NIGHT): (1500, 5.0),
    (TerrainClass.MOUNTAINOUS, False, LightingCondition.NIGHT_NVIS_HTAWS): (1000, 5.0),
}


def lighting_condition(
    *, night_ops: bool, nvis_or_htaws: bool = False
) -> LightingCondition:
    """Map night/equipage booleans onto the table's lighting axis.

    The NVIS/HTAWS credit only exists at night; by day the equipment changes
    nothing in the table, so a day flight is :attr:`LightingCondition.DAY`
    regardless of equipage.

    Args:
        night_ops: True when the flight is a night operation.
        nvis_or_htaws: True when operating with an approved NVIS or HTAWS.

    Returns:
        LightingCondition: The applicable column of the 135.609 table.
    """
    if not night_ops:
        return LightingCondition.DAY
    return (
        LightingCondition.NIGHT_NVIS_HTAWS if nvis_or_htaws else LightingCondition.NIGHT
    )


def resolve(
    *,
    terrain: TerrainClass | str | None,
    local_flying_area: bool | None,
    night_ops: bool,
    nvis_or_htaws: bool = False,
) -> RegulatoryMinimum | None:
    """Return the 135.609 floor for these conditions, or None if unresolvable.

    ``None`` is returned when terrain or local-area membership is unknown. That
    is a deliberate refusal, not a failure: the caller must report the floor as
    unverified rather than assume the flight is legal. Guessing a row here would
    put a fabricated number underneath a go/no-go decision.

    Args:
        terrain: Terrain class for the route, or None when unknown.
        local_flying_area: True inside a designated local flying area, False
            outside it, None when unknown.
        night_ops: True when the flight is a night operation.
        nvis_or_htaws: True when operating with an approved NVIS or HTAWS.

    Returns:
        RegulatoryMinimum: The applicable floor, or None when unresolvable.

    Raises:
        ValueError: If ``terrain`` is a string that is not a TerrainClass value.
    """
    if terrain is None or local_flying_area is None:
        return None

    terrain_class = TerrainClass(terrain) if isinstance(terrain, str) else terrain
    lighting = lighting_condition(night_ops=night_ops, nvis_or_htaws=nvis_or_htaws)

    entry = _TABLE.get((terrain_class, bool(local_flying_area), lighting))
    if entry is None:  # pragma: no cover -- table is exhaustive over the enums
        return None

    ceiling_ft, visibility_sm = entry
    return RegulatoryMinimum(
        ceiling_ft=ceiling_ft,
        visibility_sm=visibility_sm,
        terrain=terrain_class,
        local_flying_area=bool(local_flying_area),
        lighting=lighting,
    )


def stricter_of(
    *,
    agency_ceiling_ft: int,
    agency_visibility_sm: float,
    regulatory: RegulatoryMinimum | None,
) -> tuple[int, float]:
    """Combine agency minimums with the regulatory floor, taking the stricter.

    An operator may declare minimums above the regulation and many do. It may
    never operate below it. Each dimension is compared independently, because
    an agency can be stricter on ceiling and looser on visibility at once.

    Args:
        agency_ceiling_ft: The tenant's declared ceiling minimum.
        agency_visibility_sm: The tenant's declared visibility minimum.
        regulatory: The applicable 135.609 floor, or None when unresolvable.

    Returns:
        tuple: ``(effective_ceiling_ft, effective_visibility_sm)``. When
        ``regulatory`` is None the agency values pass through unchanged -- the
        caller is responsible for flagging the floor as unverified.
    """
    if regulatory is None:
        return agency_ceiling_ft, agency_visibility_sm
    return (
        max(int(agency_ceiling_ft), regulatory.ceiling_ft),
        max(float(agency_visibility_sm), regulatory.visibility_sm),
    )
