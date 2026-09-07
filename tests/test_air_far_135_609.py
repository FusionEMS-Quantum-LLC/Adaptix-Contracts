"""Regression tests for the shared 14 CFR 135.609 VFR weather minimums table.

Adaptix-Air-Service and Adaptix-Air-Service-Pilot both import
``resolve``, ``stricter_of``, and the supporting types from here instead of
declaring their own copies of the table. The table is transcribed law, so it
is tested value-by-value against the CFR print rather than against the
implementation: every one of the twelve rows is asserted explicitly, because
a transcription slip here silently lowers the floor under a real go/no-go
flight decision and no amount of downstream testing would catch it.
"""

from __future__ import annotations

import pytest

from adaptix_contracts.air import (
    LOCAL_AREA_EXAM_VALIDITY_MONTHS,
    LOCAL_FLYING_AREA_MAX_NM,
    LightingCondition,
    RegulatoryMinimum,
    TerrainClass,
    lighting_condition,
    resolve,
    stricter_of,
)
from adaptix_contracts.air import far_135_609


# ---------------------------------------------------------------------------
# The table, row by row, exactly as printed in the CFR
# ---------------------------------------------------------------------------

# (terrain, local_flying_area, night_ops, nvis_or_htaws) -> (ceiling_ft, vis_sm)
_CFR_ROWS = [
    # Nonmountainous local flying areas: 800/2 day, 1000/3 night, 800/3 NVIS
    (("nonmountainous", True, False, False), (800, 2.0)),
    (("nonmountainous", True, True, False), (1000, 3.0)),
    (("nonmountainous", True, True, True), (800, 3.0)),
    # Nonmountainous non-local: 800/3 day, 1000/5 night, 1000/3 NVIS
    (("nonmountainous", False, False, False), (800, 3.0)),
    (("nonmountainous", False, True, False), (1000, 5.0)),
    (("nonmountainous", False, True, True), (1000, 3.0)),
    # Mountainous local: 800/3 day, 1500/3 night, 1000/3 NVIS
    (("mountainous", True, False, False), (800, 3.0)),
    (("mountainous", True, True, False), (1500, 3.0)),
    (("mountainous", True, True, True), (1000, 3.0)),
    # Mountainous non-local: 1000/3 day, 1500/5 night, 1000/5 NVIS
    (("mountainous", False, False, False), (1000, 3.0)),
    (("mountainous", False, True, False), (1500, 5.0)),
    (("mountainous", False, True, True), (1000, 5.0)),
]


@pytest.mark.parametrize(("inputs", "expected"), _CFR_ROWS)
def test_every_cfr_row_matches_the_printed_table(inputs, expected) -> None:
    """All twelve 135.609(a) rows resolve to the exact printed values."""
    terrain, local, night, nvis = inputs
    expected_ceiling, expected_vis = expected

    minimum = resolve(
        terrain=terrain,
        local_flying_area=local,
        night_ops=night,
        nvis_or_htaws=nvis,
    )

    assert minimum is not None
    assert minimum.ceiling_ft == expected_ceiling
    assert minimum.visibility_sm == expected_vis
    assert isinstance(minimum, RegulatoryMinimum)


def test_table_covers_every_combination() -> None:
    """No combination of the three axes is missing a row."""
    for terrain in TerrainClass:
        for local in (True, False):
            for night, nvis in ((False, False), (True, False), (True, True)):
                assert (
                    resolve(
                        terrain=terrain,
                        local_flying_area=local,
                        night_ops=night,
                        nvis_or_htaws=nvis,
                    )
                    is not None
                )


def test_statutory_constants_match_the_regulation() -> None:
    """135.609(b)(1) 50 nm cap and (c) 12-month exam validity."""
    assert LOCAL_FLYING_AREA_MAX_NM == 50
    assert LOCAL_AREA_EXAM_VALIDITY_MONTHS == 12


def test_package_root_reexports_module_symbols() -> None:
    """The package-root import must be the same object as the module import,
    not an independently declared copy that could drift."""

    assert LOCAL_FLYING_AREA_MAX_NM == far_135_609.LOCAL_FLYING_AREA_MAX_NM
    assert (
        LOCAL_AREA_EXAM_VALIDITY_MONTHS == far_135_609.LOCAL_AREA_EXAM_VALIDITY_MONTHS
    )
    assert resolve is far_135_609.resolve
    assert stricter_of is far_135_609.stricter_of
    assert TerrainClass is far_135_609.TerrainClass
    assert LightingCondition is far_135_609.LightingCondition
    assert RegulatoryMinimum is far_135_609.RegulatoryMinimum


