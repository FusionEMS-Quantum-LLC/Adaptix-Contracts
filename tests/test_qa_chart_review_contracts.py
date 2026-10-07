"""Contract tests for the every-chart review bundle, findings and lifecycle events."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from adaptix_contracts.events.registry import is_registered, producer_of
from adaptix_contracts.qa import (
    CHART_REVIEW_BUNDLE_VERSION,
    QA_CHART_REVIEW_COMPLETED,
    QA_CHART_REVIEW_EVENTS,
    QA_CHART_REVIEW_FAILED,
    QA_CHART_REVIEW_RECONCILED,
    QA_SERVICE_SLUG,
    ChartEvidenceReference,
    ChartReviewBundle,
    ChartReviewFinding,
    CortexReviewProvenance,
    EvidenceState,
    FindingOrigin,
    FindingOutcome,
    FindingSeverity,
    ProtocolCitation,
    QaChartReviewLifecyclePayload,
    ReviewEngineResult,
    ReviewEngineStatus,
    ReviewRunState,
    SealedChartRevision,
    build_qa_chart_review_event,
)
from adaptix_contracts.schemas.service_registry import SERVICE_BY_SLUG

NOW = datetime(2026, 10, 7, 4, 0, tzinfo=UTC)
SEAL = "sha256:sealed-content"


def _ref(**overrides: object) -> ChartEvidenceReference:
    values: dict[str, object] = {
        "source_service": "epcr",
        "record_type": "vitals",
        "record_id": "vit-1",
        "element": "eVitals.06",
        "chart_section": "vitals",
        "recorded_at": NOW,
        "sealed_content_hash": SEAL,
    }
    values.update(overrides)
    return ChartEvidenceReference.model_validate(values)


def _finding(**overrides: object) -> ChartReviewFinding:
    values: dict[str, object] = {
        "finding_key": "clinical_rules:vitals.hypotension_adult:vit-1",
        "engine": "clinical_rules",
        "rule_id": "vitals.hypotension_adult",
        "title": "Hypotension",
        "message": "Systolic blood pressure below the configured threshold.",
        "severity": FindingSeverity.MAJOR,
        "engine_severity": "high",
        "outcome": FindingOutcome.DEVIATION,
        "evidence_state": EvidenceState.DOCUMENTED,
        "origin": FindingOrigin.DETERMINISTIC,
        "evidence": (_ref(),),
    }
    values.update(overrides)
    return ChartReviewFinding.model_validate(values)


def _revision(**overrides: object) -> SealedChartRevision:
    values: dict[str, object] = {
        "chart_id": "chart-1",
        "signed_version_id": "sv-1",
        "signed_version_number": 1,
        "content_hash": SEAL,
        "snapshot_algorithm": "v5",
        "sealed_at": NOW,
        "is_amendment": False,
    }
    values.update(overrides)
    return SealedChartRevision.model_validate(values)


def _bundle(*engines: ReviewEngineResult) -> ChartReviewBundle:
    return ChartReviewBundle(
        tenant_id="tenant-a",
        revision=_revision(),
        engines=engines
        or (
            ReviewEngineResult(
                engine="clinical_rules",
                engine_version="default:2026.09.1",
                status=ReviewEngineStatus.COMPLETED,
                findings=(_finding(),),
            ),
        ),
        generated_at=NOW,
    )


class TestFindingEvidenceStates:
    def test_documented_finding_with_evidence_is_valid(self) -> None:
        finding = _finding()
        assert finding.evidence_state is EvidenceState.DOCUMENTED
        assert finding.confidence is None

    def test_documented_finding_without_evidence_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="documented finding must reference"):
            _finding(evidence=())

    def test_contradiction_requires_both_sides(self) -> None:
        with pytest.raises(ValidationError, match="both conflicting facts"):
            _finding(evidence_state=EvidenceState.CONTRADICTORY)
        finding = _finding(
            evidence_state=EvidenceState.CONTRADICTORY,
            counter_evidence=(
                _ref(record_type="narrative", record_id=None, element=None),
            ),
        )
        assert finding.counter_evidence[0].record_type == "narrative"

    def test_not_documented_may_reference_nothing(self) -> None:
        finding = _finding(evidence_state=EvidenceState.NOT_DOCUMENTED, evidence=())
        assert finding.evidence == ()

    def test_unknown_is_its_own_state(self) -> None:
        finding = _finding(
            evidence_state=EvidenceState.UNKNOWN,
            outcome=FindingOutcome.UNABLE_TO_EVALUATE,
            evidence=(),
        )
        assert finding.evidence_state is EvidenceState.UNKNOWN
        assert finding.outcome is FindingOutcome.UNABLE_TO_EVALUATE

    def test_deterministic_finding_cannot_claim_ai_inference(self) -> None:
        with pytest.raises(ValidationError, match="may not claim ai_inference"):
            _finding(evidence_state=EvidenceState.AI_INFERENCE)

    def test_deterministic_finding_carries_no_confidence(self) -> None:
        with pytest.raises(ValidationError, match="carries no confidence"):
            _finding(confidence=1.0)

    def test_cortex_finding_must_be_ai_inference(self) -> None:
        with pytest.raises(ValidationError, match="must be ai_inference"):
            _finding(origin=FindingOrigin.CORTEX, confidence=0.6)
        finding = _finding(
            origin=FindingOrigin.CORTEX,
            evidence_state=EvidenceState.AI_INFERENCE,
            confidence=0.6,
        )
        assert finding.confidence == 0.6

    def test_confidence_bounds(self) -> None:
        with pytest.raises(ValidationError):
            _finding(
                origin=FindingOrigin.CORTEX,
                evidence_state=EvidenceState.AI_INFERENCE,
                confidence=1.5,
            )

    def test_met_requirement_is_informational(self) -> None:
        with pytest.raises(ValidationError, match="informational"):
            _finding(outcome=FindingOutcome.MET)
        finding = _finding(
            outcome=FindingOutcome.MET, severity=FindingSeverity.INFORMATIONAL
        )
        assert finding.outcome is FindingOutcome.MET

    def test_signal_reports_a_documented_condition(self) -> None:
        finding = _finding(
            outcome=FindingOutcome.SIGNAL,
            severity=FindingSeverity.CRITICAL,
            engine_severity="critical",
        )
        assert finding.outcome is FindingOutcome.SIGNAL
        assert finding.severity is FindingSeverity.CRITICAL

    @pytest.mark.parametrize(
        "state",
        [
            EvidenceState.NOT_DOCUMENTED,
            EvidenceState.UNKNOWN,
        ],
    )
    def test_signal_must_be_documented(self, state: EvidenceState) -> None:
        with pytest.raises(ValidationError, match="must be documented"):
            _finding(outcome=FindingOutcome.SIGNAL, evidence_state=state)

    def test_signal_without_evidence_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="documented finding must reference"):
            _finding(outcome=FindingOutcome.SIGNAL, evidence=())

    def test_unknown_fields_are_refused(self) -> None:
        with pytest.raises(ValidationError):
            ChartReviewFinding.model_validate(
                {**_finding().model_dump(), "patient_name": "x"}
            )

    def test_protocol_citation_round_trips(self) -> None:
        citation = ProtocolCitation(
            protocol_id="p-1",
            protocol_version_id="pv-3",
            protocol_name="Adult Hypotension",
            version_label="2026.1",
            effective_from=date(2026, 1, 1),
            section="4.2",
            item_id="fluid_bolus",
        )
        finding = _finding(protocol_citation=citation)
        restored = ChartReviewFinding.model_validate_json(finding.model_dump_json())
        assert restored == finding


class TestEngineResults:
    @pytest.mark.parametrize(
        "status",
        [
            ReviewEngineStatus.NOT_APPLICABLE,
            ReviewEngineStatus.UNAVAILABLE,
            ReviewEngineStatus.FAILED,
        ],
    )
    def test_engine_that_did_not_complete_states_a_reason(
        self, status: ReviewEngineStatus
    ) -> None:
        with pytest.raises(ValidationError, match="must state its reason"):
            ReviewEngineResult(engine="e", engine_version="1", status=status)
        result = ReviewEngineResult(
            engine="e", engine_version="1", status=status, reason="dependency down"
        )
        assert result.findings == ()

    def test_engine_that_did_not_complete_carries_no_findings(self) -> None:
        with pytest.raises(ValidationError, match="only a completed engine"):
            ReviewEngineResult(
                engine="clinical_rules",
                engine_version="1",
                status=ReviewEngineStatus.UNAVAILABLE,
                reason="x",
                findings=(_finding(),),
            )

    def test_completed_with_no_findings_is_valid(self) -> None:
        result = ReviewEngineResult(
            engine="clinical_rules",
            engine_version="1",
            status=ReviewEngineStatus.COMPLETED,
        )
        assert result.findings == ()

    def test_findings_must_belong_to_the_engine(self) -> None:
        with pytest.raises(ValidationError, match="another engine"):
            ReviewEngineResult(
                engine="narrative_consistency",
                engine_version="1",
                status=ReviewEngineStatus.COMPLETED,
                findings=(_finding(),),
            )

    def test_finding_keys_unique_within_engine(self) -> None:
        with pytest.raises(ValidationError, match="unique"):
            ReviewEngineResult(
                engine="clinical_rules",
                engine_version="1",
                status=ReviewEngineStatus.COMPLETED,
                findings=(_finding(), _finding()),
            )


class TestBundle:
    def test_bundle_version_is_pinned(self) -> None:
        assert _bundle().bundle_version == CHART_REVIEW_BUNDLE_VERSION == "1.0"

    def test_evidence_read_under_another_seal_is_refused(self) -> None:
        stale = ReviewEngineResult(
            engine="clinical_rules",
            engine_version="1",
            status=ReviewEngineStatus.COMPLETED,
            findings=(_finding(evidence=(_ref(sealed_content_hash="sha256:other"),)),),
        )
        with pytest.raises(ValidationError, match="different seal"):
            _bundle(stale)

    def test_each_engine_answers_once(self) -> None:
        result = ReviewEngineResult(
            engine="clinical_rules",
            engine_version="1",
            status=ReviewEngineStatus.COMPLETED,
        )
        with pytest.raises(ValidationError, match="answer once"):
            _bundle(result, result)

    def test_bundle_needs_at_least_one_engine(self) -> None:
        with pytest.raises(ValidationError):
            ChartReviewBundle(
                tenant_id="t", revision=_revision(), engines=(), generated_at=NOW
            )

    def test_review_engine_version_is_deterministic_and_order_free(self) -> None:
        a = ReviewEngineResult(
            engine="a", engine_version="1", status=ReviewEngineStatus.COMPLETED
        )
        b = ReviewEngineResult(
            engine="b", engine_version="2", status=ReviewEngineStatus.COMPLETED
        )
        first = _bundle(a, b).review_engine_version()
        assert first == _bundle(b, a).review_engine_version()
        assert first.startswith("crb1:") and len(first) == len("crb1:") + 32

    def test_review_engine_version_changes_with_any_engine_version(self) -> None:
        a1 = ReviewEngineResult(
            engine="a", engine_version="1", status=ReviewEngineStatus.COMPLETED
        )
        a2 = ReviewEngineResult(
            engine="a", engine_version="2", status=ReviewEngineStatus.COMPLETED
        )
        assert (
            _bundle(a1).review_engine_version() != _bundle(a2).review_engine_version()
        )

    def test_bundle_round_trips_through_json(self) -> None:
        bundle = _bundle()
        assert ChartReviewBundle.model_validate_json(bundle.model_dump_json()) == bundle

    def test_cortex_provenance_shape(self) -> None:
        provenance = CortexReviewProvenance(
            capability_key="epcr.clinical_contradiction_detection",
            model_id="model",
            ai_request_id="req-1",
            prompt_version="qa.every_chart/1",
        )
        assert provenance.discarded_items == 0


class TestLifecycleEvents:
    def test_qa_is_a_registered_service(self) -> None:
        assert QA_SERVICE_SLUG == "qa"
        assert SERVICE_BY_SLUG["qa"].route_prefix == "/api/v1/qa"

    @pytest.mark.parametrize("event_type", sorted(QA_CHART_REVIEW_EVENTS))
    def test_every_lifecycle_event_is_registered_to_qa(self, event_type: str) -> None:
        assert is_registered(event_type)
        assert producer_of(event_type).slug == "qa"

    def test_completed_event_builds(self) -> None:
        payload = QaChartReviewLifecyclePayload(
            tenant_id="tenant-a",
            review_run_id="run-1",
            chart_id="chart-1",
            signed_version_id="sv-1",
            review_engine_version="crb1:abc",
            state=ReviewRunState.COMPLETED,
            finding_counts={FindingSeverity.MAJOR: 2},
            blocking_finding_count=1,
        )
        envelope = build_qa_chart_review_event(QA_CHART_REVIEW_COMPLETED, payload)
        assert envelope.event_type == QA_CHART_REVIEW_COMPLETED
        assert envelope.tenant_id == "tenant-a"
        assert envelope.payload["finding_counts"] == {"major": 2}

    def test_event_state_must_match_event_type(self) -> None:
        payload = QaChartReviewLifecyclePayload(
            tenant_id="t",
            review_run_id="r",
            chart_id="c",
            signed_version_id="s",
            review_engine_version="v",
            state=ReviewRunState.FAILED,
            failure_class="epcr_unavailable",
        )
        with pytest.raises(ValueError, match="announces state completed"):
            build_qa_chart_review_event(QA_CHART_REVIEW_COMPLETED, payload)
        assert build_qa_chart_review_event(QA_CHART_REVIEW_FAILED, payload)
        assert build_qa_chart_review_event(QA_CHART_REVIEW_RECONCILED, payload)

    def test_unknown_event_type_refused(self) -> None:
        payload = QaChartReviewLifecyclePayload(
            tenant_id="t",
            review_run_id="r",
            chart_id="c",
            signed_version_id="s",
            review_engine_version="v",
            state=ReviewRunState.QUEUED,
        )
        with pytest.raises(ValueError, match="not a chart-review lifecycle event"):
            build_qa_chart_review_event("qa.review.completed", payload)

    def test_failed_needs_failure_class_and_others_refuse_it(self) -> None:
        with pytest.raises(ValidationError, match="must name its failure_class"):
            QaChartReviewLifecyclePayload(
                tenant_id="t",
                review_run_id="r",
                chart_id="c",
                signed_version_id="s",
                review_engine_version="v",
                state=ReviewRunState.FAILED,
            )
        with pytest.raises(ValidationError, match="only a failed review"):
            QaChartReviewLifecyclePayload(
                tenant_id="t",
                review_run_id="r",
                chart_id="c",
                signed_version_id="s",
                review_engine_version="v",
                state=ReviewRunState.COMPLETED,
                failure_class="x",
            )

    def test_only_completed_reports_counts(self) -> None:
        with pytest.raises(ValidationError, match="only a completed review"):
            QaChartReviewLifecyclePayload(
                tenant_id="t",
                review_run_id="r",
                chart_id="c",
                signed_version_id="s",
                review_engine_version="v",
                state=ReviewRunState.QUEUED,
                blocking_finding_count=1,
            )

    def test_negative_counts_refused(self) -> None:
        with pytest.raises(ValidationError, match="cannot be negative"):
            QaChartReviewLifecyclePayload(
                tenant_id="t",
                review_run_id="r",
                chart_id="c",
                signed_version_id="s",
                review_engine_version="v",
                state=ReviewRunState.COMPLETED,
                finding_counts={FindingSeverity.MINOR: -1},
            )

    def test_payload_refuses_unknown_fields(self) -> None:
        with pytest.raises(ValidationError):
            QaChartReviewLifecyclePayload.model_validate(
                {
                    "tenant_id": "t",
                    "review_run_id": "r",
                    "chart_id": "c",
                    "signed_version_id": "s",
                    "review_engine_version": "v",
                    "state": "queued",
                    "narrative": "free text",
                }
            )
