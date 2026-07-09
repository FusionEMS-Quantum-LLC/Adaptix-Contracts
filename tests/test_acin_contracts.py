"""Tests for the ACIN (AdaptixCore Clinical Intelligence Narrative) contracts.

These tests lock the ACIN non-negotiables at the contract layer:
- generated claims must be grounded (no fabrication),
- ai_generated content must require human review,
- contradictions are flagged, not resolved,
- narrative/summary are never authoritative,
- reviews can report failed_unavailable,
- scores stay within bounds,
- the full record round-trips and emits JSON schema.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

import pytest
from pydantic import BaseModel, ValidationError

import adaptix_contracts.acin as acin
from adaptix_contracts.acin import (
    ACINActivationDTO,
    ACINClaimDTO,
    ACINClinicalPictureDTO,
    ACINConditionFlagsDTO,
    ACINContradictionFlagDTO,
    ACINDifferentialDTO,
    ACINEvidenceDTO,
    ACINIntelligenceDTO,
    ACINLogicDTO,
    ACINNarrativeDTO,
    ACINRecordDTO,
    ACINRecordStatus,
    ACINReviewDTO,
    ACINReviewFindingDTO,
    ACINReviewSeverity,
    ACINReviewStatus,
    ACINReviewType,
    ACINScoreSetDTO,
    ACINSection,
    ACINSourceRef,
    ACINSummaryDTO,
    ACINTimelineEntryDTO,
    ACINWitnessStatementDTO,
)


def _ref(field_id: str = "eSituation.09") -> ACINSourceRef:
    return ACINSourceRef(field_id=field_id)


# ---------------------------------------------------------------------------
# Export surface
# ---------------------------------------------------------------------------


def test_all_exported_names_are_resolvable_and_unique() -> None:
    assert len(acin.__all__) == len(set(acin.__all__))
    for name in acin.__all__:
        assert hasattr(acin, name), f"Missing ACIN export: {name}"


def test_section_enum_has_seven_sections_with_letters() -> None:
    letters = {s.letter for s in ACINSection}
    assert letters == {"A", "C", "I", "N", "E", "L", "S"}
    assert len(list(ACINSection)) == 7


def test_all_acin_enums_have_unique_values() -> None:
    for name in acin.__all__:
        symbol = getattr(acin, name)
        if isinstance(symbol, type) and issubclass(symbol, Enum):
            values = [m.value for m in symbol]
            assert len(values) == len(set(values)), f"Duplicate enum values in {name}"


# ---------------------------------------------------------------------------
# Grounding / fail-closed claim
# ---------------------------------------------------------------------------


def test_ai_generated_claim_without_source_ref_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ACINClaimDTO(claim_id="c1", statement="likely sepsis", source_field_refs=[])


def test_ai_generated_claim_with_source_ref_is_accepted() -> None:
    claim = ACINClaimDTO(
        claim_id="c1",
        statement="likely sepsis",
        source_field_refs=[_ref("epcr_vitals.hr")],
    )
    assert claim.ai_generated is True
    assert claim.requires_human_review is True
    assert len(claim.source_field_refs) == 1


def test_human_authored_claim_may_skip_grounding() -> None:
    # A provider-authored (non-AI) claim is not subject to the grounding guard.
    claim = ACINClaimDTO(
        claim_id="c2",
        statement="provider note",
        ai_generated=False,
    )
    assert claim.ai_generated is False


def test_claim_confidence_bounds_enforced() -> None:
    with pytest.raises(ValidationError):
        ACINClaimDTO(
            claim_id="c3",
            statement="x",
            source_field_refs=[_ref()],
            confidence=1.5,
        )


def test_provenance_rejects_ai_without_human_review() -> None:
    with pytest.raises(ValidationError):
        ACINDifferentialDTO(
            claim_id="d1",
            statement="stroke",
            source_field_refs=[_ref()],
            ai_generated=True,
            requires_human_review=False,
        )


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


def test_activation_section_defaults_to_non_ai() -> None:
    a = ACINActivationDTO(
        dispatch_priority="1",
        cad_determinant="26D01",
        cad_timeline=[
            ACINTimelineEntryDTO(label="dispatch", timestamp=datetime.now(timezone.utc))
        ],
    )
    assert a.section is ACINSection.ACTIVATION
    assert a.ai_generated is False


def test_clinical_picture_pain_score_bounds() -> None:
    with pytest.raises(ValidationError):
        ACINClinicalPictureDTO(pain_score=11)
    ok = ACINClinicalPictureDTO(
        chief_complaint="chest pain",
        pain_score=7,
        witness_statements=[
            ACINWitnessStatementDTO(statement="pt collapsed", attributed_to="bystander")
        ],
    )
    assert ok.section is ACINSection.CLINICAL_PICTURE


def test_contradiction_is_flagged_not_resolved() -> None:
    flag = ACINContradictionFlagDTO(
        contradiction_id="x1",
        message="documented unconscious but GCS 15",
        field_a="mental_status",
        field_b="gcs",
    )
    assert flag.resolution is None
    with pytest.raises(ValidationError):
        ACINContradictionFlagDTO(
            contradiction_id="x2",
            message="conflict",
            resolution="resolved by crew",
        )


def test_intelligence_is_generated_and_advisory() -> None:
    i = ACINIntelligenceDTO(
        differentials=[
            ACINDifferentialDTO(
                claim_id="d1",
                statement="STEMI",
                likelihood="high",
                source_field_refs=[_ref("ekg.1")],
                snomed_code="401303003",
            )
        ],
        condition_flags=ACINConditionFlagsDTO(stemi=True),
        cms_medical_necessity_score=88.0,
    )
    assert i.ai_generated is True
    assert i.advisory_only is True
    assert i.requires_human_review is True

    with pytest.raises(ValidationError):
        ACINIntelligenceDTO(advisory_only=False)


def test_intelligence_med_necessity_score_bounds() -> None:
    with pytest.raises(ValidationError):
        ACINIntelligenceDTO(cms_medical_necessity_score=140.0)


def test_narrative_and_summary_never_authoritative() -> None:
    n = ACINNarrativeDTO(generated_prose="chronological prose")
    assert n.is_authoritative_truth is False
    with pytest.raises(ValidationError):
        ACINNarrativeDTO(generated_prose="x", is_authoritative_truth=True)

    s = ACINSummaryDTO(generated_paragraph="disposition summary")
    assert s.is_authoritative_truth is False
    with pytest.raises(ValidationError):
        ACINSummaryDTO(is_authoritative_truth=True)


def test_evidence_is_reference_layer_non_ai() -> None:
    e = ACINEvidenceDTO(
        vitals_refs=[_ref("epcr_vitals.1"), _ref("epcr_vitals.2")],
        signature_refs=[_ref("epcr_signature.1")],
    )
    assert e.section is ACINSection.EVIDENCE
    assert e.ai_generated is False
    assert len(e.vitals_refs) == 2


def test_logic_section_generated_with_grounded_claims() -> None:
    logic = ACINLogicDTO(
        medical_necessity=ACINClaimDTO(
            claim_id="mn1",
            statement="ALS necessary due to cardiac monitoring",
            source_field_refs=[_ref("procedures.monitor")],
        ),
        billing_confidence=0.91,
    )
    assert logic.ai_generated is True
    assert logic.medical_necessity is not None


# ---------------------------------------------------------------------------
# Scores
# ---------------------------------------------------------------------------


def test_score_set_bounds_and_defaults() -> None:
    scores = ACINScoreSetDTO(
        acin_record_id="r1",
        tenant_id="t1",
        chart_id="ch1",
        clinical_completeness=90.0,
        medical_necessity=85.0,
        billing_readiness=80.0,
        legal_defensibility=88.0,
        nemsis_compliance=95.0,
        protocol_compliance=92.0,
        documentation_quality=87.0,
        audit_risk=12.0,
        contradictions_count=1,
        missing_elements_count=2,
    )
    assert scores.capability_key == "acin.scoring"
    assert scores.contradictions_count == 1


def test_score_out_of_range_rejected() -> None:
    with pytest.raises(ValidationError):
        ACINScoreSetDTO(
            acin_record_id="r1",
            tenant_id="t1",
            chart_id="ch1",
            clinical_completeness=101.0,
            medical_necessity=85.0,
            billing_readiness=80.0,
            legal_defensibility=88.0,
            nemsis_compliance=95.0,
            protocol_compliance=92.0,
            documentation_quality=87.0,
            audit_risk=12.0,
            contradictions_count=0,
            missing_elements_count=0,
        )


def test_score_negative_count_rejected() -> None:
    with pytest.raises(ValidationError):
        ACINScoreSetDTO(
            acin_record_id="r1",
            tenant_id="t1",
            chart_id="ch1",
            clinical_completeness=90.0,
            medical_necessity=85.0,
            billing_readiness=80.0,
            legal_defensibility=88.0,
            nemsis_compliance=95.0,
            protocol_compliance=92.0,
            documentation_quality=87.0,
            audit_risk=12.0,
            contradictions_count=-1,
            missing_elements_count=0,
        )


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------


def test_review_can_report_failed_unavailable() -> None:
    review = ACINReviewDTO(
        review_id="rev1",
        acin_record_id="r1",
        tenant_id="t1",
        chart_id="ch1",
        review_type=ACINReviewType.LEGAL,
        status=ACINReviewStatus.FAILED_UNAVAILABLE,
    )
    assert review.status is ACINReviewStatus.FAILED_UNAVAILABLE
    assert review.findings == []


def test_review_finding_contradiction_flag_guard() -> None:
    finding = ACINReviewFindingDTO(
        finding_id="f1",
        severity=ACINReviewSeverity.CRITICAL,
        category="consistency",
        message="timeline contradiction",
        is_contradiction=True,
        source_field_refs=[_ref("times.1")],
    )
    assert finding.resolution is None
    with pytest.raises(ValidationError):
        ACINReviewFindingDTO(
            finding_id="f2",
            severity=ACINReviewSeverity.CRITICAL,
            category="consistency",
            message="conflict",
            is_contradiction=True,
            resolution="auto-fixed",
        )


# ---------------------------------------------------------------------------
# Full record
# ---------------------------------------------------------------------------


def _full_record() -> ACINRecordDTO:
    return ACINRecordDTO(
        id="acin-1",
        tenant_id="t1",
        chart_id="ch1",
        version=1,
        activation=ACINActivationDTO(cad_determinant="26D01"),
        clinical_picture=ACINClinicalPictureDTO(
            chief_complaint="chest pain", pain_score=8
        ),
        intelligence=ACINIntelligenceDTO(
            differentials=[
                ACINDifferentialDTO(
                    claim_id="d1",
                    statement="STEMI",
                    source_field_refs=[_ref("ekg.1")],
                )
            ]
        ),
        narrative=ACINNarrativeDTO(generated_prose="prose"),
        evidence=ACINEvidenceDTO(vitals_refs=[_ref("epcr_vitals.1")]),
        logic=ACINLogicDTO(billing_confidence=0.9),
        summary=ACINSummaryDTO(generated_paragraph="summary"),
        scores=ACINScoreSetDTO(
            acin_record_id="acin-1",
            tenant_id="t1",
            chart_id="ch1",
            clinical_completeness=90.0,
            medical_necessity=85.0,
            billing_readiness=80.0,
            legal_defensibility=88.0,
            nemsis_compliance=95.0,
            protocol_compliance=92.0,
            documentation_quality=87.0,
            audit_risk=12.0,
            contradictions_count=0,
            missing_elements_count=1,
        ),
        reviews=[
            ACINReviewDTO(
                review_id="rev1",
                acin_record_id="acin-1",
                tenant_id="t1",
                chart_id="ch1",
                review_type=ACINReviewType.CLINICAL,
                status=ACINReviewStatus.COMPLETE,
            )
        ],
    )


def test_full_record_defaults_are_advisory() -> None:
    rec = _full_record()
    assert rec.status is ACINRecordStatus.DRAFT
    assert rec.overall_ai_generated is True
    assert rec.requires_human_review is True


def test_record_rejects_ai_without_review() -> None:
    with pytest.raises(ValidationError):
        ACINRecordDTO(
            id="acin-2",
            tenant_id="t1",
            chart_id="ch1",
            overall_ai_generated=True,
            requires_human_review=False,
        )


def test_record_version_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        ACINRecordDTO(id="a", tenant_id="t", chart_id="c", version=0)


def test_record_round_trips_through_json() -> None:
    rec = _full_record()
    payload = rec.model_dump_json()
    restored = ACINRecordDTO.model_validate_json(payload)
    assert restored == rec


def test_all_exported_models_emit_json_schema() -> None:
    for name in acin.__all__:
        symbol = getattr(acin, name)
        if isinstance(symbol, type) and issubclass(symbol, BaseModel):
            schema = symbol.model_json_schema()
            assert isinstance(schema, dict) and schema


def test_from_attributes_construction() -> None:
    class _Row:
        field_id = "eSituation.09"
        source_model = "epcr_situation"
        source_pk = "abc"
        observed_value_redacted = True
        included_in_prompt = False

    ref = ACINSourceRef.model_validate(_Row())
    assert ref.field_id == "eSituation.09"
    assert ref.source_model == "epcr_situation"
