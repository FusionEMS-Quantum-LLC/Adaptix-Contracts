"""Adaptix Event Registry — All registered event types across all domains.

``source_service`` contract
---------------------------
Every ``ALL_EVENTS`` entry stamps ``source_service`` with the **service registry
slug** of the producing service — the same vocabulary
``adaptix_contracts.schemas.service_registry.SERVICE_BY_SLUG`` is keyed on, and
the same value ``events/operational_envelope.py`` documents for its
``source_service`` field. It is deliberately NOT the JWT audience
(``adaptix_contracts.service_audiences``) and NOT the ECS/ECR service name
(``platform/ownership_manifest.json`` ``service_name``); those are separate
identifier namespaces that happen to look similar for some services.

Use :func:`resolve_source_service` / :func:`producer_of` rather than indexing
``SERVICE_BY_SLUG`` directly, so a caller that still holds a legacy
``adaptix``-prefixed string keeps resolving.
"""

from __future__ import annotations

from typing import Final

from adaptix_contracts.scheduling.events import (
    ALL_SCHEDULING_EVENTS,
)
from adaptix_contracts.schemas.service_registry import (
    SERVICE_BY_SLUG,
    ServiceDefinition,
)

BILLING_CLAIM_UPDATED: Final[str] = "billing.claim.updated"
EPCR_CHART_UPDATED: Final[str] = "epcr.chart.updated"

# ---------------------------------------------------------------------------
# Workforce operational events (EventBridge backbone, Phase 1)
# ---------------------------------------------------------------------------
# Emitted by Adaptix-Workforce-Service (service registry slug ``workforce``) when
# a shift is cancelled — i.e. the shift is vacated / the staff assignment is
# removed. ``source_service="workforce"`` resolves via SERVICE_BY_SLUG, so this
# event is NOT one of the 27 ``schedule.*`` events that carry the
# ``scheduling`` source; it is a workforce-owned event whose producer is
# the live Workforce service. See tests/test_workforce_event_backbone.py.
WORKFORCE_SHIFT_CANCELLED: Final[str] = "workforce.shift.cancelled"

# ---------------------------------------------------------------------------
# Fleet operational events (producer: Adaptix-Fleet-Service, slug ``fleet``)
# ---------------------------------------------------------------------------
# Emitted by ``fleet_app/outbox.py`` (transactional outbox, same lifecycle as
# the Workforce outbox above) when a vehicle's status changes. Fleet ALSO
# publishes these two event names to a separate SQS queue
# (``signal-events-queue``, ``fleet_app/intelligence_event_publisher.py``) for
# OpsTwin/PulseIQ — that is a distinct transport, not this registry's
# EventBridge backbone. Registering here is what lets CAD-Service's event
# worker (which polls the Core event bus, not signal-events-queue) subscribe.
# Producer citation: Adaptix-Fleet-Service/backend/fleet_app/outbox.py,
# ``enqueue_unit_status_changed`` / ``enqueue_vehicle_out_of_service``.
FLEET_UNIT_STATUS_CHANGED: Final[str] = "fleet.unit.status_changed"
FLEET_VEHICLE_OUT_OF_SERVICE: Final[str] = "fleet.vehicle.out_of_service"

# ---------------------------------------------------------------------------
# Billing domain events (producer: Adaptix-Billing-Service, slug ``billing``)
# ---------------------------------------------------------------------------
# Every constant below is emitted TODAY through the shared contract envelope
# ``adaptix_contracts.event_contracts.EventSchema``. Producer citations are
# origin/main of Adaptix-Billing-Service, verified 2026-08-09:
#   billing_app/services/event_publisher.py:34   billing.claim.created
#   billing_app/services/event_publisher.py:130  billing.claim.status_changed
#   billing_app/services/event_publisher.py:166  billing.payment.received
#   billing_app/services/event_publisher.py:201  billing.invoice.created
#   billing_app/services/event_publisher.py:238  billing.invoice.paid
#   billing_app/event_consumers_calls.py:103     billing.call_context.assembled
#   billing_app/api/trustsign_routes.py:892      trustsign.document.signed
# They were unregistered, so ``is_registered()`` returned False for real
# production traffic and ``assert_event_type_registered()`` would have rejected
# them on the operational backbone.
BILLING_CLAIM_CREATED: Final[str] = "billing.claim.created"
BILLING_CLAIM_STATUS_CHANGED: Final[str] = "billing.claim.status_changed"
BILLING_PAYMENT_RECEIVED: Final[str] = "billing.payment.received"
BILLING_INVOICE_CREATED: Final[str] = "billing.invoice.created"
BILLING_INVOICE_PAID: Final[str] = "billing.invoice.paid"
BILLING_CALL_CONTEXT_ASSEMBLED: Final[str] = "billing.call_context.assembled"

