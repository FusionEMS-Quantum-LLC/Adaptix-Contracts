"""Adaptix Hydrant Registry — Enumerations.

Play P07 (Hydrant registry / fire flow test history). Enums are shared
across ``models.py`` and ``events.py`` so status, color, and test-type
strings never drift between the models a service publishes and the events
consumers read.
"""

from __future__ import annotations

from enum import StrEnum


class HydrantStatus(StrEnum):
    """Operational status of a hydrant."""

    IN_SERVICE = "in_service"
    OUT_OF_SERVICE = "out_of_service"
    DAMAGED = "damaged"


class HydrantColor(StrEnum):
    """NFPA 291 flow-class bonnet/cap color for a hydrant.

    Mirrors the standard NFPA 291 color-coding used by fire departments to
    mark expected flow rate at a glance: blue (>1500 GPM), green
    (1000-1499 GPM), orange (500-999 GPM), red (<500 GPM).
    """

    BLUE = "blue"
    GREEN = "green"
    ORANGE = "orange"
    RED = "red"


class TestType(StrEnum):
    """The kind of hydrant test/inspection event being recorded."""

    FLOW_TEST = "flow_test"
    STATIC_PRESSURE_TEST = "static_pressure_test"
    RESIDUAL_PRESSURE_TEST = "residual_pressure_test"
    VISUAL_INSPECTION = "visual_inspection"
    OPERABILITY_CHECK = "operability_check"
    PAINT_INSPECTION = "paint_inspection"
    OTHER = "other"


__all__ = [
    "HydrantColor",
    "HydrantStatus",
    "TestType",
]
