"""Adaptix QA (Chart Review / QI Workbench) contracts.

Public surface for the Adaptix QA Service. Nothing in this package runs
QA behaviour — it defines the models, enums, events, and error types
that Adaptix services and clients share when talking about chart
review, review findings, checklists, reviewer assignments, and CQI
(continuous quality improvement) metrics.

Import from the subpackage root, not the leaf modules::

    from adaptix_contracts.qa import ChartReview, QA_REVIEW_COMPLETED
"""

from adaptix_contracts.qa.enums import (
    FindingSeverity,
    ReviewOutcome,
    ReviewerRole,
)
from adaptix_contracts.qa.errors import (
    QaAssignmentError,
    QaChecklistError,
    QaError,
    QaErrorCode,
    QaErrorEnvelope,
    QaFindingError,
    QaMetricError,
    QaReviewNotFoundError,
    QaReviewStateError,
    QaTenantMismatchError,
)
from adaptix_contracts.qa.events import (
    QA_CQI_METRIC_COMPUTED,
    QA_EVENTS,
    QA_FINDING_RECORDED,
    QA_FINDING_RESOLVED,
    QA_REVIEW_ASSIGNED,
    QA_REVIEW_COMPLETED,
    QA_SOURCE_SERVICE,
    QaCqiMetricComputedPayload,
    QaFindingRecordedPayload,
    QaFindingResolvedPayload,
    QaReviewAssignedPayload,
    QaReviewCompletedPayload,
    build_qa_cqi_metric_computed_event,
    build_qa_finding_recorded_event,
    build_qa_finding_resolved_event,
    build_qa_review_assigned_event,
    build_qa_review_completed_event,
)
from adaptix_contracts.qa.models import (
    ChartReview,
    CqiMetric,
    ReviewChecklist,
    ReviewFinding,
    ReviewerAssignment,
)

__all__ = [
    "ChartReview",
    "CqiMetric",
    "FindingSeverity",
    "QA_CQI_METRIC_COMPUTED",
    "QA_EVENTS",
    "QA_FINDING_RECORDED",
    "QA_FINDING_RESOLVED",
    "QA_REVIEW_ASSIGNED",
    "QA_REVIEW_COMPLETED",
    "QA_SOURCE_SERVICE",
    "QaAssignmentError",
    "QaChecklistError",
    "QaCqiMetricComputedPayload",
    "QaError",
    "QaErrorCode",
    "QaErrorEnvelope",
    "QaFindingError",
    "QaFindingRecordedPayload",
    "QaFindingResolvedPayload",
    "QaMetricError",
    "QaReviewAssignedPayload",
    "QaReviewCompletedPayload",
    "QaReviewNotFoundError",
    "QaReviewStateError",
    "QaTenantMismatchError",
    "ReviewChecklist",
    "ReviewFinding",
    "ReviewOutcome",
    "ReviewerAssignment",
    "ReviewerRole",
    "build_qa_cqi_metric_computed_event",
    "build_qa_finding_recorded_event",
    "build_qa_finding_resolved_event",
    "build_qa_review_assigned_event",
    "build_qa_review_completed_event",
]
