"""Service-specific error types for the Adaptix Wildland federal sync service.

Two layers are provided so callers can pick the right primitive:

* :class:`WildlandError` and its subclasses are Python exceptions raised
  inside the Wildland service and its clients; they carry structured
  context (``assignment_id``, ``order_id``, etc.) and know how to render
  themselves into the shared Adaptix HTTP error envelope.
* :class:`WildlandErrorEnvelope` extends
  :class:`~adaptix_contracts.errors.envelope.AdaptixErrorEnvelope` so
  the wire format is exactly the platform envelope — the ``error_code``
  field is widened to accept :class:`WildlandErrorCode`, and
  wildland-specific factory classmethods produce well-typed envelopes
  without callers hand-building the dict.

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


class WildlandErrorCode(str, Enum):
    """Wildland-specific error codes.

    Kept distinct from :class:`AdaptixErrorCode` (rather than trying to
    extend it — Python does not allow enum extension in a way that keeps
    ``isinstance`` sensible) and merged at the envelope boundary through
    :class:`WildlandErrorEnvelope.error_code`. When a wildland-specific
    code truly overlaps a platform-wide one, prefer the platform code
    and do not add a duplicate here.
    """

    WILDLAND_ASSIGNMENT_NOT_FOUND = "wildland.assignment.not_found"
    WILDLAND_ASSIGNMENT_TENANT_MISMATCH = "wildland.assignment.tenant_mismatch"

    WILDLAND_DEPLOYMENT_NOT_FOUND = "wildland.deployment.not_found"
    WILDLAND_DEPLOYMENT_INVALID = "wildland.deployment.invalid"

    WILDLAND_IROC_ORDER_NOT_FOUND = "wildland.iroc.order.not_found"
    WILDLAND_IROC_SYNC_FAILED = "wildland.iroc.sync_failed"
    WILDLAND_IROC_ORDER_ALREADY_FILLED = "wildland.iroc.order.already_filled"

    WILDLAND_IRWIN_INCIDENT_NOT_FOUND = "wildland.irwin.incident.not_found"
    WILDLAND_IRWIN_SYNC_FAILED = "wildland.irwin.sync_failed"

    WILDLAND_WFDSS_DECISION_NOT_FOUND = "wildland.wfdss.decision.not_found"
    WILDLAND_WFDSS_SYNC_FAILED = "wildland.wfdss.sync_failed"
    WILDLAND_WFDSS_PHASE_INVALID = "wildland.wfdss.phase_invalid"

    WILDLAND_ICS209_NOT_FOUND = "wildland.ics209.not_found"
    WILDLAND_ICS209_SECTION_INCOMPLETE = "wildland.ics209.section_incomplete"
    WILDLAND_ICS209_ALREADY_SUBMITTED = "wildland.ics209.already_submitted"


class WildlandError(Exception):
    """Base exception for the Wildland service.

    Subclasses set :attr:`code` to a :class:`WildlandErrorCode`; callers
    catch :class:`WildlandError` when they want to handle any Wildland
    fault generically, or a specific subclass when they can act on it.

    :meth:`to_envelope` renders the exception into the shared HTTP error
    envelope; nothing in the exception itself decides HTTP status.
    """

    code: WildlandErrorCode = WildlandErrorCode.WILDLAND_ASSIGNMENT_NOT_FOUND

    def __init__(
        self,
        message: str,
        *,
        code: WildlandErrorCode | None = None,
        tenant_id: str | None = None,
        assignment_id: str | None = None,
        order_id: str | None = None,
        decision_id: str | None = None,
        report_id: str | None = None,
        detail: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code
        self.message = message
        self.detail = detail
        self.tenant_id = tenant_id
        self.assignment_id = assignment_id
        self.order_id = order_id
        self.decision_id = decision_id
        self.report_id = report_id
        self.context: dict[str, Any] = dict(context or {})

    def to_envelope(
        self,
        *,
        trace: AdaptixTraceContext | None = None,
    ) -> "WildlandErrorEnvelope":
        """Render this exception as a :class:`WildlandErrorEnvelope`.

        No stack trace or raw exception text is emitted — only the
        structured fields the caller supplied when constructing the
        exception.
        """

        effective_trace = trace
        if effective_trace is None and self.tenant_id is not None:
            effective_trace = AdaptixTraceContext(tenant_id=self.tenant_id)

        return WildlandErrorEnvelope(
            error_code=self.code,
            message=self.message,
            detail=self.detail,
            trace=effective_trace,
            wildland_context=self._wildland_context(),
        )

    def _wildland_context(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.tenant_id is not None:
            payload["tenant_id"] = self.tenant_id
        if self.assignment_id is not None:
            payload["assignment_id"] = self.assignment_id
        if self.order_id is not None:
            payload["order_id"] = self.order_id
        if self.decision_id is not None:
            payload["decision_id"] = self.decision_id
        if self.report_id is not None:
            payload["report_id"] = self.report_id
        payload.update(self.context)
        return payload


class WildlandAssignmentNotFoundError(WildlandError):
    """Raised when a wildland assignment id does not resolve for the caller's tenant."""

    code = WildlandErrorCode.WILDLAND_ASSIGNMENT_NOT_FOUND


class WildlandAssignmentTenantMismatchError(WildlandError):
    """Raised when a caller's tenant does not match the target assignment.

    Distinct from :class:`WildlandAssignmentNotFoundError` because a
    mismatch is a tenancy fault (the caller has an authenticated identity
    in another tenant) whereas ``not found`` covers unknown-id lookups
    within the caller's own tenant. Callers MUST NOT downgrade this to a
    404 — the distinction is required for cross-tenant audit.
    """

    code = WildlandErrorCode.WILDLAND_ASSIGNMENT_TENANT_MISMATCH


