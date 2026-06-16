"""
GRAVITY DOCUMENTS CONTRACTS
ADAPTIX_PLATFORM_GRAVITY_COMPLETION_LOCK
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class DocumentState(str, Enum):
    UPLOADING = "uploading"
    PROCESSING = "processing"
    OCR_PENDING = "ocr_pending"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    LEGAL_HOLD = "legal_hold"
    EXPIRED = "expired"


class DocumentSensitivity(str, Enum):
    PHI = "phi"
    PII = "pii"
    CONFIDENTIAL = "confidential"
    PUBLIC = "public"


class DocumentReviewAction(BaseModel):
    id: str
    document_id: str
    action: str
    actor_id: str
    actor_name: str | None = None
    reason: str | None = None
    created_at: datetime


class DocumentResponse(BaseModel):
    id: str
    tenant_id: str
    record_id: str
    name: str
    document_type: str
    state: DocumentState
    sensitivity: DocumentSensitivity
    mime_type: str
    size_bytes: int
    content_hash: str
    current_version: int
    legal_hold: bool
    audit_hold: bool
    uploaded_by: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class DocumentListItemResponse(BaseModel):
    id: str
    name: str
    document_type: str
    state: DocumentState
    sensitivity: DocumentSensitivity
    size_bytes: int
    uploaded_by: str
    created_at: datetime
    updated_at: datetime
    link_count: int


class DocumentListResponse(BaseModel):
    items: list[DocumentListItemResponse]
    total: int
    page: int
    limit: int


class DocumentReviewRequest(BaseModel):
    reason: str | None = None


class DocumentReviewResponse(BaseModel):
    document: DocumentResponse
    audit_event_id: str


class BulkDocumentRequest(BaseModel):
    document_ids: list[str]


class BulkDocumentResponse(BaseModel):
    processed: int
    audit_event_id: str
