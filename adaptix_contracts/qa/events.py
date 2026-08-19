"""Signal Bus event contracts for the Adaptix QA (Chart Review / QI Workbench) service.

Every event rides on :class:`adaptix_contracts.events.envelope.AdaptixEventEnvelope`
so tenant scope, correlation, idempotency, and payload versioning survive
across service boundaries the same way every other Adaptix domain event
does. The typed payload models below sit inside ``envelope.payload`` and
are validated by consumers using :meth:`AdaptixEventEnvelope.create`.

Registration in the central ``adaptix_contracts.events.registry``
allow-list is intentionally NOT done here. That registry requires a live
producer file:line citation (see
``tests/test_event_producer_registry_drift.py``); the QA Service does not
yet publish these events in production, so registering them centrally
would either fail the drift guard or need a fabricated citation. When the
live QA producer lands, its shipping session must add the citations and
the QA service slug to ``adaptix_contracts.schemas.service_registry`` in
the same change.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from adaptix_contracts.events.envelope import AdaptixEventEnvelope
from adaptix_contracts.qa.enums import FindingSeverity, ReviewOutcome, ReviewerRole

# ---------------------------------------------------------------------------
# Event-name string constants (subscribe by these on the Signal Bus)
# ---------------------------------------------------------------------------

QA_REVIEW_ASSIGNED: Final[str] = "qa.review.assigned"
QA_REVIEW_COMPLETED: Final[str] = "qa.review.completed"
QA_FINDING_RECORDED: Final[str] = "qa.finding.recorded"
QA_FINDING_RESOLVED: Final[str] = "qa.finding.resolved"
QA_CQI_METRIC_COMPUTED: Final[str] = "qa.cqi_metric.computed"

QA_EVENTS: Final[frozenset[str]] = frozenset(
    {
        QA_REVIEW_ASSIGNED,
        QA_REVIEW_COMPLETED,
        QA_FINDING_RECORDED,
        QA_FINDING_RESOLVED,
        QA_CQI_METRIC_COMPUTED,
    }
)

QA_SOURCE_SERVICE: Final[str] = "qa"
"""Service registry slug for the QA service that publishes these events."""


# ---------------------------------------------------------------------------
# Typed payload contracts (ride inside AdaptixEventEnvelope.payload)
# ---------------------------------------------------------------------------


class _QaEventPayload(BaseModel):
    """Base for every QA event payload.

    ``tenant_id`` is redundant with :attr:`AdaptixEventEnvelope.tenant_id`
    but is kept on the payload so a consumer that stores raw payloads
    (e.g. Reality projections, analytics warehouse) still has tenant
    scope in a single row without re-joining envelope columns.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    tenant_id: str = Field(..., description="Tenant scope.")
    correlation_id: str | None = Field(
        default=None,
        description="Correlation id for tracing (mirrors envelope.correlation_id).",
    )
    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the domain event occurred (may pre-date publish).",
    )


class QaReviewAssignedPayload(_QaEventPayload):
    """Payload for ``qa.review.assigned``."""

    review_id: str
    chart_id: str
    reviewer_id: str
    reviewer_role: ReviewerRole
    due_at: datetime | None = None


class QaReviewCompletedPayload(_QaEventPayload):
    """Payload for ``qa.review.completed``."""

    review_id: str
    chart_id: str
    reviewer_id: str
    outcome: ReviewOutcome
    finding_count: int = Field(default=0, ge=0)
    critical_finding_count: int = Field(default=0, ge=0)
    completed_at: datetime


class QaFindingRecordedPayload(_QaEventPayload):
    """Payload for ``qa.finding.recorded``."""

    finding_id: str
    review_id: str
    checklist_item: str
    severity: FindingSeverity
    reviewer_id: str
    requires_followup: bool = False


class QaFindingResolvedPayload(_QaEventPayload):
    """Payload for ``qa.finding.resolved``."""

    finding_id: str
    review_id: str
    resolved_by: str
    resolved_at: datetime


class QaCqiMetricComputedPayload(_QaEventPayload):
    """Payload for ``qa.cqi_metric.computed``."""

    metric_id: str
    dimension: str
    period_start: datetime
    period_end: datetime
    reviewed_count: int = Field(default=0, ge=0)
    pass_rate_pct: float | None = Field(default=None, ge=0.0, le=100.0)


# ---------------------------------------------------------------------------
# build_* factories — each returns a ready-to-publish AdaptixEventEnvelope
# ---------------------------------------------------------------------------


def build_qa_review_assigned_event(
    *,
    tenant_id: str,
    review_id: str,
    chart_id: str,
    reviewer_id: str,
    reviewer_role: ReviewerRole,
    due_at: datetime | None = None,
    actor_id: str | None = None,
    correlation_id: str | None = None,
    causation_id: str | None = None,
) -> AdaptixEventEnvelope:
    """Build an ``AdaptixEventEnvelope`` for ``qa.review.assigned``."""

    payload = QaReviewAssignedPayload(
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        review_id=review_id,
        chart_id=chart_id,
        reviewer_id=reviewer_id,
        reviewer_role=reviewer_role,
        due_at=due_at,
    )
    return AdaptixEventEnvelope.create(
        event_type=QA_REVIEW_ASSIGNED,
        tenant_id=tenant_id,
        source_service=QA_SOURCE_SERVICE,
        payload=payload.model_dump(mode="json"),
        actor_id=actor_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
    )


