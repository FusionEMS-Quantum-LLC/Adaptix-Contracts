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
    WORKFORCE_SHIFT_CANCELLED: {"version": "1.0", "source_service": "workforce"},
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


def is_registered(event_type: str) -> bool:
    """Return True if the event_type is in the registry."""
    return event_type in ALL_EVENTS


def get_all_events() -> list:
    """Return all registered event types."""
    return list(ALL_REGISTERED_EVENTS)


def resolve_source_service(source_service: str) -> ServiceDefinition | None:
    """Resolve an event ``source_service`` string to its ``ServiceDefinition``.

    Accepts the canonical service-registry slug (``"fire"``) and any string in
    :data:`LEGACY_SOURCE_SERVICE_ALIASES` (``"adaptix-fire"``). Returns ``None``
    when the string names no registered service — callers must treat that as
    drift, not as an absent-but-acceptable producer.
    """
    service = SERVICE_BY_SLUG.get(source_service)
    if service is not None:
        return service
    aliased = LEGACY_SOURCE_SERVICE_ALIASES.get(source_service)
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
    "EPCR_CHART_CREATED",
    "EPCR_CHART_FINALIZED",
    "EPCR_CHART_LOCKED",
    "EPCR_CHART_NEMSIS_EXPORT_COMPLETED",
    "EPCR_CHART_NEMSIS_VALIDATION_COMPLETED",
    "EPCR_CHART_SIGNED",
    "EPCR_CHART_UNLOCKED",
    "EPCR_CHART_UPDATED",
    "FIRE_BENCHMARK_TIMELINE_UPDATED",
    "FIRE_INCIDENT_CLOSED",
    "FIRE_INCIDENT_COMPLETED",
    "FIRE_INCIDENT_STATUS_CHANGED",
    "FIRE_INCIDENT_STATUS_UPDATED",
    "FIRE_INVESTIGATION_READINESS_UPDATED",
    "FIRE_UNIT_DISPATCHED",
    "LEGACY_SOURCE_SERVICE_ALIASES",
    "NERIS_AUDIT_EVENT_CREATED",
    "NERIS_NORMALIZATION_COMPLETED",
    "NERIS_SCHEMA_ASSET_REFRESHED",
    "NERIS_VALIDATION_COMPLETED",
    "TRUSTSIGN_DOCUMENT_SIGNED",
    "WORKFORCE_SHIFT_CANCELLED",
    "get_all_events",
    "is_registered",
    "producer_of",
    "resolve_source_service",
]
