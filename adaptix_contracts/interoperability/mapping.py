"""Versioned semantic mapping contracts between source standards and canonical data."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MappingType(str, Enum):
    DIRECT = "DIRECT"
    NORMALIZED = "NORMALIZED"
    CONDITIONAL = "CONDITIONAL"
    DERIVED = "DERIVED"
    NO_EQUIVALENT = "NO_EQUIVALENT"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class SemanticMappingRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    mapping_rule_id: str = Field(..., min_length=1)
    mapping_set_id: str = Field(..., min_length=1)
    source_standard: str = Field(..., min_length=1)
    source_version: str = Field(..., min_length=1)
    source_path: str = Field(..., min_length=1)
    canonical_path: str = Field(..., min_length=1)
    target_standard: str | None = None
    target_version: str | None = None
    target_path: str | None = None
    mapping_type: MappingType
    transform: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    conditions: dict[str, Any] = Field(default_factory=dict)
    effective_from: datetime
    deprecated_at: datetime | None = None
    source_reference: str | None = None


class MappingPreviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mapped: list[dict[str, Any]] = Field(default_factory=list)
    unmapped: list[dict[str, Any]] = Field(default_factory=list)
    conditional: list[dict[str, Any]] = Field(default_factory=list)
    blocked: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    mapping_evidence: list[dict[str, Any]] = Field(default_factory=list)


__all__ = ["MappingPreviewResult", "MappingType", "SemanticMappingRule"]
