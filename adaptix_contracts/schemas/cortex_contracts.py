"""Cortex recommendation contracts.

Typed request/response contracts for the newly-separated Cortex AI
recommendation service. Cortex returns advisory recommendations to calling
domain modules and never fabricates operational facts; when evidence is
insufficient it surfaces missing data and flags human review.
"""

from pydantic import BaseModel, Field


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
