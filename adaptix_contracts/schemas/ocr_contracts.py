"""OCR extraction contract schemas for cross-domain communication.

Defines all typed contracts for the OCR job lifecycle: submission,
field candidate extraction, confidence scoring, human review, approval,
and structured field promotion into transport and care records.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class OcrSourceType(str, Enum):
    PCS = "pcs"
    AOB = "aob"
    PHYSICIAN_CERTIFICATION = "physician_certification"
    TRANSPORT_CONSENT = "transport_consent"
    FACE_SHEET = "face_sheet"
    PRIOR_AUTHORIZATION = "prior_authorization"
    OTHER = "other"


class OcrJobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    EXTRACTION_COMPLETE = "extraction_complete"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"


class OcrFieldConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNRESOLVED = "unresolved"


class OcrJobCreate(BaseModel):
    source_type: OcrSourceType
    document_id: str
    transport_request_id: str | None = None
    chart_id: str | None = None
    s3_key: str
    tenant_id: str
    requested_by_user_id: str


class OcrJobStatusResponse(BaseModel):
    id: str
    tenant_id: str

    source_type: OcrSourceType
    document_id: str

    transport_request_id: str | None = None
    chart_id: str | None = None

    status: OcrJobStatus

    field_candidates_count: int
    review_required_count: int
    approved_count: int

    submitted_at: datetime
    extraction_completed_at: datetime | None = None
    reviewed_at: datetime | None = None
    reviewer_user_id: str | None = None

    failure_reason: str | None = None


class OcrFieldCandidateResponse(BaseModel):
    id: str
    job_id: str

    field_name: str
    extracted_value: str
    normalized_value: str | None = None

    confidence: OcrFieldConfidence
    confidence_score: float = Field(..., ge=0.0, le=1.0)

    page_number: int | None = None
    bounding_box: dict | None = None

    alternative_values: list[str] = Field(default_factory=list)

    review_status: str
    reviewer_note: str | None = None


class OcrJobDetailResponse(BaseModel):
    id: str
    tenant_id: str

    source_type: OcrSourceType
    document_id: str

    transport_request_id: str | None = None
    chart_id: str | None = None

    status: OcrJobStatus

    submitted_at: datetime
    extraction_completed_at: datetime | None = None

    field_candidates: list[OcrFieldCandidateResponse]

    failure_reason: str | None = None


class OcrFieldApproval(BaseModel):
    field_candidate_id: str
    approved: bool
    corrected_value: str | None = None
    reviewer_note: str | None = Field(default=None, max_length=500)


class OcrApprovalRequest(BaseModel):
    job_id: str
    reviewer_user_id: str

    field_approvals: list[OcrFieldApproval]

    overall_approved: bool
    rejection_reason: str | None = None


class OcrApprovalResponse(BaseModel):
    job_id: str
    status: OcrJobStatus

    approved_fields: int
    rejected_fields: int

    promoted_to_structured: bool
    reviewed_at: datetime


class OcrExtractionCompletedEvent(BaseModel):
    event_type: str = "care.ocr.extraction_completed"

    job_id: str
    tenant_id: str

    source_type: OcrSourceType
    document_id: str

    transport_request_id: str | None = None
    chart_id: str | None = None

    field_candidates_count: int
    review_required: bool

    completed_at: datetime


class OcrFieldsApprovedEvent(BaseModel):
    event_type: str = "care.ocr.fields_approved"

    job_id: str
    tenant_id: str

    transport_request_id: str | None = None
    chart_id: str | None = None

    approved_fields_count: int
    promoted_at: datetime
