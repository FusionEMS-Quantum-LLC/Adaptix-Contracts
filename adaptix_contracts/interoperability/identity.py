"""Identity references used by canonical interoperability resources.

Patient matching remains owned by Adaptix-Patient-Identity-Service. These are
references only; they deliberately do not implement matching logic.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PatientIdentityReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    patient_identity_ref: str = Field(..., min_length=1)
    external_patient_identity_ref: str | None = None
    match_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    match_status: str | None = None


__all__ = ["PatientIdentityReference"]