# Cross-domain: the TrustSign signature completion event is published BY
# Adaptix-Billing-Service (it owns the TrustSign request tables) so ePCR and the
# claim pipeline can react without polling. ``source_service`` therefore names
# the actual producer, ``billing`` — not the ``trustsign`` topic prefix.
TRUSTSIGN_DOCUMENT_SIGNED: Final[str] = "trustsign.document.signed"

# ---------------------------------------------------------------------------
# ePCR domain events (producer: Adaptix-EPCR-Service, slug ``epcr``)
# ---------------------------------------------------------------------------
# Producer citations are origin/main of Adaptix-EPCR-Service, verified
# 2026-08-09:
#   epcr_app/services/chart_publisher.py:27   epcr.chart.finalized
#   epcr_app/services/chart_publisher.py:62   epcr.chart.created
#   epcr_app/services/chart_publisher.py:165  epcr.chart.signed
#   epcr_app/services/chart_publisher.py:203  epcr.chart.locked
#   epcr_app/services/chart_publisher.py:239  epcr.chart.unlocked
#   epcr_app/services/chart_publisher.py:277  epcr.chart.nemsis_validation_completed
#   epcr_app/services/chart_publisher.py:318  epcr.chart.nemsis_export_completed
EPCR_CHART_CREATED: Final[str] = "epcr.chart.created"
EPCR_CHART_FINALIZED: Final[str] = "epcr.chart.finalized"
EPCR_CHART_SIGNED: Final[str] = "epcr.chart.signed"
EPCR_CHART_LOCKED: Final[str] = "epcr.chart.locked"
EPCR_CHART_UNLOCKED: Final[str] = "epcr.chart.unlocked"
EPCR_CHART_NEMSIS_VALIDATION_COMPLETED: Final[str] = (
    "epcr.chart.nemsis_validation_completed"
)
EPCR_CHART_NEMSIS_EXPORT_COMPLETED: Final[str] = "epcr.chart.nemsis_export_completed"

# ---------------------------------------------------------------------------
# ePCR outbox-relayed events (producer: Adaptix-EPCR-Service, slug ``epcr``)
# ---------------------------------------------------------------------------
# Every constant below is written to the ``ChartEventOutbox`` table and then
# republished onto the shared contract envelope
# (``adaptix_contracts.event_contracts.EventSchema``, ``source_service="epcr"``)
# by the generic relay at
# ``Adaptix-EPCR-Service/backend/epcr_app/outbox_worker.py:99``. That relay
# passes the row's own ``event_type``, so the string never appears literally at
# the envelope construction site — which is exactly why these stayed invisible
# to the earlier producer audit and unregistered here. Producer citations are
# origin/main of Adaptix-EPCR-Service, verified 2026-08-09:
#   epcr_app/chart_amendment_service.py:92        epcr.chart.amended
#   epcr_app/api_chart_cortex_lifecycle.py:102    epcr.chart.billing_handoff
#   epcr_app/chart_finalization_service.py:57     epcr.nemsis_submit.failed
#   epcr_app/chart_finalization_service.py:58     epcr.nemsis_submit.succeeded
#
# ``epcr.chart.hospital_handoff`` is registered here as the shared typed
# contract for the upcoming EPCR->hospital handoff emission. The producer is
# not yet present in this workspace, so it is intentionally NOT listed in the
# live indirect-producer drift inventory until EPCR lands the emitting file:line.
EPCR_CHART_AMENDED: Final[str] = "epcr.chart.amended"
EPCR_CHART_BILLING_HANDOFF: Final[str] = "epcr.chart.billing_handoff"
EPCR_CHART_HOSPITAL_HANDOFF: Final[str] = "epcr.chart.hospital_handoff"
EPCR_NEMSIS_SUBMIT_FAILED: Final[str] = "epcr.nemsis_submit.failed"
EPCR_NEMSIS_SUBMIT_SUCCEEDED: Final[str] = "epcr.nemsis_submit.succeeded"

