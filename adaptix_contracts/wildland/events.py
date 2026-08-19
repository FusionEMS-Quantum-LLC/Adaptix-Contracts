"""Signal Bus event contracts for the Adaptix Wildland federal sync service.

Three things live in this module:

* the canonical event-type STRINGS a Wildland producer stamps on the
  :class:`adaptix_contracts.events.envelope.AdaptixEventEnvelope`
  (``WILDLAND_ASSIGNMENT_CREATED`` and friends, plus the
  :data:`WILDLAND_EVENTS` set);
* the typed Pydantic PAYLOAD contracts a consumer can validate the
  envelope's ``payload`` dict against (``WildlandAssignmentCreatedEvent``
  and friends); and
* ``build_*`` factory functions that assemble a fully-formed
  :class:`~adaptix_contracts.events.envelope.AdaptixEventEnvelope` from a
  domain record, so a producer never hand-builds the envelope dict.

Registration in the central ``adaptix_contracts.events.registry``
allow-list is intentionally NOT done here. That registry requires a live
producer file:line citation (see
``tests/test_event_producer_registry_drift.py``); Play P10's
Wildland-Service does not yet publish these events in production, so
registering them centrally would either fail the drift guard or need a
fabricated citation. When the live Wildland producer lands, its shipping
session must add the citations and the ``WILDLAND_SERVICE`` slug to
``adaptix_contracts.schemas.service_registry`` in the same change.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from pydantic import BaseModel

from adaptix_contracts.events.envelope import AdaptixEventEnvelope
from adaptix_contracts.wildland.enums import WfdssPhase
from adaptix_contracts.wildland.models import (
    IrocResourceOrder,
    WfdssDecision,
    WildlandAssignment,
    WildlandDeployment,
)

WILDLAND_SOURCE_SERVICE: Final[str] = "wildland-service"

WILDLAND_ASSIGNMENT_CREATED: Final[str] = "wildland.assignment.created"
WILDLAND_DEPLOYMENT_REPORTED: Final[str] = "wildland.deployment.reported"
WILDLAND_IROC_ORDER_SYNCED: Final[str] = "wildland.iroc.order.synced"
WILDLAND_WFDSS_DECISION_SYNCED: Final[str] = "wildland.wfdss.decision.synced"
WILDLAND_ICS209_SUBMITTED: Final[str] = "wildland.ics209.submitted"

WILDLAND_EVENTS: Final[frozenset[str]] = frozenset(
    {
        WILDLAND_ASSIGNMENT_CREATED,
        WILDLAND_DEPLOYMENT_REPORTED,
        WILDLAND_IROC_ORDER_SYNCED,
        WILDLAND_WFDSS_DECISION_SYNCED,
        WILDLAND_ICS209_SUBMITTED,
    }
)


class _WildlandEventBase(BaseModel):
    """Base shape shared by every Wildland event payload.

    Carries ``tenant_id`` / ``correlation_id`` / ``occurred_at`` on the
    typed payload itself (in addition to the envelope carrying the same
    fields) so a consumer that only has the ``payload`` dict — for
    example after deserializing ``envelope.payload`` in isolation — can
    still validate a self-contained record. ``event_type`` is a literal
    on each subclass so the string a producer stamps and the contract a
    consumer validates against live in one place.
    """

    tenant_id: str
    correlation_id: str
    occurred_at: datetime


class WildlandAssignmentCreatedEvent(_WildlandEventBase):
    """Payload for :data:`WILDLAND_ASSIGNMENT_CREATED`.

    Carries the full :class:`WildlandAssignment` snapshot so downstream
    consumers (fleet, workforce, billing) do not have to make a
    follow-up read against Wildland-Service just to render the new
    assignment.
    """

    event_type: str = WILDLAND_ASSIGNMENT_CREATED
    assignment: WildlandAssignment


class WildlandDeploymentReportedEvent(_WildlandEventBase):
    """Payload for :data:`WILDLAND_DEPLOYMENT_REPORTED`.

    Emitted per report, not on a fixed cadence — the Wildland worker
    filters steady-state position noise and only emits on a meaningful
    relocation or staging change.
    """

    event_type: str = WILDLAND_DEPLOYMENT_REPORTED
    deployment: WildlandDeployment


class WildlandIrocOrderSyncedEvent(_WildlandEventBase):
    """Payload for :data:`WILDLAND_IROC_ORDER_SYNCED`.

    Carries the full :class:`IrocResourceOrder` at the point of sync so a
    consumer scoped to order fill-rate does not need a follow-up read.
    """

    event_type: str = WILDLAND_IROC_ORDER_SYNCED
    order: IrocResourceOrder


class WildlandWfdssDecisionSyncedEvent(_WildlandEventBase):
    """Payload for :data:`WILDLAND_WFDSS_DECISION_SYNCED`."""

    event_type: str = WILDLAND_WFDSS_DECISION_SYNCED
    decision: WfdssDecision
    previous_phase: WfdssPhase | None = None


class WildlandIcs209SubmittedEvent(_WildlandEventBase):
    """Payload for :data:`WILDLAND_ICS209_SUBMITTED`.

    ``report_id`` and ``report_number`` are surfaced directly (not just
    nested under a full report payload) so consumers that only track
    submission cadence can filter cheaply without fetching the entire
    :class:`~adaptix_contracts.wildland.models.Ics209Report`.
    """

    event_type: str = WILDLAND_ICS209_SUBMITTED
    report_id: str
    irwin_incident_id: str | None = None
    incident_name: str
    report_number: int


def build_wildland_assignment_created(
    assignment: WildlandAssignment,
    *,
    occurred_at: datetime,
    actor_id: str | None = None,
    causation_id: str | None = None,
) -> AdaptixEventEnvelope:
    """Build the :data:`WILDLAND_ASSIGNMENT_CREATED` Signal Bus envelope."""

    event = WildlandAssignmentCreatedEvent(
        tenant_id=assignment.tenant_id,
        correlation_id=assignment.correlation_id,
        occurred_at=occurred_at,
        assignment=assignment,
    )
    return AdaptixEventEnvelope.create(
        event_type=WILDLAND_ASSIGNMENT_CREATED,
        tenant_id=assignment.tenant_id,
        source_service=WILDLAND_SOURCE_SERVICE,
        payload=event.model_dump(mode="json"),
        actor_id=actor_id,
        correlation_id=assignment.correlation_id,
        causation_id=causation_id,
    )


def build_wildland_deployment_reported(
    deployment: WildlandDeployment,
    *,
    occurred_at: datetime,
    actor_id: str | None = None,
    causation_id: str | None = None,
) -> AdaptixEventEnvelope:
    """Build the :data:`WILDLAND_DEPLOYMENT_REPORTED` Signal Bus envelope."""

    event = WildlandDeploymentReportedEvent(
        tenant_id=deployment.tenant_id,
        correlation_id=deployment.correlation_id,
        occurred_at=occurred_at,
        deployment=deployment,
    )
    return AdaptixEventEnvelope.create(
        event_type=WILDLAND_DEPLOYMENT_REPORTED,
        tenant_id=deployment.tenant_id,
        source_service=WILDLAND_SOURCE_SERVICE,
        payload=event.model_dump(mode="json"),
        actor_id=actor_id,
        correlation_id=deployment.correlation_id,
        causation_id=causation_id,
    )


def build_wildland_iroc_order_synced(
    order: IrocResourceOrder,
    *,
    occurred_at: datetime,
    actor_id: str | None = None,
    causation_id: str | None = None,
) -> AdaptixEventEnvelope:
    """Build the :data:`WILDLAND_IROC_ORDER_SYNCED` Signal Bus envelope."""

    event = WildlandIrocOrderSyncedEvent(
        tenant_id=order.tenant_id,
        correlation_id=order.correlation_id,
        occurred_at=occurred_at,
        order=order,
    )
    return AdaptixEventEnvelope.create(
        event_type=WILDLAND_IROC_ORDER_SYNCED,
        tenant_id=order.tenant_id,
        source_service=WILDLAND_SOURCE_SERVICE,
        payload=event.model_dump(mode="json"),
        actor_id=actor_id,
        correlation_id=order.correlation_id,
        causation_id=causation_id,
    )


def build_wildland_wfdss_decision_synced(
    decision: WfdssDecision,
    *,
    occurred_at: datetime,
    previous_phase: WfdssPhase | None = None,
    actor_id: str | None = None,
    causation_id: str | None = None,
) -> AdaptixEventEnvelope:
    """Build the :data:`WILDLAND_WFDSS_DECISION_SYNCED` Signal Bus envelope."""

    event = WildlandWfdssDecisionSyncedEvent(
        tenant_id=decision.tenant_id,
        correlation_id=decision.correlation_id,
        occurred_at=occurred_at,
        decision=decision,
        previous_phase=previous_phase,
    )
    return AdaptixEventEnvelope.create(
        event_type=WILDLAND_WFDSS_DECISION_SYNCED,
        tenant_id=decision.tenant_id,
        source_service=WILDLAND_SOURCE_SERVICE,
        payload=event.model_dump(mode="json"),
        actor_id=actor_id,
        correlation_id=decision.correlation_id,
        causation_id=causation_id,
    )


def build_wildland_ics209_submitted(
    *,
    tenant_id: str,
    correlation_id: str,
    occurred_at: datetime,
    report_id: str,
    incident_name: str,
    report_number: int,
    irwin_incident_id: str | None = None,
    actor_id: str | None = None,
    causation_id: str | None = None,
) -> AdaptixEventEnvelope:
    """Build the :data:`WILDLAND_ICS209_SUBMITTED` Signal Bus envelope.

    Takes discrete fields rather than a full
    :class:`~adaptix_contracts.wildland.models.Ics209Report` because a
    submission notification should not force the caller to assemble the
    entire report model just to announce it was filed.
    """

    event = WildlandIcs209SubmittedEvent(
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        occurred_at=occurred_at,
        report_id=report_id,
        irwin_incident_id=irwin_incident_id,
        incident_name=incident_name,
        report_number=report_number,
    )
    return AdaptixEventEnvelope.create(
        event_type=WILDLAND_ICS209_SUBMITTED,
        tenant_id=tenant_id,
        source_service=WILDLAND_SOURCE_SERVICE,
        payload=event.model_dump(mode="json"),
        actor_id=actor_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
    )


__all__ = [
    "WILDLAND_ASSIGNMENT_CREATED",
    "WILDLAND_DEPLOYMENT_REPORTED",
    "WILDLAND_EVENTS",
    "WILDLAND_ICS209_SUBMITTED",
    "WILDLAND_IROC_ORDER_SYNCED",
    "WILDLAND_SOURCE_SERVICE",
    "WILDLAND_WFDSS_DECISION_SYNCED",
    "WildlandAssignmentCreatedEvent",
    "WildlandDeploymentReportedEvent",
    "WildlandIcs209SubmittedEvent",
    "WildlandIrocOrderSyncedEvent",
    "WildlandWfdssDecisionSyncedEvent",
    "build_wildland_assignment_created",
    "build_wildland_deployment_reported",
    "build_wildland_ics209_submitted",
    "build_wildland_iroc_order_synced",
    "build_wildland_wfdss_decision_synced",
]
