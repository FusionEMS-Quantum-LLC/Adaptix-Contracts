"""Legal execution contracts for the Adaptix platform.

Contains contract schemas and types for legal document execution,
including contract types, status enums, and mapping relationships.
"""

from enum import Enum

from datetime import datetime
from pydantic import BaseModel, Field


class ContractType(str, Enum):
    """Enumeration of contract types supported by the platform.

    Used for document execution and module enablement workflows.
    """

    MASTER_SERVICES_AGREEMENT = "master_services_agreement"
    BUSINESS_ASSOCIATE_AGREEMENT = "business_associate_agreement"
    AGENCY_ONBOARDING_AGREEMENT = "agency_onboarding_agreement"
    MODULE_LICENSE_AGREEMENT = "module_license_agreement"
    DEA_COMPLIANCE_AGREEMENT = "dea_compliance_agreement"
    INVESTOR_NDA = "investor_nda"
    PARTNER_AGREEMENT = "partner_agreement"
    CUSTOMER_SLA = "customer_sla"
    EMERGENCY_SERVICES_AGREEMENT = "emergency_services_agreement"
    BILLING_SERVICES_AGREEMENT = "billing_services_agreement"


class ContractStatus(str, Enum):
    """Enumeration of contract execution status values.

    Tracks the state of a contract through its lifecycle.
    """

    PENDING = "pending"
    SENT = "sent"
    VIEWED = "viewed"
    SIGNED = "signed"
    COMPLETED = "completed"
    DECLINED = "declined"
    EXPIRED = "expired"
    CANCELED = "canceled"
    VOIDED = "voided"


class TenantContractStatusMap(BaseModel):
    """Mapping between tenant, contract type, and execution status.

    Provides the current state of all contracts for a given tenant.
    """

    tenant_id: str = Field(..., description="Tenant ID")
    contract_statuses: dict[ContractType, ContractStatus] = Field(
        ..., description="Mapping of contract types to their current statuses"
    )


class ContractSignatureEvent(BaseModel):
    """Event payload for contract signature events.

    Published when a contract status changes due to a signature or other event.
    """

    tenant_id: str = Field(..., description="Tenant ID")
    contract_type: ContractType = Field(..., description="Type of contract signed")
    status: ContractStatus = Field(..., description="New status of the contract")
    signer_email: str = Field(..., description="Email of the signer")
    signer_name: str = Field(..., description="Name of the signer")
    timestamp: datetime = Field(..., description="Timestamp of the signature")
    contract_id: str = Field(..., description="ID of the contract document")
    metadata: dict[str, str] | None = Field(None, description="Additional metadata")


class ContractAccessCheckRequest(BaseModel):
    """Request to check if a tenant has access to a module via contract.

    Used to gate access to features based on contract status.
    """

    tenant_id: str = Field(..., description="Tenant ID")
    contract_type: ContractType = Field(..., description="Type of contract to check")
    required_status: ContractStatus = Field(
        ContractStatus.COMPLETED,
        description="Status required for access (defaults to COMPLETED)",
    )


class ContractAccessCheckResponse(BaseModel):
    """Response from checking tenant's access to module via contract.

    Returns access status and reason for access decisions.
    """

    tenant_id: str = Field(..., description="Tenant ID")
    contract_type: ContractType = Field(..., description="Type of contract checked")
    has_access: bool = Field(..., description="Whether tenant has access")
    current_status: ContractStatus | None = Field(
        None, description="Current status of the contract"
    )
    reason: str | None = Field(None, description="Reason for access decision")
