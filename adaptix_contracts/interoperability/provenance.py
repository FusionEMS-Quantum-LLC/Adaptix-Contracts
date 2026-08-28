"""Provenance contracts for the AdaptixCore interagency exchange fabric."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class TransformationType(str, Enum):
    """What happened to a value between its source system and canonical form.

    ``DIRECT`` carried the source value through unchanged, ``NORMALIZED``
    reshaped it into canonical form, ``DERIVED`` computed it from other
    values, and ``USER_CONFIRMED`` records that a person affirmed it. Keeping
    the four distinct is what lets a consumer tell a reported fact from a
    computed one.
    """

    DIRECT = "DIRECT"
    NORMALIZED = "NORMALIZED"
    DERIVED = "DERIVED"
    USER_CONFIRMED = "USER_CONFIRMED"


# pylint too-few-public-methods (R0903) is disabled per class below. These are
# declarative Pydantic wire contracts whose entire contract IS their field set,
# exactly the shape pylint already exempts for @dataclass; the rule's intent (a
# class doing so little it should be a function or a tuple) cannot apply to a
# validated wire contract. Per class, never module-wide, so a future non-schema
# class added to this module is still checked.
class DataProvenance(BaseModel):  # pylint: disable=too-few-public-methods
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
