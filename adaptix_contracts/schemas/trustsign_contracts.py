"""TrustSign signature package contracts.

Typed request/response contracts for the newly-separated Adaptix-native
TrustSign signing service. Covers creation of a signature package and the
service response describing package state and availability.
"""

from pydantic import BaseModel, Field


class SignaturePackageCreateRequest(BaseModel):
    """Request to create a TrustSign signature package."""

    tenant_id: str = Field(..., description="Tenant ID")
    correlation_id: str = Field(..., description="Request correlation identifier")
    document_ref: str = Field(..., description="Reference to the document to be signed")
    signers: list[str] = Field(
        default_factory=list, description="Signer identifiers or emails"
    )


class SignaturePackageResponse(BaseModel):
    """TrustSign signature package response."""

    package_id: str | None = Field(
        None, description="Created package identifier, if any"
    )
    status: str = Field(..., description="Current package status")
    signed: bool = Field(..., description="Whether the package is fully signed")
    available: bool = Field(
        ..., description="Whether the TrustSign service was available"
    )
    reason: str | None = Field(None, description="Reason for the current state, if any")
    tenant_id: str = Field(..., description="Tenant ID")
    correlation_id: str = Field(..., description="Request correlation identifier")
