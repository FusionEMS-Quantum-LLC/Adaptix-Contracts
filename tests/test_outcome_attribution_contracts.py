"""Contract tests for outcome attribution (shared platform primitive K)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from adaptix_contracts import schemas
from adaptix_contracts.schemas.outcome_attribution_contracts import (
    AttributionMethod,
    OutcomeAttribution,
    OutcomeDefinition,
    OutcomeDirection,
    OutcomeObservation,
    supports_causal_claim,
)
import pytest
from pydantic import ValidationError

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)


def _attribution(**overrides: object) -> OutcomeAttribution:
    payload: dict[str, object] = {
        "attribution_id": "attr-1",
        "tenant_id": "tenant-a",
        "outcome_id": "outcome-1",
        "intervention_type": "crr_smoke_alarm",
        "method": AttributionMethod.OBSERVED_ONLY,
        "direction": OutcomeDirection.IMPROVED,
        "exposed_observation_id": "obs-1",
        "computed_at": NOW,
        "correlation_id": "corr-1",
    }
    payload.update(overrides)
    return OutcomeAttribution(**payload)  # type: ignore[arg-type]


class TestCausalClaims:
    @pytest.mark.parametrize(
        "method",
        [
            AttributionMethod.DIFFERENCE_IN_DIFFERENCES,
            AttributionMethod.RANDOMIZED,
        ],
    )
    def test_controlled_designs_may_claim_causation(
        self, method: AttributionMethod
    ) -> None:
        assert supports_causal_claim(method)

    @pytest.mark.parametrize(
        "method",
        [
            AttributionMethod.OBSERVED_ONLY,
            AttributionMethod.PRE_POST,
            AttributionMethod.MATCHED_COHORT,
            AttributionMethod.MODEL_ESTIMATE,
        ],
    )
    def test_weaker_designs_may_not(self, method: AttributionMethod) -> None:
        assert not supports_causal_claim(method)

    def test_a_confident_model_still_cannot_claim_causation(self) -> None:
        attribution = _attribution(
            method=AttributionMethod.MODEL_ESTIMATE, effect_size=-3.4
        )
        assert not attribution.causal_claim_supported

    def test_an_observation_only_attribution_reports_no_causation(self) -> None:
        assert not _attribution().causal_claim_supported

    def test_a_randomized_attribution_reports_causation(self) -> None:
        attribution = _attribution(
            method=AttributionMethod.RANDOMIZED, control_observation_id="obs-2"
        )
        assert attribution.causal_claim_supported

    def test_causal_claim_is_derived_and_cannot_be_set(self) -> None:
        """The only way to report causation is to have used a design for it."""

        assert "causal_claim_supported" not in OutcomeAttribution.model_fields
        with pytest.raises(ValidationError):
            _attribution(causal_claim_supported=True)

    def test_unknown_method_fails_closed(self) -> None:
        assert not supports_causal_claim("vibes")

    def test_every_method_is_classified(self) -> None:
        for method in AttributionMethod:
            assert isinstance(supports_causal_claim(method), bool)


class TestDesignRequirements:
    def test_a_comparison_design_needs_a_control(self) -> None:
        with pytest.raises(ValidationError, match="requires control_observation_id"):
            _attribution(method=AttributionMethod.MATCHED_COHORT)

    def test_observation_only_needs_no_control(self) -> None:
        assert _attribution().control_observation_id is None

    def test_model_estimate_needs_no_control(self) -> None:
        assert _attribution(method=AttributionMethod.MODEL_ESTIMATE).method is (
            AttributionMethod.MODEL_ESTIMATE
        )

    def test_pre_post_must_state_its_assumptions(self) -> None:
        """An uncontrolled before/after is confounded by everything else."""

        with pytest.raises(ValidationError, match="must state its assumptions"):
            _attribution(
                method=AttributionMethod.PRE_POST, control_observation_id="obs-2"
            )

    def test_pre_post_with_assumptions_is_valid(self) -> None:
        attribution = _attribution(
            method=AttributionMethod.PRE_POST,
            control_observation_id="obs-2",
            assumptions=["No staffing model change occurred in the same window."],
        )
        assert attribution.assumptions

    def test_reversed_confidence_interval_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="confidence_interval_high precedes"):
            _attribution(
                confidence_interval_low=1.0,
                confidence_interval_high=0.5,
            )

    def test_indeterminate_is_a_legitimate_answer(self) -> None:
        attribution = _attribution(direction=OutcomeDirection.INDETERMINATE)
        assert attribution.direction is OutcomeDirection.INDETERMINATE


class TestOutcomeDefinitionAndObservation:
    def test_definition_pins_its_calculation_version(self) -> None:
        definition = OutcomeDefinition(
            outcome_id="outcome-1",
            name="90th percentile response time",
            description="Time from dispatch to on-scene, 90th percentile.",
            unit="minutes",
            higher_is_better=False,
            calculation_version="1.3.0",
            exclusions=["Mutual-aid responses outside the district"],
        )
        assert definition.higher_is_better is False
        assert definition.tenant_id is None

    def test_observation_period_must_be_ordered(self) -> None:
        with pytest.raises(ValidationError, match="period_end precedes period_start"):
            OutcomeObservation(
                observation_id="obs-1",
                tenant_id="tenant-a",
                outcome_id="outcome-1",
                population_id="pop-1",
                period_start=date(2026, 7, 1),
                period_end=date(2026, 6, 1),
                value=9.4,
                sample_size=812,
                data_freshness_at=NOW,
                calculation_version="1.3.0",
            )

    def test_a_zero_sample_observation_is_representable(self) -> None:
        """Nothing measured is a real answer and must not be faked as a value."""

        observation = OutcomeObservation(
            observation_id="obs-1",
            tenant_id="tenant-a",
            outcome_id="outcome-1",
            population_id="pop-1",
            period_start=date(2026, 6, 1),
            period_end=date(2026, 6, 30),
            value=0.0,
            sample_size=0,
            data_freshness_at=NOW,
            calculation_version="1.3.0",
        )
        assert observation.sample_size == 0


def test_surface_is_exported_from_the_package_root() -> None:
    for name in (
        "AttributionMethod",
        "OutcomeAttribution",
        "OutcomeDefinition",
        "OutcomeDirection",
        "OutcomeObservation",
        "CAUSAL_ATTRIBUTION_METHODS",
    ):
        assert name in schemas.__all__
        assert hasattr(schemas, name)
