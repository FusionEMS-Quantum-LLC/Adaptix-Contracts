"""ACIN score set — the 10 AI scores, model-attributed.

The 10 scores mirror the founder spec. Eight are 0-100 quality scores; two are
raw counts (contradictions, missing elements). Every score set is attributed to
the model that produced it and may reference the existing RunIQ / ChartIntel
score rows it aggregates (ACIN aggregates rather than silently recomputing).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ACINScoreSetDTO(BaseModel):
    """The 10-score ACIN score set for one record (model-attributed)."""

    acin_record_id: str
    tenant_id: str
    chart_id: str

    # Eight 0-100 quality scores.
    clinical_completeness: float = Field(ge=0.0, le=100.0)
    medical_necessity: float = Field(ge=0.0, le=100.0)
    billing_readiness: float = Field(ge=0.0, le=100.0)
    legal_defensibility: float = Field(ge=0.0, le=100.0)
    nemsis_compliance: float = Field(ge=0.0, le=100.0)
    protocol_compliance: float = Field(ge=0.0, le=100.0)
    documentation_quality: float = Field(ge=0.0, le=100.0)
    audit_risk: float = Field(ge=0.0, le=100.0)

    # Two raw counts.
    contradictions_count: int = Field(ge=0)
    missing_elements_count: int = Field(ge=0)

    # Model attribution.
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    capability_key: str = "acin.scoring"
    scored_at: Optional[datetime] = None

    # Aggregation provenance — references to existing score rows this set draws from.
    source_run_iq_score_id: Optional[str] = None
    source_chart_intel_score_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


__all__ = ["ACINScoreSetDTO"]