# ---------------------------------------------------------------------------
# Lighting axis
# ---------------------------------------------------------------------------


def test_nvis_credit_only_applies_at_night() -> None:
    """By day the equipment changes nothing in the table."""
    assert lighting_condition(night_ops=False, nvis_or_htaws=True) is (
        LightingCondition.DAY
    )
    assert lighting_condition(night_ops=True, nvis_or_htaws=True) is (
        LightingCondition.NIGHT_NVIS_HTAWS
    )
    assert lighting_condition(night_ops=True, nvis_or_htaws=False) is (
        LightingCondition.NIGHT
    )
    # A day flight with NVIS resolves to the day row, not a night row.
    day_with_nvis = resolve(
        terrain="mountainous",
        local_flying_area=True,
        night_ops=False,
        nvis_or_htaws=True,
    )
    assert day_with_nvis is not None
    assert (day_with_nvis.ceiling_ft, day_with_nvis.visibility_sm) == (800, 3.0)


# ---------------------------------------------------------------------------
# Refusal to guess
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("terrain", "local"),
    [(None, True), ("mountainous", None), (None, None)],
)
def test_unresolvable_classification_returns_none_never_a_guess(terrain, local) -> None:
    """Unknown terrain or flying area yields None, not an assumed row."""
    assert resolve(terrain=terrain, local_flying_area=local, night_ops=False) is None


def test_invalid_terrain_string_raises() -> None:
    """A terrain value with no table row is an error, not a silent None."""
    with pytest.raises(ValueError):
        resolve(terrain="hilly", local_flying_area=True, night_ops=False)


def test_terrain_class_instance_accepted_directly() -> None:
    """Callers may pass the enum member instead of its string value."""
    minimum = resolve(
        terrain=TerrainClass.MOUNTAINOUS,
        local_flying_area=True,
        night_ops=False,
    )
    assert minimum is not None
    assert minimum.terrain is TerrainClass.MOUNTAINOUS


# ---------------------------------------------------------------------------
# RegulatoryMinimum.citation
# ---------------------------------------------------------------------------


def test_citation_names_the_exact_row_applied() -> None:
    minimum = resolve(terrain="mountainous", local_flying_area=False, night_ops=True)
    assert minimum is not None
    citation = minimum.citation
    assert "135.609" in citation
    assert "mountainous" in citation
    assert "non-local" in citation
    assert "1500" in citation
    assert "5.0" in citation


# ---------------------------------------------------------------------------
# stricter_of -- the agency-may-exceed-never-undercut rule
# ---------------------------------------------------------------------------


def test_stricter_of_takes_the_higher_value_per_dimension() -> None:
    """An agency stricter on one axis and looser on the other is corrected."""
    regulatory = resolve(
        terrain="mountainous", local_flying_area=False, night_ops=True
    )  # 1500 ft / 5 sm
    assert regulatory is not None

    # Agency: stricter ceiling (1800), looser visibility (3).
    ceiling, visibility = stricter_of(
        agency_ceiling_ft=1800, agency_visibility_sm=3.0, regulatory=regulatory
    )
    assert ceiling == 1800  # agency wins where it is stricter
    assert visibility == 5.0  # CFR wins where the agency is looser


def test_stricter_of_passes_agency_values_through_when_floor_unknown() -> None:
    """With no resolvable floor the agency values are returned unchanged."""
    assert stricter_of(
        agency_ceiling_ft=800, agency_visibility_sm=3.0, regulatory=None
    ) == (800, 3.0)


def test_stricter_of_never_undercuts_a_looser_agency_value() -> None:
    """An agency below the regulation on both axes is corrected on both."""
    regulatory = resolve(
        terrain="nonmountainous", local_flying_area=True, night_ops=False
    )  # 800 ft / 2.0 sm
    assert regulatory is not None

    ceiling, visibility = stricter_of(
        agency_ceiling_ft=500, agency_visibility_sm=1.0, regulatory=regulatory
    )
    assert ceiling == 800
    assert visibility == 2.0
