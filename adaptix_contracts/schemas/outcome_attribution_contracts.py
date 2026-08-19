"""Outcome attribution contracts — shared platform primitive K.

"AdaptixCore improved this agency" is either a measured claim or a slide. This
contract is what makes it the former: a named outcome, a defined population, an
observation, and an explicit statement of what the study design can and cannot
support.

The one thing it refuses to let a caller do is report correlation as causation.
:class:`OutcomeAttribution` carries ``method`` and ``assumptions``, and
``causal_claim_supported`` is derived from the method — a caller cannot set it
to ``True`` on an observation-only design just because the number moved the
right way.

Used by clinical QA, denial analysis, CRR, training, air safety, staffing,
shortages, transport, destination selection, grant outcomes, and AI suggestion
value.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OutcomeDirection(str, Enum):
    """Which way the measured outcome moved.

    ``INDETERMINATE`` is a first-class answer, not a failure to compute: an
    underpowered or confounded comparison that reports ``UNCHANGED`` is making a
    claim it cannot support.
    """

    IMPROVED = "improved"
    UNCHANGED = "unchanged"
    WORSENED = "worsened"
    INDETERMINATE = "indeterminate"


class AttributionMethod(str, Enum):
    """The study design behind an attribution, in ascending strength.

    * ``OBSERVED_ONLY`` — the number was measured. No comparison at all.
    * ``PRE_POST`` — before versus after, same population, no control. Confounded
      by anything else that changed at the same time.
    * ``MATCHED_COHORT`` — compared against a matched non-exposed group.
    * ``DIFFERENCE_IN_DIFFERENCES`` — change in exposed versus change in control.
    * ``RANDOMIZED`` — exposure was assigned at random.
    * ``MODEL_ESTIMATE`` — a model's estimate of effect. Explicitly *not* strong
      evidence of causation regardless of the model's confidence.
    """

    OBSERVED_ONLY = "observed_only"
    PRE_POST = "pre_post"
    MATCHED_COHORT = "matched_cohort"
    DIFFERENCE_IN_DIFFERENCES = "difference_in_differences"
    RANDOMIZED = "randomized"
    MODEL_ESTIMATE = "model_estimate"


#: Designs that can support a causal claim. Deliberately short.
CAUSAL_ATTRIBUTION_METHODS: frozenset[AttributionMethod] = frozenset(
    {
        AttributionMethod.DIFFERENCE_IN_DIFFERENCES,
        AttributionMethod.RANDOMIZED,
    }
)


def supports_causal_claim(method: AttributionMethod | str) -> bool:
    """Return ``True`` only for designs that can support a causal claim.

    Fails closed: an unrecognised method cannot support causation. A design
    nobody has classified is not evidence.
    """

    try:
        resolved = AttributionMethod(method)
    except ValueError:
        return False
    return resolved in CAUSAL_ATTRIBUTION_METHODS


class OutcomeDefinition(BaseModel):
    """What is being measured, precisely enough to reproduce.

    ``calculation_version`` is required so a number reported last quarter can be
    reproduced even after the definition changes. Without it, a dashboard that
    silently changed its denominator looks like an improvement.
    """

    model_config = ConfigDict(extra="forbid")

    outcome_id: str = Field(..., min_length=1)
    tenant_id: str | None = Field(
        default=None, description="None for a platform-standard outcome definition"
    )
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    unit: str = Field(
        ..., min_length=1, description="e.g. minutes, percent, count, usd"
    )
    higher_is_better: bool = Field(
        ...,
        description="Direction of improvement; response time and revenue disagree",
    )
    calculation_version: str = Field(..., min_length=1)
    exclusions: list[str] = Field(
        default_factory=list,
        description="Populations or records deliberately excluded, in plain language",
    )


class OutcomeObservation(BaseModel):
    """One measurement of one outcome over one window for one population."""

    model_config = ConfigDict(extra="forbid")

    observation_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    outcome_id: str = Field(..., min_length=1)
    population_id: str = Field(
        ..., min_length=1, description="The cohort this was measured over"
    )
    period_start: date
    period_end: date
    value: float
    sample_size: int = Field(
        ..., ge=0, description="Records behind the value; 0 means nothing was measured"
    )
    data_freshness_at: datetime = Field(
        ..., description="As-of instant of the underlying data"
    )
    calculation_version: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def _period_is_ordered(self) -> OutcomeObservation:
        if self.period_end < self.period_start:
            raise ValueError("period_end precedes period_start")
        return self


class OutcomeAttribution(BaseModel):
    """An attempt to attribute an outcome change to an intervention.

    ``causal_claim_supported`` is computed from ``method`` and cannot be
    overridden by the caller. That is the whole point of the model: the only way
    to report causation is to have used a design that supports it.
    """

    model_config = ConfigDict(extra="forbid")

    attribution_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    outcome_id: str = Field(..., min_length=1)
    intervention_type: str = Field(
        ...,
        min_length=1,
        description="What is credited, e.g. crr_smoke_alarm, ai_coding_suggestion",
    )
    intervention_id: str | None = None
    method: AttributionMethod
    direction: OutcomeDirection
    effect_size: float | None = Field(
        default=None, description="In the outcome's own unit; None when not estimated"
    )
    confidence_interval_low: float | None = None
    confidence_interval_high: float | None = None
    exposed_observation_id: str = Field(..., min_length=1)
    control_observation_id: str | None = Field(
        default=None, description="Required by every design except OBSERVED_ONLY"
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Plain-language assumptions the reader must know to trust this",
    )
    computed_at: datetime
    correlation_id: str = Field(..., min_length=1)

    @property
    def causal_claim_supported(self) -> bool:
        """Whether this design can support a causal claim. Derived, never set."""

        return supports_causal_claim(self.method)

    @model_validator(mode="after")
    def _design_requirements(self) -> OutcomeAttribution:
        if (
            self.method is not AttributionMethod.OBSERVED_ONLY
            and self.control_observation_id is None
            and self.method is not AttributionMethod.MODEL_ESTIMATE
        ):
            raise ValueError(
                f"method {self.method.value!r} is a comparison design and requires "
                "control_observation_id"
            )
        if (
            self.confidence_interval_low is not None
            and self.confidence_interval_high is not None
            and self.confidence_interval_high < self.confidence_interval_low
        ):
            raise ValueError(
                "confidence_interval_high precedes confidence_interval_low"
            )
        if self.method is AttributionMethod.PRE_POST and not self.assumptions:
            raise ValueError(
                "a PRE_POST attribution must state its assumptions: an uncontrolled "
                "before/after comparison is confounded by anything else that changed"
            )
        return self


__all__ = [
    "CAUSAL_ATTRIBUTION_METHODS",
    "AttributionMethod",
    "OutcomeAttribution",
    "OutcomeDefinition",
    "OutcomeDirection",
    "OutcomeObservation",
    "supports_causal_claim",
]
