"""NFPA 1620 Pre-Incident Planning contracts (Play P07).

Re-exports the models, enums, event names/payloads/envelope factories,
and service error contracts for the Preplan service — preplans, floor
plans, and hazards for NFPA 1620 pre-incident planning.
"""

from adaptix_contracts.preplan.enums import HazardClass, KnoxKeyStatus, OccupancyType
from adaptix_contracts.preplan.errors import (
    PreplanErrorCode,
    PreplanErrorEnvelope,
    PreplanServiceError,
    knox_box_missing,
    occupancy_not_found,
    preplan_not_found,
    preplan_not_ready_for_response,
    to_adaptix_error_code,
)
from adaptix_contracts.preplan.events import (
    PREPLAN_EVENTS,
    PREPLAN_FLOOR_PLAN_ADDED,
    PREPLAN_HAZARD_RECORDED,
    PREPLAN_OCCUPANCY_REGISTERED,
    PREPLAN_PUBLISHED,
    PREPLAN_READINESS_CHANGED,
    PREPLAN_SOURCE_SERVICE,
    PreplanFloorPlanAddedPayload,
    PreplanHazardRecordedPayload,
    PreplanOccupancyRegisteredPayload,
    PreplanPublishedPayload,
    PreplanReadinessChangedPayload,
    build_preplan_floor_plan_added_event,
    build_preplan_hazard_recorded_event,
    build_preplan_occupancy_registered_event,
    build_preplan_published_event,
    build_preplan_readiness_changed_event,
)
from adaptix_contracts.preplan.models import (
    FloorPlan,
    Hazard,
    KnoxBox,
    Occupancy,
    Preplan,
    UtilityShutoff,
)

__all__ = [
    "FloorPlan",
    "Hazard",
    "HazardClass",
    "KnoxBox",
    "KnoxKeyStatus",
    "Occupancy",
    "OccupancyType",
    "PREPLAN_EVENTS",
    "PREPLAN_FLOOR_PLAN_ADDED",
    "PREPLAN_HAZARD_RECORDED",
    "PREPLAN_OCCUPANCY_REGISTERED",
    "PREPLAN_PUBLISHED",
    "PREPLAN_READINESS_CHANGED",
    "PREPLAN_SOURCE_SERVICE",
    "Preplan",
    "PreplanErrorCode",
    "PreplanErrorEnvelope",
    "PreplanFloorPlanAddedPayload",
    "PreplanHazardRecordedPayload",
    "PreplanOccupancyRegisteredPayload",
    "PreplanPublishedPayload",
    "PreplanReadinessChangedPayload",
    "PreplanServiceError",
    "UtilityShutoff",
    "build_preplan_floor_plan_added_event",
    "build_preplan_hazard_recorded_event",
    "build_preplan_occupancy_registered_event",
    "build_preplan_published_event",
    "build_preplan_readiness_changed_event",
    "knox_box_missing",
    "occupancy_not_found",
    "preplan_not_found",
    "preplan_not_ready_for_response",
    "to_adaptix_error_code",
]
