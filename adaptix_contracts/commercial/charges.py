"""Charge classes and pass-through charge types for the offer catalog.

A commercial line on a quote or an invoice is exactly one :class:`ChargeClass`.
The class decides which commercial terms reach the line: the annual-prepay
discount, for example, applies to subscription classes only and never to usage
or pass-through charges (Wisconsin launch plan section 261). Pass-through
charges are third-party costs shown transparently instead of being folded into
a fee (sections 23, 268, 270-272).
"""

from __future__ import annotations

import enum
from decimal import Decimal

__all__ = ["ChargeClass", "PassThroughChargeType", "is_cent_amount"]


class ChargeClass(str, enum.Enum):
    """The kind of money a commercial line represents."""

    #: The AdaptixCore Platform subscription, paid once per organization.
    PLATFORM_SUBSCRIPTION = "platform_subscription"
    #: An application, application-module or capability subscription.
    APPLICATION_SUBSCRIPTION = "application_subscription"
    #: A package subscription: a discount over the applications it contains.
    PACKAGE_SUBSCRIPTION = "package_subscription"
    #: The monthly base of work FusionEMS performs for the customer (Managed Billing).
    MANAGED_SERVICE = "managed_service"
    #: Metered usage the catalog prices, such as an accepted billable encounter.
    USAGE = "usage"
    #: A third-party cost passed through transparently.
    PASS_THROUGH = "pass_through"  # nosec B105  # noqa: S105
    #: Optional professional services such as onsite implementation days.
    PROFESSIONAL_SERVICE = "professional_service"
    #: A custom interface FusionEMS continuously maintains for one customer.
    MAINTAINED_INTERFACE = "maintained_interface"


class PassThroughChargeType(str, enum.Enum):
    """External costs that are passed through, never hidden inside a fee."""

    INSURANCE_DISCOVERY = "insurance_discovery"
    EXCEPTIONAL_ELIGIBILITY_OR_DISCOVERY_VOLUME = (
        "exceptional_eligibility_or_discovery_volume"
    )
    MBI_OR_COB_PAID_SERVICE = "mbi_or_cob_paid_service"
    ELECTRONIC_ATTACHMENT_275 = "electronic_attachment_275"
    PAPER_CLAIM = "paper_claim"
    PAPER_STATEMENT_POSTAGE = "paper_statement_postage"
    PROCESSOR_CARD_FEE = "processor_card_fee"
    ACH_FEE = "ach_fee"
    PAYER_IMPOSED_FEE = "payer_imposed_fee"
    CARRIER_USAGE = "carrier_usage"
    LEGACY_VENDOR_DATA_RELEASE_FEE = "legacy_vendor_data_release_fee"
    PHYSICAL_MEDIA_HANDLING = "physical_media_handling"
    THIRD_PARTY_EXTRACTION = "third_party_extraction"
    TRAVEL = "travel"


def is_cent_amount(amount: object) -> bool:
    """True for a finite, positive ``Decimal`` with at most cent precision.

    Money in this package is ``Decimal`` authored from exact text. A float, a
    bool, zero, a negative value or a fraction of a cent is rejected rather
    than rounded, so a mistyped price fails validation instead of being
    silently repaired.
    """

    if not isinstance(amount, Decimal) or not amount.is_finite() or amount <= 0:
        return False
    exponent = amount.as_tuple().exponent
    return isinstance(exponent, int) and exponent >= -2
