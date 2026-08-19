"""Universal exception inbox contracts — shared platform primitive F.

Every domain in AdaptixCore produces work that a machine could not finish and a
person now has to: claim rejects, payer mismatches, NERIS rejects, controlled-
substance discrepancies, offline sync conflicts, QHIN failures, credential
conflicts, provider enrollment failures, agent approvals, inventory mismatches,
RSNAT expirations, air safety actions.

Today each of those would grow its own list, its own statuses, and its own
notion of "handled". One shared contract means an operator has one queue, and a
supervisor can ask "what is outstanding across this agency?" and get an answer.

Naming: this is ``ExceptionRecord``, not ``PlatformException`` — it is a
persisted work item, not a Python exception, and code that catches one from the
other is a defect waiting to happen.

Two invariants the model enforces:

* a terminal status (``RESOLVED`` / ``WAIVED``) requires ``resolved_at``,
  ``resolved_by`` and ``resolution`` — an exception cannot quietly become
  closed with nobody attached to the decision;
* a non-terminal status must not carry resolution fields, so "in review" cannot
  be dressed up as finished.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExceptionSeverity(str, Enum):
    """How much this matters, in operator terms.

    ``CRITICAL`` means patient safety, controlled-substance custody, or a
    regulatory deadline — not "the biggest number in the dashboard".
    """

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ExceptionStatus(str, Enum):
    """Lifecycle of one exception.

    ``WAITING_EXTERNAL`` is deliberately distinct from ``IN_REVIEW``: work that
    is blocked on a payer, a hospital, or a provider is not work an operator can
    advance, and mixing the two makes every queue look permanently stalled.

    ``WAIVED`` is distinct from ``RESOLVED``: the underlying problem was not
    fixed, a person with authority accepted it. Collapsing them destroys the
    only number that matters in an audit — how often we accept rather than fix.
    """

    OPEN = "open"
    ASSIGNED = "assigned"
    IN_REVIEW = "in_review"
    WAITING_EXTERNAL = "waiting_external"
    RESOLVED = "resolved"
    WAIVED = "waived"
    ESCALATED = "escalated"


#: Statuses in which the exception is closed and needs no further operator work.
TERMINAL_EXCEPTION_STATUSES: frozenset[ExceptionStatus] = frozenset(
    {
        ExceptionStatus.RESOLVED,
        ExceptionStatus.WAIVED,
    }
)


def is_open(status: ExceptionStatus | str) -> bool:
    """Return ``True`` when this exception still needs someone.

    Fails closed: an unrecognised status counts as open, so an exception in a
    state a consumer does not understand stays visible rather than disappearing
    from the queue.
    """

    try:
        resolved = ExceptionStatus(status)
    except ValueError:
        return True
    return resolved not in TERMINAL_EXCEPTION_STATUSES


class ExceptionRecord(BaseModel):
    """One piece of work a machine could not finish.

    ``human_summary`` is what an operator reads and must be plain language with
    no protected content — it renders in queues, notifications and exports.
    ``machine_context`` is structured detail for the owning service: reason
    codes, ids, counts, versions. Neither field may carry PHI, PII, free
    clinical narrative, claim free text, or provider credentials.
    """

    model_config = ConfigDict(extra="forbid")

    exception_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    domain: str = Field(
        ...,
        min_length=1,
        description="Owning domain, e.g. billing, narcotics, fire, air",
    )
    subject_type: str = Field(..., min_length=1)
    subject_id: str = Field(..., min_length=1)
    severity: ExceptionSeverity
    reason_code: str = Field(
        ...,
        min_length=1,
        description="Stable machine-readable cause; consumers branch on this",
    )
    human_summary: str = Field(
        ...,
        min_length=1,
        description="Plain-language description for an operator. No protected data.",
    )
    machine_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured non-protected detail for the owning service",
    )
    owner_role: str | None = Field(
        default=None,
        description="Role expected to act, e.g. billing_manager, medical_director",
    )
    status: ExceptionStatus = ExceptionStatus.OPEN
    created_at: datetime
    due_at: datetime | None = Field(
        default=None,
        description="Operational or regulatory deadline, when one genuinely exists",
    )
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    resolution: str | None = Field(
        default=None, description="What was actually done, in plain language"
    )
    correlation_id: str = Field(..., min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _resolution_fields_match_status(self) -> ExceptionRecord:
        terminal = self.status in TERMINAL_EXCEPTION_STATUSES
        fields = (
            ("resolved_at", self.resolved_at),
            ("resolved_by", self.resolved_by),
            ("resolution", self.resolution),
        )
        if terminal:
            missing = [name for name, value in fields if value is None]
            if missing:
                raise ValueError(
                    f"status {self.status.value!r} is terminal but "
                    f"{', '.join(missing)} is missing"
                )
        else:
            present = [name for name, value in fields if value is not None]
            if present:
                raise ValueError(
                    f"status {self.status.value!r} is not terminal but carries "
                    f"{', '.join(present)}"
                )

        if self.resolved_at is not None and self.resolved_at < self.created_at:
            raise ValueError("resolved_at precedes created_at")
        return self

    def is_open(self) -> bool:
        """Return ``True`` when this exception still needs someone."""

        return is_open(self.status)

    def is_overdue(self, now: datetime) -> bool:
        """Return ``True`` when an open exception has passed its deadline.

        A closed exception is never overdue, and an exception with no genuine
        deadline is never overdue — a synthetic due date would turn every queue
        into false urgency.
        """

        if self.due_at is None or not self.is_open():
            return False
        return now > self.due_at


__all__ = [
    "TERMINAL_EXCEPTION_STATUSES",
    "ExceptionRecord",
    "ExceptionSeverity",
    "ExceptionStatus",
    "is_open",
]
