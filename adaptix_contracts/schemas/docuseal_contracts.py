"""DocuSeal package contracts.

Typed request/response contracts for the newly-separated DocuSeal signing
integration service. Covers creation of a DocuSeal package and the service
response describing vendor state and availability.
"""

from pydantic import BaseModel, Field


class DocuSealPackageCreateRequest(BaseModel):
    """Request to create a DocuSeal package."""

    tenant_id: str = Field(..., description="Tenant ID")
    correlation_id: str = Field(..., description="Request correlation identifier")
    template_id: str = Field(..., description="DocuSeal template identifier")


class DocuSealPackageResponse(BaseModel):
    """DocuSeal package response."""

    package_id: str | None = Field(
        None, description="Created package identifier, if any"
    )
    vendor_state: str = Field(..., description="Vendor-reported package state")
    available: bool = Field(
        ..., description="Whether the DocuSeal service was available"
    )
    reason: str | None = Field(None, description="Reason for the current state, if any")
    tenant_id: str = Field(..., description="Tenant ID")
    correlation_id: str = Field(..., description="Request correlation identifier")
