"""Public-intake, onboarding, growth, and founder-action event contracts.

Defines the 23 cross-service event payload schemas that flow from the
public access page (``/access``) through CRM, tenant provisioning, BAA
gating, sandbox, go-live readiness, and the Growth Post Engine.

Every event carries a stable ``event_type`` literal and uses Pydantic v2
for runtime validation. These models are intentionally narrow: they
describe what crosses a service boundary, not internal storage shape.

Statuses, segments, and channel enums are defined alongside the events
so consumers (Adaptix-Core-Service intake_service, billing readiness
gates, growth post engine, founder dashboard) speak the exact same
vocabulary.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .billing_contracts import MigrationSourceVendor

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class IntakeSegment(str, enum.Enum):
    EMS_AGENCY = "ems_agency"
    FIRE_AGENCY = "fire_agency"
    BILLING_COMPANY = "billing_company"
    INVESTOR = "investor"
    DEVELOPER = "developer"
    PARTNER = "partner"
    GOVERNMENT_PUBLIC_SAFETY = "government_public_safety"


class LeadTemperature(str, enum.Enum):
    HOT = "hot"
    WARM = "warm"
    COOL = "cool"
    COLD = "cold"


class OnboardingStepStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


class ContractSignatureState(str, enum.Enum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    SENT = "sent"
    VIEWED = "viewed"
    SIGNED = "signed"
    DECLINED = "declined"
    EXPIRED = "expired"


class BillingReadinessState(str, enum.Enum):
    BILLING_NOT_STARTED = "billing_not_started"
    BILLING_PROFILE_STARTED = "billing_profile_started"
    BILLING_PROFILE_COMPLETE = "billing_profile_complete"
    CLEARINGHOUSE_PENDING = "clearinghouse_pending"
    MIGRATION_PENDING = "migration_pending"
    READY_FOR_TEST_CLAIM = "ready_for_test_claim"
    READY_FOR_PRODUCTION_CLAIMS = "ready_for_production_claims"
    BLOCKED = "blocked"


class GrowthPostStatus(str, enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"
    REJECTED = "rejected"


class GrowthPostChannel(str, enum.Enum):
    FOUNDER_INTERNAL = "founder_internal"
    LINKEDIN = "linkedin"
    X = "x"
    EMAIL_UPDATE = "email_update"
    INVESTOR_UPDATE = "investor_update"
    CAMPAIGN_UPDATE = "campaign_update"


class AdaptixModule(str, enum.Enum):
    CAD = "Adaptix CAD"
    FIELD = "Adaptix Field"
    CARE = "Adaptix Care"
    CREWLINK = "Adaptix CrewLink"
    TRANSPORTLINK = "Adaptix TransportLink"
    BILLING = "Adaptix Billing"
    FIRE = "Adaptix Fire"
    AIR = "Adaptix Air"
    AIR_PILOT = "Adaptix Air Pilot"
    WORKFORCE = "Adaptix Workforce"


# ---------------------------------------------------------------------------
# Shared event envelope
# ---------------------------------------------------------------------------


class _EventBase(BaseModel):
    """Shared envelope fields enforced on every cross-service event."""

    event_id: UUID
    event_type: str
    event_version: int = Field(default=1, ge=1)
    tenant_id: UUID | None = Field(
        default=None,
        description="Null only for pre-tenant intake events (visitor stage).",
    )
    organization_id: UUID | None = None
    actor_id: UUID | None = Field(
        default=None,
        description="System actor for unauthenticated public submissions.",
    )
    actor_type: str = Field(
        default="system",
        description="One of: visitor | agency_admin | agency_user | founder | system | copilot",
    )
    correlation_id: UUID
    idempotency_key: str | None = None
    occurred_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Intake / CRM events (1-4)
# ---------------------------------------------------------------------------


class IntakeSubmittedEvent(_EventBase):
    event_type: Literal["IntakeSubmitted"] = "IntakeSubmitted"


class IntakeClassifiedEvent(_EventBase):
    event_type: Literal["IntakeClassified"] = "IntakeClassified"


class LeadScoredEvent(_EventBase):
    event_type: Literal["LeadScored"] = "LeadScored"


class CrmContactCreatedEvent(_EventBase):
    event_type: Literal["CrmContactCreated"] = "CrmContactCreated"


# ---------------------------------------------------------------------------
# Onboarding events (5-8)
# ---------------------------------------------------------------------------


class OnboardingSessionCreatedEvent(_EventBase):
    event_type: Literal["OnboardingSessionCreated"] = "OnboardingSessionCreated"


class OnboardingStepStartedEvent(_EventBase):
    event_type: Literal["OnboardingStepStarted"] = "OnboardingStepStarted"


class OnboardingStepCompletedEvent(_EventBase):
    event_type: Literal["OnboardingStepCompleted"] = "OnboardingStepCompleted"


class OnboardingStepBlockedEvent(_EventBase):
    event_type: Literal["OnboardingStepBlocked"] = "OnboardingStepBlocked"


# ---------------------------------------------------------------------------
# Contract / signature events (9-10)
# ---------------------------------------------------------------------------


class ContractSignaturePacketCreatedEvent(_EventBase):
    event_type: Literal["ContractSignaturePacketCreated"] = (
        "ContractSignaturePacketCreated"
    )


class ContractSignatureCompletedEvent(_EventBase):
    event_type: Literal["ContractSignatureCompleted"] = "ContractSignatureCompleted"


# ---------------------------------------------------------------------------
# Provisioning + agency lifecycle events (11-15)
# ---------------------------------------------------------------------------


class TenantProvisionedEvent(_EventBase):
    event_type: Literal["TenantProvisioned"] = "TenantProvisioned"


class AgencyModuleSelectionUpdatedEvent(_EventBase):
    event_type: Literal["AgencyModuleSelectionUpdated"] = "AgencyModuleSelectionUpdated"


class AgencyUnitCreatedEvent(_EventBase):
    event_type: Literal["AgencyUnitCreated"] = "AgencyUnitCreated"


class AgencyUserInvitedEvent(_EventBase):
    event_type: Literal["AgencyUserInvited"] = "AgencyUserInvited"


class BillingProfileCompletedEvent(_EventBase):
    event_type: Literal["BillingProfileCompleted"] = "BillingProfileCompleted"


# ---------------------------------------------------------------------------
# Training / sandbox / go-live events (16-19)
# ---------------------------------------------------------------------------


class TrainingBookedEvent(_EventBase):
    event_type: Literal["TrainingBooked"] = "TrainingBooked"


class SandboxLaunchedEvent(_EventBase):
    event_type: Literal["SandboxLaunched"] = "SandboxLaunched"


class GoLiveReadinessCalculatedEvent(_EventBase):
    event_type: Literal["GoLiveReadinessCalculated"] = "GoLiveReadinessCalculated"


class GoLiveRequestedEvent(_EventBase):
    event_type: Literal["GoLiveRequested"] = "GoLiveRequested"


# ---------------------------------------------------------------------------
# Growth Post Engine events (20-22)
# ---------------------------------------------------------------------------


class GrowthPostDraftedEvent(_EventBase):
    event_type: Literal["GrowthPostDrafted"] = "GrowthPostDrafted"


class GrowthPostApprovedEvent(_EventBase):
    event_type: Literal["GrowthPostApproved"] = "GrowthPostApproved"


class GrowthPostPublishedEvent(_EventBase):
    event_type: Literal["GrowthPostPublished"] = "GrowthPostPublished"


# ---------------------------------------------------------------------------
# Founder action event (23)
# ---------------------------------------------------------------------------


class FounderNextActionCreatedEvent(_EventBase):
    event_type: Literal["FounderNextActionCreated"] = "FounderNextActionCreated"


# ---------------------------------------------------------------------------
# Public-API DTOs (intake initialize)
# ---------------------------------------------------------------------------


class ConditionalEmsFireFields(BaseModel):
    number_of_units: int | None = Field(default=None, ge=0)
    current_epcr_system: str | None = None
    current_dispatch_system: str | None = None
    billing_model: str | None = None
    billing_vendor: MigrationSourceVendor | None = None
    go_live_timeline: str | None = None
    needs_baa: bool | None = None
    requested_modules: list[AdaptixModule] = Field(default_factory=list)


class ConditionalBillingCompanyFields(BaseModel):
    monthly_claim_volume: int | None = Field(default=None, ge=0)
    current_clearinghouse: MigrationSourceVendor | None = None
    current_billing_system: str | None = None
    number_of_clients: int | None = Field(default=None, ge=0)
    migration_needed: bool | None = None
    office_ally_status: str | None = None


class ConditionalInvestorFields(BaseModel):
    investor_type: str | None = None
    check_size_range: str | None = None
    interest_area: str | None = None
    funding_timeline: str | None = None
    wants_demo: bool | None = None


class ConditionalDeveloperFields(BaseModel):
    integration_type: str | None = None
    technical_stack: str | None = None
    expected_api_use: str | None = None
    sandbox_needed: bool | None = None


class IntakeInitializeRequest(BaseModel):
    """Request body for ``POST /api/v1/intake/initialize``."""

    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    organization_name: str = Field(min_length=1, max_length=255)
    role_title: str = Field(min_length=1, max_length=255)
    organization_type: IntakeSegment
    state_region: str = Field(min_length=1, max_length=128)
    monthly_volume: int | None = Field(default=None, ge=0)
    primary_goal: str = Field(min_length=1, max_length=2048)
    phone_optional: str | None = Field(default=None, max_length=50)
    website_optional: str | None = Field(default=None, max_length=512)
    terms_accepted: bool

    ems_fire: ConditionalEmsFireFields | None = None
    billing_company: ConditionalBillingCompanyFields | None = None
    investor: ConditionalInvestorFields | None = None
    developer: ConditionalDeveloperFields | None = None


class IntakeInitializeResponse(BaseModel):
    """Response body for ``POST /api/v1/intake/initialize``."""

    intake_id: UUID
    organization_id: UUID
    contact_id: UUID
    tenant_id: UUID | None = None
    onboarding_session_id: UUID | None = None
    segment: IntakeSegment
    lead_score: int = Field(ge=0, le=100)
    lead_temperature: LeadTemperature
    redirect_url: str
    provisioned: bool
    required_next_step: str | None = None
    founder_action_required: bool


# ---------------------------------------------------------------------------
# Billing defaults DTOs (Slice 2)
# ---------------------------------------------------------------------------


class BillingModelChoice(str, enum.Enum):
    IN_HOUSE = "in_house"
    OUTSOURCED = "outsourced"
    HYBRID = "hybrid"
    NOT_YET_DECIDED = "not_yet_decided"


class PayerType(str, enum.Enum):
    MEDICARE = "medicare"
    MEDICAID = "medicaid"
    TRICARE = "tricare"
    COMMERCIAL = "commercial"
    SELF_PAY = "self_pay"
    WORKERS_COMP = "workers_comp"


class BillingDefaultsRequest(BaseModel):
    """Request body for ``POST /api/v1/intake/{intake_id}/billing-defaults``.

    All operational fields are optional so a partial save is valid.  The
    endpoint is idempotent: re-posting overwrites the stored record.
    """

    model_config = ConfigDict(populate_by_name=True)

    npi: str | None = Field(
        default=None,
        pattern=r"^\d{10}$",
        description="10-digit National Provider Identifier.",
    )
    tax_id: str | None = Field(
        default=None,
        pattern=r"^\d{2}-\d{7}$",
        description="EIN in XX-XXXXXXX format.",
    )
    taxonomy_code: str | None = Field(
        default=None,
        max_length=20,
        description="Provider taxonomy code (e.g. 341600000X for ground ambulance).",
    )
    migration_source_vendor: MigrationSourceVendor = Field(
        default=MigrationSourceVendor.NONE_YET,
        validation_alias="clearinghouse",
        description=(
            "Incumbent/migration source vendor only. Live billing submission is "
            "STEDI-only and is not selected by this field."
        ),
    )
    payer_mix: list[PayerType] = Field(
        default_factory=list,
        description="Payer types the agency bills.",
    )
    billing_model: BillingModelChoice = Field(
        default=BillingModelChoice.NOT_YET_DECIDED,
    )
    existing_software: str | None = Field(
        default=None,
        max_length=128,
        description="Name of current billing software if migrating.",
    )
    average_monthly_transport_volume: int | None = Field(
        default=None,
        ge=0,
        description="Average number of transports billed per month.",
    )
    wants_migration_support: bool = Field(default=False)


class BillingDefaultsResponse(BaseModel):
    """Response body for billing-defaults POST and GET."""

    model_config = ConfigDict(populate_by_name=True)

    intake_id: UUID
    organization_id: UUID
    billing_readiness_state: BillingReadinessState
    npi: str | None = None
    tax_id: str | None = None
    taxonomy_code: str | None = None
    migration_source_vendor: MigrationSourceVendor = Field(
        validation_alias="clearinghouse",
        description=(
            "Incumbent/migration source vendor only. Live billing submission is "
            "STEDI-only and is not selected by this field."
        ),
    )
    payer_mix: list[PayerType]
    billing_model: BillingModelChoice
    existing_software: str | None = None
    average_monthly_transport_volume: int | None = None
    wants_migration_support: bool
    profile_complete: bool


__all__ = [
    "IntakeSegment",
    "LeadTemperature",
    "OnboardingStepStatus",
    "ContractSignatureState",
    "BillingReadinessState",
    "GrowthPostStatus",
    "GrowthPostChannel",
    "AdaptixModule",
    "IntakeSubmittedEvent",
    "IntakeClassifiedEvent",
    "LeadScoredEvent",
    "CrmContactCreatedEvent",
    "OnboardingSessionCreatedEvent",
    "OnboardingStepStartedEvent",
    "OnboardingStepCompletedEvent",
    "OnboardingStepBlockedEvent",
    "ContractSignaturePacketCreatedEvent",
    "ContractSignatureCompletedEvent",
    "TenantProvisionedEvent",
    "AgencyModuleSelectionUpdatedEvent",
    "AgencyUnitCreatedEvent",
    "AgencyUserInvitedEvent",
    "BillingProfileCompletedEvent",
    "TrainingBookedEvent",
    "SandboxLaunchedEvent",
    "GoLiveReadinessCalculatedEvent",
    "GoLiveRequestedEvent",
    "GrowthPostDraftedEvent",
    "GrowthPostApprovedEvent",
    "GrowthPostPublishedEvent",
    "FounderNextActionCreatedEvent",
    "IntakeInitializeRequest",
    "IntakeInitializeResponse",
    "ConditionalEmsFireFields",
    "ConditionalBillingCompanyFields",
    "ConditionalInvestorFields",
    "ConditionalDeveloperFields",
    "MigrationSourceVendor",
    "BillingModelChoice",
    "PayerType",
    "BillingDefaultsRequest",
    "BillingDefaultsResponse",
]
