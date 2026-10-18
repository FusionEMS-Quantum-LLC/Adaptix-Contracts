"""AI workflow contracts shared across Adaptix services."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AIRunStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AIWorkflowType(str, enum.Enum):
    BILLING_RISK_SCORE = "billing_risk_score"
    DENIAL_PREDICTION = "denial_prediction"
    APPEAL_DRAFT = "appeal_draft"
    TRANSCRIPT_SUMMARY = "transcript_summary"
    CLAIM_CALL_SUMMARY = "claim_call_summary"
    CHART_QUALITY_SUGGESTION = "chart_quality_suggestion"
    FOUNDER_REVENUE_INSIGHT = "founder_revenue_insight"


class AIRunContract(BaseModel):
    id: UUID
    tenant_id: UUID
    workflow_name: AIWorkflowType
    input_hash: str
    provider: str
    model: str
    status: AIRunStatus
    structured_output: dict[str, Any] | None = None
    error_message: str | None = None
    confidence_score: float | None = None
    prompt_version: str | None = None
    token_count_input: int | None = None
    token_count_output: int | None = None
    cost_usd: float | None = None
    created_at: datetime
    completed_at: datetime | None = None


class AIRunCreateRequest(BaseModel):
    workflow_name: AIWorkflowType
    input_data: dict[str, Any]
    provider: str | None = None
    model: str | None = None


class AIRunResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    workflow_name: AIWorkflowType
    status: AIRunStatus
    structured_output: dict[str, Any] | None = None
    confidence_score: float | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class BillingCopilotRiskScoreContract(BaseModel):
    claim_id: UUID
    risk_score: float = Field(ge=0.0, le=1.0)
    risk_factors: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    ai_run_id: UUID


class BillingCopilotDenialPredictionContract(BaseModel):
    claim_id: UUID
    denial_probability: float = Field(ge=0.0, le=1.0)
    likely_denial_reasons: list[str] = Field(default_factory=list)
    recommended_corrections: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    ai_run_id: UUID


class BillingCopilotAppealDraftContract(BaseModel):
    claim_id: UUID
    denial_id: UUID
    appeal_text: str
    supporting_evidence: list[str] = Field(default_factory=list)
    recommended_attachments: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    ai_run_id: UUID


class TranscriptSummaryContract(BaseModel):
    call_id: UUID
    summary: str
    action_items: list[str] = Field(default_factory=list)
    deadlines: list[str] = Field(default_factory=list)
    linked_claim_id: UUID | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    ai_run_id: UUID


class AIRunCompletedEvent(BaseModel):
    ai_run_id: UUID
    tenant_id: UUID
    workflow_name: AIWorkflowType
    status: AIRunStatus
    completed_at: datetime
