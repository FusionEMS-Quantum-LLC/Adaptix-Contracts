"""Commercial terms, discount authority and Community eligibility.

Terms are data on a catalog version (:class:`CommercialTerms`), so an agreement
signed under one version keeps its terms when a later version changes them
(founder Wisconsin launch plan, section 129). Nothing here applies a discount
or computes a term price; the pricing/billing service does that from these
values.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from adaptix_contracts.commercial.charges import ChargeClass

__all__ = [
    "DISCOUNTS_REQUIRING_FOUNDER_APPROVAL",
    "CommercialTerms",
    "CommunityEligibilityCriterion",
    "CommunityEligibilityDecision",
    "CommunityEligibilityOutcome",
    "DiscountType",
]


class DiscountType(str, enum.Enum):
    """The only discount kinds a quote may carry (section 264)."""

    COMMUNITY_ELIGIBILITY = "community_eligibility"
    ANNUAL_PREPAY = "annual_prepay"
    MULTI_YEAR = "multi_year"
    FOUNDING_AGENCY_PILOT = "founding_agency_pilot"
    STRATEGIC_REFERENCE_CUSTOMER = "strategic_reference_customer"
    PACKAGE = "package"
    #: Any other discount: founder approval and a written reason on the quote.
    FOUNDER_APPROVED_EXCEPTION = "founder_approved_exception"


#: Discount kinds that are valid only with founder approval and a written
#: reason attached to the quote.
DISCOUNTS_REQUIRING_FOUNDER_APPROVAL: frozenset[DiscountType] = frozenset(
    {DiscountType.FOUNDER_APPROVED_EXCEPTION}
)


@dataclass(frozen=True)
class CommercialTerms:  # pylint: disable=too-many-instance-attributes
    """The standard commercial terms of one catalog version.

    One flat record keeps every term a quote or contract cites in one place;
    grouping them into nested objects would add indirection without adding a
    single invariant.
    """

    #: Standard agreement length in months, billed monthly at list price.
    standard_term_months: int
    #: The annual-prepay discount rate (``Decimal("0.10")`` is 10%).
    annual_prepay_discount_rate: Decimal
    #: The only charge classes the annual-prepay discount applies to without
    #: an explicit contract term; never usage or pass-through charges.
    annual_prepay_eligible_charge_classes: frozenset[ChargeClass]
    #: Premium over standard 12-month subscription pricing when month-to-month
    #: is offered.
    month_to_month_premium_rate: Decimal
    #: Length of a multi-year government or public-agency commitment.
    multi_year_term_months: int
    #: Ceiling on the annual subscription increase under that commitment.
    multi_year_max_annual_subscription_increase_rate: Decimal
    #: Shortest and longest negotiated strategic pilot, in days.
    strategic_pilot_min_days: int
    strategic_pilot_max_days: int
    #: Optional onsite implementation per day; travel is a pass-through charge.
    onsite_daily_rate: Decimal
    #: Starting monthly price per custom, continuously maintained interface.
    maintained_interface_monthly_starting_price: Decimal
    #: The standard Cortex-powered migration fee. External costs such as a
    #: legacy vendor's data-release fee are pass-through charges, not this fee.
    standard_migration_fee: Decimal
    #: Every discount kind a quote may carry under this version.
    allowed_discounts: frozenset[DiscountType]
    #: Normal users are never charged per seat.
    standard_users_unlimited: bool
    #: Standard remote onboarding and training carry no implementation invoice.
    standard_remote_onboarding_included: bool
    #: Standard support is included; contractual coverage beyond it is quoted.
    standard_support_included: bool
    #: Patient-payment software is part of Adaptix Billing; processor, card and
    #: ACH fees are pass-through charges.
    patient_payments_software_included_with_billing: bool


class CommunityEligibilityCriterion(str, enum.Enum):
    """Organizational characteristics reviewed for Community pricing (section 265).

    Community pricing follows organizational reality, not claim volume. A
    reviewer records which characteristics apply; the decision itself is a
    human review stored as :class:`CommunityEligibilityDecision`.
    """

    WISCONSIN_ORGANIZATION = "wisconsin_organization"
    GOVERNMENT_OR_NONPROFIT_WHERE_APPLICABLE = (
        "government_or_nonprofit_where_applicable"
    )
    VOLUNTEER_OR_PAID_ON_CALL_WORKFORCE = "volunteer_or_paid_on_call_workforce"
    SINGLE_AGENCY_IMPLEMENTATION = "single_agency_implementation"
    NORMAL_IMPLEMENTATION_COMPLEXITY = "normal_implementation_complexity"
    NOT_COMMERCIAL_MULTI_AGENCY_BILLING_COMPANY = (
        "not_commercial_multi_agency_billing_company"
    )
    NOT_LARGE_REGIONAL_SHARED_SERVICE = "not_large_regional_shared_service"
    NOT_LARGE_FOR_PROFIT_TRANSPORT_ENTERPRISE = (
        "not_large_for_profit_transport_enterprise"
    )


class CommunityEligibilityOutcome(str, enum.Enum):
    """A reviewer's Community pricing decision."""

    APPROVED = "approved"
    DENIED = "denied"


@dataclass(frozen=True)
class CommunityEligibilityDecision:
    """A recorded Community pricing decision: outcome, reason, reviewer and date."""

    outcome: CommunityEligibilityOutcome
    reason: str
    reviewer: str
    decided_on: date
    criteria_met: frozenset[CommunityEligibilityCriterion] = field(
        default_factory=frozenset
    )

    def __post_init__(self) -> None:
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("a Community eligibility decision needs a written reason")
        if not isinstance(self.reviewer, str) or not self.reviewer.strip():
            raise ValueError(
                "a Community eligibility decision needs the reviewer who made it"
            )
