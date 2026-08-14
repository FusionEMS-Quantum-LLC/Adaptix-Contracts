"""CAD Connect provenance primitives — where every normalized value came from.

Contract-enforced non-negotiables:

- Every normalized value can be traced to its source (a page/line/cell/bbox in
  the uploaded artifact) and to how it was derived (deterministic parse, an
  approved agency mapping profile, or the Cortex CAD Mapper).
- Cortex is understanding only. Cortex-derived content records its capability
  key + model id for attribution and never asserts a value the source did not
  contain (that surfaces as ``FieldStatus.MISSING`` on the field, not a guess).
- Raw dispatch content is treated as sensitive: source references carry a
  redaction flag so PHI/CJIS-sensitive text is never assumed safe to log.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import ExtractionMethod, FieldStatus, IngestionMethod


class CadConnectSourceRef(BaseModel):
    """A pointer to where a normalized value was found in the source artifact.

    Modeled on ``adaptix_contracts.acin.ACINSourceRef`` so redaction semantics
    match the rest of the platform. Locators are optional because different
    input formats expose different addressing (a PDF has page/bbox, a CSV has a
    cell, pasted text has a char span).
    """

    page: Optional[int] = Field(
        default=None, description="1-based page number (PDF/image)."
    )
    line: Optional[int] = Field(
        default=None, description="1-based line number (text/PDF)."
    )
    cell: Optional[str] = Field(
        default=None,
        description="Cell/column reference (CSV/XLSX), e.g. 'DSP' or 'C4'.",
    )
    bbox: Optional[list[float]] = Field(
        default=None,
        description="Bounding box [x0,y0,x1,y1] in the source image/PDF, if available.",
    )
    char_span: Optional[list[int]] = Field(
        default=None,
        description="[start,end] character offsets in pasted/extracted text.",
    )
    raw_text: Optional[str] = Field(
        default=None,
        description="The exact source text this value was read from (may be redacted for logs).",
    )
    observed_value_redacted: bool = Field(
        default=True,
        description="True when raw_text is redacted for logs/telemetry (no PHI/CJIS content).",
    )

    model_config = ConfigDict(from_attributes=True)


class CadConnectProvenance(BaseModel):
    """Source + attribution carried by a normalized CAD Incident.

    Answers: which vendor/product produced it, what external ids it had, how it
    entered the gateway, which agency mapping-profile version was applied, and
    (when interpretation was needed) which Cortex capability/model interpreted
    it. Enough to reconstruct 'where did this value come from?' for every field.
    """

    source_vendor: Optional[str] = Field(
        default=None,
        description="Detected CAD/source vendor (e.g. 'motorola','centralsquare'); None if unknown.",
    )
    source_product: Optional[str] = Field(
        default=None, description="CAD product/name when known (e.g. 'premierone')."
    )
    source_version: Optional[str] = Field(
        default=None, description="Source product/schema version when known."
    )
    external_incident_id: Optional[str] = Field(
        default=None, description="The source system's incident id, if present."
    )
    external_event_id: Optional[str] = Field(
        default=None, description="The source system's event/update id, if present."
    )
    ingestion_method: IngestionMethod = Field(
        ..., description="How this payload entered the Universal CAD Gateway."
    )
    mapping_profile_version: Optional[int] = Field(
        default=None,
        description="Version of the agency mapping profile applied, if one matched.",
    )
    cortex_capability_key: Optional[str] = Field(
        default=None,
        description="AI-Service capability key that interpreted the payload (attribution).",
    )
    cortex_model_id: Optional[str] = Field(
        default=None,
        description="Model id that produced Cortex-derived values (attribution).",
    )

    model_config = ConfigDict(from_attributes=True)


class FieldValue(BaseModel):
    """One normalized field: its value, where it came from, and its review state.

    Values are normalized to a canonical string form (ISO-8601 for timestamps,
    decimal strings for coordinates, canonical strings for codes/text) so the
    contract is uniform and serializable; ``raw_text`` preserves the original.

    Fail-closed invariants (no fabrication, no silent guessing):
    - ``MISSING``  => ``value`` MUST be None (the source had nothing).
    - ``CONFLICT`` => at least two ``candidates`` (the competing values).
    - ``CONFIRMED``/``REVIEW`` => ``value`` MUST be present.
    """

    value: Optional[str] = Field(
        default=None,
        description="Normalized canonical value (ISO-8601 for times); None if missing.",
    )
    raw_text: Optional[str] = Field(
        default=None, description="The value exactly as it appeared in the source."
    )
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Extraction confidence 0.0-1.0, if available.",
    )
    status: FieldStatus = Field(
        ..., description="Confirmed / Review / Missing / Conflict."
    )
    extraction_method: Optional[ExtractionMethod] = Field(
        default=None, description="deterministic | profile | cortex."
    )
    source_ref: Optional[CadConnectSourceRef] = Field(
        default=None, description="Where in the source artifact this value was found."
    )
    candidates: list["FieldValue"] = Field(
        default_factory=list,
        description="Competing values when status is CONFLICT (firefighter selects the correct one).",
    )

    @model_validator(mode="after")
    def _enforce_status_invariants(self) -> "FieldValue":
        if self.status is FieldStatus.MISSING and self.value is not None:
            raise ValueError(
                "FieldStatus.MISSING must not carry a value (no fabrication)."
            )
        if self.status is FieldStatus.CONFLICT and len(self.candidates) < 2:
            raise ValueError("FieldStatus.CONFLICT must list >= 2 candidate values.")
        if (
            self.status in (FieldStatus.CONFIRMED, FieldStatus.REVIEW)
            and self.value is None
        ):
            raise ValueError(f"FieldStatus.{self.status.name} requires a value.")
        return self

    model_config = ConfigDict(from_attributes=True)


FieldValue.model_rebuild()


__all__ = [
    "CadConnectSourceRef",
    "CadConnectProvenance",
    "FieldValue",
]
