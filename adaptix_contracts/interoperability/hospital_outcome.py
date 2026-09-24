"""Hospital outcome received: a hospital's outcome for a patient EMS brought in.

A receiving hospital returns what happened to a patient after handoff
(emergency department disposition, admission, diagnoses, discharge outcome:
NEMSIS eOutcome). It arrives through an exchange gateway as a
:class:`~adaptix_contracts.interoperability.exchange.PublicSafetyExchangeEnvelope`
and must then be matched to the EMS chart it belongs to. This event publishes
the result of that match.

Match status
------------
* ``MATCHED``: exactly one chart; ``matched_chart_id`` names it.
* ``AMBIGUOUS``: two or more candidate charts fit. Nothing is linked
  automatically; a person resolves it. ``candidate_chart_ids`` lists them.
* ``NO_MATCH``: no chart fits. The outcome is held, never attached to a
  guessed chart.

An ambiguous or missing match is a first-class answer, not an error to be
hidden: attaching an outcome to the wrong patient's chart is the failure this
contract exists to prevent.

PHI boundary
------------
The outcome content (codes, dates, diagnoses) stays behind ``payload_ref``,
bound by ``payload_sha256``, exactly as the exchange envelope keeps its
payload. This event carries identifiers and references only: no patient
name, date of birth, medical record number or clinical code travels on the
bus. ``extra="forbid"`` is the guard: a producer that attaches any of them
fails validation at the publish site.

Producer and reuse
------------------
Adaptix-EPCR-Service (service-registry slug ``epcr``) owns the chart's
hospital outcome linkage (``epcr_app/api_chart_outcome.py``, NEMSIS
eOutcome.01-24), so it is the authority that decides which chart an outcome
belongs to. Provenance reuses
:class:`~adaptix_contracts.interoperability.provenance.DataProvenance`.
A measured outcome built from these facts (for example "percent of STEMI
patients with door-to-balloon under 90 minutes") is an
:class:`adaptix_contracts.schemas.outcome_attribution_contracts.OutcomeObservation`,
and any claim that Adaptix changed it is an ``OutcomeAttribution``; this
event restates neither.
"""

from __future__ import annotations

from enum import Enum
from typing import Final

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from .gateway import ExchangeGatewayKind, ExchangeReference
from .provenance import DataProvenance

HOSPITAL_OUTCOME_RECEIVED: Final[str] = "hospital.outcome.received"

HOSPITAL_OUTCOME_SOURCE_SERVICE: Final[str] = "epcr"
"""Service-registry slug of the producer (the chart outcome owner)."""

#: Upper bound on candidate charts carried by one AMBIGUOUS result. A match
#: that fits more charts than this is not a candidate list a person can
#: review; the producer reports the first ones and the reviewer searches.
HOSPITAL_OUTCOME_MAX_CANDIDATES: Final[int] = 25


class HospitalOutcomeMatchStatus(str, Enum):
    """Whether a received hospital outcome was matched to one EMS chart."""

    MATCHED = "MATCHED"
    AMBIGUOUS = "AMBIGUOUS"
    NO_MATCH = "NO_MATCH"


# pylint too-few-public-methods (R0903) is disabled per class below. These are
# declarative Pydantic wire contracts whose entire contract IS their field set,
# exactly the shape pylint already exempts for @dataclass; the rule's intent (a
# class doing so little it should be a function or a tuple) cannot apply to a
# validated wire contract. Per class, never module-wide, so a future non-schema
# class added to this module is still checked.
class HospitalOutcomeReceivedPayload(BaseModel):  # pylint: disable=too-few-public-methods
    """Payload of ``hospital.outcome.received``.

    ``tenant_id`` is the EMS tenant that owns the chart, resolved server-side.
    ``idempotency_key`` identifies the received outcome (the hospital's own
    message identity), so a redelivered outcome is matched and applied once.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    outcome_id: ExchangeReference
    tenant_id: ExchangeReference
    exchange_id: ExchangeReference
    gateway_id: ExchangeReference
    gateway_kind: ExchangeGatewayKind
    facility_id: ExchangeReference
    match_status: HospitalOutcomeMatchStatus
    matched_chart_id: ExchangeReference | None = None
    matched_global_encounter_id: ExchangeReference | None = None
    candidate_chart_ids: tuple[ExchangeReference, ...] = Field(
        default=(), max_length=HOSPITAL_OUTCOME_MAX_CANDIDATES
    )
    payload_ref: ExchangeReference
    payload_sha256: str = Field(..., pattern=r"^[0-9a-f]{64}$")
    provenance: tuple[DataProvenance, ...] = ()
    outcome_recorded_at: AwareDatetime
    received_at: AwareDatetime
    correlation_id: ExchangeReference
    idempotency_key: ExchangeReference

    @model_validator(mode="after")
    def validate_match(self) -> HospitalOutcomeReceivedPayload:
        """The match status and the chart references must agree exactly."""

        status = self.match_status
        if status is HospitalOutcomeMatchStatus.MATCHED:
            if self.matched_chart_id is None:
                raise ValueError("a MATCHED outcome names matched_chart_id")
            if self.candidate_chart_ids:
                raise ValueError("a MATCHED outcome carries no candidate_chart_ids")
        else:
            if (
                self.matched_chart_id is not None
                or self.matched_global_encounter_id is not None
            ):
                raise ValueError(
                    f"a {status.value} outcome is linked to no chart or encounter"
                )
            if status is HospitalOutcomeMatchStatus.AMBIGUOUS:
                if len(set(self.candidate_chart_ids)) < 2:
                    raise ValueError(
                        "an AMBIGUOUS outcome lists at least two distinct "
                        "candidate_chart_ids"
                    )
            elif self.candidate_chart_ids:
                raise ValueError("a NO_MATCH outcome carries no candidate_chart_ids")
        if len(set(self.candidate_chart_ids)) != len(self.candidate_chart_ids):
            raise ValueError("candidate_chart_ids must not repeat a chart")
        return self


__all__ = [
    "HOSPITAL_OUTCOME_MAX_CANDIDATES",
    "HOSPITAL_OUTCOME_RECEIVED",
    "HOSPITAL_OUTCOME_SOURCE_SERVICE",
    "HospitalOutcomeMatchStatus",
    "HospitalOutcomeReceivedPayload",
]
