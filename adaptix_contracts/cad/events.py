"""CAD domain events — canonical event type strings.

All CAD events must be imported from this module.
"""

from __future__ import annotations

from typing import Final

# Medical transport intake events
CAD_INTAKE_CREATED: Final[str] = "cad.medical_transport.intake.created"
CAD_INTAKE_UPDATED: Final[str] = "cad.medical_transport.intake.updated"
# CAD live outbox family is cad.intake.* (Adaptix-CAD-Service).
CAD_INTAKE_CANCELLED: Final[str] = "cad.intake.cancelled"

# Assessment events
CAD_LEVEL_OF_CARE_ASSESSED: Final[str] = "cad.medical_transport.level_of_care.assessed"
CAD_MEDICAL_NECESSITY_ASSESSED: Final[str] = (
    "cad.medical_transport.medical_necessity.assessed"
)
CAD_UNIT_RECOMMENDED: Final[str] = "cad.medical_transport.unit.recommended"
CAD_CREW_RECOMMENDED: Final[str] = "cad.medical_transport.crew.recommended"

# Dispatch events
CAD_DISPATCH_CREATED: Final[str] = "cad.medical_transport.dispatch.created"
CAD_DISPATCH_UPDATED: Final[str] = "cad.medical_transport.dispatch.updated"
CAD_DISPATCH_CANCELLED: Final[str] = "cad.medical_transport.dispatch.cancelled"

# Unit / crew assignment events
CAD_UNIT_ASSIGNED: Final[str] = "cad.medical_transport.unit.assigned"
CAD_UNIT_REASSIGNED: Final[str] = "cad.medical_transport.unit.reassigned"
CAD_UNIT_STATUS_UPDATED: Final[str] = "cad.medical_transport.unit.status.updated"

# Vehicle tracking events
CAD_VEHICLE_LOCATION_UPDATED: Final[str] = (
    "cad.medical_transport.vehicle.location.updated"
)
CAD_VEHICLE_TELEMETRY_RECEIVED: Final[str] = (
    "cad.medical_transport.vehicle.telemetry.received"
)

# Routing / ETA events
CAD_ROUTING_ETA_UPDATED: Final[str] = "cad.medical_transport.routing_eta.updated"

# Handoff events
CAD_TRANSPORTLINK_HANDOFF_CREATED: Final[str] = (
    "cad.medical_transport.transportlink.handoff.created"
)
CAD_EPCR_CREATED: Final[str] = "cad.medical_transport.epcr.created"
CAD_EPCR_HANDOFF_CREATED: Final[str] = "cad.medical_transport.epcr_handoff.created"
CAD_NEMSIS_HANDOFF_GENERATED: Final[str] = (
    "cad.medical_transport.nemsis_handoff.generated"
)
CAD_BILLING_HANDOFF_CREATED: Final[str] = (
    "cad.medical_transport.billing_handoff.created"
)
CAD_CREWLINK_PAGE_CREATED: Final[str] = "cad.medical_transport.crewlink.page.created"
CAD_VOICE_ROOM_CREATED: Final[str] = "cad.medical_transport.voice_room.created"

# MDT / Scheduling sync events
CAD_MDT_SYNCED: Final[str] = "cad.medical_transport.mdt.synced"
CAD_SCHEDULING_SYNCED: Final[str] = "cad.medical_transport.scheduling.synced"

# HEMS events
CAD_HEMS_REQUEST_CREATED: Final[str] = "cad.hems.request.created"
CAD_HEMS_ELIGIBILITY_ASSESSED: Final[str] = "cad.hems.eligibility.assessed"
CAD_HEMS_BRIEFING_GENERATED: Final[str] = "cad.hems.briefing.generated"
CAD_HEMS_GROUND_FALLBACK_RECOMMENDED: Final[str] = (
    "cad.hems.ground_fallback.recommended"
)
CAD_HEMS_STATUS_UPDATED: Final[str] = "cad.hems.status.updated"

# AI / Audit events
CAD_AI_ASSESSMENT_CREATED: Final[str] = "cad.ai.assessment.created"
CAD_AUDIT_EVENT_CREATED: Final[str] = "cad.audit.event.created"

ALL_CAD_EVENTS: Final[list] = [
    CAD_INTAKE_CREATED,
    CAD_INTAKE_UPDATED,
    CAD_INTAKE_CANCELLED,
    CAD_LEVEL_OF_CARE_ASSESSED,
    CAD_MEDICAL_NECESSITY_ASSESSED,
    CAD_UNIT_RECOMMENDED,
    CAD_CREW_RECOMMENDED,
    CAD_DISPATCH_CREATED,
    CAD_DISPATCH_UPDATED,
    CAD_DISPATCH_CANCELLED,
    CAD_UNIT_ASSIGNED,
    CAD_UNIT_REASSIGNED,
    CAD_UNIT_STATUS_UPDATED,
    CAD_VEHICLE_LOCATION_UPDATED,
    CAD_VEHICLE_TELEMETRY_RECEIVED,
    CAD_ROUTING_ETA_UPDATED,
    CAD_TRANSPORTLINK_HANDOFF_CREATED,
    CAD_EPCR_CREATED,
    CAD_EPCR_HANDOFF_CREATED,
    CAD_NEMSIS_HANDOFF_GENERATED,
    CAD_BILLING_HANDOFF_CREATED,
    CAD_CREWLINK_PAGE_CREATED,
    CAD_VOICE_ROOM_CREATED,
    CAD_MDT_SYNCED,
    CAD_SCHEDULING_SYNCED,
    CAD_HEMS_REQUEST_CREATED,
    CAD_HEMS_ELIGIBILITY_ASSESSED,
    CAD_HEMS_BRIEFING_GENERATED,
    CAD_HEMS_GROUND_FALLBACK_RECOMMENDED,
    CAD_HEMS_STATUS_UPDATED,
    CAD_AI_ASSESSMENT_CREATED,
    CAD_AUDIT_EVENT_CREATED,
]
