"""Semantic acknowledgement contracts for exchange delivery."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class AcknowledgementType(str, Enum):
    RECEIVED = "RECEIVED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    PARTIAL = "PARTIAL"


class ExchangeAcknowledgement(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    acknowledgement_id: str = Field(..., min_length=1)
    delivery_id: str = Field(..., min_length=1)
    exchange_id: str = Field(..., min_length=1)
    ack_type: AcknowledgementType
    remote_reference: str | None = None
    error_code: str | None = None
    error_detail_redacted: str | None = None
    received_at: datetime


__all__ = ["AcknowledgementType", "ExchangeAcknowledgement"]