def build_qa_review_completed_event(
    *,
    tenant_id: str,
    review_id: str,
    chart_id: str,
    reviewer_id: str,
    outcome: ReviewOutcome,
    completed_at: datetime,
    finding_count: int = 0,
    critical_finding_count: int = 0,
    actor_id: str | None = None,
    correlation_id: str | None = None,
    causation_id: str | None = None,
) -> AdaptixEventEnvelope:
    """Build an ``AdaptixEventEnvelope`` for ``qa.review.completed``."""

    payload = QaReviewCompletedPayload(
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        review_id=review_id,
        chart_id=chart_id,
        reviewer_id=reviewer_id,
        outcome=outcome,
        finding_count=finding_count,
        critical_finding_count=critical_finding_count,
        completed_at=completed_at,
    )
    return AdaptixEventEnvelope.create(
        event_type=QA_REVIEW_COMPLETED,
        tenant_id=tenant_id,
        source_service=QA_SOURCE_SERVICE,
        payload=payload.model_dump(mode="json"),
        actor_id=actor_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
    )


def build_qa_finding_recorded_event(
    *,
    tenant_id: str,
    finding_id: str,
    review_id: str,
    checklist_item: str,
    severity: FindingSeverity,
    reviewer_id: str,
    requires_followup: bool = False,
    actor_id: str | None = None,
    correlation_id: str | None = None,
    causation_id: str | None = None,
) -> AdaptixEventEnvelope:
    """Build an ``AdaptixEventEnvelope`` for ``qa.finding.recorded``."""

    payload = QaFindingRecordedPayload(
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        finding_id=finding_id,
        review_id=review_id,
        checklist_item=checklist_item,
        severity=severity,
        reviewer_id=reviewer_id,
        requires_followup=requires_followup,
    )
    return AdaptixEventEnvelope.create(
        event_type=QA_FINDING_RECORDED,
        tenant_id=tenant_id,
        source_service=QA_SOURCE_SERVICE,
        payload=payload.model_dump(mode="json"),
        actor_id=actor_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
    )


def build_qa_finding_resolved_event(
    *,
    tenant_id: str,
    finding_id: str,
    review_id: str,
    resolved_by: str,
    resolved_at: datetime,
    actor_id: str | None = None,
    correlation_id: str | None = None,
    causation_id: str | None = None,
) -> AdaptixEventEnvelope:
    """Build an ``AdaptixEventEnvelope`` for ``qa.finding.resolved``."""

    payload = QaFindingResolvedPayload(
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        finding_id=finding_id,
        review_id=review_id,
        resolved_by=resolved_by,
        resolved_at=resolved_at,
    )
    return AdaptixEventEnvelope.create(
        event_type=QA_FINDING_RESOLVED,
        tenant_id=tenant_id,
        source_service=QA_SOURCE_SERVICE,
        payload=payload.model_dump(mode="json"),
        actor_id=actor_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
    )


def build_qa_cqi_metric_computed_event(
    *,
    tenant_id: str,
    metric_id: str,
    dimension: str,
    period_start: datetime,
    period_end: datetime,
    reviewed_count: int = 0,
    pass_rate_pct: float | None = None,
    actor_id: str | None = None,
    correlation_id: str | None = None,
    causation_id: str | None = None,
) -> AdaptixEventEnvelope:
    """Build an ``AdaptixEventEnvelope`` for ``qa.cqi_metric.computed``."""

    payload = QaCqiMetricComputedPayload(
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        metric_id=metric_id,
        dimension=dimension,
        period_start=period_start,
        period_end=period_end,
        reviewed_count=reviewed_count,
        pass_rate_pct=pass_rate_pct,
    )
    return AdaptixEventEnvelope.create(
        event_type=QA_CQI_METRIC_COMPUTED,
        tenant_id=tenant_id,
        source_service=QA_SOURCE_SERVICE,
        payload=payload.model_dump(mode="json"),
        actor_id=actor_id,
        correlation_id=correlation_id,
        causation_id=causation_id,
    )


__all__ = [
    "QA_CQI_METRIC_COMPUTED",
    "QA_EVENTS",
    "QA_FINDING_RECORDED",
    "QA_FINDING_RESOLVED",
    "QA_REVIEW_ASSIGNED",
    "QA_REVIEW_COMPLETED",
    "QA_SOURCE_SERVICE",
    "QaCqiMetricComputedPayload",
    "QaFindingRecordedPayload",
    "QaFindingResolvedPayload",
    "QaReviewAssignedPayload",
    "QaReviewCompletedPayload",
    "build_qa_cqi_metric_computed_event",
    "build_qa_finding_recorded_event",
    "build_qa_finding_resolved_event",
    "build_qa_review_assigned_event",
    "build_qa_review_completed_event",
]
