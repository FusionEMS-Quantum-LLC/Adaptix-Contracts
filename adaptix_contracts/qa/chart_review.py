"""Every-chart review contracts: the sealed-revision review bundle and its findings.

Adaptix-QA-Service reviews every finalized ePCR chart. Adaptix-EPCR-Service owns
the chart and the deterministic clinical engines that read it, so ePCR computes
the deterministic findings for one SEALED chart revision and returns them as a
:class:`ChartReviewBundle`; QA persists them as the canonical review record.
A contextual (Cortex) stage adds :class:`ChartReviewFinding` rows of origin
``cortex`` afterwards. This module is the one shared shape for all of it, so no
service keeps a private clone of a review result.

Binding to a sealed revision
----------------------------
Every bundle names the sealed signed version it was computed from
(:class:`SealedChartRevision`) and the content hash of that seal. Every evidence
reference repeats the hash it was read under, and :class:`ChartReviewBundle`
refuses a reference read under any other hash. A finding therefore always says
which exact signed content it is about; a later amendment produces a new
revision and a new bundle, never an edited one.

Evidence states
---------------
:class:`EvidenceState` is the one vocabulary for what the chart shows about a
finding. ``unknown`` is never collapsed into ``not_documented`` or into false,
and ``ai_inference`` is reserved for Cortex findings: a model's interpretation
can never be stored as documented clinical fact (directive 2026-10-07 §10).

Engine results are explicit
---------------------------
An engine that could not run says so (``unavailable`` / ``failed`` with a
reason) and carries no findings. An engine that ran and found nothing is
``completed`` with an empty list. The two are never the same shape, so "the
check did not happen" can never read as "the chart passed".

PHI
---
Findings carry rule ids, coded severities, short non-identifying messages and
REFERENCES into the chart (record type, record id, NEMSIS element, timestamp).
They never carry the narrative, a patient name, a date of birth or any other
identifier: the chart stays in ePCR and is read there.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from enum import StrEnum
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from adaptix_contracts.qa.enums import FindingSeverity

#: Shape version of :class:`ChartReviewBundle`. Bump on any breaking change to
#: the bundle or the models it contains.
CHART_REVIEW_BUNDLE_VERSION: Final[Literal["1.0"]] = "1.0"


class EvidenceState(StrEnum):
    """What the chart shows about a finding.

    * ``documented`` - the chart records the fact the finding is about.
    * ``not_documented`` - the chart was read and the expected fact is absent.
    * ``contradictory`` - two charted facts cannot both be true.
    * ``unknown`` - the fact could not be established either way (an input
      could not be read, a required context is missing). Never a pass and
      never an absence.
    * ``ai_inference`` - a model's interpretation, not a charted fact.
    """

    DOCUMENTED = "documented"
    NOT_DOCUMENTED = "not_documented"
    CONTRADICTORY = "contradictory"
    UNKNOWN = "unknown"
    AI_INFERENCE = "ai_inference"


class ReviewRunState(StrEnum):
    """Lifecycle of one review run of one sealed chart revision."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SUPERSEDED = "superseded"


class ReviewEngineStatus(StrEnum):
    """Outcome of one engine over one sealed revision.

    Only ``completed`` may carry findings. ``not_applicable`` means the engine
    had nothing to evaluate on this chart (stated in the reason);
    ``unavailable`` means a dependency or configuration it needs was missing;
    ``failed`` means it raised. None of the last three is "no findings".
    """

    COMPLETED = "completed"
    NOT_APPLICABLE = "not_applicable"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


class FindingOrigin(StrEnum):
    """Which stage produced a finding."""

    DETERMINISTIC = "deterministic"
    CORTEX = "cortex"


class FindingOutcome(StrEnum):
    """What a finding asserts.

    * ``deviation`` - a requirement was not met.
    * ``met`` - a requirement was explicitly met (positive finding).
    * ``unable_to_evaluate`` - the rule applied but could not be evaluated;
      the evidence state says why.
    """

    DEVIATION = "deviation"
    MET = "met"
    UNABLE_TO_EVALUATE = "unable_to_evaluate"


