"""
ADAPTIX GRAVITY MODULE CONTRACTS
ADAPTIX_PLATFORM_GRAVITY_COMPLETION_LOCK

Authoritative Pydantic schemas for all gravity-level modules.
These contracts are the boundary between frontend and backend.
No frontend module may invent local-only DTOs for backend-backed state.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field

# ─── Enums ───────────────────────────────────────────────────────────────────


class GravityModuleState(str, Enum):
    LOADING = "loading"
    READY = "ready"
    ERROR = "error"
    DEGRADED = "degraded"
    EMPTY = "empty"
    STALE = "stale"


class GravityRiskLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class GravityActionStatus(str, Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    SNOOZED = "snoozed"
    RESOLVED = "resolved"


class GravityNotificationSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class GravityNotificationState(str, Enum):
    UNREAD = "unread"
    READ = "read"
    RESOLVED = "resolved"
    SNOOZED = "snoozed"
    ESCALATED = "escalated"


# ─── AI Run Payload ───────────────────────────────────────────────────────────


class GravityAIRunPayload(BaseModel):
    """
    Authoritative AI run contract.
    Every AI output must include source, confidence, risk level, and human action boundary.
    AI may NOT finalize records, submit exports, send messages, or alter authoritative state
    without human acceptance.
    """

    ai_run_id: str
    model_or_engine_id: str
    source_record_ids: list[str] = Field(default_factory=list)
    source_evidence: list[str] = Field(default_factory=list)
    generated_at: datetime
    confidence_score: float = Field(ge=0.0, le=1.0)
    risk_level: GravityRiskLevel
    human_action_required: bool
    recommended_action: str | None = None
    explanation: str
    accepted_at: datetime | None = None
    accepted_by: str | None = None
    rejected_at: datetime | None = None
    rejected_by: str | None = None
    audit_event_id: str | None = None


# ─── Audit Event Payload ──────────────────────────────────────────────────────


class GravityAuditEventPayload(BaseModel):
    """
    Immutable audit event. Every mutation must write an audit event.
    No silent writes. No silent failures.
    """

    id: str
    tenant_id: str
    actor_id: str
    actor_name: str | None = None
    action: str
    resource_type: str
    resource_id: str
    changes: Optional[dict[str, Any]] = None
    metadata: Optional[dict[str, Any]] = None
    timestamp: datetime
    version: int = 1


# ─── Notification Payload ─────────────────────────────────────────────────────


class GravityNotificationPayload(BaseModel):
    """
    Unified notification contract.
    All modules route user-visible action feedback through the notification system.
    """

    id: str
    tenant_id: str
    title: str
    message: str | None = None
    severity: GravityNotificationSeverity
    state: GravityNotificationState = GravityNotificationState.UNREAD
    module: str
    source_record_id: str | None = None
    source_record_type: str | None = None
    action_url: str | None = None
    created_at: datetime
    read_at: datetime | None = None
    resolved_at: datetime | None = None
    snoozed_until: datetime | None = None
    escalated_at: datetime | None = None
    audit_event_id: str | None = None


# ─── Action Payload ───────────────────────────────────────────────────────────


class GravityActionPayload(BaseModel):
    """
    Prioritized action item requiring human decision.
    """

    id: str
    tenant_id: str
    label: str
    description: str | None = None
    severity: GravityRiskLevel
    status: GravityActionStatus = GravityActionStatus.OPEN
    assignee_id: str | None = None
    assignee_name: str | None = None
    due_at: datetime | None = None
    snoozed_until: datetime | None = None
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    source_module: str
    source_record_id: str | None = None
    created_at: datetime
    updated_at: datetime
    audit_event_id: str | None = None


# ─── Validation Result ────────────────────────────────────────────────────────


class GravityValidationError(BaseModel):
    field: str
    message: str
    code: str
    severity: GravityRiskLevel = GravityRiskLevel.HIGH


class GravityValidationResult(BaseModel):
    """
    Structured validation result. Never suppress low-confidence errors.
    """

    valid: bool
    errors: list[GravityValidationError] = Field(default_factory=list)
    warnings: list[GravityValidationError] = Field(default_factory=list)
    validated_at: datetime
    validator_version: str = "1.0"


# ─── Error Envelope ───────────────────────────────────────────────────────────


class GravityErrorEnvelope(BaseModel):
    """
    Structured error response. Never return fake success.
    """

    error_code: str
    message: str
    detail: str | None = None
    field: str | None = None
    retry_allowed: bool = True
    timestamp: datetime
    request_id: str | None = None


# ─── Pagination ───────────────────────────────────────────────────────────────


class GravityPaginatedResponse(BaseModel):
    """
    Standard paginated response envelope.
    """

    items: list[Any]
    total: int
    page: int = 1
    limit: int = 50
    has_more: bool = False
