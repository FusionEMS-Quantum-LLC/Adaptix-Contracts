"""Pydantic v2 models for the Adaptix QA (Chart Review / QI Workbench) service.

Every model on the QA boundary carries ``tenant_id`` and
``correlation_id`` — ``tenant_id`` because chart review is agency-scoped
clinical QA, and ``correlation_id`` so a Signal Bus event, an API call,
and the underlying ePCR chart for the same review can be joined post-hoc.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from adaptix_contracts.qa.enums import FindingSeverity, ReviewOutcome, ReviewerRole


class ReviewChecklist(BaseModel):
    """A named, versioned checklist a chart review is scored against.

    ``items`` is an ordered list of checklist item labels (not a
    dict) so item order is stable for rendering and so two checklists
    with the same items in a different order are distinguishable.
    """

    tenant_id: str
    correlation_id: str

    checklist_id: str
    name: str
    version: str
    items: list[str] = Field(default_factory=list)

    active: bool = True
    created_at: datetime
    updated_at: datetime | None = None

    notes: str | None = None


class ReviewerAssignment(BaseModel):
    """Assignment of a reviewer to a chart review.

    Kept as its own model (rather than a bare field on
    :class:`ChartReview`) because a review can be reassigned, and the
    assignment history — who, in what role, when — is itself part of
    the QA audit trail.
    """

    tenant_id: str
    correlation_id: str

    assignment_id: str
    review_id: str

    reviewer_id: str
    reviewer_role: ReviewerRole

    assigned_at: datetime
    assigned_by: str | None = None
    accepted_at: datetime | None = None
    reassigned_from_assignment_id: str | None = None


class ReviewFinding(BaseModel):
    """A single finding recorded against a chart review.

    ``checklist_item`` names which :class:`ReviewChecklist` item the
    finding relates to; it is a free-text label rather than an index
    so a finding remains meaningful if the checklist is later edited.
    """

    tenant_id: str
    correlation_id: str

    finding_id: str
    review_id: str

    checklist_item: str
    severity: FindingSeverity
    description: str

    reviewer_id: str
    recorded_at: datetime

    requires_followup: bool = False
    followup_notes: str | None = None
    resolved_at: datetime | None = None
    resolved_by: str | None = None

    metadata: dict[str, Any] = Field(default_factory=dict)


class ChartReview(BaseModel):
    """A single QA review of one ePCR chart.

    ``chart_id`` and ``incident_id`` reference the ePCR domain by id
    only — ChartReview does not become a duplicate source of truth for
    the underlying chart; the chart's clinical content stays owned by
    ePCR.
    """

    tenant_id: str
    correlation_id: str

    review_id: str
    chart_id: str
    incident_id: str | None = None

    checklist_id: str
    checklist_version: str

    reviewer_id: str
    reviewer_role: ReviewerRole

    outcome: ReviewOutcome | None = None
    finding_count: int = Field(default=0, ge=0)
    critical_finding_count: int = Field(default=0, ge=0)

    opened_at: datetime
    completed_at: datetime | None = None
    due_at: datetime | None = None

    escalated: bool = False
    escalated_to: str | None = None

    summary: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)


class CqiMetric(BaseModel):
    """A rolled-up continuous quality improvement (CQI) metric snapshot.

    Metrics are period-scoped aggregates (e.g. pass rate for a
    ``dimension`` over ``period_start``..``period_end``), not
    per-review records — a metric is computed from a population of
    :class:`ChartReview` records, never hand-authored per chart.
    """

    tenant_id: str
    correlation_id: str

    metric_id: str
    dimension: str

    period_start: datetime
    period_end: datetime

    reviewed_count: int = Field(default=0, ge=0)
    pass_count: int = Field(default=0, ge=0)
    fail_count: int = Field(default=0, ge=0)
    partial_count: int = Field(default=0, ge=0)
    critical_finding_count: int = Field(default=0, ge=0)

    pass_rate_pct: float | None = Field(default=None, ge=0.0, le=100.0)

    computed_at: datetime
    scope: dict[str, str] = Field(default_factory=dict)


__all__ = [
    "ChartReview",
    "CqiMetric",
    "ReviewChecklist",
    "ReviewFinding",
    "ReviewerAssignment",
]
