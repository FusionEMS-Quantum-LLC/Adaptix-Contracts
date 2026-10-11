"""The ACIN scoring context: the input of the AI-Service ACIN scoring rules.

EPCR's ACIN assembler produces it (``epcr_app.acin.service._build_scoring_context``)
and sends it in the body of AI-Service ``POST /api/v1/ai/acin/score``, which
validates it with this model before any rule reads it. Both sides import this one
model, so producer and consumer cannot drift. Two states stay distinct:

* MISSING: a section or field is absent. That is a legitimate state, and it
  means *unknown*. An absent section makes its metric ``insufficient_evidence``
  (never a pass). An absent field reads as ``None``; a metric that reads it is
  ``insufficient_evidence`` and names the field, because an unknown can neither
  certify a pass nor manufacture a deficiency. No absent field takes a default
  that a rule scores. A producer omits what it cannot substantiate.
* MALFORMED: present with the wrong type or shape (a string where a boolean
  belongs, a negative count, an unknown key, a section that is not an object).
  An explicit ``null`` for a field is malformed too: a producer that does not
  know a value omits the field. That is a contract violation: validation fails
  (the scoring route answers 422) and nothing is scored or persisted. A
  malformed value is never coerced into a plausible score.

Every model is strict (``true`` is a boolean, ``1`` is not) and forbids
unknown keys. Because unknown keys are rejected, a new key is released here and
deployed in AI-Service before EPCR starts sending it.

Moved unchanged from AI-Service ``ai_app/acin/scoring/context.py``
(acin-scoring-rules 2.0.0, AI-Service #356).
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, NonNegativeInt


def _null_is_malformed(value: object) -> object:
    """Reject an explicit null: an unknown value is omitted, never sent as null."""
    if value is None:
        raise ValueError("null is not a value; omit the field when it is unknown")
    return value


# A scored input: absent (None, unknown) or a value of the type. Never null on the wire.
KnownBool = Annotated[bool | None, BeforeValidator(_null_is_malformed)]
KnownCount = Annotated[NonNegativeInt | None, BeforeValidator(_null_is_malformed)]
KnownNames = Annotated[list[str] | None, BeforeValidator(_null_is_malformed)]


class _ContextModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class ClinicalSection(_ContextModel):
    """C: the clinical picture. Each flag says whether that element is documented."""

    general_appearance_documented: KnownBool = None
    mental_status_documented: KnownBool = None
    airway_documented: KnownBool = None
    breathing_documented: KnownBool = None
    circulation_documented: KnownBool = None
    skin_documented: KnownBool = None
    chief_complaint_documented: KnownBool = None
    hpi_documented: KnownBool = None
    pain_assessed: KnownBool = None
    vitals_count: KnownCount = None
    interventions_count: KnownCount = None
    reassessment_count: KnownCount = None
    # Element name (without its _documented/_assessed suffix) -> source field id.
    field_refs: dict[str, str] = Field(default_factory=dict[str, str])

    def documented_elements(self) -> tuple[tuple[str, bool | None], ...]:
        """The nine documented-element flags, in the ruleset's canonical order."""
        return (
            ("general_appearance_documented", self.general_appearance_documented),
            ("mental_status_documented", self.mental_status_documented),
            ("airway_documented", self.airway_documented),
            ("breathing_documented", self.breathing_documented),
            ("circulation_documented", self.circulation_documented),
            ("skin_documented", self.skin_documented),
            ("chief_complaint_documented", self.chief_complaint_documented),
            ("hpi_documented", self.hpi_documented),
            ("pain_assessed", self.pain_assessed),
        )


class NecessitySection(_ContextModel):
    """I/L: medical-necessity inputs."""

    # Shown beside the score, never scored.
    level_of_service: str | None = None
    transport_reason_documented: KnownBool = None
    medical_necessity_supported: KnownBool = None
    dx_supports_claim: KnownBool = None
    pcs_required: KnownBool = None
    pcs_on_file: KnownBool = None


class BillingSection(_ContextModel):
    """L: billing-readiness inputs."""

    # Carried for the producer's inventory; no rule reads it.
    required_fields_present: list[str] = Field(default_factory=list[str])
    required_fields_missing: KnownNames = None
    signature_required: KnownBool = None
    signature_captured: KnownBool = None
    mileage_documented: KnownBool = None
    pcs_required: KnownBool = None
    pcs_on_file: KnownBool = None


class LegalSection(_ContextModel):
    """Legal-defensibility inputs."""

    patient_signature_present: KnownBool = None
    crew_signature_present: KnownBool = None
    receiving_signature_present: KnownBool = None
    consent_documented: KnownBool = None
    transfer_of_care_documented: KnownBool = None
    witnesses_required: KnownBool = None
    witnesses_documented: KnownBool = None


class NemsisSection(_ContextModel):
    """NEMSIS-compliance inputs."""

    required_panels_present: KnownNames = None
    required_panels_missing: KnownNames = None
    schematron_error_count: KnownCount = None


class ProtocolSection(_ContextModel):
    """Protocol-compliance inputs."""

    # Shown beside the score, never scored.
    protocol_triggered: KnownBool = None
    steps_required: KnownCount = None
    steps_documented: KnownCount = None
    medication_error_count: KnownCount = None


class DocumentationSection(_ContextModel):
    """N: documentation-quality inputs."""

    narrative_present: KnownBool = None
    narrative_length: KnownCount = None
    observed_vs_stated_distinguished: KnownBool = None
    reassessments_referenced: KnownBool = None
    interventions_justified: KnownBool = None


class ContradictionFinding(_ContextModel):
    """One flagged (not resolved) contradiction."""

    message: str = ""
    # "info" | "warning" | "critical" as EPCR maps it; compared case-insensitively.
    severity: str | None = None
    source_field_refs: list[str] = Field(default_factory=list[str])


class MissingElementFinding(_ContextModel):
    """One flagged missing required element. EPCR sends None when it has no id."""

    element: str | None = None
    section: str | None = None
    severity: str | None = None


class ACINScoringContext(_ContextModel):
    """The whole scoring context. Every part is optional: absent means missing."""

    clinical: ClinicalSection | None = None
    necessity: NecessitySection | None = None
    billing: BillingSection | None = None
    legal: LegalSection | None = None
    nemsis: NemsisSection | None = None
    protocol: ProtocolSection | None = None
    documentation: DocumentationSection | None = None
    # None (absent or null) and [] differ: None with the analysis flag unset
    # means the count is unknown.
    contradictions: list[ContradictionFinding] | None = None
    contradiction_analysis_performed: bool = False
    missing_elements: list[MissingElementFinding] | None = None
    completeness_analysis_performed: bool = False


__all__ = [
    "ACINScoringContext",
    "BillingSection",
    "ClinicalSection",
    "ContradictionFinding",
    "DocumentationSection",
    "KnownBool",
    "KnownCount",
    "KnownNames",
    "LegalSection",
    "MissingElementFinding",
    "NecessitySection",
    "NemsisSection",
    "ProtocolSection",
]