# CareGraph / CPAE / VAS are ePCR-owned clinical sub-domains. Their events take
# the same ``ChartEventOutbox`` -> ``outbox_worker.py:99`` relay, so they too
# arrive at cross-service consumers stamped ``source_service="epcr"`` — the
# topic prefix names the sub-domain, not a separate producing service.
# Producer citations are origin/main of Adaptix-EPCR-Service (2026-08-09):
#   epcr_app/services_caregraph.py:57-62   caregraph.*
#   epcr_app/services_cpae.py:55-60        cpae.*
#   epcr_app/services_vas.py:47-54         vas.*
CAREGRAPH_NODE_CREATED: Final[str] = "caregraph.node.created"
CAREGRAPH_NODE_AMENDED: Final[str] = "caregraph.node.amended"
CAREGRAPH_NODE_REVIEWED: Final[str] = "caregraph.node.reviewed"
CAREGRAPH_NODE_RULED_OUT: Final[str] = "caregraph.node.ruled_out"
CAREGRAPH_EDGE_CREATED: Final[str] = "caregraph.edge.created"
CAREGRAPH_EDGE_REMOVED: Final[str] = "caregraph.edge.removed"
CPAE_FINDING_CREATED: Final[str] = "cpae.finding.created"
CPAE_FINDING_PROPOSED: Final[str] = "cpae.finding.proposed"
CPAE_FINDING_ACCEPTED: Final[str] = "cpae.finding.accepted"
CPAE_FINDING_AMENDED: Final[str] = "cpae.finding.amended"
CPAE_FINDING_REJECTED: Final[str] = "cpae.finding.rejected"
CPAE_FINDING_CONTRADICTION_DETECTED: Final[str] = "cpae.finding.contradiction_detected"
VAS_OVERLAY_CREATED: Final[str] = "vas.overlay.created"
VAS_OVERLAY_ACCEPTED: Final[str] = "vas.overlay.accepted"
VAS_OVERLAY_REJECTED: Final[str] = "vas.overlay.rejected"
VAS_OVERLAY_AMENDED: Final[str] = "vas.overlay.amended"
VAS_OVERLAY_REMOVED: Final[str] = "vas.overlay.removed"
VAS_PROJECTION_PROPOSED: Final[str] = "vas.projection.proposed"
VAS_PROJECTION_REVIEWED: Final[str] = "vas.projection.reviewed"

# ePCR vision-capture events go DIRECTLY to the shared envelope through the thin
# publish wrapper ``_publish_event(event_type=...)`` at
# ``Adaptix-EPCR-Service/backend/epcr_app/services/chart_vision_capture_service.py:728``,
# which stamps ``source_service="epcr"``. Producer citations are origin/main of
# Adaptix-EPCR-Service, verified 2026-08-09:
#   chart_vision_capture_service.py:905   epcr.vision.capture_created
#   chart_vision_capture_service.py:1119  epcr.vision.capture_accepted
#   chart_vision_capture_service.py:1132  epcr.vision.vital_signs_accepted
#   chart_vision_capture_service.py:1147  epcr.vision.twelve_lead_accepted
#   chart_vision_capture_service.py:1201  epcr.vision.capture_rejected
EPCR_VISION_CAPTURE_CREATED: Final[str] = "epcr.vision.capture_created"
EPCR_VISION_CAPTURE_ACCEPTED: Final[str] = "epcr.vision.capture_accepted"
EPCR_VISION_VITAL_SIGNS_ACCEPTED: Final[str] = "epcr.vision.vital_signs_accepted"
EPCR_VISION_TWELVE_LEAD_ACCEPTED: Final[str] = "epcr.vision.twelve_lead_accepted"
EPCR_VISION_CAPTURE_REJECTED: Final[str] = "epcr.vision.capture_rejected"

# Cross-domain: the cath-lab activation recommendation is published BY
# Adaptix-EPCR-Service (the 12-lead interpretation lives there) so a receiving
# hospital can pre-activate. ``source_service`` therefore names the actual
# producer, ``epcr`` — not the ``hospital`` topic prefix. Same precedent as
# ``trustsign.document.signed`` being produced by ``billing``.
#   chart_vision_capture_service.py:1155  hospital.cath_lab.activate_recommended
HOSPITAL_CATH_LAB_ACTIVATE_RECOMMENDED: Final[str] = (
    "hospital.cath_lab.activate_recommended"
)

