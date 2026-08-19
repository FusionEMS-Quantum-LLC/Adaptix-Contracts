"""Adaptix Hydrant Registry contracts (Play P07).

Re-exports the models, enums, event names/payloads/envelope factories,
and service error contracts for the Hydrant-Service.
"""

from adaptix_contracts.hydrant.enums import (
    HydrantColor,
    HydrantStatus,
    TestType,
)
from adaptix_contracts.hydrant.errors import (
    HydrantErrorCode,
    HydrantErrorEnvelope,
    HydrantServiceError,
    hydrant_invalid_status_transition,
    hydrant_not_found,
    maintenance_not_found,
    test_invalid_reading,
    to_adaptix_error_code,
)
from adaptix_contracts.hydrant.events import (
    HYDRANT_EVENTS,
    HYDRANT_MAINTENANCE_LOGGED,
    HYDRANT_REGISTERED,
    HYDRANT_SOURCE_SERVICE,
    HYDRANT_STATUS_CHANGED,
    HYDRANT_TESTED,
    HydrantMaintenanceLoggedPayload,
    HydrantRegisteredPayload,
    HydrantStatusChangedPayload,
    HydrantTestedPayload,
    build_hydrant_maintenance_logged_event,
    build_hydrant_registered_event,
    build_hydrant_status_changed_event,
    build_hydrant_tested_event,
)
from adaptix_contracts.hydrant.models import (
    Hydrant,
    HydrantMaintenance,
    HydrantTest,
)

__all__ = [
    "HYDRANT_EVENTS",
    "HYDRANT_MAINTENANCE_LOGGED",
    "HYDRANT_REGISTERED",
    "HYDRANT_SOURCE_SERVICE",
    "HYDRANT_STATUS_CHANGED",
    "HYDRANT_TESTED",
    "Hydrant",
    "HydrantColor",
    "HydrantErrorCode",
    "HydrantErrorEnvelope",
    "HydrantMaintenance",
    "HydrantMaintenanceLoggedPayload",
    "HydrantRegisteredPayload",
    "HydrantServiceError",
    "HydrantStatus",
    "HydrantStatusChangedPayload",
    "HydrantTest",
    "HydrantTestedPayload",
    "TestType",
    "build_hydrant_maintenance_logged_event",
    "build_hydrant_registered_event",
    "build_hydrant_status_changed_event",
    "build_hydrant_tested_event",
    "hydrant_invalid_status_transition",
    "hydrant_not_found",
    "maintenance_not_found",
    "test_invalid_reading",
    "to_adaptix_error_code",
]
