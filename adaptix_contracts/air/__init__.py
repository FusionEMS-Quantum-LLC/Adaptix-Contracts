"""Aviation regulatory contracts shared across Air Operations services.

Currently holds the 14 CFR 135.267 duty/rest module (``far_135_267``), the
single numeric authority for the duty-period and rest-before-completion
floors that Adaptix-Air-Service and Adaptix-Air-Service-Pilot both consume.
"""

from adaptix_contracts.air.far_135_267 import (
    DUTY_EXCEPTION_MAX_DUTY_HOURS,
    REST_BEFORE_COMPLETION_HOURS,
)

__all__ = [
    "DUTY_EXCEPTION_MAX_DUTY_HOURS",
    "REST_BEFORE_COMPLETION_HOURS",
]
