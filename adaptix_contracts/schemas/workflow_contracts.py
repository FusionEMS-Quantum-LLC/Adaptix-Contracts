"""Workflow and orchestration contracts.

Defines typed contracts for long-running workflows, saga-style orchestration,
step execution, compensation, and workflow state transitions across Adaptix.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

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

    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class WorkflowContext(BaseModel):
    workflow_id: str
    tenant_id: Optional[str] = None
    correlation_id: Optional[str] = None
    initiator_user_id: Optional[str] = None


class WorkflowExecution(BaseModel):
    workflow_id: str
    workflow_type: str

    context: WorkflowContext
    status: WorkflowStatus

    current_step_id: Optional[str] = None
    steps: list[WorkflowStep] = Field(default_factory=list)

    started_at: datetime
    completed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None


class WorkflowStartRequest(BaseModel):
    workflow_type: str
    tenant_id: Optional[str] = None
    correlation_id: Optional[str] = None
    initiator_user_id: Optional[str] = None
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
    current_step_id: Optional[str] = None
    failure_reason: str

    failed_at: datetime


class WorkflowCompensationTriggeredEvent(BaseModel):
    event_type: str = "workflow.compensation.triggered"

    workflow_id: str
    workflow_type: str
    triggered_at: datetime
