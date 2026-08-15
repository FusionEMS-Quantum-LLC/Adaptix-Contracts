"""Office Ally migration/read-only clearinghouse contracts.

Canonical historical submission, response, and enrollment-status shapes for
Office Ally data imported into Adaptix. These models do not authorize Office
Ally as a live billing claim submitter; live submissions are STEDI-only.
"""
# This legacy DTO module intentionally mirrors the common schema-file layout.
# pylint: disable=duplicate-code

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class OfficeAllyEnrollmentStatus(str, Enum):
    """Enrollment state of a provider/payer with Office Ally."""

    NOT_ENROLLED = "not_enrolled"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ACTIVE = "active"
    SUSPENDED = "suspended"


# ---------------------------------------------------------------------------
# Enrollment
# ---------------------------------------------------------------------------


class OfficeAllyEnrollment(BaseModel):
    """Provider/payer enrollment record with Office Ally."""

    model_config = ConfigDict(from_attributes=True)

    tenant_id: UUID
    status: OfficeAllyEnrollmentStatus
    npi: Optional[str] = Field(None, max_length=10)
    provider_id: Optional[str] = Field(None, max_length=64)
    payer_id: Optional[str] = Field(None, max_length=64)
    enrolled_at: Optional[datetime] = None
    updated_at: datetime


# ---------------------------------------------------------------------------
# Submission & Response
# ---------------------------------------------------------------------------


class OfficeAllySubmission(BaseModel):
    """A historical/imported X12 submission associated with Office Ally."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    correlation_id: Optional[str] = None
    claim_id: Optional[str] = Field(None, max_length=64)
    batch_id: Optional[str] = Field(None, max_length=64)
    submission_type: str = Field(
        ..., min_length=1, max_length=32, description="e.g. 837P, 837I, 270."
    )
    file_name: Optional[str] = Field(None, max_length=255)
    payload_reference: Optional[str] = Field(
        None, max_length=2000, description="Pointer to the stored X12 payload."
    )
    submitted_at: Optional[datetime] = None
    created_at: datetime


class OfficeAllyResponse(BaseModel):
    """An acknowledgement/response received from Office Ally."""

    submission_id: UUID
    tenant_id: UUID
    accepted: bool
    office_ally_ref: Optional[str] = Field(None, max_length=128)
    ack_type: Optional[str] = Field(
        None, max_length=32, description="e.g. 999, 277CA, TA1."
    )
    status_code: Optional[str] = Field(None, max_length=32)
    message: Optional[str] = Field(None, max_length=2000)
    errors: list[str] = Field(default_factory=list)
    received_at: datetime
