"""Adaptix Necessity — Play P02 pre-submit medical-necessity linter contracts.

The pre-submit medical-necessity linter runs at the ePCR chart-lock boundary,
before a claim is dropped to the clearinghouse. It evaluates the chart against
Local Coverage Determinations (LCDs) for the servicing MAC and against
historical payer-denial patterns for the tenant, then emits an assessment
that either clears the chart, warns the reviewer, or blocks the lock.

This subpackage owns the shared contracts every producer/consumer must agree
on:

* :class:`~adaptix_contracts.necessity.enums.NecessityVerdict` and
  :class:`~adaptix_contracts.necessity.enums.MacRegion` — the two enums that
  bound the assessment output and the MAC jurisdiction axis.
* :class:`~adaptix_contracts.necessity.models.NecessityAssessment`,
  :class:`~adaptix_contracts.necessity.models.NecessityFinding`,
  :class:`~adaptix_contracts.necessity.models.DenialPrediction`,
  :class:`~adaptix_contracts.necessity.models.LcdRule`, and
  :class:`~adaptix_contracts.necessity.models.PayerDenialPattern` — the five
  data contracts the linter, ePCR, Billing, and Cortex share.
* :mod:`adaptix_contracts.necessity.events` — the three cross-domain event
  type strings (``necessity.assessed``, ``chart.lock.blocked``,
  ``denial.predicted``) and their payload models.

The event types are registered in
``adaptix_contracts.events.registry.ALL_EVENTS`` with
``source_service="epcr"`` — the linter runs inside Adaptix-EPCR-Service, even
for the billing-shaped ``denial.predicted`` payload.
"""

from adaptix_contracts.necessity.enums import (
    MacRegion,
    NecessityVerdict,
)
from adaptix_contracts.necessity.events import (
    CHART_LOCK_BLOCKED,
    ChartLockBlockedEvent,
    DENIAL_PREDICTED,
    DenialPredictedEvent,
    NECESSITY_ASSESSED,
    NecessityAssessedEvent,
)
from adaptix_contracts.necessity.models import (
    DenialPrediction,
    LcdRule,
    NecessityAssessment,
    NecessityFinding,
    PayerDenialPattern,
)

__all__ = [
    "CHART_LOCK_BLOCKED",
    "ChartLockBlockedEvent",
    "DENIAL_PREDICTED",
    "DenialPrediction",
    "DenialPredictedEvent",
    "LcdRule",
    "MacRegion",
    "NECESSITY_ASSESSED",
    "NecessityAssessedEvent",
    "NecessityAssessment",
    "NecessityFinding",
    "NecessityVerdict",
    "PayerDenialPattern",
]