class ChartEvidenceReference(BaseModel):
    """A pointer into the chart a finding is grounded on. Never a copy of it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_service: str = Field(
        ..., min_length=1, description="Service registry slug owning the record"
    )
    record_type: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Owning record type, e.g. vitals, medication_administration",
    )
    record_id: str | None = Field(
        default=None,
        max_length=128,
        description="Record primary key; None when the evidence is an absence",
    )
    element: str | None = Field(
        default=None,
        max_length=64,
        description="NEMSIS element id the value was read from, e.g. eVitals.06",
    )
    chart_section: str | None = Field(
        default=None,
        max_length=64,
        description="Chart workspace section the record is edited in",
    )
    recorded_at: datetime | None = Field(
        default=None,
        description="When the charted fact occurred; None when the chart has no time",
    )
    sealed_content_hash: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Content hash of the seal this reference was read under",
    )


class ProtocolCitation(BaseModel):
    """The published protocol version a protocol-dependent finding is judged by."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol_id: str = Field(..., min_length=1, max_length=64)
    protocol_version_id: str = Field(..., min_length=1, max_length=64)
    protocol_name: str = Field(..., min_length=1, max_length=255)
    version_label: str | None = Field(default=None, max_length=64)
    effective_from: date | None = None
    section: str | None = Field(default=None, max_length=255)
    item_id: str | None = Field(
        default=None, max_length=128, description="Rule or rubric item id"
    )
    citation_text: str | None = Field(default=None, max_length=1000)


class ChartReviewFinding(BaseModel):
    """One finding about one sealed chart revision.

    ``finding_key`` is stable for the same engine, rule and charted record, so a
    re-review of the same revision yields the same keys and a consumer can
    de-duplicate on them.

    ``confidence`` is meaningful only for a Cortex interpretation. A
    deterministic finding has no confidence: it is not "100% sure", it is the
    rule's answer, and inventing a percentage would be fabrication.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    finding_key: str = Field(..., min_length=1, max_length=128)
    engine: str = Field(..., min_length=1, max_length=64)
    rule_id: str = Field(..., min_length=1, max_length=128)
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Non-identifying explanation; never quotes the narrative",
    )
    severity: FindingSeverity
    engine_severity: str | None = Field(
        default=None,
        max_length=32,
        description="The engine's own severity label, kept for audit",
    )
    outcome: FindingOutcome
    evidence_state: EvidenceState
    origin: FindingOrigin
    evidence: tuple[ChartEvidenceReference, ...] = ()
    counter_evidence: tuple[ChartEvidenceReference, ...] = ()
    protocol_citation: ProtocolCitation | None = None
    reference: str | None = Field(
        default=None,
        max_length=500,
        description="Guideline or standard the rule cites",
    )
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    suggested_action: str | None = Field(
        default=None,
        max_length=500,
        description="What to verify or document; never a charted value",
    )

    @model_validator(mode="after")
    def _origin_and_state_agree(self) -> ChartReviewFinding:
        if self.origin is FindingOrigin.CORTEX:
            if self.evidence_state is not EvidenceState.AI_INFERENCE:
                raise ValueError(
                    "a cortex finding is an interpretation: its evidence_state "
                    "must be ai_inference"
                )
        else:
            if self.evidence_state is EvidenceState.AI_INFERENCE:
                raise ValueError("a deterministic finding may not claim ai_inference")
            if self.confidence is not None:
                raise ValueError("a deterministic finding carries no confidence")
        return self

    @model_validator(mode="after")
    def _evidence_matches_state(self) -> ChartReviewFinding:
        if self.evidence_state is EvidenceState.DOCUMENTED and not self.evidence:
            raise ValueError("a documented finding must reference the charted fact")
        if self.evidence_state is EvidenceState.CONTRADICTORY and not (
            self.evidence and self.counter_evidence
        ):
            raise ValueError(
                "a contradictory finding must reference both conflicting facts"
            )
        return self

    @model_validator(mode="after")
    def _met_is_informational(self) -> ChartReviewFinding:
        if (
            self.outcome is FindingOutcome.MET
            and self.severity is not FindingSeverity.INFORMATIONAL
        ):
            raise ValueError("a met requirement is informational, never a defect")
        return self


class ReviewEngineResult(BaseModel):
    """One engine's answer for one sealed revision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    engine: str = Field(..., min_length=1, max_length=64)
    engine_version: str = Field(..., min_length=1, max_length=128)
    status: ReviewEngineStatus
    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Required unless completed: why the engine did not answer",
    )
    findings: tuple[ChartReviewFinding, ...] = ()

    @model_validator(mode="after")
    def _status_is_honest(self) -> ReviewEngineResult:
        if self.status is not ReviewEngineStatus.COMPLETED:
            if not self.reason:
                raise ValueError(
                    f"engine status {self.status.value} must state its reason"
                )
            if self.findings:
                raise ValueError(
                    "only a completed engine may carry findings: a check that did "
                    "not run cannot report a result"
                )
        mismatched = [f.finding_key for f in self.findings if f.engine != self.engine]
        if mismatched:
            raise ValueError(
                f"findings attributed to another engine: {', '.join(mismatched)}"
            )
        keys = [f.finding_key for f in self.findings]
        if len(keys) != len(set(keys)):
            raise ValueError("finding_key values must be unique within an engine")
        return self