class WildlandDeploymentError(WildlandError):
    """Raised for wildland deployment lookup or validation faults."""

    code = WildlandErrorCode.WILDLAND_DEPLOYMENT_NOT_FOUND


class WildlandIrocSyncError(WildlandError):
    """Raised when an IROC resource order sync round fails or cannot proceed."""

    code = WildlandErrorCode.WILDLAND_IROC_SYNC_FAILED


class WildlandIrwinSyncError(WildlandError):
    """Raised when an IRWIN incident identity sync round fails."""

    code = WildlandErrorCode.WILDLAND_IRWIN_SYNC_FAILED


class WildlandWfdssSyncError(WildlandError):
    """Raised when a WFDSS strategic decision sync round fails or is invalid."""

    code = WildlandErrorCode.WILDLAND_WFDSS_SYNC_FAILED


class WildlandIcs209Error(WildlandError):
    """Raised for ICS-209 report lookup, completeness, or submission faults."""

    code = WildlandErrorCode.WILDLAND_ICS209_NOT_FOUND


class WildlandErrorEnvelope(AdaptixErrorEnvelope):
    """Adaptix HTTP error envelope widened for Wildland-specific codes.

    Overrides only ``error_code`` (widened to accept
    :class:`WildlandErrorCode`) and adds ``wildland_context`` for
    structured Wildland-scoped fields (``assignment_id``, ``order_id``
    …). The envelope shape, timestamp field, trace context, and
    ``to_http_response`` behaviour are inherited unchanged from
    :class:`~adaptix_contracts.errors.envelope.AdaptixErrorEnvelope`.
    """

    error_code: WildlandErrorCode | AdaptixErrorCode
    wildland_context: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def assignment_not_found(
        cls,
        assignment_id: str,
        *,
        tenant_id: str | None = None,
        trace: AdaptixTraceContext | None = None,
    ) -> "WildlandErrorEnvelope":
        return cls(
            error_code=WildlandErrorCode.WILDLAND_ASSIGNMENT_NOT_FOUND,
            message=f"Wildland assignment not found: {assignment_id}",
            trace=trace,
            wildland_context={
                k: v
                for k, v in {
                    "assignment_id": assignment_id,
                    "tenant_id": tenant_id,
                }.items()
                if v is not None
            },
        )

    @classmethod
    def iroc_sync_failed(
        cls,
        order_id: str,
        reason: str,
        *,
        trace: AdaptixTraceContext | None = None,
    ) -> "WildlandErrorEnvelope":
        return cls(
            error_code=WildlandErrorCode.WILDLAND_IROC_SYNC_FAILED,
            message=f"IROC sync failed for order {order_id}",
            detail=reason,
            trace=trace,
            wildland_context={"order_id": order_id},
        )

    @classmethod
    def irwin_sync_failed(
        cls,
        irwin_incident_id: str,
        reason: str,
        *,
        trace: AdaptixTraceContext | None = None,
    ) -> "WildlandErrorEnvelope":
        return cls(
            error_code=WildlandErrorCode.WILDLAND_IRWIN_SYNC_FAILED,
            message=f"IRWIN sync failed for incident {irwin_incident_id}",
            detail=reason,
            trace=trace,
            wildland_context={"irwin_incident_id": irwin_incident_id},
        )

    @classmethod
    def wfdss_sync_failed(
        cls,
        decision_id: str,
        reason: str,
        *,
        trace: AdaptixTraceContext | None = None,
    ) -> "WildlandErrorEnvelope":
        return cls(
            error_code=WildlandErrorCode.WILDLAND_WFDSS_SYNC_FAILED,
            message=f"WFDSS sync failed for decision {decision_id}",
            detail=reason,
            trace=trace,
            wildland_context={"decision_id": decision_id},
        )

    @classmethod
    def ics209_section_incomplete(
        cls,
        report_id: str,
        section: str,
        *,
        trace: AdaptixTraceContext | None = None,
    ) -> "WildlandErrorEnvelope":
        return cls(
            error_code=WildlandErrorCode.WILDLAND_ICS209_SECTION_INCOMPLETE,
            message=f"ICS-209 report {report_id} missing required section {section}",
            trace=trace,
            wildland_context={"report_id": report_id, "section": section},
        )

    @classmethod
    def tenant_mismatch(
        cls,
        *,
        expected_tenant_id: str,
        actual_tenant_id: str,
        assignment_id: str | None = None,
        trace: AdaptixTraceContext | None = None,
    ) -> "WildlandErrorEnvelope":
        return cls(
            error_code=WildlandErrorCode.WILDLAND_ASSIGNMENT_TENANT_MISMATCH,
            message="Wildland assignment belongs to a different tenant",
            trace=trace,
            wildland_context={
                k: v
                for k, v in {
                    "expected_tenant_id": expected_tenant_id,
                    "actual_tenant_id": actual_tenant_id,
                    "assignment_id": assignment_id,
                }.items()
                if v is not None
            },
        )


__all__ = [
    "WildlandAssignmentNotFoundError",
    "WildlandAssignmentTenantMismatchError",
    "WildlandDeploymentError",
    "WildlandError",
    "WildlandErrorCode",
    "WildlandErrorEnvelope",
    "WildlandIcs209Error",
    "WildlandIrocSyncError",
    "WildlandIrwinSyncError",
    "WildlandWfdssSyncError",
]
