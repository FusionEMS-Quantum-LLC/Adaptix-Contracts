"""Cortex contracts: advisory recommendations and the governed-plan execution boundary.

Recommendations
---------------
Typed request/response contracts for the newly-separated Cortex AI
recommendation service. Cortex returns advisory recommendations to calling
domain modules and never fabricates operational facts; when evidence is
insufficient it surfaces missing data and flags human review.

Governed-plan execution boundary (DOM-FND-004)
----------------------------------------------
Cortex never executes what it proposes. A governed plan action is executed by
the domain service that owns the target record, and that service re-checks
:class:`DomainPreconditionContract` against its OWN authoritative record and
the caller's verified identity before it changes anything. The outcome is a
:class:`DomainActionResult`; a version mismatch is
:attr:`DomainResultType.STALE_PLAN` and nothing is changed.

``ActionTarget``, ``DomainPreconditionContract``, ``DomainResultType``,
``DomainRecordState`` and ``DomainActionResult`` are field for field the
types Adaptix-Cortex-Service declares in ``app/models/governed_plan.py``
(origin/main ``eb4b09fa23c2230c66c20e9739d5c69148726781``, verified
2026-09-24): same field names, types, defaults, constraints, ``extra`` policy
and enum members. They are published here so a domain service can import the
boundary types instead of copying them. ``tests/test_cortex_governed_plan_boundary_drift.py``
fails when either side changes without the other.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RecommendationRequest(BaseModel):
    """Request from a domain module for a Cortex recommendation."""

    source_module: str = Field(..., description="Calling domain module identifier")
    tenant_id: str = Field(..., description="Tenant ID")
    correlation_id: str = Field(..., description="Request correlation identifier")
    context: dict = Field(
        ..., description="Domain context supplied for the recommendation"
    )


class RecommendationResponse(BaseModel):
    """Cortex recommendation response returned to the calling module."""

    recommendation: str | None = Field(
        default=None, description="Recommended action, if any"
    )
    reasoning: str | None = Field(
        default=None, description="Explanation supporting the recommendation"
    )
    confidence: float | None = Field(
        default=None, description="Model confidence for the recommendation"
    )
    data_used: list[str] = Field(
        default_factory=list,
        description="Data elements used to produce the recommendation",
    )
    missing_data: list[str] = Field(
        default_factory=list,
        description="Data elements that were missing or insufficient",
    )
    next_action: str | None = Field(
        default=None, description="Suggested next action for the caller"
    )
    human_review_required: bool = Field(
        ..., description="Whether a human must review before acting"
    )
    source_module: str = Field(..., description="Calling domain module identifier")
    tenant_id: str = Field(..., description="Tenant ID")
    correlation_id: str = Field(..., description="Request correlation identifier")
    available: bool = Field(..., description="Whether the Cortex service was available")


# ---------------------------------------------------------------------------
# Governed-plan execution boundary (mirrors Adaptix-Cortex-Service
# app/models/governed_plan.py; see the module docstring)
# ---------------------------------------------------------------------------


class ActionTarget(BaseModel):
    """The record a governed plan action targets."""

    model_config = ConfigDict(extra="forbid")

    resource_type: str = Field(min_length=1, max_length=120)
    resource_id: str = Field(min_length=1, max_length=200)


class DomainPreconditionContract(BaseModel):
    """What a domain service MUST re-check before executing a Cortex plan action.

    Cortex's validation and approval are necessary, never sufficient. The owning
    domain service executes only if ALL of the following hold at execution time,
    evaluated against its own authoritative record and the caller's verified
    identity (never against values copied from the plan):

    * ``tenant_id`` equals the verified caller tenant AND the record's tenant;
    * the verified executing identity holds ``required_permission``;
    * the record's current version equals ``expected_version`` - otherwise the
      result is ``STALE_PLAN`` and nothing is changed;
    * ``plan_revision`` has a current APPROVED decision for this action (when
      ``requires_approval``) - an approval of an older revision does not count;
    * ``idempotency_key`` has not already been applied (a repeat returns the
      original result instead of mutating twice);
    * ``arguments`` still satisfy the action's registered ``input_contract``.
    """

    model_config = ConfigDict(extra="forbid")

    plan_id: str
    plan_revision: str
    tenant_id: str
    action_index: int
    action_key: str
    required_permission: str
    target: ActionTarget
    arguments: dict[str, Any]
    idempotency_key: str | None
    expected_version: str | None
    requires_approval: bool
    timeout_seconds: int


class DomainResultType(str, Enum):
    """Outcome of one governed plan action at the owning domain service."""

    SUCCEEDED = "SUCCEEDED"
    #: The record changed since the plan was built (version mismatch). Nothing
    #: was executed; the plan must be rebuilt from current state and re-approved.
    STALE_PLAN = "STALE_PLAN"
    REJECTED_TENANT = "REJECTED_TENANT"
    REJECTED_PERMISSION = "REJECTED_PERMISSION"
    REJECTED_NOT_APPROVED = "REJECTED_NOT_APPROVED"
    FAILED = "FAILED"


class DomainRecordState(BaseModel):
    """What the domain service observed at execution time (its own authority)."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    current_version: str | None
    executor_permissions: list[str] = Field(default_factory=list)
    approved_revision: str | None = None


class DomainActionResult(BaseModel):
    """The domain service's answer to one governed plan action."""

    result_type: DomainResultType
    message: str
    expected_version: str | None = None
    current_version: str | None = None


__all__ = [
    "ActionTarget",
    "DomainActionResult",
    "DomainPreconditionContract",
    "DomainRecordState",
    "DomainResultType",
    "RecommendationRequest",
    "RecommendationResponse",
]
