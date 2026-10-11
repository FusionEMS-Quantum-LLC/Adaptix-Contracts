"""The ACIN scoring context: absent is unknown, malformed is refused.

The model is the shared input of AI-Service's ACIN scoring rules and EPCR's ACIN
assembler. These tests pin its validation contract at the contract layer; the
scoring behaviour that reads it is tested in AI-Service.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from adaptix_contracts.acin import ACINScoringContext
from adaptix_contracts.acin.scoring_context import (
    BillingSection,
    ClinicalSection,
    ContradictionFinding,
    DocumentationSection,
    LegalSection,
    MissingElementFinding,
    NecessitySection,
    NemsisSection,
    ProtocolSection,
)


def _epcr_payload() -> dict[str, object]:
    """The shape EPCR's _build_scoring_context sends for a fully signalled chart."""
    return {
        "clinical": {
            "general_appearance_documented": True,
            "mental_status_documented": True,
            "airway_documented": True,
            "breathing_documented": True,
            "circulation_documented": True,
            "skin_documented": True,
            "chief_complaint_documented": True,
            "hpi_documented": True,
            "pain_assessed": True,
            "vitals_count": 1,
            "interventions_count": 1,
            "reassessment_count": 0,
        },
        "documentation": {"narrative_present": True, "narrative_length": 640},
        "contradictions": [
            {"message": "m", "severity": "warning", "source_field_refs": ["eVitals.03"]}
        ],
        "contradiction_analysis_performed": True,
        "missing_elements": [
            {"element": None, "section": "eVitals", "severity": "info"}
        ],
        "completeness_analysis_performed": True,
        "necessity": {"transport_reason_documented": True, "level_of_service": "ALS1"},
        "billing": {
            "signature_required": True,
            "signature_captured": True,
            "mileage_documented": True,
        },
        "legal": {"patient_signature_present": True},
    }


def test_the_producer_payload_validates() -> None:
    context = ACINScoringContext.model_validate(_epcr_payload())
    assert context.clinical is not None
    assert context.clinical.vitals_count == 1
    assert context.legal is not None
    assert context.legal.patient_signature_present is True


def test_an_absent_field_is_unknown_not_a_default() -> None:
    context = ACINScoringContext.model_validate(_epcr_payload())
    assert context.legal is not None
    assert context.legal.crew_signature_present is None
    assert context.legal.witnesses_required is None
    assert context.billing is not None
    assert context.billing.required_fields_missing is None
    assert context.billing.pcs_required is None
    assert context.necessity is not None
    assert context.necessity.medical_necessity_supported is None
    assert context.documentation is not None
    assert context.documentation.observed_vs_stated_distinguished is None


def test_an_absent_section_is_none_and_an_empty_one_supplies_nothing() -> None:
    context = ACINScoringContext.model_validate({"protocol": {}})
    assert context.nemsis is None
    assert context.protocol is not None
    assert context.protocol.model_fields_set == set()


@pytest.mark.parametrize(
    ("section", "field"),
    [
        ("legal", "crew_signature_present"),
        ("clinical", "vitals_count"),
        ("billing", "required_fields_missing"),
        ("nemsis", "schematron_error_count"),
        ("documentation", "narrative_present"),
    ],
)
def test_an_explicit_null_is_malformed(section: str, field: str) -> None:
    with pytest.raises(ValidationError) as caught:
        _ = ACINScoringContext.model_validate({section: {field: None}})
    assert [error["loc"] for error in caught.value.errors()] == [(section, field)]


@pytest.mark.parametrize(
    ("payload", "loc"),
    [
        ({"clinical": {"airway_documented": "no"}}, ("clinical", "airway_documented")),
        ({"legal": {"consent_documented": 1}}, ("legal", "consent_documented")),
        ({"clinical": {"vitals_count": "3"}}, ("clinical", "vitals_count")),
        ({"clinical": {"vitals_count": 3.7}}, ("clinical", "vitals_count")),
        (
            {"protocol": {"medication_error_count": -2}},
            ("protocol", "medication_error_count"),
        ),
        (
            {"billing": {"required_fields_missing": "abc"}},
            ("billing", "required_fields_missing"),
        ),
        ({"legal": {"witness_count": 2}}, ("legal", "witness_count")),
        ({"vitals": {}}, ("vitals",)),
        ({"clinical": [1]}, ("clinical",)),
        ({"contradictions": ["a"]}, ("contradictions", 0)),
        (
            {"contradiction_analysis_performed": "true"},
            ("contradiction_analysis_performed",),
        ),
    ],
)
def test_a_malformed_value_is_refused_never_coerced(
    payload: dict[str, object], loc: tuple[str | int, ...]
) -> None:
    with pytest.raises(ValidationError) as caught:
        _ = ACINScoringContext.model_validate(payload)
    assert loc in [error["loc"] for error in caught.value.errors()]


def test_every_model_is_strict_frozen_and_closed() -> None:
    models = (
        ACINScoringContext,
        ClinicalSection,
        NecessitySection,
        BillingSection,
        LegalSection,
        NemsisSection,
        ProtocolSection,
        DocumentationSection,
        ContradictionFinding,
        MissingElementFinding,
    )
    for model in models:
        config = model.model_config
        assert config.get("strict") is True, model.__name__
        assert config.get("frozen") is True, model.__name__
        assert config.get("extra") == "forbid", model.__name__
