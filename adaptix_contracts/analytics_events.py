"""Authoritative catalog of Analytics KPI source-event types + payload contracts.

The Analytics Service aggregates ``analytics_kpi_source_events`` rows into
KPI snapshots. Every producer domain service publishes into that store via
``POST /api/v1/analytics/events``. This module is the single source of truth
for BOTH sides of the contract:

* the exact string every producer sends as ``event_type``
* the exact payload shape (field name + type) the KPI engine reads

The Analytics repo pins these constants; keep it and this file in step. A
producer that constructs a string literal itself is a defect — import from
here so a rename or a typo fails at import time, never silently at runtime
as ``data_status="unknown"`` on a live dashboard.

Payload contracts mirror ``Adaptix-Analytics-Service/backend/analytics_app/
kpi_definitions.py`` (the definition text names the exact field the
aggregator reads). ``rate``-style KPIs read a categorical field; the
truthy value that counts toward the numerator is annotated here so
producers cannot drift the vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# ---------------------------------------------------------------------------
# Event-type constants — one per KPI source_event_type in the Analytics catalog
# ---------------------------------------------------------------------------

# EMS / ePCR
EMS_RESPONSE_TIME: Final[str] = "ems.response_time"
EMS_SCENE_TIME: Final[str] = "ems.scene_time"
EMS_TRANSPORT_TIME: Final[str] = "ems.transport_time"
EMS_CLOSE_TO_CLOSE: Final[str] = "ems.close_to_close"
EMS_PROTOCOL_OUTCOME: Final[str] = "ems.protocol_outcome"
EPCR_CHART_COMPLETION: Final[str] = "epcr.chart_completion"

# Fire / NERIS
FIRE_TURNOUT_TIME: Final[str] = "fire.turnout_time"
FIRE_FIRST_UNIT_ON_SCENE: Final[str] = "fire.first_unit_on_scene"
FIRE_ERF_TIME: Final[str] = "fire.erf_time"
FIRE_FIRE_LOSS: Final[str] = "fire.fire_loss"
NERIS_SUBMISSION_OUTCOME: Final[str] = "neris.submission_outcome"

# Law enforcement (dispatched from CAD)
LAW_DISPATCH_TO_ARREST: Final[str] = "law.dispatch_to_arrest"
LAW_CASE_OUTCOME: Final[str] = "law.case_outcome"

# CAD
CAD_CALL_PROCESSING_TIME: Final[str] = "cad.call_processing_time"
CAD_QUEUE_TIME: Final[str] = "cad.queue_time"

# Billing
BILLING_CLAIM_OUTCOME: Final[str] = "billing.claim_outcome"
BILLING_CLAIM_SUBMISSION: Final[str] = "billing.claim_submission"
BILLING_AR_DAYS: Final[str] = "billing.ar_days"
BILLING_REIMBURSEMENT: Final[str] = "billing.reimbursement"

# Transport
TRANSPORT_TURNAROUND: Final[str] = "transport.turnaround"
TRANSPORT_PICKUP_OUTCOME: Final[str] = "transport.pickup_outcome"

# Air
AIR_MISSION_REQUEST: Final[str] = "air.mission_request"
AIR_LIFTOFF_TIME: Final[str] = "air.liftoff_time"

# Workforce / Labor (shared event stream w/ report_builders)
LABOR_OVERTIME: Final[str] = "labor.overtime"
LABOR_CALLBACK: Final[str] = "labor.callback"
LABOR_TRAINING_ATTENDANCE: Final[str] = "labor.training_attendance"
LABOR_CERTIFICATION: Final[str] = "labor.certification"

# Fleet
FLEET_UNIT_STATUS_CHECK: Final[str] = "fleet.unit_status_check"
FLEET_DOWNTIME: Final[str] = "fleet.downtime"

# Inventory
INVENTORY_PAR_CHECK: Final[str] = "inventory.par_check"
INVENTORY_EXPIRY_CHECK: Final[str] = "inventory.expiry_check"

# Compliance
COMPLIANCE_AUDIT_OUTCOME: Final[str] = "compliance.audit_outcome"


# ---------------------------------------------------------------------------
# Payload contracts — the exact fields the aggregator reads for each event
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EventPayloadContract:
    """Names the field(s) the KPI engine reads from an event's payload.

    ``value_field`` is the numeric (or categorical, for rate KPIs) field.
    ``rate_truthy`` is set only for rate KPIs — the exact value that counts
    toward the numerator. Everything else is illustrative context: producers
    MAY include extra fields, but the KPI engine only reads ``value_field``.
    """

    event_type: str
    value_field: str
    unit: str
    rate_truthy: str | None = None


PAYLOAD_CONTRACTS: Final[dict[str, EventPayloadContract]] = {
    EMS_RESPONSE_TIME: EventPayloadContract(EMS_RESPONSE_TIME, "minutes", "minutes"),
    EMS_SCENE_TIME: EventPayloadContract(EMS_SCENE_TIME, "minutes", "minutes"),
    EMS_TRANSPORT_TIME: EventPayloadContract(EMS_TRANSPORT_TIME, "minutes", "minutes"),
    EMS_CLOSE_TO_CLOSE: EventPayloadContract(EMS_CLOSE_TO_CLOSE, "minutes", "minutes"),
    EMS_PROTOCOL_OUTCOME: EventPayloadContract(
        EMS_PROTOCOL_OUTCOME, "outcome", "category", "compliant"
    ),
    EPCR_CHART_COMPLETION: EventPayloadContract(
        EPCR_CHART_COMPLETION, "hours", "hours"
    ),
    FIRE_TURNOUT_TIME: EventPayloadContract(FIRE_TURNOUT_TIME, "seconds", "seconds"),
    FIRE_FIRST_UNIT_ON_SCENE: EventPayloadContract(
        FIRE_FIRST_UNIT_ON_SCENE, "minutes", "minutes"
    ),
    FIRE_ERF_TIME: EventPayloadContract(FIRE_ERF_TIME, "minutes", "minutes"),
    FIRE_FIRE_LOSS: EventPayloadContract(FIRE_FIRE_LOSS, "usd", "USD"),
    NERIS_SUBMISSION_OUTCOME: EventPayloadContract(
        NERIS_SUBMISSION_OUTCOME, "outcome", "category", "accepted"
    ),
    LAW_DISPATCH_TO_ARREST: EventPayloadContract(
        LAW_DISPATCH_TO_ARREST, "minutes", "minutes"
    ),
    LAW_CASE_OUTCOME: EventPayloadContract(
        LAW_CASE_OUTCOME, "outcome", "category", "cleared"
    ),
    CAD_CALL_PROCESSING_TIME: EventPayloadContract(
        CAD_CALL_PROCESSING_TIME, "seconds", "seconds"
    ),
    CAD_QUEUE_TIME: EventPayloadContract(CAD_QUEUE_TIME, "seconds", "seconds"),
    BILLING_CLAIM_OUTCOME: EventPayloadContract(
        BILLING_CLAIM_OUTCOME, "outcome", "category", "denied"
    ),
    BILLING_CLAIM_SUBMISSION: EventPayloadContract(
        BILLING_CLAIM_SUBMISSION, "outcome", "category", "accepted_first_pass"
    ),
    BILLING_AR_DAYS: EventPayloadContract(BILLING_AR_DAYS, "days", "days"),
    BILLING_REIMBURSEMENT: EventPayloadContract(BILLING_REIMBURSEMENT, "usd", "USD"),
    TRANSPORT_TURNAROUND: EventPayloadContract(
        TRANSPORT_TURNAROUND, "minutes", "minutes"
    ),
    TRANSPORT_PICKUP_OUTCOME: EventPayloadContract(
        TRANSPORT_PICKUP_OUTCOME, "outcome", "category", "on_time"
    ),
    AIR_MISSION_REQUEST: EventPayloadContract(
        AIR_MISSION_REQUEST, "outcome", "category", "accepted"
    ),
    AIR_LIFTOFF_TIME: EventPayloadContract(AIR_LIFTOFF_TIME, "minutes", "minutes"),
    LABOR_OVERTIME: EventPayloadContract(LABOR_OVERTIME, "overtime_hours", "hours"),
    LABOR_CALLBACK: EventPayloadContract(LABOR_CALLBACK, "accepted", "boolean", "true"),
    LABOR_TRAINING_ATTENDANCE: EventPayloadContract(
        LABOR_TRAINING_ATTENDANCE, "attended", "boolean", "true"
    ),
    LABOR_CERTIFICATION: EventPayloadContract(
        LABOR_CERTIFICATION, "status", "category", "current"
    ),
    FLEET_UNIT_STATUS_CHECK: EventPayloadContract(
        FLEET_UNIT_STATUS_CHECK, "status", "category", "available"
    ),
    FLEET_DOWNTIME: EventPayloadContract(FLEET_DOWNTIME, "hours", "hours"),
    INVENTORY_PAR_CHECK: EventPayloadContract(
        INVENTORY_PAR_CHECK, "outcome", "category", "compliant"
    ),
    INVENTORY_EXPIRY_CHECK: EventPayloadContract(
        INVENTORY_EXPIRY_CHECK, "outcome", "category", "expired"
    ),
    COMPLIANCE_AUDIT_OUTCOME: EventPayloadContract(
        COMPLIANCE_AUDIT_OUTCOME, "outcome", "category", "pass"
    ),
}


# The complete, ordered list of allowed event types — importers can iterate
# to build validation gates, dashboards, or migration allowlists.
ALL_EVENT_TYPES: Final[tuple[str, ...]] = tuple(PAYLOAD_CONTRACTS)


def payload_contract(event_type: str) -> EventPayloadContract:
    """Return the payload contract for a known event type or raise ``KeyError``."""
    try:
        return PAYLOAD_CONTRACTS[event_type]
    except KeyError as exc:  # pragma: no cover - explicit for callers
        raise KeyError(
            f"Unknown analytics event_type {event_type!r}. Add it to "
            "adaptix_contracts.analytics_events before publishing."
        ) from exc


__all__ = [
    # ------------------------------------------------------------------
    # Event-type constants (grouped by domain)
    # ------------------------------------------------------------------
    "EMS_RESPONSE_TIME",
    "EMS_SCENE_TIME",
    "EMS_TRANSPORT_TIME",
    "EMS_CLOSE_TO_CLOSE",
    "EMS_PROTOCOL_OUTCOME",
    "EPCR_CHART_COMPLETION",
    "FIRE_TURNOUT_TIME",
    "FIRE_FIRST_UNIT_ON_SCENE",
    "FIRE_ERF_TIME",
    "FIRE_FIRE_LOSS",
    "NERIS_SUBMISSION_OUTCOME",
    "LAW_DISPATCH_TO_ARREST",
    "LAW_CASE_OUTCOME",
    "CAD_CALL_PROCESSING_TIME",
    "CAD_QUEUE_TIME",
    "BILLING_CLAIM_OUTCOME",
    "BILLING_CLAIM_SUBMISSION",
    "BILLING_AR_DAYS",
    "BILLING_REIMBURSEMENT",
    "TRANSPORT_TURNAROUND",
    "TRANSPORT_PICKUP_OUTCOME",
    "AIR_MISSION_REQUEST",
    "AIR_LIFTOFF_TIME",
    "LABOR_OVERTIME",
    "LABOR_CALLBACK",
    "LABOR_TRAINING_ATTENDANCE",
    "LABOR_CERTIFICATION",
    "FLEET_UNIT_STATUS_CHECK",
    "FLEET_DOWNTIME",
    "INVENTORY_PAR_CHECK",
    "INVENTORY_EXPIRY_CHECK",
    "COMPLIANCE_AUDIT_OUTCOME",
    # ------------------------------------------------------------------
    # Payload contracts
    # ------------------------------------------------------------------
    "ALL_EVENT_TYPES",
    "EventPayloadContract",
    "PAYLOAD_CONTRACTS",
    "payload_contract",
]