class SealedChartRevision(BaseModel):
    """The sealed signed chart version a review is bound to."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    chart_id: str = Field(..., min_length=1, max_length=64)
    signed_version_id: str = Field(..., min_length=1, max_length=64)
    signed_version_number: int = Field(..., ge=1)
    content_hash: str = Field(..., min_length=1, max_length=128)
    snapshot_algorithm: str = Field(..., min_length=1, max_length=32)
    sealed_at: datetime
    is_amendment: bool


class ChartReviewBundle(BaseModel):
    """Every deterministic engine's answer for one sealed chart revision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    bundle_version: Literal["1.0"] = CHART_REVIEW_BUNDLE_VERSION
    tenant_id: str = Field(..., min_length=1, max_length=64)
    revision: SealedChartRevision
    engines: tuple[ReviewEngineResult, ...] = Field(..., min_length=1)
    generated_at: datetime

    @model_validator(mode="after")
    def _engines_unique_and_bound(self) -> ChartReviewBundle:
        names = [result.engine for result in self.engines]
        if len(names) != len(set(names)):
            raise ValueError("each engine may answer once per bundle")
        sealed = self.revision.content_hash
        for result in self.engines:
            for finding in result.findings:
                for ref in (*finding.evidence, *finding.counter_evidence):
                    if ref.sealed_content_hash != sealed:
                        raise ValueError(
                            f"finding {finding.finding_key} cites evidence read "
                            "under a different seal than the bundle's revision"
                        )
        return self

    def engine_versions(self) -> dict[str, str]:
        """``engine -> engine_version`` for every engine in the bundle."""
        return {result.engine: result.engine_version for result in self.engines}

    def review_engine_version(self) -> str:
        """Deterministic identity of the engine set that produced this bundle.

        Equal for two bundles exactly when they carry the same bundle version
        and the same engines at the same versions, so a review run keyed on
        (tenant, chart, sealed revision, review_engine_version) is replay-safe
        and a new engine version produces a new run instead of a silent overwrite.
        """
        parts = [f"bundle={self.bundle_version}"]
        parts.extend(
            f"{name}={version}"
            for name, version in sorted(self.engine_versions().items())
        )
        digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
        return f"crb1:{digest[:32]}"


class CortexReviewProvenance(BaseModel):
    """Where a Cortex review answer came from."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_key: str = Field(..., min_length=1, max_length=128)
    model_id: str = Field(..., min_length=1, max_length=128)
    ai_request_id: str = Field(..., min_length=1, max_length=128)
    prompt_version: str = Field(..., min_length=1, max_length=64)
    discarded_items: int = Field(default=0, ge=0)


__all__ = [
    "CHART_REVIEW_BUNDLE_VERSION",
    "ChartEvidenceReference",
    "ChartReviewBundle",
    "ChartReviewFinding",
    "CortexReviewProvenance",
    "EvidenceState",
    "FindingOrigin",
    "FindingOutcome",
    "ProtocolCitation",
    "ReviewEngineResult",
    "ReviewEngineStatus",
    "ReviewRunState",
    "SealedChartRevision",
]
