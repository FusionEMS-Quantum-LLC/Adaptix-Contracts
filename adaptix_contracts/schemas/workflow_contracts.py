"""Workflow and orchestration contracts.

Defines typed contracts for long-running workflows, saga-style orchestration,
step execution, compensation, and workflow state transitions across Adaptix.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    CANCELLED = "cancelled"


class WorkflowStepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    COMPENSATED = "compensated"


class WorkflowStep(BaseModel):
    step_id: str
    step_name: str
    service_name: str

    status: WorkflowStepStatus
    retry_count: int = Field(default=0, ge=0)

    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None


class WorkflowContext(BaseModel):
    workflow_id: str
    tenant_id: str | None = None
    correlation_id: str | None = None
    initiator_user_id: str | None = None


class WorkflowExecution(BaseModel):
    workflow_id: str
    workflow_type: str

    context: WorkflowContext
    status: WorkflowStatus

    current_step_id: str | None = None
    steps: list[WorkflowStep] = Field(default_factory=list)

    started_at: datetime
    completed_at: datetime | None = None
    failure_reason: str | None = None


class WorkflowStartRequest(BaseModel):
    workflow_type: str
    tenant_id: str | None = None
    correlation_id: str | None = None
    initiator_user_id: str | None = None
    input_payload: dict = Field(default_factory=dict)


class WorkflowStartResponse(BaseModel):
    workflow_id: str
    workflow_type: str
    status: WorkflowStatus
    started_at: datetime


class WorkflowStepCompletedEvent(BaseModel):
    event_type: str = "workflow.step.completed"

    workflow_id: str
    workflow_type: str
    step_id: str
    step_name: str
    service_name: str

    completed_at: datetime


class WorkflowFailedEvent(BaseModel):
    event_type: str = "workflow.failed"

    workflow_id: str
    workflow_type: str
    current_step_id: str | None = None
    failure_reason: str

    failed_at: datetime


class WorkflowCompensationTriggeredEvent(BaseModel):
    event_type: str = "workflow.compensation.triggered"

    workflow_id: str
    workflow_type: str
    triggered_at: datetime
