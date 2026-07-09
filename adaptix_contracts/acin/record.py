"""ACIN record — the canonical aggregation DTO.

One ACIN record per (tenant_id, chart_id, version). It carries the seven sections
(A-C-I-N-E-L-S), the 10-score set, and the four Cortex reviews. It is advisory
output: ``overall_ai_generated`` is True and ``requires_human_review`` is True.
Nothing here is authoritative until a human accepts it, and the underlying
narrative persists to the chart only on explicit human acceptance (handled by the
EPCR assembler, not by this contract).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import ACINRecordStatus
from .reviews import ACINReviewDTO
from .scores import ACINScoreSetDTO
from .sections import (
    ACINActivationDTO,
    ACINClinicalPictureDTO,
    ACINEvidenceDTO,
    ACINIntelligenceDTO,
    ACINLogicDTO,
    ACINNarrativeDTO,
    ACINSummaryDTO,
)


class ACINRecordDTO(BaseModel):
    """The full ACIN record: sections + scores + reviews + provenance."""

    id: str
    tenant_id: str
    chart_id: str
    version: int = Field(default=1, ge=1)
    status: ACINRecordStatus = ACINRecordStatus.DRAFT

    overall_ai_generated: bool = Field(
        default=True, description="True — ACIN is generated advisory output."
    )
    requires_human_review: bool = Field(
        default=True, description="Always True — nothing is auto-committed or signed."
    )

    # Sections A-C-I-N-E-L-S (optional to allow partial/incremental generation).
    activation: Optional[ACINActivationDTO] = None
    clinical_picture: Optional[ACINClinicalPictureDTO] = None
    intelligence: Optional[ACINIntelligenceDTO] = None
    narrative: Optional[ACINNarrativeDTO] = None
    evidence: Optional[ACINEvidenceDTO] = None
    logic: Optional[ACINLogicDTO] = None
    summary: Optional[ACINSummaryDTO] = None

    # The 10-score set.
    scores: Optional[ACINScoreSetDTO] = None

    # The four Cortex reviews (clinical / billing / qa / legal).
    reviews: list[ACINReviewDTO] = Field(default_factory=list)

    # Attribution / lifecycle timestamps.
    generated_by_model: Optional[str] = None
    generated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    locked_at: Optional[datetime] = None

    @model_validator(mode="after")
    def _enforce_advisory_review(self) -> "ACINRecordDTO":
        if self.overall_ai_generated and not self.requires_human_review:
            raise ValueError(
                "An ai-generated ACIN record must set requires_human_review=True "
                "(nothing is auto-committed or signed)"
            )
        return self

    model_config = ConfigDict(from_attributes=True)


__all__ = ["ACINRecordDTO"]
