"""Provenance contracts for the AdaptixCore interagency exchange fabric."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class TransformationType(str, Enum):
    DIRECT = "DIRECT"
    NORMALIZED = "NORMALIZED"
    DERIVED = "DERIVED"
    USER_CONFIRMED = "USER_CONFIRMED"


class DataProvenance(BaseModel):
    """Evidence describing the exact origin and transformation of a value."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    source_agency_id: str = Field(..., min_length=1)
    source_tenant_id: str = Field(..., min_length=1)
    source_service: str = Field(..., min_length=1)
    source_record_id: str = Field(..., min_length=1)
    source_field: str | None = None
    source_standard: str | None = None
    source_standard_version: str | None = None
    mapping_set_id: str | None = None
    mapping_rule_id: str | None = None
    mapping_version: str | None = None
    transformation_type: TransformationType
    confidence: float = Field(..., ge=0.0, le=1.0)
    observed_at: datetime
    received_at: datetime


__all__ = ["DataProvenance", "TransformationType"]
