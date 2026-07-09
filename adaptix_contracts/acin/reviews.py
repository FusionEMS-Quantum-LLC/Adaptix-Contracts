"""ACIN Cortex reviews — the four review lenses and their findings.

Cortex applies four reviews to an ACIN record: Clinical, Billing, QA, Legal.
Each review is model-attributed. When the Bedrock broker is unavailable the
review is recorded truthfully as ``failed_unavailable`` — never stubbed complete.

Findings are grounded to source fields. A finding flagged as a contradiction is
FLAGGED, never resolved (its resolution stays None), matching the ACIN
non-negotiable that contradictions are surfaced for a human, not auto-resolved.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import ACINReviewSeverity, ACINReviewStatus, ACINReviewType
from .provenance import ACINSourceRef


class ACINReviewFindingDTO(BaseModel):
    """A single finding produced by a Cortex review."""

    finding_id: str
    review_id: Optional[str] = None
    severity: ACINReviewSeverity
    category: str
    message: str
    source_field_refs: list[ACINSourceRef] = Field(default_factory=list)
    is_contradiction: bool = False
    resolution: Optional[str] = Field(
        default=None,
        description="Always None when is_contradiction — ACIN flags, it does not resolve.",
    )
    suggested_action: Optional[str] = None
    requires_human_review: bool = True
    accepted_by: Optional[str] = None
    accepted_at: Optional[datetime] = None

    @model_validator(mode="after")
    def _contradictions_are_flagged_not_resolved(self) -> "ACINReviewFindingDTO":
        if self.is_contradiction and self.resolution is not None:
            raise ValueError(
                "A contradiction finding is flagged, not resolved (resolution must be None)"
            )
        return self

    model_config = ConfigDict(from_attributes=True)


class ACINReviewDTO(BaseModel):
    """One Cortex review of an ACIN record (clinical / billing / qa / legal)."""

    review_id: str
    acin_record_id: str
    tenant_id: str
    chart_id: str
    review_type: ACINReviewType
    status: ACINReviewStatus = ACINReviewStatus.PENDING
    capability_key: Optional[str] = None
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    generated_at: Optional[datetime] = None
    summary_text_redacted: Optional[str] = None
    findings: list[ACINReviewFindingDTO] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


__all__ = [
    "ACINReviewFindingDTO",
    "ACINReviewDTO",
]
