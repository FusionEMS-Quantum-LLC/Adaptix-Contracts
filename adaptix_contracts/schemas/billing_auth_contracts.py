"""Adaptix Third-Party Billing authentication and access contracts.

Defines the typed shapes for billing-specific sign-in context,
organization resolution, role mapping, and post-auth route selection.

These contracts are the single source of truth for the identity layer.
The web layer must consume them; it must not infer or hardcode role logic.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class BillingRole(str, Enum):
    """Billing portal role enumeration."""

    SOLO_BILLER = "solo_biller"
    BILLING_SPECIALIST = "billing_specialist"
    BILLING_SUPERVISOR = "billing_supervisor"
    AGENCY_ADMINISTRATOR = "agency_administrator"
    FOUNDER_OVERSIGHT = "founder_oversight"
    RESTRICTED_SUPPORT = "restricted_support"


class BillingPostAuthRoute(str, Enum):
    """Canonical post-auth destination routes for billing roles."""

    PORTAL_HOME = "/billing/portal"
    CLAIMS = "/billing/portal/claims"
    DENIALS = "/billing/portal/denials"
    AR_RECOVERY = "/billing/portal/ar"
    RECOVERY = "/billing/portal/recovery"
    PATIENT_FINANCIAL = "/billing/portal/patient-financial"
    IMPORTS = "/billing/portal/imports"
    ADMIN = "/billing/portal/admin"
    FOUNDER_OVERSIGHT = "/founder-command/billing"


class MFARequirement(str, Enum):
    """MFA requirement level for a given role and session context."""

    NOT_REQUIRED = "not_required"
    REQUIRED = "required"
    ALREADY_SATISFIED = "already_satisfied"


class SessionAnomalyState(str, Enum):
    """Anomaly detection result for a sign-in attempt or active session."""

    CLEAN = "clean"
    NEW_DEVICE = "new_device"
    UNUSUAL_LOCATION = "unusual_location"
    CONCURRENT_SESSION = "concurrent_session"
    HIGH_RISK = "high_risk"


class BillingSignInContext(BaseModel):
    """Context payload returned after successful credential verification."""

    event_type: str = "billing.auth.sign_in_context"

    user_id: str
    organization_id: str
    organization_name: str
    role: BillingRole

    mfa_requirement: MFARequirement
    anomaly_state: SessionAnomalyState
    anomaly_detail: str | None = None

    session_token: str
    session_expires_at: datetime

    post_auth_route: BillingPostAuthRoute

    work_entry_options: list[str] = Field(
        default_factory=list,
        description="Role-specific contextual work entry paths shown after sign-in",
    )

    device_trusted: bool
    requires_device_registration: bool


class BillingAccessResolution(BaseModel):
    """Resolution payload for the /billing/access route guard."""

    resolved: bool
    user_id: str
    organization_id: str
    role: BillingRole

    destination_route: BillingPostAuthRoute

    access_blocked: bool
    block_reason: str | None = None

    feature_flags: dict[str, bool] = Field(
        default_factory=dict,
        description="Feature flags controlling staged rollout of portal surfaces",
    )


class BillingOrgSelectorEntry(BaseModel):
    """Single entry in the organization selector during billing sign-in."""

    organization_id: str
    organization_name: str
    role_in_org: BillingRole

    environment: str = Field(
        ...,
        description="production | staging | sandbox",
    )

    last_accessed_at: datetime | None = None
