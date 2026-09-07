"""Aviation regulatory contracts shared across Air Operations services.

Holds the 14 CFR 135.267 duty/rest module (``far_135_267``), the single
numeric authority for the duty-period and rest-before-completion floors, and
the 14 CFR 135.609 VFR weather minimums module (``far_135_609``), the single
authority for the ceiling/visibility table by terrain, local-flying-area
membership, and lighting. Adaptix-Air-Service and Adaptix-Air-Service-Pilot
both consume both modules.
"""

from adaptix_contracts.air.far_135_267 import (
    DUTY_EXCEPTION_MAX_DUTY_HOURS,
    REST_BEFORE_COMPLETION_HOURS,
)
from adaptix_contracts.air.far_135_609 import (
    LOCAL_AREA_EXAM_VALIDITY_MONTHS,
    LOCAL_FLYING_AREA_MAX_NM,
    LightingCondition,
    RegulatoryMinimum,
    TerrainClass,
    lighting_condition,
    resolve,
    stricter_of,
)

__all__ = [
    "DUTY_EXCEPTION_MAX_DUTY_HOURS",
    "REST_BEFORE_COMPLETION_HOURS",
    "LOCAL_AREA_EXAM_VALIDITY_MONTHS",
    "LOCAL_FLYING_AREA_MAX_NM",
    "LightingCondition",
    "RegulatoryMinimum",
    "TerrainClass",
    "lighting_condition",
    "resolve",
    "stricter_of",
]