# ---------------------------------------------------------------------------
# Patient identity events (producer: Adaptix-Patient-Identity-Service)
# ---------------------------------------------------------------------------
# Written to the ``OutboxEvent`` table at
# ``Adaptix-Patient-Identity-Service/backend/patient_identity_app/outbox.py:173``
# and republished onto the shared envelope by the relay at
# ``.../patient_identity_app/outbox_worker.py:88``, which stamps
# ``source_service="patient_identity"``. The registry declares the canonical
# service-registry slug ``patient-identity``; the underscore form the producer
# actually emits resolves through PRODUCER_SOURCE_SERVICE_ALIASES.
# Verified against that repo's origin/main 2026-08-09.
PATIENT_IDENTITY_MERGED: Final[str] = "patient.identity.merged"

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

# --- Fire events with a live envelope producer -----------------------------
# Emitted TODAY by Adaptix-Fire-Service through
# ``adaptix_contracts.event_contracts.EventSchema``. Producer citations are
# origin/main of Adaptix-Fire-Service, verified 2026-08-09:
#   fire_app/services/event_publisher.py:110  fire.incident.completed
#   fire_app/services/event_publisher.py:148  fire.incident.closed
#   fire_app/services/event_publisher.py:186  fire.unit.dispatched
#   fire_app/models/incident.py:420           fire.incident.status_changed
FIRE_INCIDENT_COMPLETED: Final[str] = "fire.incident.completed"
FIRE_INCIDENT_CLOSED: Final[str] = "fire.incident.closed"
FIRE_UNIT_DISPATCHED: Final[str] = "fire.unit.dispatched"

# NAMING DRIFT, deliberately preserved rather than collapsed:
# ``FIRE_INCIDENT_STATUS_UPDATED`` above is "fire.incident.status.updated"
# (dot-separated) and has NO envelope producer in the workspace. The live
# producer at fire_app/models/incident.py:420 emits the DISTINCT string
# "fire.incident.status_changed" (underscore). Both are registered because both
# are real strings a consumer can receive; renaming either one is a breaking
# change to whichever side already matches on it, and choosing the survivor is a
# Fire-domain decision, not a contracts decision. Consumers that need "status
# moved" semantics must subscribe to BOTH until the Fire domain retires one.
FIRE_INCIDENT_STATUS_CHANGED: Final[str] = "fire.incident.status_changed"

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
# Necessity domain events — Play P02 pre-submit medical-necessity linter
# ---------------------------------------------------------------------------
# Emitted by Adaptix-EPCR-Service at the pre-submit / chart-lock boundary when
# the medical-necessity linter runs. All three are ``source_service="epcr"``
# because the linter executes inside the ePCR service — Billing subscribes to
# ``denial.predicted`` as a consumer even though the payload is billing-shaped.
# See adaptix_contracts/necessity/events.py for the payload models.
NECESSITY_ASSESSED: Final[str] = "necessity.assessed"
CHART_LOCK_BLOCKED: Final[str] = "chart.lock.blocked"
DENIAL_PREDICTED: Final[str] = "denial.predicted"

# ---------------------------------------------------------------------------
# Scheduling Events
# ---------------------------------------------------------------------------
SCHEDULING_EVENTS = ALL_SCHEDULING_EVENTS

