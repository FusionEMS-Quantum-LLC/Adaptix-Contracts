"""Necessity domain event definitions — Play P02 pre-submit linter.

Three cross-domain events fire from the ePCR pre-submit / chart-lock boundary
when the medical-necessity linter runs:

* ``necessity.assessed``    — every linter run emits this. Carries the full
  :class:`~adaptix_contracts.necessity.models.NecessityAssessment` so Billing
  and Cortex can react without re-querying ePCR.
* ``chart.lock.blocked``    — emitted when ``verdict == BLOCK`` and the chart
  lock attempt is rejected. Separate from ``necessity.assessed`` because chart
  lock has other blockers (missing signatures, incomplete required NEMSIS
  elements); a consumer that only cares about lock-time rejections subscribes
  here.
* ``denial.predicted``      — emitted once per :class:`DenialPrediction` when
  the linter is confident enough to warrant Billing pre-work (appeal draft,
  ABN generation). Small payload so it can fan out to many consumers cheaply.

Constants are the canonical event-type strings routed through
``adaptix_contracts.events.registry.ALL_EVENTS``; producer citation lives in
the registry entry itself.

``source_service`` for all three is ``"epcr"`` because the pre-submit linter
executes inside Adaptix-EPCR-Service at chart-lock time — even
``denial.predicted``, whose payload is billing-shaped, is emitted from the
ePCR service. Billing subscribes as a consumer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final, Literal, Optional

from pydantic import BaseModel, Field

from adaptix_contracts.necessity.enums import MacRegion, NecessityVerdict
from adaptix_contracts.necessity.models import (
    DenialPrediction,
    NecessityAssessment,
    NecessityFinding,
)


# ---------------------------------------------------------------------------
# Canonical event-type strings (registered in events/registry.py)
# ---------------------------------------------------------------------------

NECESSITY_ASSESSED: Final[str] = "necessity.assessed"
CHART_LOCK_BLOCKED: Final[str] = "chart.lock.blocked"
DENIAL_PREDICTED: Final[str] = "denial.predicted"


# ---------------------------------------------------------------------------
# Event payload models
# ---------------------------------------------------------------------------


class NecessityAssessedEvent(BaseModel):
    """Payload for ``necessity.assessed``.

    Contract-only; the transport envelope (tenant_id, correlation_id, etc.)
    lives on ``AdaptixEventEnvelope`` / ``EventSchema``. This model carries
    only the domain payload the consumer needs.
    """

    event_type: Literal["necessity.assessed"] = Field(
        default="necessity.assessed",
        description="Canonical event type — locked to the registry constant",
    )
    tenant_id: str
    chart_id: str
    assessment: NecessityAssessment
    occurred_at: datetime


class ChartLockBlockedEvent(BaseModel):
    """Payload for ``chart.lock.blocked`` — chart lock rejected by the linter.

    Emitted ONLY when the block is caused by the pre-submit medical-necessity
    linter. Other chart-lock blockers (unsigned narrative, missing NEMSIS
    fields, absent signatures) do not travel on this event — they have
    domain-specific events in the ePCR contracts.
    """

    event_type: Literal["chart.lock.blocked"] = Field(
        default="chart.lock.blocked",
        description="Canonical event type — locked to the registry constant",
    )
    tenant_id: str
    chart_id: str
    assessment_id: str = Field(
        ...,
        description="``NecessityAssessment.assessment_id`` that caused the block",
    )
    verdict: NecessityVerdict = Field(
        default=NecessityVerdict.BLOCK,
        description="Always BLOCK for this event; kept explicit for consumer clarity",
    )
    blocking_findings: list[NecessityFinding] = Field(
        default_factory=list,
        description="Findings with ``blocks_submission=True`` that produced the block",
    )
    mac_region: MacRegion
    attempted_by_user_id: Optional[str] = Field(
        None, description="ePCR user who attempted the lock"
    )
    occurred_at: datetime


class DenialPredictedEvent(BaseModel):
    """Payload for ``denial.predicted`` — one prediction per event.

    Fanned out to Billing (to pre-generate appeal drafts / ABNs) and to
    Cortex (to feed the denial-prevention learning loop). Kept small
    intentionally: consumers that need the full assessment fetch it by
    ``assessment_id`` or subscribe to ``necessity.assessed`` instead.
    """

    event_type: Literal["denial.predicted"] = Field(
        default="denial.predicted",
        description="Canonical event type — locked to the registry constant",
    )
    tenant_id: str
    chart_id: str
    assessment_id: str
    prediction: DenialPrediction
    occurred_at: datetime


__all__ = [
    "CHART_LOCK_BLOCKED",
    "ChartLockBlockedEvent",
    "DENIAL_PREDICTED",
    "DenialPredictedEvent",
    "NECESSITY_ASSESSED",
    "NecessityAssessedEvent",
]
