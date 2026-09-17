"""Usage vocabulary: metrics, usage rates and the billable-encounter unit.

Usage pricing exists only where usage legitimately drives cost or value
(founder Wisconsin launch plan, section 4). Adaptix Billing and Adaptix Managed
Billing charge per **billable encounter**: one accepted billable patient
encounter is one usage unit (sections 21, 176, 178, 256). The same encounter
never produces another unit because it needed a corrected submission, a
resubmission, a secondary-payer claim, a status inquiry, a denial, an appeal,
an ERA, payment posting or reposting, or a rebill
(:class:`SameEncounterActivity`). Managed Billing counts exactly the same units
at a different rate; there is no second definition of a claim.

Deduplication is enforced server-side on the canonical encounter identity and
is never inferred from EDI transaction counts. :class:`BillableEncounterUsageKey`
is the uniqueness key: tenant + canonical billable encounter + usage metric
(section 338). Usage is never deleted: a unit recorded in error is reversed or
adjusted with a reason and the operator who made the correction (section 177).

The event that records a unit (``billing.billable_encounter.accepted``,
section 176) is registered in ``events.registry`` together with its producer in
Adaptix-Billing-Service. That registry requires a cited producer, so the event
is deliberately not declared here ahead of one.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from decimal import Decimal

from adaptix_contracts.commercial.charges import is_cent_amount

__all__ = [
    "USAGE_LEDGER_STATES_REQUIRING_REASON",
    "BillableEncounterUsageKey",
    "SameEncounterActivity",
    "UsageLedgerState",
    "UsageMetric",
    "UsageRate",
    "UsageRateBasis",
]


class UsageMetric(str, enum.Enum):
    """A metered quantity a catalog may price."""

    #: One accepted billable patient encounter (Billing and Managed Billing).
    BILLABLE_ENCOUNTER = "billable_encounter"
    #: Telephony and messaging carrier consumption behind Communications.
    COMMUNICATIONS_CARRIER_USAGE = "communications_carrier_usage"
    #: AI provider consumption behind Cortex Pro automation.
    CORTEX_PROVIDER_USAGE = "cortex_provider_usage"


class UsageRateBasis(str, enum.Enum):
    """How a usage metric is charged."""

    #: A published price per unit.
    PER_UNIT = "per_unit"
    #: A rate agreed in the customer's contract.
    NEGOTIATED = "negotiated"
    #: The actual third-party cost, passed through transparently or with a
    #: markup documented in the contract.
    PASS_THROUGH = "pass_through"
    #: Metered internally; no customer-facing usage charge is published yet.
    POLICY_PENDING = "policy_pending"


@dataclass(frozen=True)
class UsageRate:
    """How one usage metric is charged in one customer segment."""

    metric: UsageMetric
    basis: UsageRateBasis
    unit_price: Decimal | None = None

    def __post_init__(self) -> None:
        if self.basis is UsageRateBasis.PER_UNIT:
            if not is_cent_amount(self.unit_price):
                raise ValueError(
                    f"{self.metric.value}: a per-unit rate needs a positive Decimal "
                    f"unit_price with at most cent precision, got {self.unit_price!r}"
                )
        elif self.unit_price is not None:
            raise ValueError(
                f"{self.metric.value}: a {self.basis.value} rate must not carry a "
                f"unit_price, got {self.unit_price!r}"
            )


class SameEncounterActivity(str, enum.Enum):
    """Billing work on an existing encounter that never creates another usage unit."""

    CORRECTED_SUBMISSION = "corrected_submission"
    RESUBMISSION = "resubmission"
    SECONDARY_PAYER_SUBMISSION = "secondary_payer_submission"
    CLAIM_STATUS_INQUIRY = "claim_status_inquiry"
    DENIAL = "denial"
    APPEAL = "appeal"
    ERA = "era"
    PAYMENT_POSTING = "payment_posting"
    PAYMENT_REPOSTING = "payment_reposting"
    REBILL = "rebill"


class UsageLedgerState(str, enum.Enum):
    """The state of one recorded usage unit."""

    RECORDED = "recorded"
    REVERSED = "reversed"
    ADJUSTED = "adjusted"


#: Ledger states that only exist as a deliberate correction. Each must carry a
#: written reason and the operator who made it; usage is never deleted.
USAGE_LEDGER_STATES_REQUIRING_REASON: frozenset[UsageLedgerState] = frozenset(
    {UsageLedgerState.REVERSED, UsageLedgerState.ADJUSTED}
)


@dataclass(frozen=True)
class BillableEncounterUsageKey:
    """The uniqueness key of one usage unit.

    Two recordings with equal keys are the same unit, whichever claim
    transaction, retry or concurrent worker produced them.
    ``billable_encounter_id`` is the canonical encounter identity, never a
    claim, submission or transaction id.
    """

    tenant_id: str
    billable_encounter_id: str
    metric: UsageMetric

    def __post_init__(self) -> None:
        for name, value in (
            ("tenant_id", self.tenant_id),
            ("billable_encounter_id", self.billable_encounter_id),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