# ---------------------------------------------------------------------------
# Full Registry
# ---------------------------------------------------------------------------
ALL_EVENTS: Final[dict[str, dict[str, object]]] = {
    BILLING_CLAIM_UPDATED: {"version": "1.0", "source_service": "billing"},
    BILLING_CLAIM_CREATED: {"version": "1.0", "source_service": "billing"},
    BILLING_CLAIM_STATUS_CHANGED: {"version": "1.0", "source_service": "billing"},
    BILLING_PAYMENT_RECEIVED: {"version": "1.0", "source_service": "billing"},
    BILLING_INVOICE_CREATED: {"version": "1.0", "source_service": "billing"},
    BILLING_INVOICE_PAID: {"version": "1.0", "source_service": "billing"},
    BILLING_CALL_CONTEXT_ASSEMBLED: {"version": "1.0", "source_service": "billing"},
    TRUSTSIGN_DOCUMENT_SIGNED: {"version": "1.0", "source_service": "billing"},
    EPCR_CHART_UPDATED: {"version": "1.0", "source_service": "epcr"},
    EPCR_CHART_CREATED: {"version": "1.0", "source_service": "epcr"},
    EPCR_CHART_FINALIZED: {"version": "1.0", "source_service": "epcr"},
    EPCR_CHART_SIGNED: {"version": "1.0", "source_service": "epcr"},
    EPCR_CHART_LOCKED: {"version": "1.0", "source_service": "epcr"},
    EPCR_CHART_UNLOCKED: {"version": "1.0", "source_service": "epcr"},
    EPCR_CHART_NEMSIS_VALIDATION_COMPLETED: {
        "version": "1.0",
        "source_service": "epcr",
    },
    EPCR_CHART_NEMSIS_EXPORT_COMPLETED: {"version": "1.0", "source_service": "epcr"},
    EPCR_CHART_AMENDED: {"version": "1.0", "source_service": "epcr"},
    EPCR_CHART_BILLING_HANDOFF: {"version": "1.0", "source_service": "epcr"},
    EPCR_CHART_HOSPITAL_HANDOFF: {"version": "1.0", "source_service": "epcr"},
    EPCR_NEMSIS_SUBMIT_FAILED: {"version": "1.0", "source_service": "epcr"},
    EPCR_NEMSIS_SUBMIT_SUCCEEDED: {"version": "1.0", "source_service": "epcr"},
    EPCR_VISION_CAPTURE_CREATED: {"version": "1.0", "source_service": "epcr"},
    EPCR_VISION_CAPTURE_ACCEPTED: {"version": "1.0", "source_service": "epcr"},
    EPCR_VISION_VITAL_SIGNS_ACCEPTED: {"version": "1.0", "source_service": "epcr"},
    EPCR_VISION_TWELVE_LEAD_ACCEPTED: {"version": "1.0", "source_service": "epcr"},
    EPCR_VISION_CAPTURE_REJECTED: {"version": "1.0", "source_service": "epcr"},
    HOSPITAL_CATH_LAB_ACTIVATE_RECOMMENDED: {
        "version": "1.0",
        "source_service": "epcr",
    },
    CAREGRAPH_NODE_CREATED: {"version": "1.0", "source_service": "epcr"},
    CAREGRAPH_NODE_AMENDED: {"version": "1.0", "source_service": "epcr"},
    CAREGRAPH_NODE_REVIEWED: {"version": "1.0", "source_service": "epcr"},
    CAREGRAPH_NODE_RULED_OUT: {"version": "1.0", "source_service": "epcr"},
    CAREGRAPH_EDGE_CREATED: {"version": "1.0", "source_service": "epcr"},
    CAREGRAPH_EDGE_REMOVED: {"version": "1.0", "source_service": "epcr"},
    CPAE_FINDING_CREATED: {"version": "1.0", "source_service": "epcr"},
    CPAE_FINDING_PROPOSED: {"version": "1.0", "source_service": "epcr"},
    CPAE_FINDING_ACCEPTED: {"version": "1.0", "source_service": "epcr"},
    CPAE_FINDING_AMENDED: {"version": "1.0", "source_service": "epcr"},
    CPAE_FINDING_REJECTED: {"version": "1.0", "source_service": "epcr"},
    CPAE_FINDING_CONTRADICTION_DETECTED: {"version": "1.0", "source_service": "epcr"},
    VAS_OVERLAY_CREATED: {"version": "1.0", "source_service": "epcr"},
    VAS_OVERLAY_ACCEPTED: {"version": "1.0", "source_service": "epcr"},
    VAS_OVERLAY_REJECTED: {"version": "1.0", "source_service": "epcr"},
    VAS_OVERLAY_AMENDED: {"version": "1.0", "source_service": "epcr"},
    VAS_OVERLAY_REMOVED: {"version": "1.0", "source_service": "epcr"},
    VAS_PROJECTION_PROPOSED: {"version": "1.0", "source_service": "epcr"},
    VAS_PROJECTION_REVIEWED: {"version": "1.0", "source_service": "epcr"},
    PATIENT_IDENTITY_MERGED: {"version": "1.0", "source_service": "patient-identity"},
    WORKFORCE_SHIFT_CANCELLED: {"version": "1.0", "source_service": "workforce"},
    FLEET_UNIT_STATUS_CHANGED: {"version": "1.0", "source_service": "fleet"},
    FLEET_VEHICLE_OUT_OF_SERVICE: {"version": "1.0", "source_service": "fleet"},
    FIRE_INCIDENT_CREATED: {"version": "1.0", "source_service": "fire"},
    FIRE_INCIDENT_COMPLETED: {"version": "1.0", "source_service": "fire"},
    FIRE_INCIDENT_CLOSED: {"version": "1.0", "source_service": "fire"},
    FIRE_INCIDENT_STATUS_CHANGED: {"version": "1.0", "source_service": "fire"},
    FIRE_UNIT_DISPATCHED: {"version": "1.0", "source_service": "fire"},
    FIRE_INCIDENT_UPDATED: {"version": "1.0", "source_service": "fire"},
    FIRE_INCIDENT_CANCELLED: {"version": "1.0", "source_service": "fire"},
    FIRE_INCIDENT_STATUS_UPDATED: {"version": "1.0", "source_service": "fire"},
    FIRE_COMMAND_ROLE_ASSIGNED: {"version": "1.0", "source_service": "fire"},
    FIRE_COMMAND_ROLE_CHANGED: {"version": "1.0", "source_service": "fire"},
    FIRE_APPARATUS_ASSIGNED: {"version": "1.0", "source_service": "fire"},
    FIRE_APPARATUS_STATUS_UPDATED: {"version": "1.0", "source_service": "fire"},
    FIRE_PERSONNEL_ASSIGNED: {"version": "1.0", "source_service": "fire"},
    FIRE_PERSONNEL_ACCOUNTABILITY_UPDATED: {
        "version": "1.0",
        "source_service": "fire",
    },
    FIRE_TIMELINE_EVENT_CREATED: {"version": "1.0", "source_service": "fire"},
    FIRE_PREPLAN_ATTACHED: {"version": "1.0", "source_service": "fire"},
    FIRE_HYDRANT_ATTACHED: {"version": "1.0", "source_service": "fire"},
    FIRE_WATER_SUPPLY_PLAN_CREATED: {
        "version": "1.0",
        "source_service": "fire",
    },
    FIRE_HAZARD_ATTACHED: {"version": "1.0", "source_service": "fire"},
    FIRE_OCCUPANCY_PROFILE_ATTACHED: {
        "version": "1.0",
        "source_service": "fire",
    },
    FIRE_EMS_ASSIST_REQUESTED: {"version": "1.0", "source_service": "fire"},
    FIRE_REHAB_REQUESTED: {"version": "1.0", "source_service": "fire"},
    FIRE_PATIENT_CARE_LINKED: {"version": "1.0", "source_service": "fire"},
    FIRE_INVENTORY_USAGE_RECORDED: {"version": "1.0", "source_service": "fire"},
    FIRE_VOICE_ROOM_CREATED: {"version": "1.0", "source_service": "fire"},
    FIRE_AI_ASSESSMENT_CREATED: {"version": "1.0", "source_service": "fire"},
    FIRE_AR_OVERLAY_GENERATED: {"version": "1.0", "source_service": "fire"},
    FIRE_AUDIT_EVENT_CREATED: {"version": "1.0", "source_service": "fire"},
    FIRE_BENCHMARK_TIMELINE_UPDATED: {
        "version": "1.0",
        "source_service": "fire",
    },
    FIRE_INVESTIGATION_READINESS_UPDATED: {
        "version": "1.0",
        "source_service": "fire",
    },
    NERIS_MAPPING_STARTED: {"version": "1.0", "source_service": "fire"},
    NERIS_MAPPING_COMPLETED: {"version": "1.0", "source_service": "fire"},
    NERIS_REQUIRED_FIELD_MISSING: {"version": "1.0", "source_service": "fire"},
    NERIS_VALIDATION_REQUESTED: {"version": "1.0", "source_service": "fire"},
    NERIS_VALIDATION_COMPLETED: {"version": "1.0", "source_service": "neris"},
    NERIS_EXPORT_CREATED: {"version": "1.0", "source_service": "neris"},
    NERIS_EXPORT_FAILED: {"version": "1.0", "source_service": "neris"},
    NERIS_SUBMISSION_READINESS_UPDATED: {
        "version": "1.0",
        "source_service": "fire",
    },
    NERIS_AUDIT_EVENT_CREATED: {"version": "1.0", "source_service": "neris"},
    NERIS_SCHEMA_ASSET_REFRESHED: {"version": "1.0", "source_service": "neris"},
    NERIS_NORMALIZATION_COMPLETED: {
        "version": "1.0",
        "source_service": "neris",
    },
    # Play P02 pre-submit medical-necessity linter — producer is the ePCR
    # pre-submit / chart-lock code path in Adaptix-EPCR-Service. Payload models
    # live in adaptix_contracts/necessity/events.py.
    NECESSITY_ASSESSED: {"version": "1.0", "source_service": "epcr"},
    CHART_LOCK_BLOCKED: {"version": "1.0", "source_service": "epcr"},
    DENIAL_PREDICTED: {"version": "1.0", "source_service": "epcr"},
}

