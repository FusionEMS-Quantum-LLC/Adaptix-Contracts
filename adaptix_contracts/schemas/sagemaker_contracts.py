"""SageMaker prediction contracts.

Typed request/response contracts for the newly-separated SageMaker prediction
service. Predictions are advisory; when input evidence is insufficient the
response flags the gap, records whether a rules fallback was used, and whether
human review is required.
"""

from pydantic import BaseModel, Field


class PredictionRequest(BaseModel):
    """Request for a SageMaker prediction."""

    prediction_type: str = Field(..., description="Type of prediction requested")
    tenant_id: str = Field(..., description="Tenant ID")
    correlation_id: str = Field(..., description="Request correlation identifier")
    features: dict = Field(..., description="Input features for the prediction")


class PredictionResponse(BaseModel):
    """SageMaker prediction response."""

    prediction_type: str = Field(..., description="Type of prediction produced")
    prediction_value: float | None = Field(None, description="Predicted value, if any")
    confidence: float | None = Field(
        None, description="Model confidence for the prediction"
    )
    model_id: str | None = Field(None, description="Identifier of the model used")
    model_version: str | None = Field(None, description="Version of the model used")
    data_used: list[str] = Field(
        default_factory=list, description="Feature elements used for the prediction"
    )
    missing_data: list[str] = Field(
        default_factory=list,
        description="Feature elements that were missing or insufficient",
    )
    insufficient_data: bool = Field(
        ..., description="Whether input data was insufficient for a prediction"
    )
    rules_fallback_used: bool = Field(
        ..., description="Whether a deterministic rules fallback was used"
    )
    human_review_required: bool = Field(
        ..., description="Whether a human must review before acting"
    )
    message: str = Field(..., description="Human-readable status or explanation")
    tenant_id: str = Field(..., description="Tenant ID")
    correlation_id: str = Field(..., description="Request correlation identifier")
