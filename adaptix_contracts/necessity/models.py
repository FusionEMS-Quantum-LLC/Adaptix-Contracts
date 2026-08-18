"""Necessity domain models — Play P02 pre-submit medical-necessity linter.

These Pydantic contracts define the shape of the linter's output at the ePCR
pre-submit gate and the reference data (LCD rules, payer denial patterns) that
feeds it. Contract-only: no persistence, no HTTP, no policy logic.

Design invariants:

* ``NecessityAssessment.verdict == BLOCK`` implies at least one finding whose
  ``blocks_submission`` is True — enforced by ``model_validator``.
* ``NecessityAssessment.findings`` is ordered by descending severity (the
  linter surfaces block-level findings first); the model does not sort — it
  requires the producer to emit them already ordered so a downstream diff
  against a previous assessment is stable.
* ``DenialPrediction.probability`` is a float in ``[0.0, 1.0]``. ``0.0``
  means "no historical denials for this pattern" — it is NOT a sentinel for
  "no data". Absence of data is expressed by omitting the prediction.
* All monetary amounts are USD cents (int) — never floats, per platform rule.

Nothing here is tenant-scoped implicitly; every model carries ``tenant_id``
explicitly because the linter runs across many agencies and its output rides
the shared event bus.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from adaptix_contracts.necessity.enums import MacRegion, NecessityVerdict


# ---------------------------------------------------------------------------
# Reference data — LCD rules and historical payer denial patterns
# ---------------------------------------------------------------------------


class LcdRule(BaseModel):
    """Local Coverage Determination rule from a MAC.

    An LCD binds a CPT/HCPCS code (ambulance transport level, ALS/BLS
    assessment, etc.) to the ICD-10 diagnoses the MAC will cover and the
    documentation requirements to substantiate that coverage. The linter
    matches the chart's coded diagnoses and signs/symptoms against
    ``covered_icd10_codes`` and ``required_signs_symptoms`` to decide whether
    submitting the claim would be covered under this LCD.

    A rule is scoped to a single MAC region; agencies in multiple MAC regions
    hold multiple ``LcdRule`` rows per CPT. ``revision`` is the CMS-published
    revision number for the LCD, not an internal version.
    """

    lcd_id: str = Field(..., description="CMS LCD identifier, e.g. 'L35162'")
    mac_region: MacRegion = Field(
        ..., description="MAC jurisdiction this LCD applies to"
    )
    cpt_code: str = Field(
        ..., description="CPT/HCPCS code the rule adjudicates (e.g. 'A0428')"
    )
    title: str = Field(..., description="Human-readable LCD title from CMS")
    effective_date: datetime = Field(
        ..., description="First date this LCD revision is in force"
    )
    revision: int = Field(
        ..., ge=1, description="CMS-published revision number for this LCD"
    )
    covered_icd10_codes: list[str] = Field(
        default_factory=list,
        description="ICD-10-CM codes explicitly listed as medically necessary",
    )
    required_signs_symptoms: list[str] = Field(
        default_factory=list,
        description=(
            "Signs/symptoms the documentation must show to substantiate "
            "necessity when only a covered ICD-10 is present"
        ),
    )
    documentation_requirements: list[str] = Field(
        default_factory=list,
        description="Narrative/attestation elements the MAC requires on file",
    )
    source_url: Optional[str] = Field(
        None, description="CMS Coverage Database URL for this LCD revision"
    )

    model_config = ConfigDict(from_attributes=True)


class PayerDenialPattern(BaseModel):
    """Historical denial pattern for a (payer, CPT, ICD-10, MAC) combination.

    The linter uses this to compute ``DenialPrediction.probability``: if the
    combination has denied 68 of the last 100 submissions to this payer in
    this MAC, ``historical_denial_rate`` is ``0.68`` and the linter can BLOCK
    with an evidence-backed reason instead of a heuristic guess.

    ``window_start`` / ``window_end`` bound the observation window used to
    compute the rate so a consumer can tell whether a pattern is based on 30
    days of data or 3 years. ``sample_size`` is the denominator; the linter
    must ignore patterns with a sample size below its configured floor rather
    than treating "3 of 4 denied = 75%" as a real signal.
    """

    pattern_id: str = Field(..., description="Stable identifier for this pattern row")
    tenant_id: str = Field(
        ..., description="Agency (tenant) the pattern was computed for"
    )
    payer_id: str = Field(..., description="Adaptix payer identifier")
    payer_name: str = Field(..., description="Payer display name")
    mac_region: MacRegion = Field(
        ..., description="MAC jurisdiction the historical claims fell under"
    )
    cpt_code: str = Field(..., description="CPT/HCPCS code observed on the claim line")
    icd10_code: str = Field(..., description="Primary ICD-10-CM code observed")
    modifier: Optional[str] = Field(
        None, description="Claim-line modifier if the pattern is modifier-scoped"
    )
    sample_size: int = Field(..., ge=1, description="Number of claims in the window")
    denial_count: int = Field(
        ..., ge=0, description="Denials among ``sample_size`` claims"
    )
    historical_denial_rate: float = Field(
        ..., ge=0.0, le=1.0, description="denial_count / sample_size, precomputed"
    )
    top_denial_reason_codes: list[str] = Field(
        default_factory=list,
        description="CARC/RARC codes cited most often on the denials in-window",
    )
    window_start: datetime = Field(..., description="Observation window start (UTC)")
    window_end: datetime = Field(..., description="Observation window end (UTC)")
    computed_at: datetime = Field(
        ..., description="When this row was (re)computed by the analytics pipeline"
    )

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def _check_denial_count_within_sample(self) -> "PayerDenialPattern":
        if self.denial_count > self.sample_size:
            raise ValueError(
                f"denial_count ({self.denial_count}) cannot exceed sample_size "
                f"({self.sample_size})"
            )
        expected = self.denial_count / self.sample_size
        # Tolerate rounding drift from upstream analytics (typically 6 dp).
        if abs(expected - self.historical_denial_rate) > 1e-4:
            raise ValueError(
                "historical_denial_rate does not match denial_count / sample_size "
                f"({expected:.6f} vs {self.historical_denial_rate:.6f})"
            )
        if self.window_end < self.window_start:
            raise ValueError("window_end must be on or after window_start")
        return self


# ---------------------------------------------------------------------------
# Linter output — assessment and per-finding rows
# ---------------------------------------------------------------------------


class DenialPrediction(BaseModel):
    """Predicted denial for a single claim line at pre-submit.

    Attached to a ``NecessityFinding`` when the finding is grounded in a
    historical ``PayerDenialPattern``. ``expected_denial_amount_cents`` is the
    line-level allowed amount that would be at risk if the claim were
    submitted as-is; the linter uses it to rank findings so the reviewer
    tackles the highest-dollar risks first.
    """

    prediction_id: str = Field(..., description="Stable id for this prediction")
    tenant_id: str
    chart_id: str = Field(..., description="ePCR chart the prediction is bound to")
    claim_line_id: Optional[str] = Field(
        None,
        description=(
            "Prospective claim-line identifier when the pre-submit linter "
            "runs against a drafted claim; None when running purely against "
            "the chart"
        ),
    )
    payer_id: str
    cpt_code: str
    icd10_code: str
    mac_region: MacRegion
    modifier: Optional[str] = None
    probability: float = Field(
        ..., ge=0.0, le=1.0, description="Predicted denial probability in [0,1]"
    )
    expected_denial_amount_cents: int = Field(
        ...,
        ge=0,
        description="Line-level allowed amount at risk in USD cents (no floats)",
    )
    based_on_pattern_id: Optional[str] = Field(
        None,
        description=(
            "``PayerDenialPattern.pattern_id`` this prediction is grounded in. "
            "None only when the prediction comes from an LCD rule miss with "
            "no historical pattern (e.g. brand-new CPT/ICD combination)."
        ),
    )
    top_denial_reason_codes: list[str] = Field(default_factory=list)
    predicted_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NecessityFinding(BaseModel):
    """One row in a ``NecessityAssessment``.

    A finding is either LCD-grounded (``lcd_id`` set) or pattern-grounded
    (``pattern_id`` set) — the two are not mutually exclusive; a finding may
    cite both an LCD miss and a matching historical denial pattern.
    ``blocks_submission`` is a per-finding hard/soft flag; the aggregate
    verdict on ``NecessityAssessment.verdict`` is derived from these.
    """

    finding_id: str
    tenant_id: str
    chart_id: str
    code: str = Field(
        ...,
        description=(
            "Machine-readable finding code (e.g. 'LCD_MISS_MISSING_ICD10', "
            "'PATTERN_HIGH_DENIAL_RATE', 'MODIFIER_REQUIRED'). Stable across "
            "linter versions so consumers can filter/route on it."
        ),
    )
    severity: NecessityVerdict = Field(
        ...,
        description=(
            "Per-finding severity. When aggregated, the assessment verdict is "
            "the maximum of finding severities (BLOCK > WARN > CLEAR)."
        ),
    )
    message: str = Field(..., description="Human-readable message for the reviewer UI")
    cpt_code: Optional[str] = Field(
        None, description="CPT/HCPCS the finding is anchored to"
    )
    icd10_code: Optional[str] = Field(
        None, description="ICD-10-CM the finding is anchored to"
    )
    lcd_id: Optional[str] = Field(
        None, description="``LcdRule.lcd_id`` when the finding is LCD-grounded"
    )
    pattern_id: Optional[str] = Field(
        None,
        description="``PayerDenialPattern.pattern_id`` when pattern-grounded",
    )
    denial_prediction: Optional[DenialPrediction] = Field(
        None,
        description="Attached prediction when the finding forecasts a denial",
    )
    blocks_submission: bool = Field(
        ...,
        description=(
            "True iff this finding must prevent chart lock / claim submission. "
            "Derived from ``severity == BLOCK`` in ordinary flows; kept as an "
            "explicit field so a governance override can force-block a WARN "
            "or downgrade a BLOCK without losing the severity signal."
        ),
    )
    remediation_hint: Optional[str] = Field(
        None,
        description=(
            "Short reviewer-facing hint on what to fix, e.g. "
            "'Add signs/symptoms to justify BLS assessment' — plain English, "
            "no code snippets."
        ),
    )
    surfaced_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NecessityAssessment(BaseModel):
    """Aggregated pre-submit medical-necessity assessment for one ePCR chart.

    Emitted once per linter run at the pre-submit / chart-lock boundary. A
    subsequent edit re-runs the linter and emits a new assessment with a new
    ``assessment_id`` — assessments are append-only; consumers pick the
    highest ``assessed_at`` per ``chart_id``.

    ``verdict`` is the aggregate:

    * ``CLEAR`` iff ``findings`` is empty OR every finding is severity CLEAR.
    * ``WARN``  iff at least one finding is WARN and none are BLOCK.
    * ``BLOCK`` iff at least one finding is BLOCK — enforced by validator.
    """

    assessment_id: str = Field(..., description="Stable id for this assessment run")
    tenant_id: str
    chart_id: str
    payer_id: Optional[str] = Field(
        None,
        description=(
            "Primary payer the assessment was scoped to when known at "
            "pre-submit; None during pre-billing chart lock when payer has "
            "not yet been assigned."
        ),
    )
    mac_region: MacRegion = Field(
        ...,
        description=(
            "MAC region derived from the servicing provider's state. Every "
            "assessment is MAC-scoped; a cross-MAC agency runs the linter "
            "once per applicable MAC and emits distinct assessments."
        ),
    )
    verdict: NecessityVerdict
    findings: list[NecessityFinding] = Field(
        default_factory=list,
        description=(
            "Findings ordered by descending severity by the producer. The "
            "model does not re-sort — consumers may rely on the incoming "
            "order for stable diffs against a previous assessment."
        ),
    )
    linter_version: str = Field(
        ...,
        description=(
            "Version string for the linter that produced this assessment "
            "(e.g. 'p02-linter@2026.08.18-1'). Included in every emitted "
            "event so a consumer can attribute a false BLOCK to a specific "
            "linter release."
        ),
    )
    assessed_at: datetime = Field(
        ..., description="UTC time the linter completed this run"
    )

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def _check_verdict_matches_findings(self) -> "NecessityAssessment":
        blocking = [f for f in self.findings if f.blocks_submission]
        has_warn = any(
            f.severity is NecessityVerdict.WARN and not f.blocks_submission
            for f in self.findings
        )
        if self.verdict is NecessityVerdict.BLOCK and not blocking:
            raise ValueError(
                "verdict=BLOCK requires at least one finding with "
                "blocks_submission=True"
            )
        if self.verdict is NecessityVerdict.WARN and (blocking or not has_warn):
            raise ValueError(
                "verdict=WARN requires at least one WARN finding and no "
                "blocking findings"
            )
        if self.verdict is NecessityVerdict.CLEAR and (blocking or has_warn):
            raise ValueError("verdict=CLEAR requires no blocking or WARN findings")
        return self


__all__ = [
    "DenialPrediction",
    "LcdRule",
    "NecessityAssessment",
    "NecessityFinding",
    "PayerDenialPattern",
]