for event_name in SCHEDULING_EVENTS:
    ALL_EVENTS.setdefault(
        event_name, {"version": "1.0", "source_service": "scheduling"}
    )

ALL_REGISTERED_EVENTS = [
    *ALL_EVENTS.keys(),
]

#: Source-service strings this registry published BEFORE the slug normalisation,
#: mapped to the canonical service-registry slug. Kept so a consumer holding a
#: previously-published value (from a persisted event row, a replayed
#: EventBridge archive, or a pinned older adaptix-contracts) still resolves to
#: the right producer instead of silently returning None.
LEGACY_SOURCE_SERVICE_ALIASES: Final[dict[str, str]] = {
    "adaptix-fire": "fire",
    "adaptix-neris": "neris",
    "adaptix-scheduling": "scheduling",
}

#: Source-service strings a LIVE producer stamps today that are not themselves
#: ``SERVICE_BY_SLUG`` keys, mapped to the canonical slug. Distinct from
#: :data:`LEGACY_SOURCE_SERVICE_ALIASES`: nothing here is historical — a running
#: service emits these strings right now, so a consumer that cannot resolve them
#: cannot identify the producer of an event it is holding.
#:
#: ``patient_identity`` (underscore) is stamped by
#: ``Adaptix-Patient-Identity-Service/backend/patient_identity_app/outbox_worker.py:88``
#: at that repo's origin/main (verified 2026-08-09); the service-registry slug is
#: ``patient-identity`` (hyphen). Accepting the alias keeps consumers correct
#: without a coordinated cross-repo rename, which would strand every event
#: already persisted with the underscore form.
PRODUCER_SOURCE_SERVICE_ALIASES: Final[dict[str, str]] = {
    "patient_identity": "patient-identity",
}


