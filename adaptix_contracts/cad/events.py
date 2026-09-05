"""CAD domain events — canonical event type strings.

Two vocabularies live in this module, and they must not be conflated:

* ``CAD_INCIDENT_CREATED``, ``CAD_UNIT_DISPATCHED``, ``CAD_INCIDENT_CLOSED``,
  ``CAD_UNIT_STATUS_CHANGED`` — the 911/incident dispatch lane. VERIFIED
  live producer: ``Adaptix-CAD-Service/backend/cad_app/cad_event_publisher.py``
  (outbox relay to the core event bus; called from
  ``cad_app/api/incidents_router.py`` and
  ``cad_app/api/incident_dispatches_router.py``).
* ``CAD_INTAKE_CREATED``, ``CAD_INTAKE_UPDATED``, ``CAD_INTAKE_CANCELLED`` —
  the IFT intake lifecycle. VERIFIED live producer:
  ``Adaptix-CAD-Service/backend/cad_app/services/intake_repository.py``
  (same outbox relay; direct string literals at the ``publish_outbox`` call
  sites). ``CAD_INTAKE_CANCELLED`` was already corrected to its live value
  by a prior change (see the now-removed comment this docstring replaces);
  ``CAD_INTAKE_CREATED``/``CAD_INTAKE_UPDATED`` carried the same class of
  drift and are corrected here the same way.

  All seven of the above are registered in
  ``adaptix_contracts.events.registry.ALL_EVENTS`` and cited there and in
  ``tests/test_event_producer_registry_drift.py::INDIRECT_ENVELOPE_PRODUCERS``.
* Every other constant below (``cad.medical_transport.*``, ``cad.hems.*``,
  ``cad.ai.*``, ``cad.audit.*``) is the IFT/medical-transport CAD lane.
  Adaptix-CAD-Service hosts both the 911 lane above and this IFT lane in one
  service; they are distinguished by their record field set, not by a shared
  event vocabulary — do not assume a handler for one lane also covers the
  other. Audit 2026-09-05: an org-wide search for each of these dotted strings
  found NO producer anywhere in the fleet — ``Adaptix-CAD-Service`` mentions
  ``cad.medical_transport.epcr_handoff.created`` and
  ``cad.medical_transport.nemsis_handoff.generated`` only in one docstring
  (``cad_app/epcr_handoff_service.py``), with no corresponding emission
  code. They are therefore DELIBERATELY NOT registered in
  ``events.registry.ALL_EVENTS`` — registering an event with no real
  producer would require a fabricated file:line citation, which
  ``tests/test_event_producer_registry_drift.py`` exists specifically to
  catch (see ``adaptix_contracts.cad_connect.events`` /
  ``adaptix_contracts.qa.events`` for the same staged-contract pattern).
  Register each one, with its real producer's file:line, in the same pull
  request that ships that producer.

The previous revision of this docstring said "All CAD events must be
imported from this module" — that was never true for the incident lane
above (Adaptix-CAD-Service defines its own copy of those four constants and
does not import this module) and gave every reader the false impression the
medical_transport/hems/ai/audit vocabulary below was live.
"""

from __future__ import annotations

from typing import Final

# --- 911/incident dispatch lane (verified live producer — see module docstring) ---
CAD_INCIDENT_CREATED: Final[str] = "cad.incident.created"
CAD_UNIT_DISPATCHED: Final[str] = "cad.unit.dispatched"
CAD_INCIDENT_CLOSED: Final[str] = "cad.incident.closed"
CAD_UNIT_STATUS_CHANGED: Final[str] = "cad.unit.status_changed"

# --- IFT/medical-transport CAD lane (staged contract — see module docstring) ---

# Medical transport intake events — live outbox family is cad.intake.*
# (Adaptix-CAD-Service/backend/cad_app/services/intake_repository.py:307,463,539).
CAD_INTAKE_CREATED: Final[str] = "cad.intake.created"
CAD_INTAKE_UPDATED: Final[str] = "cad.intake.updated"
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
    CAD_INCIDENT_CREATED,
    CAD_UNIT_DISPATCHED,
    CAD_INCIDENT_CLOSED,
    CAD_UNIT_STATUS_CHANGED,
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
