"""NEMSIS 3.5.1 gravity-level export lifecycle contracts.

This module defines the authoritative contract layer for chart-level NEMSIS export,
validation, artifact persistence, queueing, state submission, retry lineage,
and audit history.

Design goals:
- no ambiguous lifecycle states
- no illegal success/failure combinations
- explicit async queue/submission modeling
- explicit validation issue structure
- explicit downstream response capture
- explicit retry lineage and idempotency
- stable machine-readable reason codes alongside human-readable detail
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class NemsisVersion(str, Enum):
    V3_5_1 = "3.5.1"


class ExportLifecycleStatus(str, Enum):
    BLOCKED = "blocked"

    REQUESTED = "requested"
    GENERATION_IN_PROGRESS = "generation_in_progress"
    GENERATED = "generated"

    VALIDATION_IN_PROGRESS = "validation_in_progress"
    VALIDATION_FAILED = "validation_failed"
    VALIDATION_PASSED = "validation_passed"

    PERSISTENCE_IN_PROGRESS = "persistence_in_progress"
    PERSISTENCE_FAILED = "persistence_failed"
    READY_FOR_SUBMISSION = "ready_for_submission"

    QUEUED_FOR_SUBMISSION = "queued_for_submission"
    SUBMISSION_IN_PROGRESS = "submission_in_progress"
    SUBMISSION_PENDING = "submission_pending"
    SUBMISSION_ACCEPTED = "submission_accepted"
    SUBMISSION_REJECTED = "submission_rejected"

    RETRIEVAL_IN_PROGRESS = "retrieval_in_progress"
    RETRIEVAL_FAILED = "retrieval_failed"

    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class ExportFailureType(str, Enum):
    READINESS_BLOCKED = "readiness_blocked"
    GENERATION_ERROR = "generation_error"
    VALIDATION_ERROR = "validation_error"
    PERSISTENCE_ERROR = "persistence_error"
    QUEUE_ERROR = "queue_error"
    SUBMISSION_ERROR = "submission_error"
    RETRIEVAL_ERROR = "retrieval_error"
    TIMEOUT = "timeout"
    CANCELED = "canceled"
    UNKNOWN = "unknown"


class ExportTriggerSource(str, Enum):
    CHART = "chart"
    READINESS_PAGE = "readiness_page"
    OPERATOR_PANEL = "operator_panel"
    MANUAL_RETRY = "manual_retry"
    SYSTEM_RETRY = "system_retry"
    API = "api"
    FINALIZATION_PIPELINE = "finalization_pipeline"
    BATCH_EXPORT = "batch_export"


class SubmissionChannel(str, Enum):
    NONE = "none"
    STATE_API = "state_api"
    NEMSIS_WEB_SERVICE = "nemsis_web_service"
    CERTIFICATION_EXPORT = "certification_export"
    FILE_DOWNLOAD = "file_download"


class SubmissionLifecycleStatus(str, Enum):
    NOT_REQUESTED = "not_requested"
    QUEUED = "queued"
    SUBMITTED = "submitted"
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"


class ValidationIssueLevel(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ArtifactStorageKind(str, Enum):
    NONE = "none"
    DATABASE = "database"
    OBJECT_STORAGE = "object_storage"
    FILE_SYSTEM = "file_system"


class ExportScope(str, Enum):
    SINGLE_RECORD = "single_record"
    BATCH = "batch"
    CERTIFICATION_RUN = "certification_run"


class ExportReadinessSnapshot(BaseModel):
    ready_for_export: bool
    blocker_count: int
    warning_count: int

    readiness_score: float | None = None
    mandatory_completion_percentage: float | None = None

    missing_mandatory_fields: list[str] = Field(default_factory=list)
    missing_recommended_fields: list[str] = Field(default_factory=list)

    blocking_rule_ids: list[str] = Field(default_factory=list)
    warning_rule_ids: list[str] = Field(default_factory=list)

    derived_from_validation: bool = True
    captured_at: datetime | None = None


class ExportArtifactMetadata(BaseModel):
    file_name: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None

    checksum_sha256: str | None = None

    storage_kind: ArtifactStorageKind = ArtifactStorageKind.NONE
    storage_key: str | None = None

    has_xml_payload: bool = False
    xml_base64_included: bool = False

    generated_at: datetime | None = None
    persisted_at: datetime | None = None


class ExportValidationIssue(BaseModel):
    issue_id: str | None = None
    level: ValidationIssueLevel
    code: str | None = None
    path: str | None = None
    element_id: str | None = None
    ui_section: str | None = None
    suggested_fix: str | None = None
    message: str


class ExportValidationMetadata(BaseModel):
    valid: bool | None = None
    xsd_valid: bool | None = None
    schematron_valid: bool | None = None

    errors: list[ExportValidationIssue] = Field(default_factory=list)
    warnings: list[ExportValidationIssue] = Field(default_factory=list)

    validator_asset_version: str | None = None
    checksum_sha256: str | None = None

    validated_at: datetime | None = None
    validation_duration_ms: int | None = None


class DownstreamResponseMetadata(BaseModel):
    http_status_code: int | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    body_excerpt: str | None = None
    response_blob: dict[str, Any] | None = None
    received_at: datetime | None = None


class ExportSubmissionMetadata(BaseModel):
    channel: SubmissionChannel = SubmissionChannel.NONE
    submission_status: SubmissionLifecycleStatus = (
        SubmissionLifecycleStatus.NOT_REQUESTED
    )

    queue_message_id: str | None = None
    correlation_id: str | None = None
    submission_request_handle: str | None = None

    state_code: str | None = None
    endpoint_url: str | None = None

    submitted_at: datetime | None = None
    last_checked_at: datetime | None = None
    completed_at: datetime | None = None

    downstream_response: DownstreamResponseMetadata | None = None


class ExportStatusHistoryEntry(BaseModel):
    status: ExportLifecycleStatus
    at: datetime

    failure_type: ExportFailureType | None = None
    status_reason_code: str | None = None
    summary: str | None = None


class ExportAttemptSummary(BaseModel):
    export_id: int
    chart_id: str
    tenant_id: str

    scope: ExportScope = ExportScope.SINGLE_RECORD
    nemsis_version: NemsisVersion = NemsisVersion.V3_5_1
    state_dataset: str | None = None

    status: ExportLifecycleStatus
    failure_type: ExportFailureType | None = None

    trigger_source: ExportTriggerSource
    retry_count: int = 0
    attempt_sequence: int = 1

    status_reason_code: str | None = None
    message: str | None = None

    has_artifact: bool = False
    has_validation: bool = False
    has_submission: bool = False

    created_at: datetime
    updated_at: datetime


class ExportAttemptDetail(BaseModel):
    export_id: int
    chart_id: str
    tenant_id: str

    scope: ExportScope = ExportScope.SINGLE_RECORD
    nemsis_version: NemsisVersion = NemsisVersion.V3_5_1
    state_dataset: str | None = None

    status: ExportLifecycleStatus
    failure_type: ExportFailureType | None = None

    trigger_source: ExportTriggerSource

    retry_count: int = 0
    attempt_sequence: int = 1

    idempotency_key: str | None = None
    correlation_id: str | None = None

    status_reason_code: str | None = None
    message: str | None = None
    failure_reason: str | None = None

    supersedes_export_id: int | None = None
    superseded_by_export_id: int | None = None

    readiness_snapshot: ExportReadinessSnapshot
    artifact: ExportArtifactMetadata | None = None
    validation: ExportValidationMetadata | None = None
    submission: ExportSubmissionMetadata | None = None
    history: list[ExportStatusHistoryEntry] = Field(default_factory=list)

    created_at: datetime
    updated_at: datetime

    requested_at: datetime | None = None
    generation_started_at: datetime | None = None
    generated_at: datetime | None = None
    validation_started_at: datetime | None = None
    validated_at: datetime | None = None
    persistence_started_at: datetime | None = None
    persisted_at: datetime | None = None
    queued_at: datetime | None = None
    submission_started_at: datetime | None = None
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_lifecycle_consistency(self) -> ExportAttemptDetail:
        success_states = {
            ExportLifecycleStatus.COMPLETED,
            ExportLifecycleStatus.SUBMISSION_ACCEPTED,
        }
        failure_states = {
            ExportLifecycleStatus.BLOCKED,
            ExportLifecycleStatus.VALIDATION_FAILED,
            ExportLifecycleStatus.PERSISTENCE_FAILED,
            ExportLifecycleStatus.SUBMISSION_REJECTED,
            ExportLifecycleStatus.RETRIEVAL_FAILED,
            ExportLifecycleStatus.FAILED,
            ExportLifecycleStatus.CANCELED,
        }
        post_generation_states = {
            ExportLifecycleStatus.GENERATED,
            ExportLifecycleStatus.VALIDATION_IN_PROGRESS,
            ExportLifecycleStatus.VALIDATION_FAILED,
            ExportLifecycleStatus.VALIDATION_PASSED,
            ExportLifecycleStatus.PERSISTENCE_IN_PROGRESS,
            ExportLifecycleStatus.PERSISTENCE_FAILED,
            ExportLifecycleStatus.READY_FOR_SUBMISSION,
            ExportLifecycleStatus.QUEUED_FOR_SUBMISSION,
            ExportLifecycleStatus.SUBMISSION_IN_PROGRESS,
            ExportLifecycleStatus.SUBMISSION_PENDING,
            ExportLifecycleStatus.SUBMISSION_ACCEPTED,
            ExportLifecycleStatus.SUBMISSION_REJECTED,
            ExportLifecycleStatus.RETRIEVAL_IN_PROGRESS,
            ExportLifecycleStatus.RETRIEVAL_FAILED,
            ExportLifecycleStatus.COMPLETED,
        }

        if (
            self.status == ExportLifecycleStatus.BLOCKED
            and self.readiness_snapshot.ready_for_export
        ):
            raise ValueError("blocked export cannot have ready_for_export=True")

        if self.status in success_states and self.failure_type is not None:
            raise ValueError("successful terminal states cannot include failure_type")

        if self.status in failure_states and self.failure_type is None:
            raise ValueError("failed terminal states must include failure_type")

        if self.status in post_generation_states and self.artifact is None:
            raise ValueError("post-generation states require artifact metadata")

        if self.status in {
            ExportLifecycleStatus.VALIDATION_PASSED,
            ExportLifecycleStatus.READY_FOR_SUBMISSION,
            ExportLifecycleStatus.QUEUED_FOR_SUBMISSION,
            ExportLifecycleStatus.SUBMISSION_IN_PROGRESS,
            ExportLifecycleStatus.SUBMISSION_PENDING,
            ExportLifecycleStatus.SUBMISSION_ACCEPTED,
            ExportLifecycleStatus.COMPLETED,
        }:
            if self.validation is None:
                raise ValueError(
                    "validated submission-capable states require validation metadata"
                )
            if self.validation.valid is not True:
                raise ValueError(
                    "submission-capable states require validation.valid=True"
                )

        if self.validation and self.validation.valid is True and self.validation.errors:
            raise ValueError(
                "validation.valid=True cannot coexist with validation errors"
            )

        if self.status == ExportLifecycleStatus.QUEUED_FOR_SUBMISSION:
            if self.submission is None:
                raise ValueError("queued_for_submission requires submission metadata")
            if self.submission.submission_status != SubmissionLifecycleStatus.QUEUED:
                raise ValueError(
                    "queued_for_submission requires submission_status=queued"
                )

        if (
            self.status
            in {
                ExportLifecycleStatus.SUBMISSION_IN_PROGRESS,
                ExportLifecycleStatus.SUBMISSION_PENDING,
                ExportLifecycleStatus.SUBMISSION_ACCEPTED,
                ExportLifecycleStatus.SUBMISSION_REJECTED,
                ExportLifecycleStatus.RETRIEVAL_IN_PROGRESS,
                ExportLifecycleStatus.RETRIEVAL_FAILED,
                ExportLifecycleStatus.COMPLETED,
            }
            and self.submission is None
        ):
            raise ValueError("submission lifecycle states require submission metadata")

        if self.status == ExportLifecycleStatus.SUBMISSION_ACCEPTED:
            if self.submission and self.submission.submission_status not in {
                SubmissionLifecycleStatus.ACCEPTED,
                SubmissionLifecycleStatus.COMPLETED,
            }:
                raise ValueError(
                    "submission_accepted requires accepted/completed submission status"
                )

        if (
            self.completed_at is not None
            and self.status not in success_states | failure_states
        ):
            raise ValueError("completed_at is only valid for terminal states")

        return self


class GenerateExportRequest(BaseModel):
    chart_id: str
    state_dataset: str | None = None

    scope: ExportScope = ExportScope.SINGLE_RECORD
    trigger_source: ExportTriggerSource = ExportTriggerSource.CHART

    allow_retry_of_failed_attempt: bool = True
    idempotency_key: str | None = None


class GenerateExportResponse(BaseModel):
    export_id: int
    chart_id: str
    tenant_id: str

    scope: ExportScope = ExportScope.SINGLE_RECORD
    nemsis_version: NemsisVersion = NemsisVersion.V3_5_1
    state_dataset: str | None = None

    success: bool
    blocked: bool

    status: ExportLifecycleStatus
    failure_type: ExportFailureType | None = None

    status_reason_code: str | None = None
    message: str | None = None
    failure_reason: str | None = None

    retry_count: int = 0
    attempt_sequence: int = 1

    readiness_snapshot: ExportReadinessSnapshot
    artifact: ExportArtifactMetadata | None = None
    validation: ExportValidationMetadata | None = None

    created_at: datetime
    updated_at: datetime


class RetryExportRequest(BaseModel):
    trigger_source: ExportTriggerSource = ExportTriggerSource.MANUAL_RETRY
    idempotency_key: str | None = None
    retry_reason: str | None = None
    force_retry: bool = False


class RetryExportResponse(BaseModel):
    original_export_id: int
    new_export_id: int

    success: bool
    blocked: bool

    nemsis_version: NemsisVersion = NemsisVersion.V3_5_1
    state_dataset: str | None = None

    status: ExportLifecycleStatus
    failure_type: ExportFailureType | None = None

    status_reason_code: str | None = None
    message: str | None = None
    failure_reason: str | None = None

    retry_count: int
    attempt_sequence: int

    readiness_snapshot: ExportReadinessSnapshot

    created_at: datetime
    updated_at: datetime


class QueueExportSubmissionRequest(BaseModel):
    submission_channel: SubmissionChannel = SubmissionChannel.STATE_API
    state_code: str
    endpoint_url: str | None = None
    correlation_id: str | None = None


class QueueExportSubmissionResponse(BaseModel):
    export_id: int
    status: ExportLifecycleStatus
    queue_message_id: str | None = None
    submission: ExportSubmissionMetadata


class ExportHistoryResponse(BaseModel):
    chart_id: str
    total_count: int
    limit: int
    offset: int
    has_more: bool = False

    exports: list[ExportAttemptSummary]


class ExportDetailResponse(BaseModel):
    export: ExportAttemptDetail
