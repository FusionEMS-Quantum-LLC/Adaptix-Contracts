"""Audit and compliance contracts.

Defines typed contracts for immutable audit logging, access tracing,
PHI-sensitive actions, security events, and compliance review workflows.

These contracts provide the canonical cross-domain audit surface for Adaptix.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuditActorType(str, Enum):
    """Actor classification for an audited action."""

    USER = "user"
    SYSTEM = "system"
    SERVICE = "service"
    PATIENT = "patient"
    UNKNOWN = "unknown"


class AuditActionType(str, Enum):
    """Canonical action categories for audit events."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXPORT = "export"
    SIGN = "sign"
    SUBMIT = "submit"
    APPROVE = "approve"
    REJECT = "reject"
    LOGIN = "login"
    LOGOUT = "logout"
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"


class AuditSeverity(str, Enum):
    """Severity classification for audit and security events."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ComplianceReviewStatus(str, Enum):
    """Status of a compliance review item."""

    OPEN = "open"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class AuditContext(BaseModel):
    """Context surrounding an audited operation."""

    tenant_id: str
    correlation_id: Optional[str] = None
    request_id: Optional[str] = None
    source_ip: Optional[str] = None
    user_agent: Optional[str] = None
    service_name: Optional[str] = None


class AuditRecord(BaseModel):
    """Canonical immutable audit record."""

    audit_id: str

    actor_type: AuditActorType
    actor_id: Optional[str] = None
    actor_name: Optional[str] = None

    action_type: AuditActionType
    resource_type: str
    resource_id: Optional[str] = None

    success: bool
    severity: AuditSeverity = AuditSeverity.LOW

    context: AuditContext

    changed_fields: list[str] = Field(default_factory=list)
    reason: Optional[str] = None
    occurred_at: datetime


class PhiAccessRecord(BaseModel):
    """PHI-specific access trace for compliance review."""

    access_id: str
    tenant_id: str

    actor_id: str
    patient_id: str

    resource_type: str
    resource_id: Optional[str] = None

    access_purpose: str
    minimum_necessary_asserted: bool

    occurred_at: datetime


class SecurityEventRecord(BaseModel):
    """Security-significant system event."""

    event_id: str
    tenant_id: Optional[str] = None

    event_type: str
    severity: AuditSeverity

    actor_id: Optional[str] = None
    source_ip: Optional[str] = None

    description: str
    detected_at: datetime


class ComplianceReviewItem(BaseModel):
    """Manual or automated compliance review work item."""

    review_id: str
    tenant_id: str

    related_audit_id: Optional[str] = None
    related_security_event_id: Optional[str] = None

    title: str
    description: str

    status: ComplianceReviewStatus
    severity: AuditSeverity

    assigned_to_user_id: Optional[str] = None
    opened_at: datetime
    resolved_at: Optional[datetime] = None


class AuditRecordCreatedEvent(BaseModel):
    """Published when an audit record is created."""

    event_type: str = "audit.record.created"

    audit_id: str
    tenant_id: str
    resource_type: str
    resource_id: Optional[str] = None

    occurred_at: datetime


class PhiAccessLoggedEvent(BaseModel):
    """Published when PHI access is logged."""

    event_type: str = "audit.phi_access.logged"

    access_id: str
    tenant_id: str
    patient_id: str
    actor_id: str

    occurred_at: datetime


class SecurityEventDetectedEvent(BaseModel):
    """Published when a security-significant event is detected."""

    event_type: str = "audit.security_event.detected"

    event_id: str
    tenant_id: Optional[str] = None
    severity: AuditSeverity

    detected_at: datetime


class ComplianceReviewOpenedEvent(BaseModel):
    """Published when a compliance review item is opened."""

    event_type: str = "audit.compliance_review.opened"

    review_id: str
    tenant_id: str
    severity: AuditSeverity

    opened_at: datetime


# ---------------------------------------------------------------------------
# Domain-Specific Audit Action Codes (additive — backward-compatible)
# ---------------------------------------------------------------------------


class AuditDomainAction(str, Enum):
    """Semantic audit action codes for individual Adaptix domains.

    These codes give compliance and HIPAA audit logs precise, human-readable
    context beyond the generic CREATE/READ/UPDATE categories in AuditActionType.
    Services should record both AuditActionType (broad category) and
    AuditDomainAction (specific operation) on the same audit record.
    """

    # HIPAA PHI access
    PHI_ACCESSED = "phi_accessed"
    CHART_VIEWED = "chart_viewed"
    CHART_CREATED = "chart_created"
    CHART_UPDATED = "chart_updated"
    CHART_SUBMITTED = "chart_submitted"
    CHART_SIGNED = "chart_signed"
    CHART_APPROVED = "chart_approved"
    CHART_REJECTED = "chart_qa_rejected"
    NEMSIS_EXPORTED = "nemsis_exported"

    # Billing
    CLAIM_CREATED = "claim_created"
    CLAIM_SUBMITTED = "claim_submitted"
    CLAIM_PAID = "claim_paid"
    CLAIM_DENIED = "claim_denied"

    # Admin / Agency
    AGENCY_ACTIVATED = "agency_activated"
    AGENCY_SUSPENDED = "agency_suspended"
    USER_INVITED = "user_invited"
    USER_DEACTIVATED = "user_deactivated"

    # Dispatch
    DISPATCH_CREATED = "dispatch_created"
    DISPATCH_STATUS_UPDATED = "dispatch_status_updated"
    DISPATCH_CLOSED = "dispatch_closed"

    # Narcotics (DEA-compliant)
    NARCOTIC_RECEIVED = "narcotic_received"
    NARCOTIC_ADMINISTERED = "narcotic_administered"
    NARCOTIC_WASTED = "narcotic_wasted"
    NARCOTIC_DISCREPANCY = "narcotic_discrepancy"

    # Search / Interoperability
    SEARCH_PERFORMED = "search_performed"
    INTEROP_DATA_SENT = "interop_data_sent"
    INTEROP_DATA_RECEIVED = "interop_data_received"


class AuditEntry(BaseModel):
    """Lightweight HIPAA-compliant audit log entry for cross-service emission.

    Intended for services that need a minimal, easy-to-emit audit record
    without the full AuditRecord/AuditContext hierarchy. No PHI values
    (names, DOBs, SSNs) are stored — only entity IDs.
    """

    service: str = Field(
        ...,
        description="Short service name: 'core', 'cad', 'billing', 'epcr', etc.",
    )
    action: AuditDomainAction
    entity_type: str = Field(
        ..., description="Resource type: 'chart', 'claim', 'dispatch', etc."
    )
    entity_id: str = Field(
        ..., description="Opaque entity ID. Never a patient name or DOB."
    )
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    ip_address: Optional[str] = None
    timestamp: datetime


# ---------------------------------------------------------------------------
# Audit Service Contracts (shared AdaptixCore Audit service)
# ---------------------------------------------------------------------------


class AuditExportFormat(str, Enum):
    """Serialization format for an audit export."""

    CSV = "csv"
    JSON = "json"
    NDJSON = "ndjson"


class AuditEvent(BaseModel):
    """Immutable audit event for the shared AdaptixCore Audit service.

    ``resource_id`` is typed as ``str`` because audited resources span every
    domain and their identifier types vary. ``action`` is a free-form action
    code (services may pass an ``AuditDomainAction`` value or a custom code).
    """

    model_config = ConfigDict(frozen=True)

    event_id: Optional[UUID] = None
    tenant_id: UUID
    actor_user_id: Optional[UUID] = None
    actor_type: AuditActorType = AuditActorType.USER
    action: str = Field(..., min_length=1, max_length=160)
    resource_type: str = Field(..., min_length=1, max_length=120)
    resource_id: Optional[str] = Field(None, max_length=255)
    correlation_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime


class AuditSearchQuery(BaseModel):
    """Query parameters for searching immutable audit events."""

    tenant_id: UUID
    actor_user_id: Optional[UUID] = None
    action: Optional[str] = Field(None, max_length=160)
    resource_type: Optional[str] = Field(None, max_length=120)
    resource_id: Optional[str] = Field(None, max_length=255)
    correlation_id: Optional[str] = None
    occurred_after: Optional[datetime] = None
    occurred_before: Optional[datetime] = None
    limit: int = Field(50, ge=1, le=1000)
    offset: int = Field(0, ge=0)


class AuditExportRequest(BaseModel):
    """Request to export a set of audit events matching a query."""

    tenant_id: UUID
    query: AuditSearchQuery
    export_format: AuditExportFormat = AuditExportFormat.CSV
    requested_by: Optional[UUID] = None
    correlation_id: Optional[str] = None
    requested_at: datetime


# ---------------------------------------------------------------------------
# Ingest / Search / Export Request-Response DTOs
#
# These complete the canonical Audit *service* surface: the shared Audit
# service accepts events via the ingest request, returns paged results for a
# search query, and reports on an export request. They supersede the direct-
# write client in ``adaptix_contracts.audit_contracts`` (deprecated), which
# embedded persistence in each caller instead of going through the service.
# ---------------------------------------------------------------------------


class AuditIngestRequest(BaseModel):
    """Request to append one audit event to the shared Audit service.

    Ingest is append-only and idempotent: the service deduplicates on the
    (``tenant_id``, ``action``, ``resource_id``, ``idempotency_key``) tuple
    when ``idempotency_key`` is provided, so a producer may safely retry.
    """

    tenant_id: UUID
    actor_user_id: Optional[UUID] = None
    actor_type: AuditActorType = AuditActorType.USER
    action: str = Field(..., min_length=1, max_length=160)
    resource_type: str = Field(..., min_length=1, max_length=120)
    resource_id: Optional[str] = Field(None, max_length=255)
    severity: AuditSeverity = AuditSeverity.LOW
    success: bool = True
    correlation_id: Optional[str] = None
    idempotency_key: Optional[str] = Field(None, max_length=255)
    metadata: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime


class AuditIngestResponse(BaseModel):
    """Result of an audit ingest request."""

    event_id: UUID
    accepted: bool = True
    duplicate: bool = Field(
        False, description="True when idempotency matched an existing event."
    )
    occurred_at: datetime


class AuditSearchResponse(BaseModel):
    """Paginated result set for an :class:`AuditSearchQuery`."""

    events: list[AuditEvent] = Field(default_factory=list)
    total: int = Field(0, ge=0)
    limit: int = Field(50, ge=1, le=1000)
    offset: int = Field(0, ge=0)


class AuditExportStatus(str, Enum):
    """Lifecycle state of an audit export job."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AuditExportResponse(BaseModel):
    """Status and location of a requested audit export."""

    export_id: UUID
    tenant_id: UUID
    export_format: AuditExportFormat
    status: AuditExportStatus = AuditExportStatus.PENDING
    record_count: Optional[int] = Field(None, ge=0)
    location: Optional[str] = Field(
        None,
        max_length=1024,
        description="Object-store URI (e.g. s3://...) of the exported evidence set.",
    )
    error_reason: Optional[str] = None
    requested_at: datetime
    completed_at: Optional[datetime] = None
