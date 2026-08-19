"""Service-specific error types for the Adaptix QA (Chart Review / QI Workbench) service.

Two layers are provided so callers can pick the right primitive:

* :class:`QaError` and its subclasses are Python exceptions raised
  inside the QA service and its clients; they carry structured
  context (``review_id``, ``finding_id``, etc.) and know how to render
  themselves into the shared Adaptix HTTP error envelope.
* :class:`QaErrorEnvelope` extends
  :class:`~adaptix_contracts.errors.envelope.AdaptixErrorEnvelope` so
  the wire format is exactly the platform envelope — the ``error_code``
  field is widened to accept :class:`QaErrorCode`, and QA-specific
  factory classmethods produce well-typed envelopes without callers
  hand-building the dict.

Nothing here catches or silences errors — it only names them. Callers
still decide when to raise, when to convert to an envelope, and when to
propagate to the operational backbone.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field

from adaptix_contracts.errors.envelope import (
    AdaptixErrorCode,
    AdaptixErrorEnvelope,
    AdaptixTraceContext,
)


class QaErrorCode(str, Enum):
    """QA-specific error codes.

    Kept distinct from :class:`AdaptixErrorCode` (rather than trying to
    extend it — Python does not allow enum extension in a way that keeps
    ``isinstance`` sensible) and merged at the envelope boundary through
    :class:`QaErrorEnvelope.error_code`. When a QA-specific code truly
    overlaps a platform-wide one, prefer the platform code and do not
    add a duplicate here.
    """

    QA_REVIEW_NOT_FOUND = "qa.review.not_found"
    QA_REVIEW_ALREADY_COMPLETED = "qa.review.already_completed"
    QA_REVIEW_NOT_ASSIGNED = "qa.review.not_assigned"
    QA_REVIEW_LOCKED = "qa.review.locked"

    QA_CHECKLIST_NOT_FOUND = "qa.checklist.not_found"
    QA_CHECKLIST_INACTIVE = "qa.checklist.inactive"
    QA_CHECKLIST_VERSION_MISMATCH = "qa.checklist.version_mismatch"

    QA_FINDING_NOT_FOUND = "qa.finding.not_found"
    QA_FINDING_ALREADY_RESOLVED = "qa.finding.already_resolved"

    QA_ASSIGNMENT_NOT_FOUND = "qa.assignment.not_found"
    QA_ASSIGNMENT_ROLE_INSUFFICIENT = "qa.assignment.role_insufficient"

    QA_METRIC_PERIOD_INVALID = "qa.metric.period_invalid"
    QA_METRIC_COMPUTE_FAILED = "qa.metric.compute_failed"

    QA_TENANT_MISMATCH = "qa.tenant.mismatch"


class QaError(Exception):
    """Base exception for the QA service.

    Subclasses set :attr:`code` to a :class:`QaErrorCode`; callers catch
    :class:`QaError` when they want to handle any QA fault generically,
    or a specific subclass when they can act on it.

    :meth:`to_envelope` renders the exception into the shared HTTP error
    envelope; nothing in the exception itself decides HTTP status.
    """

    code: QaErrorCode = QaErrorCode.QA_REVIEW_NOT_FOUND

    def __init__(
        self,
        message: str,
        *,
        code: QaErrorCode | None = None,
        tenant_id: str | None = None,
        review_id: str | None = None,
        finding_id: str | None = None,
        checklist_id: str | None = None,
        detail: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code
        self.message = message
        self.detail = detail
        self.tenant_id = tenant_id
        self.review_id = review_id
        self.finding_id = finding_id
        self.checklist_id = checklist_id
        self.context: dict[str, Any] = dict(context or {})

    def to_envelope(
        self,
        *,
        trace: AdaptixTraceContext | None = None,
    ) -> "QaErrorEnvelope":
        """Render this exception as a :class:`QaErrorEnvelope`.

        No stack trace or raw exception text is emitted — only the
        structured fields the caller supplied when constructing the
        exception.
        """

        effective_trace = trace
        if effective_trace is None and self.tenant_id is not None:
            effective_trace = AdaptixTraceContext(tenant_id=self.tenant_id)

        return QaErrorEnvelope(
            error_code=self.code,
            message=self.message,
            detail=self.detail,
            trace=effective_trace,
            qa_context=self._qa_context(),
        )

    def _qa_context(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.tenant_id is not None:
            payload["tenant_id"] = self.tenant_id
        if self.review_id is not None:
            payload["review_id"] = self.review_id
        if self.finding_id is not None:
            payload["finding_id"] = self.finding_id
        if self.checklist_id is not None:
            payload["checklist_id"] = self.checklist_id
        payload.update(self.context)
        return payload


class QaReviewNotFoundError(QaError):
    """Raised when a chart review id does not resolve for the caller's tenant."""

    code = QaErrorCode.QA_REVIEW_NOT_FOUND


