"""Adaptix Managed (Third-Party) Billing V2 authorization contracts.

Additive V2 contract surface for the multi-agency managed-billing operator
portal. These objects model the *persisted* managed-billing authorization
graph — Billing Organization -> membership -> client-agency relationship ->
per-operator agency grant -> effective scope — so a third-party biller's
authority over a client agency is explicit and server-resolved rather than
inferred from founder privilege, tenant switching, or browser-supplied tenant
IDs.

This module is ADDITIVE. The legacy ``billing_auth_contracts`` module
(``BillingRole``, ``BillingAccessResolution``, ...) is left in place until
every consumer has migrated to the V2 objects here; only then is V1 removed.

Canonical role/permission authority (directive P1-005 "one role authority"):
``BillingOperatorRole`` and ``BillingPermission`` defined here are THE single
source of truth for billing operator authorization. Runtime role gates
(Billing ``api/dependencies.py``), Core, Gateway and Web must converge on
these rather than maintaining independent free-text role sets.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class BillingOperatorRole(str, Enum):
    """Canonical third-party billing operator role vocabulary.

    Single authority for billing operator authorization. Chosen to match the
    directive's recommended runtime role set; legacy ``BillingRole`` values and
    the current runtime gate keys (``billing_operator`` / ``billing_admin`` /
    ``super_admin``) map onto these during consumer migration.
    """

    BILLING_ADMIN = "billing_admin"
    BILLING_SUPERVISOR = "billing_supervisor"
    BILLING_LEAD = "billing_lead"
    BILLING_OPERATOR = "billing_operator"
    CODER = "coder"
    AR_SPECIALIST = "ar_specialist"
    DENIAL_SPECIALIST = "denial_specialist"
    BILLER = "biller"
    FOUNDER = "founder"


class BillingPermission(str, Enum):
    """Fine-grained managed-billing capability.

    Mirrors the per-operator agency grant columns (directive §9.4). A grant
    carries the subset of these a membership holds on one client agency;
    authorization for an operator action on an agency resolves to a required
    permission in this vocabulary.
    """

    CLAIMS_READ = "claims_read"
    CLAIMS_WRITE = "claims_write"
    CODING_READ = "coding_read"
    CODING_WRITE = "coding_write"
    SUBMISSION_READ = "submission_read"
    SUBMISSION_WRITE = "submission_write"
    DENIALS_READ = "denials_read"
    DENIALS_WRITE = "denials_write"
    AR_READ = "ar_read"
    AR_WRITE = "ar_write"
    PAYMENTS_READ = "payments_read"
    PAYMENTS_WRITE = "payments_write"
    PATIENT_FINANCIAL_READ = "patient_financial_read"
    PATIENT_FINANCIAL_WRITE = "patient_financial_write"
    DOCUMENTS_READ = "documents_read"
    DOCUMENTS_WRITE = "documents_write"
    ANALYTICS_READ = "analytics_read"
    AGENCY_ADMIN = "agency_admin"


class BillingOperatingMode(str, Enum):
    """Billing Organization operating mode (directive §9.1 / §10).

    ``SOLO`` optimizes the application around one operator (single prioritized
    queue, all granted agencies) but is a WORKFLOW configuration only — it is
    never an authorization bypass. Agency authority still comes from explicit
    grants.
    """

    SOLO = "solo"
    TEAM = "team"


class BillingOrganizationStatus(str, Enum):
    """Lifecycle status of a Billing Organization (directive §9.1)."""

    ONBOARDING = "onboarding"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


class BillingMembershipStatus(str, Enum):
    """Lifecycle status of an operator's organization membership (§9.2)."""

    INVITED = "invited"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class BillingAgencyRelationshipStatus(str, Enum):
    """Status of the organization<->client-agency relationship (§9.3).

    Distinct from whether the agency owns the Billing module: module ownership
    grants the agency its own visibility, NOT managed-billing operational
    authority to the organization.
    """

    ONBOARDING = "onboarding"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    OFFBOARDING = "offboarding"
    TERMINATED = "terminated"


