"""Adaptix Event Registry — All registered event types across all domains."""

from __future__ import annotations

from typing import Final

from adaptix_contracts.scheduling.events import (
    ALL_SCHEDULING_EVENTS,
)

BILLING_CLAIM_UPDATED: Final[str] = "billing.claim.updated"
EPCR_CHART_UPDATED: Final[str] = "epcr.chart.updated"

FIRE_INCIDENT_CREATED: Final[str] = "fire.incident.created"
FIRE_INCIDENT_UPDATED: Final[str] = "fire.incident.updated"
FIRE_INCIDENT_CANCELLED: Final[str] = "fire.incident.cancelled"
FIRE_INCIDENT_STATUS_UPDATED: Final[str] = "fire.incident.status.updated"
FIRE_COMMAND_ROLE_ASSIGNED: Final[str] = "fire.command.role.assigned"
FIRE_COMMAND_ROLE_CHANGED: Final[str] = "fire.command.role.changed"
FIRE_APPARATUS_ASSIGNED: Final[str] = "fire.apparatus.assigned"
FIRE_APPARATUS_STATUS_UPDATED: Final[str] = "fire.apparatus.status.updated"
FIRE_PERSONNEL_ASSIGNED: Final[str] = "fire.personnel.assigned"
FIRE_PERSONNEL_ACCOUNTABILITY_UPDATED: Final[str] = (
    "fire.personnel.accountability.updated"
)
FIRE_TIMELINE_EVENT_CREATED: Final[str] = "fire.timeline.event.created"
FIRE_PREPLAN_ATTACHED: Final[str] = "fire.preplan.attached"
FIRE_HYDRANT_ATTACHED: Final[str] = "fire.hydrant.attached"
FIRE_WATER_SUPPLY_PLAN_CREATED: Final[str] = "fire.water_supply.plan.created"
FIRE_HAZARD_ATTACHED: Final[str] = "fire.hazard.attached"
FIRE_OCCUPANCY_PROFILE_ATTACHED: Final[str] = "fire.occupancy.profile.attached"
FIRE_EMS_ASSIST_REQUESTED: Final[str] = "fire.ems_assist.requested"
FIRE_REHAB_REQUESTED: Final[str] = "fire.rehab.requested"
FIRE_PATIENT_CARE_LINKED: Final[str] = "fire.patient_care.linked"
FIRE_INVENTORY_USAGE_RECORDED: Final[str] = "fire.inventory.usage.recorded"
FIRE_VOICE_ROOM_CREATED: Final[str] = "fire.voice_room.created"
FIRE_AI_ASSESSMENT_CREATED: Final[str] = "fire.ai.assessment.created"
FIRE_AR_OVERLAY_GENERATED: Final[str] = "fire.ar.overlay.generated"
FIRE_AUDIT_EVENT_CREATED: Final[str] = "fire.audit.event.created"
FIRE_BENCHMARK_TIMELINE_UPDATED: Final[str] = "fire.benchmark.timeline.updated"
FIRE_INVESTIGATION_READINESS_UPDATED: Final[str] = (
    "fire.investigation.readiness.updated"
)

NERIS_MAPPING_STARTED: Final[str] = "neris.mapping.started"
NERIS_MAPPING_COMPLETED: Final[str] = "neris.mapping.completed"
NERIS_REQUIRED_FIELD_MISSING: Final[str] = "neris.required_field.missing"
NERIS_VALIDATION_REQUESTED: Final[str] = "neris.validation.requested"
NERIS_VALIDATION_COMPLETED: Final[str] = "neris.validation.completed"
NERIS_EXPORT_CREATED: Final[str] = "neris.export.created"
NERIS_EXPORT_FAILED: Final[str] = "neris.export.failed"
NERIS_SUBMISSION_READINESS_UPDATED: Final[str] = "neris.submission.readiness.updated"
NERIS_AUDIT_EVENT_CREATED: Final[str] = "neris.audit.event.created"
NERIS_SCHEMA_ASSET_REFRESHED: Final[str] = "neris.schema.asset.refreshed"
NERIS_NORMALIZATION_COMPLETED: Final[str] = "neris.normalization.completed"

# ---------------------------------------------------------------------------
# Scheduling Events
# ---------------------------------------------------------------------------
SCHEDULING_EVENTS = ALL_SCHEDULING_EVENTS