class QaReviewStateError(QaError):
    """Raised when a chart review is not in a state that permits the operation.

    ``code`` is left assignable by the caller (already completed /
    locked / not assigned) — the state is fault-specific.
    """

    code = QaErrorCode.QA_REVIEW_LOCKED


class QaChecklistError(QaError):
    """Raised for checklist lookup, activation, or version-mismatch faults."""

    code = QaErrorCode.QA_CHECKLIST_NOT_FOUND


class QaFindingError(QaError):
    """Raised when a review finding cannot be recorded, looked up, or resolved."""

    code = QaErrorCode.QA_FINDING_NOT_FOUND


class QaAssignmentError(QaError):
    """Raised when a reviewer assignment cannot proceed as requested."""

    code = QaErrorCode.QA_ASSIGNMENT_NOT_FOUND


class QaMetricError(QaError):
    """Raised when a CQI metric computation cannot proceed as requested."""

    code = QaErrorCode.QA_METRIC_COMPUTE_FAILED


class QaTenantMismatchError(QaError):
    """Raised when a caller's tenant does not match the target QA record.

    Distinct from the ``*_not_found`` errors because a mismatch is a
    tenancy fault (the caller has an authenticated identity in another
    tenant) whereas ``not found`` covers unknown-id lookups within the
    caller's own tenant. Callers MUST NOT downgrade this to a 404 — the
    distinction is required for cross-tenant audit.
    """

    code = QaErrorCode.QA_TENANT_MISMATCH


class QaErrorEnvelope(AdaptixErrorEnvelope):
    """Adaptix HTTP error envelope widened for QA-specific codes.

    Overrides only ``error_code`` (widened to accept
    :class:`QaErrorCode`) and adds ``qa_context`` for structured
    QA-scoped fields (``review_id``, ``finding_id`` …). The envelope
    shape, timestamp field, trace context, and inherited factory
    classmethods behave exactly as on
    :class:`~adaptix_contracts.errors.envelope.AdaptixErrorEnvelope`.
    """

    error_code: QaErrorCode | AdaptixErrorCode
    qa_context: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def review_not_found(
        cls,
        review_id: str,
        *,
        tenant_id: str | None = None,
        trace: AdaptixTraceContext | None = None,
    ) -> "QaErrorEnvelope":
        return cls(
            error_code=QaErrorCode.QA_REVIEW_NOT_FOUND,
            message=f"Chart review not found: {review_id}",
            trace=trace,
            qa_context={
                k: v
                for k, v in {"review_id": review_id, "tenant_id": tenant_id}.items()
                if v is not None
            },
        )

    @classmethod
    def review_already_completed(
        cls,
        review_id: str,
        *,
        detail: str | None = None,
        trace: AdaptixTraceContext | None = None,
    ) -> "QaErrorEnvelope":
        return cls(
            error_code=QaErrorCode.QA_REVIEW_ALREADY_COMPLETED,
            message=f"Chart review already completed: {review_id}",
            detail=detail,
            trace=trace,
            qa_context={"review_id": review_id},
        )

    @classmethod
    def checklist_not_found(
        cls,
        checklist_id: str,
        *,
        trace: AdaptixTraceContext | None = None,
    ) -> "QaErrorEnvelope":
        return cls(
            error_code=QaErrorCode.QA_CHECKLIST_NOT_FOUND,
            message=f"QA checklist not found: {checklist_id}",
            trace=trace,
            qa_context={"checklist_id": checklist_id},
        )

    @classmethod
    def finding_not_found(
        cls,
        finding_id: str,
        *,
        review_id: str | None = None,
        trace: AdaptixTraceContext | None = None,
    ) -> "QaErrorEnvelope":
        return cls(
            error_code=QaErrorCode.QA_FINDING_NOT_FOUND,
            message=f"Review finding not found: {finding_id}",
            trace=trace,
            qa_context={
                k: v
                for k, v in {
                    "finding_id": finding_id,
                    "review_id": review_id,
                }.items()
                if v is not None
            },
        )

    @classmethod
    def tenant_mismatch(
        cls,
        *,
        expected_tenant_id: str,
        actual_tenant_id: str,
        review_id: str | None = None,
        trace: AdaptixTraceContext | None = None,
    ) -> "QaErrorEnvelope":
        return cls(
            error_code=QaErrorCode.QA_TENANT_MISMATCH,
            message="QA record belongs to a different tenant",
            trace=trace,
            qa_context={
                k: v
                for k, v in {
                    "expected_tenant_id": expected_tenant_id,
                    "actual_tenant_id": actual_tenant_id,
                    "review_id": review_id,
                }.items()
                if v is not None
            },
        )


__all__ = [
    "QaAssignmentError",
    "QaChecklistError",
    "QaError",
    "QaErrorCode",
    "QaErrorEnvelope",
    "QaFindingError",
    "QaMetricError",
    "QaReviewNotFoundError",
    "QaReviewStateError",
    "QaTenantMismatchError",
]
