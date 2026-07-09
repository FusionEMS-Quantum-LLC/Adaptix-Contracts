"""ACIN section DTOs — the seven sections A-C-I-N-E-L-S.

One structured record, documented once, that fans out to EPCR, NEMSIS, Billing,
Medical-Necessity, QA/QI, Legal, CMS-audit, AI-review, and CDS.

Section provenance rules:
- A (Activation), C (Clinical Picture), E (Evidence) are provider/structured
  derived — ``ai_generated`` may be False for directly observed fields.
- I (Intelligence) and L (Logic) are machine-GENERATED — ``ai_generated`` is
  always True and their claims are grounded (see ACINClaimDTO).
- N (Narrative) and S (Summary) are generated prose — ``ai_generated`` is True,
  provider-editable, and NEVER authoritative truth.
- Contradictions are FLAGGED, never resolved (resolution is always None).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import ACINClaimReviewState, ACINReviewSeverity, ACINSection
from .provenance import ACINClaimDTO, ACINProvenanceMixin, ACINSourceRef


# ===========================================================================
# Shared section base + small structured sub-DTOs
# ===========================================================================


class _ACINSectionBase(ACINProvenanceMixin):
    """Common section envelope fields (per-section human review state)."""

    human_review_state: ACINClaimReviewState = ACINClaimReviewState.PENDING_REVIEW
    reviewer_id: Optional[str] = None
    reviewed_at: Optional[datetime] = None


class ACINTimelineEntryDTO(BaseModel):
    """A single CAD/response timeline entry (grounded)."""

    label: str
    timestamp: Optional[datetime] = None
    source_field_refs: list[ACINSourceRef] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ACINWitnessStatementDTO(BaseModel):
    """A witness / patient statement.

    ``attributed_to`` preserves the observed-vs-stated distinction required by the
    ACIN narrative rules (a statement is never silently promoted to a finding).
    """

    statement: str
    attributed_to: Optional[str] = Field(
        default=None,
        description="Who stated it (e.g. 'patient', 'bystander', 'family') — stated, not observed.",
    )
    source_field_refs: list[ACINSourceRef] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ACINContradictionFlagDTO(BaseModel):
    """A detected contradiction — FLAGGED, never resolved.

    Per the ACIN non-negotiables, contradictions are surfaced for a human, not
    auto-resolved. ``resolution`` must remain None at the contract layer.
    """

    contradiction_id: str
    message: str
    field_a: Optional[str] = None
    field_b: Optional[str] = None
    severity: ACINReviewSeverity = ACINReviewSeverity.WARNING
    source_field_refs: list[ACINSourceRef] = Field(default_factory=list)
    resolution: Optional[str] = Field(
        default=None,
        description="Always None — ACIN flags contradictions, it does not resolve them.",
    )
    requires_human_review: bool = True

    @model_validator(mode="after")
    def _never_resolve(self) -> "ACINContradictionFlagDTO":
        if self.resolution is not None:
            raise ValueError(
                "ACIN contradictions are flagged, not resolved (resolution must be None)"
            )
        return self

    model_config = ConfigDict(from_attributes=True)


class ACINConditionFlagsDTO(BaseModel):
    """Machine-detected high-acuity condition flags (advisory)."""

    stroke: bool = False
    sepsis: bool = False
    stemi: bool = False
    trauma: bool = False
    behavioral: bool = False
    source_field_refs: list[ACINSourceRef] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# ===========================================================================
# A — Activation
# ===========================================================================


class ACINActivationDTO(_ACINSectionBase):
    """Section A — Activation (dispatch / response context)."""

    section: ACINSection = ACINSection.ACTIVATION
    ai_generated: bool = False  # dispatch facts are structured-derived by default

    dispatch_time: Optional[datetime] = None
    dispatch_priority: Optional[str] = None
    request_source: Optional[str] = None
    cad_determinant: Optional[str] = None
    initial_complaint: Optional[str] = None
    caller_type: Optional[str] = None
    response_mode: Optional[str] = None
    crew_ids: list[str] = Field(default_factory=list)
    weather: Optional[str] = None
    scene_hazards: list[str] = Field(default_factory=list)
    cad_timeline: list[ACINTimelineEntryDTO] = Field(default_factory=list)


# ===========================================================================
# C — Clinical Picture
# ===========================================================================


class ACINClinicalPictureDTO(_ACINSectionBase):
    """Section C — Clinical Picture (assessment + contradiction detection)."""

    section: ACINSection = ACINSection.CLINICAL_PICTURE
    ai_generated: bool = False  # observed findings are provider-documented by default

    general_appearance: Optional[str] = None
    mental_status: Optional[str] = None
    airway: Optional[str] = None
    breathing: Optional[str] = None
    circulation: Optional[str] = None
    skin: Optional[str] = None
    pain_score: Optional[int] = Field(default=None, ge=0, le=10)
    chief_complaint: Optional[str] = None
    hpi: Optional[str] = None
    mechanism: Optional[str] = None
    witness_statements: list[ACINWitnessStatementDTO] = Field(default_factory=list)
    pertinent_negatives: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    detected_contradictions: list[ACINContradictionFlagDTO] = Field(
        default_factory=list
    )


# ===========================================================================
# I — Intelligence (GENERATED)
# ===========================================================================


class ACINDifferentialDTO(ACINClaimDTO):
    """A generated differential diagnosis (grounded + Terminology-coded)."""

    likelihood: Optional[str] = Field(
        default=None,
        description="Qualitative likelihood (e.g. 'high', 'moderate', 'low').",
    )


class ACINIntelligenceDTO(_ACINSectionBase):
    """Section I — Intelligence. Machine-GENERATED, advisory only.

    Every item is grounded to source fields and requires human review. Section I
    reaches NEMSIS impressions only via a human-confirmed ImpressionBinding.
    """

    section: ACINSection = ACINSection.INTELLIGENCE
    ai_generated: bool = True

    differentials: list[ACINDifferentialDTO] = Field(default_factory=list)
    protocol_triggered: Optional[str] = None
    condition_flags: ACINConditionFlagsDTO = Field(
        default_factory=ACINConditionFlagsDTO
    )
    medication_interactions: list[ACINClaimDTO] = Field(default_factory=list)
    high_risk_factors: list[ACINClaimDTO] = Field(default_factory=list)
    cms_medical_necessity_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    transport_risk: Optional[str] = None
    hospital_capability_match: Optional[str] = None
    recommended_destination: Optional[str] = None
    protocol_compliance: Optional[str] = None
    documentation_gaps: list[str] = Field(default_factory=list)
    advisory_only: bool = Field(
        default=True, description="Section I is always advisory."
    )

    @model_validator(mode="after")
    def _force_advisory(self) -> "ACINIntelligenceDTO":
        if not self.advisory_only:
            raise ValueError(
                "ACIN Intelligence (I) is advisory only and cannot be authoritative"
            )
        return self


# ===========================================================================
# N — Narrative
# ===========================================================================


class ACINNarrativeDTO(_ACINSectionBase):
    """Section N — Narrative. Generated prose, provider-editable, never authoritative."""

    section: ACINSection = ACINSection.NARRATIVE
    ai_generated: bool = True

    generated_prose: Optional[str] = Field(
        default=None,
        description="AI-generated narrative prose (returned to caller; not for logs).",
    )
    provider_edited_prose: Optional[str] = Field(
        default=None, description="Human-edited narrative, if the provider revised it."
    )
    generation_prompt_version: Optional[str] = None
    is_authoritative_truth: bool = Field(
        default=False, description="Always False — the narrative is derived output."
    )

    @model_validator(mode="after")
    def _never_authoritative(self) -> "ACINNarrativeDTO":
        if self.is_authoritative_truth:
            raise ValueError(
                "ACIN narrative is derived output and is never authoritative truth"
            )
        return self


# ===========================================================================
# E — Evidence
# ===========================================================================


class ACINEvidenceDTO(_ACINSectionBase):
    """Section E — Evidence. A reference layer over existing EPCR structured data.

    E is not a new data store; it points at the vitals, monitor, med, procedure,
    signature, and device rows that ground every other section.
    """

    section: ACINSection = ACINSection.EVIDENCE
    ai_generated: bool = False

    vitals_refs: list[ACINSourceRef] = Field(default_factory=list)
    cardiac_monitor_refs: list[ACINSourceRef] = Field(default_factory=list)
    ekg_refs: list[ACINSourceRef] = Field(default_factory=list)
    capnography_refs: list[ACINSourceRef] = Field(default_factory=list)
    photo_refs: list[ACINSourceRef] = Field(default_factory=list)
    signature_refs: list[ACINSourceRef] = Field(default_factory=list)
    medication_admin_refs: list[ACINSourceRef] = Field(default_factory=list)
    procedure_refs: list[ACINSourceRef] = Field(default_factory=list)
    device_log_refs: list[ACINSourceRef] = Field(default_factory=list)
    hospital_data_refs: list[ACINSourceRef] = Field(default_factory=list)
    witnesses: list[ACINWitnessStatementDTO] = Field(default_factory=list)


# ===========================================================================
# L — Logic (machine-generated billing / compliance justification)
# ===========================================================================


class ACINLogicDTO(_ACINSectionBase):
    """Section L — Logic. Machine-generated medical-necessity / compliance justification.

    Each justification is a grounded claim; codes are grounded via
    Terminology-Service crosswalk/validate before they land here.
    """

    section: ACINSection = ACINSection.LOGIC
    ai_generated: bool = True

    medical_necessity: Optional[ACINClaimDTO] = None
    pcs_validation: Optional[ACINClaimDTO] = None
    medicare_compliance: Optional[ACINClaimDTO] = None
    lcd_match: Optional[ACINClaimDTO] = None
    ncd_match: Optional[ACINClaimDTO] = None
    commercial_policy_match: Optional[ACINClaimDTO] = None
    destination_justification: Optional[ACINClaimDTO] = None
    als_bls_justification: Optional[ACINClaimDTO] = None
    mileage_justification: Optional[ACINClaimDTO] = None
    procedure_justification: Optional[ACINClaimDTO] = None
    diagnosis_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    coding_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    documentation_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    billing_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


# ===========================================================================
# S — Summary
# ===========================================================================


class ACINSummaryDTO(_ACINSectionBase):
    """Section S — Summary. One auto-generated paragraph, provider-editable, never authoritative."""

    section: ACINSection = ACINSection.SUMMARY
    ai_generated: bool = True

    disposition: Optional[str] = None
    condition: Optional[str] = None
    response_to_treatment: Optional[str] = None
    transfer_of_care: Optional[str] = None
    receiving_facility: Optional[str] = None
    receiving_nurse: Optional[str] = None
    final_impression: Optional[str] = None
    crew_recommendation: Optional[str] = None
    generated_paragraph: Optional[str] = None
    is_authoritative_truth: bool = Field(
        default=False, description="Always False — the summary is derived output."
    )

    @model_validator(mode="after")
    def _never_authoritative(self) -> "ACINSummaryDTO":
        if self.is_authoritative_truth:
            raise ValueError(
                "ACIN summary is derived output and is never authoritative truth"
            )
        return self


__all__ = [
    "ACINTimelineEntryDTO",
    "ACINWitnessStatementDTO",
    "ACINContradictionFlagDTO",
    "ACINConditionFlagsDTO",
    "ACINActivationDTO",
    "ACINClinicalPictureDTO",
    "ACINDifferentialDTO",
    "ACINIntelligenceDTO",
    "ACINNarrativeDTO",
    "ACINEvidenceDTO",
    "ACINLogicDTO",
    "ACINSummaryDTO",
]
