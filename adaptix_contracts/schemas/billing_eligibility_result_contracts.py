"""Billing eligibility result: the minimum summary of one resolved 270/271 check.

Event ``billing.eligibility.result.v1`` (producer: Adaptix-Billing-Service,
service-registry slug ``billing``).

Why this event exists
---------------------
Billing owns payer eligibility verification and the whole 270/271 lifecycle:
it sends the 270, receives the 271, keeps the raw response, the benefit
detail, the payer's request rejections, the history of every check and the
verification state its claim gates read. Clinical and operational users
working a chart still need to see one thing: whether the payer's eligibility
has been checked for this encounter, when, and with which outcome. This event
carries exactly that, so a chart surface can show it without becoming a second
eligibility system.

One event is published each time a check resolves, whatever the outcome. A
check that could not be answered is published too (``error`` / ``unknown``):
"the check did not confirm coverage" is a fact a reader needs, and silence
would leave an earlier answer on display as if it were the latest.

What the payload carries, and what it never carries
---------------------------------------------------
The payload is identifiers, one coverage status, the coverage dates the payer
stated, one timestamp and the source of the answer. ``extra="forbid"`` is the
guard: a producer that attaches anything else fails validation at the publish
site, and a consumer that receives anything else refuses the event.

Never in this payload, by construction: the raw 270 or 271, benefit lines
(co-pay, deductible, co-insurance, authorization indicators), the payer's AAA
rejection detail, the plan name or description, the payer name, the
subscriber or member id, a patient name, a date of birth, an address, or the
date of service that was asked about. Those stay in Billing.

Identity, version and ordering (what a consumer may rely on)
------------------------------------------------------------
* ``eligibility_check_id`` identifies the check in Billing. With
  ``schema_version`` it is the idempotency key: the same check under the same
  schema version is one result, however many times it is delivered.
* ``checked_at`` orders results. A consumer shows the result with the latest
  ``checked_at`` and keeps the others as history; a result that arrives late
  never replaces a newer one.
* ``schema_version`` is ``MAJOR.MINOR``. This module is major 1 and the event
  name carries it (``.v1``). Because unknown fields are refused, a field is
  added by releasing the contract, moving every consumer's pin, and only then
  the producer's.

A consumer is a read projection. Nothing it stores is authoritative and
nothing in this contract lets it change Billing's state.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Final

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from adaptix_contracts.events.bus_limits import BUS_CORRELATION_ID_MAX_LENGTH

# ---------------------------------------------------------------------------
# Event name, producer and version
# ---------------------------------------------------------------------------

#: One eligibility check resolved in Billing.
BILLING_ELIGIBILITY_RESULT_V1: Final[str] = "billing.eligibility.result.v1"

BILLING_ELIGIBILITY_RESULT_SOURCE_SERVICE: Final[str] = "billing"
"""Service-registry slug of the producing service."""

BILLING_ELIGIBILITY_RESULT_SCHEMA_VERSION: Final[str] = "1.0"
"""Payload schema version. The major is fixed by the event name (``.v1``)."""

#: Widest opaque identifier the payload carries (check, tenant, chart, claim,
#: patient identity, payer and clearinghouse identifiers, trace number). A
#: consumer that stores one declares its column from this constant.
ELIGIBILITY_RESULT_ID_MAX_LENGTH: Final[int] = 120


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------


class EligibilityCoverageStatus(str, Enum):
    """What the resolved check says about coverage. A closed set of five.

    * ``ACTIVE``: the payer answered that coverage is active. When the check
      was run for a claim, Billing publishes ``ACTIVE`` only if the payer's
      own coverage dates include that claim's date of service.
    * ``INACTIVE``: the payer answered that coverage is not active, or
      answered active with coverage dates that exclude the claim's date of
      service.
    * ``NON_COVERED``: the payer answered that the service is not covered.
    * ``UNKNOWN``: the payer answered, and the answer is neither active nor
      inactive. Coverage was not confirmed.
    * ``ERROR``: there is no coverage answer. The payer rejected the request,
      or no response was obtained (the clearinghouse failed, timed out or is
      not configured). Coverage was not confirmed.

    Only ``ACTIVE`` says the payer reported coverage, and even that is a
    statement about eligibility on the date that was asked, never a promise
    that a claim will be paid.
    """

    ACTIVE = "active"
    INACTIVE = "inactive"
    NON_COVERED = "non_covered"
    UNKNOWN = "unknown"
    ERROR = "error"


class EligibilityResultSource(str, Enum):
    """Where the result came from: the clearinghouse and the transaction.

    * ``STEDI_271``: a 271 the payer returned through Stedi, the live
      eligibility clearinghouse.
    * ``STEDI_270``: a 270 sent (or attempted) through Stedi that produced no
      271. There is no payer answer behind this result, so its status is
      always ``ERROR``.
    * ``OFFICE_ALLY_271``: a 271 delivered by Office Ally for an inquiry sent
      before that clearinghouse was retired. Office Ally receives no new
      inquiries; only its inbound tail is still read.
    """

    STEDI_271 = "stedi_271"
    STEDI_270 = "stedi_270"
    OFFICE_ALLY_271 = "office_ally_271"


#: Sources that have no payer answer behind them.
ELIGIBILITY_RESULT_UNANSWERED_SOURCES: Final[frozenset[EligibilityResultSource]] = (
    frozenset({EligibilityResultSource.STEDI_270})
)


# ---------------------------------------------------------------------------
# Payload
# ---------------------------------------------------------------------------


class BillingEligibilityResultPayload(BaseModel):
    """Payload of ``billing.eligibility.result.v1``.

    Every identifier is the owning service's opaque record id. ``None`` means
    "not known to Billing for this check", never "does not exist".
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    schema_version: str = Field(
        default=BILLING_ELIGIBILITY_RESULT_SCHEMA_VERSION,
        pattern=r"^1\.[0-9]{1,4}$",
        description="Payload schema version, MAJOR.MINOR. Major 1 only.",
    )
    tenant_id: str = Field(
        ...,
        min_length=1,
        max_length=ELIGIBILITY_RESULT_ID_MAX_LENGTH,
        description="Tenant that owns the check. Equals the envelope's tenant.",
    )
    eligibility_check_id: str = Field(
        ...,
        min_length=1,
        max_length=ELIGIBILITY_RESULT_ID_MAX_LENGTH,
        description="Billing's id of the eligibility check this result is for.",
    )
    chart_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=ELIGIBILITY_RESULT_ID_MAX_LENGTH,
        description=(
            "ePCR chart the result applies to, when Billing knows it: the "
            "check was run for a claim built from that chart and answers for "
            "that claim's patient and date of service. None otherwise."
        ),
    )
    patient_identity_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=ELIGIBILITY_RESULT_ID_MAX_LENGTH,
        description=(
            "Patient-Identity id of the patient, when Billing holds it. An "
            "opaque id; no name, date of birth or member id travels here."
        ),
    )
    claim_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=ELIGIBILITY_RESULT_ID_MAX_LENGTH,
        description="Billing claim the check was run for. None for a check run without one.",
    )
    clearinghouse_eligibility_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=ELIGIBILITY_RESULT_ID_MAX_LENGTH,
        description=(
            "The clearinghouse's own identifier for the eligibility "
            "transaction, when it returned one. None when it returned none or "
            "never answered."
        ),
    )
    payer_id: str = Field(
        ...,
        min_length=1,
        max_length=ELIGIBILITY_RESULT_ID_MAX_LENGTH,
        description="Payer id the inquiry was addressed to.",
    )
    trading_partner_service_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=ELIGIBILITY_RESULT_ID_MAX_LENGTH,
        description=(
            "Clearinghouse trading-partner id the 270 was sent to. None for a "
            "check recorded before Billing kept it."
        ),
    )
    response_payer_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=ELIGIBILITY_RESULT_ID_MAX_LENGTH,
        description=(
            "Payer id the 271 named. It can differ from the id the inquiry was "
            "addressed to. None when no 271 came back or it named none."
        ),
    )
    coverage_status: EligibilityCoverageStatus = Field(
        ..., description="What the resolved check says about coverage."
    )
    coverage_effective_from: date | None = Field(
        default=None,
        description=(
            "First day of the coverage window the payer stated (the latest of "
            "its plan, eligibility and policy begin dates). None when the "
            "payer stated no begin date."
        ),
    )
    coverage_effective_through: date | None = Field(
        default=None,
        description=(
            "Last day of the coverage window the payer stated (the earliest "
            "of its plan, eligibility and policy end dates). None when the "
            "payer stated no end date."
        ),
    )
    checked_at: AwareDatetime = Field(
        ...,
        description=(
            "When Billing resolved the check: when the 271 was received, or, "
            "with no 271, when the failed attempt was recorded. Orders the "
            "results of a chart; never a consumer's receipt time."
        ),
    )
    source: EligibilityResultSource = Field(
        ..., description="Clearinghouse and transaction the result came from."
    )
    correlation_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=BUS_CORRELATION_ID_MAX_LENGTH,
        description=(
            "Correlation id of the Billing request or worker run that resolved "
            "the check; joins this event to Billing's logs."
        ),
    )
    trace_number: str | None = Field(
        default=None,
        min_length=1,
        max_length=ELIGIBILITY_RESULT_ID_MAX_LENGTH,
        description=(
            "Trace reference Billing recorded for the 270/271 exchange (the "
            "270's control number, or the reference the 271 echoed)."
        ),
    )

    @model_validator(mode="after")
    def _a_result_without_a_271_is_an_error(self) -> BillingEligibilityResultPayload:
        """No payer answer, no coverage statement."""
        if (
            self.source in ELIGIBILITY_RESULT_UNANSWERED_SOURCES
            and self.coverage_status is not EligibilityCoverageStatus.ERROR
        ):
            raise ValueError(
                f"source {self.source.value} has no payer answer behind it; "
                f"its coverage_status is error, not {self.coverage_status.value}"
            )
        return self


__all__ = [
    "BILLING_ELIGIBILITY_RESULT_SCHEMA_VERSION",
    "BILLING_ELIGIBILITY_RESULT_SOURCE_SERVICE",
    "BILLING_ELIGIBILITY_RESULT_V1",
    "ELIGIBILITY_RESULT_ID_MAX_LENGTH",
    "ELIGIBILITY_RESULT_UNANSWERED_SOURCES",
    "BillingEligibilityResultPayload",
    "EligibilityCoverageStatus",
    "EligibilityResultSource",
]