class BillingGrantStatus(str, Enum):
    """Status of a per-operator agency grant (§9.4)."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class BillingAccessBlockedReason(str, Enum):
    """Why ``/billing/access`` resolution denied entry to the portal (§13).

    ``NONE`` means access is not blocked. Every other value is an honest,
    machine-readable denial cause — never conflated with "account does not
    exist" and never rendered as fabricated zero-dollar data.
    """

    NONE = "none"
    NO_BILLING_MEMBERSHIP = "no_billing_membership"
    MEMBERSHIP_SUSPENDED = "membership_suspended"
    MEMBERSHIP_REVOKED = "membership_revoked"
    ORGANIZATION_SUSPENDED = "organization_suspended"
    ORGANIZATION_TERMINATED = "organization_terminated"
    MFA_REQUIRED = "mfa_required"
    PASSWORD_CHANGE_REQUIRED = "password_change_required"
    NOT_BILLING_OPERATOR = "not_billing_operator"
    SESSION_INVALID = "session_invalid"


class BillingMfaState(BaseModel):
    """Verified MFA state mapped from the platform MFA machinery (§45).

    ``satisfied`` reflects the gateway-verified session's MFA freshness; it is
    never derived from a browser-supplied header. ``completed_at`` supports
    freshness/expiry policy.
    """

    satisfied: bool
    completed_at: Optional[datetime] = None


class BillingOrganizationSummary(BaseModel):
    """Summary of a Billing Organization the operator is resolved into (§9.1)."""

    organization_id: str
    organization_name: str
    organization_slug: str
    operating_mode: BillingOperatingMode
    status: BillingOrganizationStatus


class BillingOrganizationMembership(BaseModel):
    """An operator's membership in a Billing Organization (§9.2)."""

    membership_id: str
    organization_id: str
    user_id: str
    role: BillingOperatorRole
    status: BillingMembershipStatus
    created_at: Optional[datetime] = None
    last_accessed_at: Optional[datetime] = None


class BillingAgencyScope(BaseModel):
    """One client agency the operator is authorized to work.

    Always carries ``agency_tenant_id`` + display name so multi-agency
    aggregates never lose tenant attribution (directive §15). This is NOT a
    database tenant the browser may assert; it is a server-resolved scope.
    """

    agency_tenant_id: str
    agency_display_name: str
    relationship_status: BillingAgencyRelationshipStatus = (
        BillingAgencyRelationshipStatus.ACTIVE
    )


class BillingAgencyGrant(BaseModel):
    """A membership's explicit per-agency capability grant (§9.4).

    ``permissions`` is the subset of :class:`BillingPermission` the operator
    holds on ``agency_tenant_id``. Knowing an agency's tenant UUID grants
    nothing; only an active grant does.
    """

    grant_id: str
    membership_id: str
    agency_tenant_id: str
    status: BillingGrantStatus
    permissions: list[BillingPermission] = Field(default_factory=list)
    agency_admin: bool = False


class BillingAgencySelectorEntry(BaseModel):
    """One entry in the portal agency selector (All Agencies / specific).

    Only agencies the server authorized are ever returned (directive §22).
    V2 replacement for the org-scoped ``BillingOrgSelectorEntry``, scoped to
    client agencies rather than organizations.
    """

    agency_tenant_id: str
    agency_display_name: str
    relationship_status: BillingAgencyRelationshipStatus


class BillingPortfolioScope(BaseModel):
    """The set of agencies an operator may work as a portfolio (§15).

    "All Authorized Agencies" is a portfolio query over ``agencies`` — never a
    synthetic tenant id. A portfolio request is resolved server-side to exactly
    these agency tenant ids.
    """

    agencies: list[BillingAgencyScope] = Field(default_factory=list)


class BillingAccessContextV2(BaseModel):
    """Authoritative post-login access resolution for ``/billing/access`` (§12/§13).

    Produced server-side from PERSISTED billing-organization membership, agency
    relationships and grants — not echoed from client inputs. When
    ``access_blocked`` is True, ``block_reason`` names the honest cause and the
    portal must not be entered.
    """

    authenticated_user_id: str

    billing_organization_id: Optional[str] = None
    billing_organization_name: Optional[str] = None

    membership_id: Optional[str] = None
    operator_role: Optional[BillingOperatorRole] = None

    mfa: BillingMfaState

    permitted_agencies: list[BillingAgencyScope] = Field(default_factory=list)
    default_scope: Optional[BillingAgencyScope] = None

    destination_route: str = "/billing/portal"

    feature_flags: dict[str, bool] = Field(default_factory=dict)

    access_blocked: bool = False
    block_reason: BillingAccessBlockedReason = BillingAccessBlockedReason.NONE