def is_registered(event_type: str) -> bool:
    """Return True if the event_type is in the registry."""
    return event_type in ALL_EVENTS


def get_all_events() -> list:
    """Return all registered event types."""
    return list(ALL_REGISTERED_EVENTS)


def resolve_source_service(source_service: str) -> ServiceDefinition | None:
    """Resolve an event ``source_service`` string to its ``ServiceDefinition``.

    Accepts the canonical service-registry slug (``"fire"``), any string in
    :data:`LEGACY_SOURCE_SERVICE_ALIASES` (``"adaptix-fire"``), and any string in
    :data:`PRODUCER_SOURCE_SERVICE_ALIASES` (``"patient_identity"``). Returns
    ``None`` when the string names no registered service — callers must treat
    that as drift, not as an absent-but-acceptable producer.
    """
    service = SERVICE_BY_SLUG.get(source_service)
    if service is not None:
        return service
    aliased = LEGACY_SOURCE_SERVICE_ALIASES.get(
        source_service
    ) or PRODUCER_SOURCE_SERVICE_ALIASES.get(source_service)
    if aliased is not None:
        return SERVICE_BY_SLUG.get(aliased)
    return None


def producer_of(event_type: str) -> ServiceDefinition:
    """Return the ``ServiceDefinition`` that publishes ``event_type``.

    Raises:
        KeyError: ``event_type`` is not in :data:`ALL_EVENTS`. An unregistered
            event type is a contract gap — register it (with its producer
            file:line citation) rather than defaulting to a guessed producer.
        ValueError: the registered ``source_service`` resolves to no service.
    """
    try:
        meta = ALL_EVENTS[event_type]
    except KeyError:
        raise KeyError(
            f"event_type is not registered in adaptix_contracts.events.registry: "
            f"{event_type!r}"
        ) from None
    source_service = str(meta["source_service"])
    service = resolve_source_service(source_service)
    if service is None:
        raise ValueError(
            f"{event_type!r} declares source_service={source_service!r}, which "
            "resolves to no ServiceDefinition in "
            "adaptix_contracts.schemas.service_registry"
        )
    return service


