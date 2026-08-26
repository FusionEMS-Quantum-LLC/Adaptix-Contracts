"""Sharing policy contracts. Trust and disclosure policy are intentionally separate."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ShareDirection(str, Enum):
    SEND = "SEND"
    RECEIVE = "RECEIVE"
    BOTH = "BOTH"


class SharePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    sharing_policy_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    description: str | None = None
    peer_id: str | None = None
    resource_type: str = Field(..., min_length=1)
    purpose_of_use: str = Field(..., min_length=1)
    direction: ShareDirection
    automatic_share: bool = False
    require_patient_match: bool = False
    require_consent: bool = False
    allow_break_glass: bool = False
    minimum_identity_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    enabled: bool = True


__all__ = ["ShareDirection", "SharePolicy"]
