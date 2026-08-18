"""Tests for the Play P02 pre-submit medical-necessity linter contracts.

Guards the shape of the assessment output, the enum vocabularies, the
verdict-vs-findings invariant, the denial-rate arithmetic invariant, and the
registration of the three cross-domain event types in
``adaptix_contracts.events.registry``.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from adaptix_contracts import necessity
from adaptix_contracts.events import registry as events_registry
from adaptix_contracts.necessity import (
    CHART_LOCK_BLOCKED,
    DENIAL_PREDICTED,
    NECESSITY_ASSESSED,
    ChartLockBlockedEvent,
    DenialPrediction,
    DenialPredictedEvent,
    LcdRule,
    MacRegion,
    NecessityAssessedEvent,
    NecessityAssessment,
    NecessityFinding,
    NecessityVerdict,
    PayerDenialPattern,
)


_UTC = timezone.utc
_NOW = datetime(2026, 8, 18, 12, 0, 0, tzinfo=_UTC)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


def test_verdict_values_are_stable_lowercase_strings() -> None:
    assert NecessityVerdict.CLEAR.value == "clear"
    assert NecessityVerdict.WARN.value == "warn"
    assert NecessityVerdict.BLOCK.value == "block"


def test_mac_region_covers_six_regions_with_cms_casing() -> None:
    values = {r.value for r in MacRegion}
    assert values == {
        "Novitas",
        "Palmetto",
        "NGS",
        "FirstCoast",
        "WPS",
        "Noridian",
    }


# ---------------------------------------------------------------------------
# NecessityAssessment invariants
# ---------------------------------------------------------------------------


def _clear_assessment() -> NecessityAssessment:
    return NecessityAssessment(
        assessment_id="asmt-1",
        tenant_id="t-1",
        chart_id="chart-1",
        payer_id=None,
        mac_region=MacRegion.NOVITAS,
        verdict=NecessityVerdict.CLEAR,
        findings=[],
        linter_version="p02-linter@2026.08.18-1",
        assessed_at=_NOW,
    )


def _blocking_finding() -> NecessityFinding:
    return NecessityFinding(
        finding_id="find-1",
        tenant_id="t-1",
        chart_id="chart-1",
        code="LCD_MISS_MISSING_ICD10",
        severity=NecessityVerdict.BLOCK,
        message="Chart does not include an ICD-10 covered by LCD L35162.",
        cpt_code="A0428",
        icd10_code=None,
        lcd_id="L35162",
        pattern_id=None,
        denial_prediction=None,
        blocks_submission=True,
        remediation_hint="Add a covered ICD-10 or reroute to a non-Medicare payer.",
        surfaced_at=_NOW,
    )


def test_clear_assessment_with_no_findings_is_accepted() -> None:
    asmt = _clear_assessment()
    assert asmt.verdict is NecessityVerdict.CLEAR


def test_block_verdict_requires_at_least_one_blocking_finding() -> None:
    with pytest.raises(ValueError, match="blocks_submission=True"):
        NecessityAssessment(
            assessment_id="asmt-2",
            tenant_id="t-1",
            chart_id="chart-1",
            mac_region=MacRegion.NOVITAS,
            verdict=NecessityVerdict.BLOCK,
            findings=[],
            linter_version="p02-linter@2026.08.18-1",
            assessed_at=_NOW,
        )


def test_block_verdict_with_blocking_finding_is_accepted() -> None:
    asmt = NecessityAssessment(
        assessment_id="asmt-3",
        tenant_id="t-1",
        chart_id="chart-1",
        mac_region=MacRegion.NOVITAS,
        verdict=NecessityVerdict.BLOCK,
        findings=[_blocking_finding()],
        linter_version="p02-linter@2026.08.18-1",
        assessed_at=_NOW,
    )
    assert asmt.verdict is NecessityVerdict.BLOCK
    assert len(asmt.findings) == 1


def test_clear_verdict_rejects_blocking_finding() -> None:
    with pytest.raises(ValueError, match="no blocking or WARN findings"):
        NecessityAssessment(
            assessment_id="asmt-4",
            tenant_id="t-1",
            chart_id="chart-1",
            mac_region=MacRegion.NOVITAS,
            verdict=NecessityVerdict.CLEAR,
            findings=[_blocking_finding()],
            linter_version="p02-linter@2026.08.18-1",
            assessed_at=_NOW,
        )


def test_warn_verdict_requires_warn_finding_and_no_blocking() -> None:
    warn_finding = NecessityFinding(
        finding_id="find-warn",
        tenant_id="t-1",
        chart_id="chart-1",
        code="WEAK_DOCUMENTATION",
        severity=NecessityVerdict.WARN,
        message="Documentation weakly supports A0428.",
        cpt_code="A0428",
        icd10_code="R55",
        lcd_id="L35162",
        pattern_id=None,
        denial_prediction=None,
        blocks_submission=False,
        remediation_hint="Add signs/symptoms narrative.",
        surfaced_at=_NOW,
    )
    asmt = NecessityAssessment(
        assessment_id="asmt-5",
        tenant_id="t-1",
        chart_id="chart-1",
        mac_region=MacRegion.NOVITAS,
        verdict=NecessityVerdict.WARN,
        findings=[warn_finding],
        linter_version="p02-linter@2026.08.18-1",
        assessed_at=_NOW,
    )
    assert asmt.verdict is NecessityVerdict.WARN


# ---------------------------------------------------------------------------
# PayerDenialPattern arithmetic invariants
# ---------------------------------------------------------------------------


def _pattern(**overrides: object) -> PayerDenialPattern:
    defaults = dict(
        pattern_id="ptn-1",
        tenant_id="t-1",
        payer_id="payer-medicare",
        payer_name="Medicare Part B",
        mac_region=MacRegion.NOVITAS,
        cpt_code="A0428",
        icd10_code="R55",
        modifier=None,
        sample_size=100,
        denial_count=68,
        historical_denial_rate=0.68,
        top_denial_reason_codes=["50", "16"],
        window_start=datetime(2026, 5, 1, tzinfo=_UTC),
        window_end=datetime(2026, 8, 1, tzinfo=_UTC),
        computed_at=_NOW,
    )
    defaults.update(overrides)
    return PayerDenialPattern(**defaults)  # type: ignore[arg-type]


def test_payer_pattern_rate_must_match_denial_over_sample() -> None:
    with pytest.raises(ValueError, match="denial_count / sample_size"):
        _pattern(historical_denial_rate=0.10)


def test_payer_pattern_rejects_denial_count_over_sample_size() -> None:
    with pytest.raises(ValueError, match="cannot exceed sample_size"):
        _pattern(sample_size=10, denial_count=11, historical_denial_rate=1.1)


def test_payer_pattern_rejects_window_end_before_start() -> None:
    with pytest.raises(ValueError, match="window_end must be on or after"):
        _pattern(
            window_start=datetime(2026, 8, 1, tzinfo=_UTC),
            window_end=datetime(2026, 7, 1, tzinfo=_UTC),
        )


def test_payer_pattern_happy_path_is_accepted() -> None:
    p = _pattern()
    assert p.historical_denial_rate == pytest.approx(0.68)
    assert p.denial_count == 68


# ---------------------------------------------------------------------------
# LcdRule
# ---------------------------------------------------------------------------


def test_lcd_rule_carries_mac_region_and_revision() -> None:
    rule = LcdRule(
        lcd_id="L35162",
        mac_region=MacRegion.NOVITAS,
        cpt_code="A0428",
        title="Ambulance Services (Ground)",
        effective_date=datetime(2026, 1, 1, tzinfo=_UTC),
        revision=7,
        covered_icd10_codes=["R55", "I63.9"],
        required_signs_symptoms=["altered mental status", "syncope"],
        documentation_requirements=["origin address", "destination address"],
        source_url="https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?LCDId=35162",
    )
    assert rule.mac_region is MacRegion.NOVITAS
    assert rule.revision == 7


# ---------------------------------------------------------------------------
# DenialPrediction
# ---------------------------------------------------------------------------


def test_denial_prediction_probability_bounds() -> None:
    with pytest.raises(ValueError):
        DenialPrediction(
            prediction_id="pred-1",
            tenant_id="t-1",
            chart_id="chart-1",
            claim_line_id=None,
            payer_id="payer-medicare",
            cpt_code="A0428",
            icd10_code="R55",
            mac_region=MacRegion.NOVITAS,
            modifier=None,
            probability=1.5,
            expected_denial_amount_cents=42000,
            based_on_pattern_id="ptn-1",
            top_denial_reason_codes=[],
            predicted_at=_NOW,
        )


def test_denial_prediction_amount_in_cents_not_floats() -> None:
    pred = DenialPrediction(
        prediction_id="pred-2",
        tenant_id="t-1",
        chart_id="chart-1",
        claim_line_id="line-1",
        payer_id="payer-medicare",
        cpt_code="A0428",
        icd10_code="R55",
        mac_region=MacRegion.NOVITAS,
        modifier=None,
        probability=0.68,
        expected_denial_amount_cents=42000,
        based_on_pattern_id="ptn-1",
        top_denial_reason_codes=["50"],
        predicted_at=_NOW,
    )
    assert isinstance(pred.expected_denial_amount_cents, int)
    assert pred.expected_denial_amount_cents == 42000


# ---------------------------------------------------------------------------
# Event constants + registry wiring
# ---------------------------------------------------------------------------


def test_event_type_constants_are_canonical_strings() -> None:
    assert NECESSITY_ASSESSED == "necessity.assessed"
    assert CHART_LOCK_BLOCKED == "chart.lock.blocked"
    assert DENIAL_PREDICTED == "denial.predicted"


@pytest.mark.parametrize(
    "event_type",
    [NECESSITY_ASSESSED, CHART_LOCK_BLOCKED, DENIAL_PREDICTED],
)
def test_event_is_registered_with_epcr_source(event_type: str) -> None:
    assert events_registry.is_registered(event_type)
    meta = events_registry.ALL_EVENTS[event_type]
    assert meta["source_service"] == "epcr"
    assert meta["version"] == "1.0"
    producer = events_registry.producer_of(event_type)
    assert producer is not None
    assert producer.slug == "epcr"


# ---------------------------------------------------------------------------
# Event payload models roundtrip
# ---------------------------------------------------------------------------


def test_necessity_assessed_event_carries_full_assessment() -> None:
    evt = NecessityAssessedEvent(
        tenant_id="t-1",
        chart_id="chart-1",
        assessment=_clear_assessment(),
        occurred_at=_NOW,
    )
    assert evt.event_type == NECESSITY_ASSESSED
    assert evt.assessment.verdict is NecessityVerdict.CLEAR


def test_chart_lock_blocked_event_carries_blocking_findings() -> None:
    evt = ChartLockBlockedEvent(
        tenant_id="t-1",
        chart_id="chart-1",
        assessment_id="asmt-3",
        blocking_findings=[_blocking_finding()],
        mac_region=MacRegion.NOVITAS,
        attempted_by_user_id="user-42",
        occurred_at=_NOW,
    )
    assert evt.event_type == CHART_LOCK_BLOCKED
    assert evt.verdict is NecessityVerdict.BLOCK
    assert len(evt.blocking_findings) == 1


def test_denial_predicted_event_carries_single_prediction() -> None:
    pred = DenialPrediction(
        prediction_id="pred-3",
        tenant_id="t-1",
        chart_id="chart-1",
        claim_line_id="line-1",
        payer_id="payer-medicare",
        cpt_code="A0428",
        icd10_code="R55",
        mac_region=MacRegion.NOVITAS,
        modifier=None,
        probability=0.68,
        expected_denial_amount_cents=42000,
        based_on_pattern_id="ptn-1",
        top_denial_reason_codes=["50"],
        predicted_at=_NOW,
    )
    evt = DenialPredictedEvent(
        tenant_id="t-1",
        chart_id="chart-1",
        assessment_id="asmt-3",
        prediction=pred,
        occurred_at=_NOW,
    )
    assert evt.event_type == DENIAL_PREDICTED
    assert evt.prediction.probability == pytest.approx(0.68)


# ---------------------------------------------------------------------------
# Subpackage surface
# ---------------------------------------------------------------------------


def test_necessity_subpackage_surface_is_stable() -> None:
    expected = {
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
    }
    assert set(necessity.__all__) == expected
    for name in expected:
        assert hasattr(necessity, name)
