"""Regression test for the shared 14 CFR 135.267 duty/rest constants.

Adaptix-Air-Service and Adaptix-Air-Service-Pilot both import
``DUTY_EXCEPTION_MAX_DUTY_HOURS`` and ``REST_BEFORE_COMPLETION_HOURS`` from
here instead of declaring their own copies. The load-bearing property is that
these two federal numbers never silently change: 14 hours duty, 10 hours
rest, per 14 CFR 135.267(c) and (d).
"""

from __future__ import annotations

from adaptix_contracts.air import (
    DUTY_EXCEPTION_MAX_DUTY_HOURS,
    REST_BEFORE_COMPLETION_HOURS,
)
from adaptix_contracts.air import far_135_267


def test_duty_exception_max_duty_hours_is_the_cfr_value() -> None:
    """14 CFR 135.267(c): 'a regularly assigned duty period of no more than
    14 hours'."""

    assert DUTY_EXCEPTION_MAX_DUTY_HOURS == 14


def test_rest_before_completion_hours_is_the_cfr_value() -> None:
    """14 CFR 135.267(d): 'at least 10 consecutive hours of rest ... that
    precedes the planned completion time of the assignment'."""

    assert REST_BEFORE_COMPLETION_HOURS == 10


def test_package_root_reexports_module_symbols() -> None:
    """The package-root import must be the same object as the module import,
    not an independently declared copy that could drift."""

    assert DUTY_EXCEPTION_MAX_DUTY_HOURS is far_135_267.DUTY_EXCEPTION_MAX_DUTY_HOURS
    assert REST_BEFORE_COMPLETION_HOURS is far_135_267.REST_BEFORE_COMPLETION_HOURS


def test_values_are_integers_not_derived_floats() -> None:
    """Both constants are whole hours; consumers that need minutes multiply
    locally rather than this module carrying a second, divergent unit."""

    assert isinstance(DUTY_EXCEPTION_MAX_DUTY_HOURS, int)
    assert isinstance(REST_BEFORE_COMPLETION_HOURS, int)
