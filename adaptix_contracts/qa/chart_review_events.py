"""Lifecycle events of an every-chart review run (producer: Adaptix-QA-Service).

One review run reviews one sealed chart revision with one engine set (see
:mod:`adaptix_contracts.qa.chart_review`). Its lifecycle is announced on the
Core event bus so Billing (pre-bill gate), Notifications, Training and
analytics consumers react to the canonical QA result instead of re-deriving it:

* ``qa.chart_review.requested`` - QA accepted a finalized or amended revision
  for review (a run row exists, state ``queued``).
* ``qa.chart_review.started`` - the run began reading the sealed revision.
* ``qa.chart_review.completed`` - findings and scores are persisted.
* ``qa.chart_review.failed`` - the run could not complete; ``failure_class``
  says why. Never published for a run that is merely waiting to retry.
* ``qa.chart_review.superseded`` - an amendment sealed a newer revision; the
  run's findings describe superseded content.
* ``qa.chart_review.reconciled`` - the reconciliation sweep found a sealed
  revision with no completed run and requeued or classified it.

The payload carries identifiers and counts only. Findings, evidence and
messages stay in QA and are read through its API under its authorization.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

from adaptix_contracts.events.envelope import AdaptixEventEnvelope
from adaptix_contracts.qa.chart_review import ReviewRunState
from adaptix_contracts.qa.enums import FindingSeverity

QA_SERVICE_SLUG: Final[str] = "qa"
"""Service registry slug of Adaptix-QA-Service, the producer of these events."""

QA_CHART_REVIEW_SCHEMA_VERSION: Final[str] = "1.0"

QA_CHART_REVIEW_REQUESTED: Final[str] = "qa.chart_review.requested"
QA_CHART_REVIEW_STARTED: Final[str] = "qa.chart_review.started"
QA_CHART_REVIEW_COMPLETED: Final[str] = "qa.chart_review.completed"
QA_CHART_REVIEW_FAILED: Final[str] = "qa.chart_review.failed"
QA_CHART_REVIEW_SUPERSEDED: Final[str] = "qa.chart_review.superseded"
QA_CHART_REVIEW_RECONCILED: Final[str] = "qa.chart_review.reconciled"

QA_CHART_REVIEW_EVENTS: Final[frozenset[str]] = frozenset(
    {
        QA_CHART_REVIEW_REQUESTED,
        QA_CHART_REVIEW_STARTED,
        QA_CHART_REVIEW_COMPLETED,
        QA_CHART_REVIEW_FAILED,
        QA_CHART_REVIEW_SUPERSEDED,
        QA_CHART_REVIEW_RECONCILED,
    }
)

#: The run state each lifecycle event announces. ``reconciled`` is not a run
#: state: it reports a sweep action on a revision, and its payload carries the
#: state the run was left in.
_STATE_FOR_EVENT: Final[dict[str, ReviewRunState | None]] = {
    QA_CHART_REVIEW_REQUESTED: ReviewRunState.QUEUED,
    QA_CHART_REVIEW_STARTED: ReviewRunState.RUNNING,
    QA_CHART_REVIEW_COMPLETED: ReviewRunState.COMPLETED,
    QA_CHART_REVIEW_FAILED: ReviewRunState.FAILED,
    QA_CHART_REVIEW_SUPERSEDED: ReviewRunState.SUPERSEDED,
    QA_CHART_REVIEW_RECONCILED: None,
}


class QaChartReviewLifecyclePayload(BaseModel):
    """Payload of every ``qa.chart_review.*`` event."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default=QA_CHART_REVIEW_SCHEMA_VERSION)
    tenant_id: str = Field(..., min_length=1, max_length=64)
    review_run_id: str = Field(..., min_length=1, max_length=64)
    chart_id: str = Field(..., min_length=1, max_length=64)
    signed_version_id: str = Field(..., min_length=1, max_length=64)
    review_engine_version: str = Field(..., min_length=1, max_length=64)
    state: ReviewRunState
    finding_counts: dict[FindingSeverity, int] = Field(
        default_factory=dict[FindingSeverity, int]
    )
    blocking_finding_count: int = Field(default=0, ge=0)
    failure_class: str | None = Field(default=None, max_length=64)
    superseded_by_run_id: str | None = Field(default=None, max_length=64)
    correlation_id: str | None = Field(default=None, max_length=128)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _state_details_agree(self) -> QaChartReviewLifecyclePayload:
        if any(count < 0 for count in self.finding_counts.values()):
            raise ValueError("finding counts cannot be negative")
        if self.state is ReviewRunState.FAILED and not self.failure_class:
            raise ValueError("a failed review must name its failure_class")
        if self.state is not ReviewRunState.FAILED and self.failure_class:
            raise ValueError("only a failed review carries a failure_class")
        if self.state is not ReviewRunState.COMPLETED and (
            self.finding_counts or self.blocking_finding_count
        ):
            raise ValueError("only a completed review reports finding counts")
        return self


def build_qa_chart_review_event(
    event_type: str,
    payload: QaChartReviewLifecyclePayload,
    *,
    actor_id: str | None = None,
    causation_id: str | None = None,
) -> AdaptixEventEnvelope:
    """Wrap ``payload`` in the platform envelope for ``event_type``.

    Refuses an event type outside :data:`QA_CHART_REVIEW_EVENTS` and a payload
    whose ``state`` contradicts the event (a ``completed`` event announcing a
    ``failed`` run). ``reconciled`` accepts any state: it reports what the
    sweep left the run in.
    """
    if event_type not in QA_CHART_REVIEW_EVENTS:
        raise ValueError(f"not a chart-review lifecycle event: {event_type}")
    expected = _STATE_FOR_EVENT[event_type]
    if expected is not None and payload.state is not expected:
        raise ValueError(
            f"{event_type} announces state {expected.value}, not {payload.state.value}"
        )
    return AdaptixEventEnvelope.create(
        event_type=event_type,
        tenant_id=payload.tenant_id,
        source_service=QA_SERVICE_SLUG,
        payload=payload.model_dump(mode="json"),
        actor_id=actor_id,
        correlation_id=payload.correlation_id,
        causation_id=causation_id,
    )


__all__ = [
    "QA_CHART_REVIEW_COMPLETED",
    "QA_CHART_REVIEW_EVENTS",
    "QA_CHART_REVIEW_FAILED",
    "QA_CHART_REVIEW_RECONCILED",
    "QA_CHART_REVIEW_REQUESTED",
    "QA_CHART_REVIEW_SCHEMA_VERSION",
    "QA_CHART_REVIEW_STARTED",
    "QA_CHART_REVIEW_SUPERSEDED",
    "QA_SERVICE_SLUG",
    "QaChartReviewLifecyclePayload",
    "build_qa_chart_review_event",
]