__all__ = [
    "ALL_EVENTS",
    "ALL_REGISTERED_EVENTS",
    "BILLING_CALL_CONTEXT_ASSEMBLED",
    "BILLING_CLAIM_CREATED",
    "BILLING_CLAIM_STATUS_CHANGED",
    "BILLING_CLAIM_UPDATED",
    "BILLING_INVOICE_CREATED",
    "BILLING_INVOICE_PAID",
    "BILLING_PAYMENT_RECEIVED",
    "CAREGRAPH_EDGE_CREATED",
    "CAREGRAPH_EDGE_REMOVED",
    "CAREGRAPH_NODE_AMENDED",
    "CAREGRAPH_NODE_CREATED",
    "CAREGRAPH_NODE_REVIEWED",
    "CAREGRAPH_NODE_RULED_OUT",
    "CHART_LOCK_BLOCKED",
    "CPAE_FINDING_ACCEPTED",
    "CPAE_FINDING_AMENDED",
    "CPAE_FINDING_CONTRADICTION_DETECTED",
    "CPAE_FINDING_CREATED",
    "CPAE_FINDING_PROPOSED",
    "CPAE_FINDING_REJECTED",
    "DENIAL_PREDICTED",
    "EPCR_CHART_AMENDED",
    "EPCR_CHART_BILLING_HANDOFF",
    "EPCR_CHART_CREATED",
    "EPCR_CHART_FINALIZED",
    "EPCR_CHART_HOSPITAL_HANDOFF",
    "EPCR_CHART_LOCKED",
    "EPCR_CHART_NEMSIS_EXPORT_COMPLETED",
    "EPCR_CHART_NEMSIS_VALIDATION_COMPLETED",
    "EPCR_CHART_SIGNED",
    "EPCR_CHART_UNLOCKED",
    "EPCR_CHART_UPDATED",
    "EPCR_NEMSIS_SUBMIT_FAILED",
    "EPCR_NEMSIS_SUBMIT_SUCCEEDED",
    "EPCR_VISION_CAPTURE_ACCEPTED",
    "EPCR_VISION_CAPTURE_CREATED",
    "EPCR_VISION_CAPTURE_REJECTED",
    "EPCR_VISION_TWELVE_LEAD_ACCEPTED",
    "EPCR_VISION_VITAL_SIGNS_ACCEPTED",
    "FIRE_BENCHMARK_TIMELINE_UPDATED",
    "FIRE_INCIDENT_CLOSED",
    "FIRE_INCIDENT_COMPLETED",
    "FIRE_INCIDENT_STATUS_CHANGED",
    "FIRE_INCIDENT_STATUS_UPDATED",
    "FIRE_INVESTIGATION_READINESS_UPDATED",
    "FIRE_UNIT_DISPATCHED",
    "FLEET_UNIT_STATUS_CHANGED",
    "FLEET_VEHICLE_OUT_OF_SERVICE",
    "HOSPITAL_CATH_LAB_ACTIVATE_RECOMMENDED",
    "LEGACY_SOURCE_SERVICE_ALIASES",
    "NECESSITY_ASSESSED",
    "NERIS_AUDIT_EVENT_CREATED",
    "NERIS_NORMALIZATION_COMPLETED",
    "NERIS_SCHEMA_ASSET_REFRESHED",
    "NERIS_VALIDATION_COMPLETED",
    "PATIENT_IDENTITY_MERGED",
    "PRODUCER_SOURCE_SERVICE_ALIASES",
    "TRUSTSIGN_DOCUMENT_SIGNED",
    "VAS_OVERLAY_ACCEPTED",
    "VAS_OVERLAY_AMENDED",
    "VAS_OVERLAY_CREATED",
    "VAS_OVERLAY_REJECTED",
    "VAS_OVERLAY_REMOVED",
    "VAS_PROJECTION_PROPOSED",
    "VAS_PROJECTION_REVIEWED",
    "WORKFORCE_SHIFT_CANCELLED",
    "get_all_events",
    "is_registered",
    "producer_of",
    "resolve_source_service",
]