# ---------------------------------------------------------------------------
# Full Registry
# ---------------------------------------------------------------------------
ALL_EVENTS: Final[dict[str, dict[str, object]]] = {
    BILLING_CLAIM_UPDATED: {"version": "1.0", "source_service": "billing"},
    EPCR_CHART_UPDATED: {"version": "1.0", "source_service": "epcr"},
    FIRE_INCIDENT_CREATED: {"version": "1.0", "source_service": "adaptix-fire"},
    FIRE_INCIDENT_UPDATED: {"version": "1.0", "source_service": "adaptix-fire"},
    FIRE_INCIDENT_CANCELLED: {"version": "1.0", "source_service": "adaptix-fire"},
    FIRE_INCIDENT_STATUS_UPDATED: {"version": "1.0", "source_service": "adaptix-fire"},
    FIRE_COMMAND_ROLE_ASSIGNED: {"version": "1.0", "source_service": "adaptix-fire"},
    FIRE_COMMAND_ROLE_CHANGED: {"version": "1.0", "source_service": "adaptix-fire"},
    FIRE_APPARATUS_ASSIGNED: {"version": "1.0", "source_service": "adaptix-fire"},
    FIRE_APPARATUS_STATUS_UPDATED: {"version": "1.0", "source_service": "adaptix-fire"},
    FIRE_PERSONNEL_ASSIGNED: {"version": "1.0", "source_service": "adaptix-fire"},
    FIRE_PERSONNEL_ACCOUNTABILITY_UPDATED: {
        "version": "1.0",
        "source_service": "adaptix-fire",
    },
    FIRE_TIMELINE_EVENT_CREATED: {"version": "1.0", "source_service": "adaptix-fire"},
    FIRE_PREPLAN_ATTACHED: {"version": "1.0", "source_service": "adaptix-fire"},
    FIRE_HYDRANT_ATTACHED: {"version": "1.0", "source_service": "adaptix-fire"},
    FIRE_WATER_SUPPLY_PLAN_CREATED: {
        "version": "1.0",
        "source_service": "adaptix-fire",
    },
    FIRE_HAZARD_ATTACHED: {"version": "1.0", "source_service": "adaptix-fire"},
    FIRE_OCCUPANCY_PROFILE_ATTACHED: {
        "version": "1.0",
        "source_service": "adaptix-fire",
    },
    FIRE_EMS_ASSIST_REQUESTED: {"version": "1.0", "source_service": "adaptix-fire"},
    FIRE_REHAB_REQUESTED: {"version": "1.0", "source_service": "adaptix-fire"},
    FIRE_PATIENT_CARE_LINKED: {"version": "1.0", "source_service": "adaptix-fire"},
    FIRE_INVENTORY_USAGE_RECORDED: {"version": "1.0", "source_service": "adaptix-fire"},
    FIRE_VOICE_ROOM_CREATED: {"version": "1.0", "source_service": "adaptix-fire"},
    FIRE_AI_ASSESSMENT_CREATED: {"version": "1.0", "source_service": "adaptix-fire"},
    FIRE_AR_OVERLAY_GENERATED: {"version": "1.0", "source_service": "adaptix-fire"},
    FIRE_AUDIT_EVENT_CREATED: {"version": "1.0", "source_service": "adaptix-fire"},
    FIRE_BENCHMARK_TIMELINE_UPDATED: {
        "version": "1.0",
        "source_service": "adaptix-fire",
    },
    FIRE_INVESTIGATION_READINESS_UPDATED: {
        "version": "1.0",
        "source_service": "adaptix-fire",
    },
    NERIS_MAPPING_STARTED: {"version": "1.0", "source_service": "adaptix-fire"},
    NERIS_MAPPING_COMPLETED: {"version": "1.0", "source_service": "adaptix-fire"},
    NERIS_REQUIRED_FIELD_MISSING: {"version": "1.0", "source_service": "adaptix-fire"},
    NERIS_VALIDATION_REQUESTED: {"version": "1.0", "source_service": "adaptix-fire"},
    NERIS_VALIDATION_COMPLETED: {"version": "1.0", "source_service": "adaptix-neris"},
    NERIS_EXPORT_CREATED: {"version": "1.0", "source_service": "adaptix-neris"},
    NERIS_EXPORT_FAILED: {"version": "1.0", "source_service": "adaptix-neris"},
    NERIS_SUBMISSION_READINESS_UPDATED: {
        "version": "1.0",
        "source_service": "adaptix-fire",
    },
    NERIS_AUDIT_EVENT_CREATED: {"version": "1.0", "source_service": "adaptix-neris"},
    NERIS_SCHEMA_ASSET_REFRESHED: {"version": "1.0", "source_service": "adaptix-neris"},
    NERIS_NORMALIZATION_COMPLETED: {
        "version": "1.0",
        "source_service": "adaptix-neris",
    },
}

for event_name in SCHEDULING_EVENTS:
    ALL_EVENTS.setdefault(
        event_name, {"version": "1.0", "source_service": "adaptix-scheduling"}
    )

ALL_REGISTERED_EVENTS = [
    *ALL_EVENTS.keys(),
]


def is_registered(event_type: str) -> bool:
    """Return True if the event_type is in the registry."""
    return event_type in ALL_EVENTS


def get_all_events() -> list:
    """Return all registered event types."""
    return list(ALL_REGISTERED_EVENTS)


__all__ = [
    "ALL_EVENTS",
    "ALL_REGISTERED_EVENTS",
    "BILLING_CLAIM_UPDATED",
    "EPCR_CHART_UPDATED",
    "FIRE_BENCHMARK_TIMELINE_UPDATED",
    "FIRE_INCIDENT_STATUS_UPDATED",
    "FIRE_INVESTIGATION_READINESS_UPDATED",
    "NERIS_AUDIT_EVENT_CREATED",
    "NERIS_NORMALIZATION_COMPLETED",
    "NERIS_SCHEMA_ASSET_REFRESHED",
    "NERIS_VALIDATION_COMPLETED",
    "get_all_events",
    "is_registered",
]
