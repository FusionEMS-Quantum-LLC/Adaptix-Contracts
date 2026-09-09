"""Managed Billing V2 authorization contracts — surface + construction tests.

WAVE 1 of the Third-Party Billing Portal Tier-5 program. Proves the additive
V2 objects are exported from the package surface, the canonical role/permission
vocabularies are stable, the access-context models construct for both the
granted and blocked cases, and the legacy V1 billing contracts remain importable
(additive migration — no V1 regression).
"""

from __future__ import annotations

import adaptix_contracts as ac
from adaptix_contracts.schemas.billing_managed_v2 import (
    BillingAccessBlockedReason,
    BillingAccessContextV2,
    BillingAgencyGrant,
    BillingAgencyRelationshipStatus,
    BillingAgencyScope,
    BillingAgencySelectorEntry,
    BillingGrantStatus,
    BillingMembershipStatus,
    BillingMfaState,
    BillingOperatingMode,
    BillingOperatorRole,
    BillingOrganizationMembership,
    BillingOrganizationStatus,
    BillingOrganizationSummary,
    BillingPermission,
    BillingPortfolioScope,
)


def test_v2_objects_exported_from_package_surface() -> None:
    for name in (
        "BillingOperatorRole",
        "BillingPermission",
        "BillingOperatingMode",
        "BillingOrganizationStatus",
        "BillingMembershipStatus",
        "BillingAgencyRelationshipStatus",
        "BillingGrantStatus",
        "BillingAccessBlockedReason",
        "BillingMfaState",
        "BillingOrganizationSummary",
        "BillingOrganizationMembership",
        "BillingAgencyScope",
        "BillingAgencyGrant",
        "BillingAgencySelectorEntry",
        "BillingPortfolioScope",
        "BillingAccessContextV2",
    ):
        assert hasattr(ac, name), (
            f"{name} missing from adaptix_contracts package surface"
        )
        assert name in ac.schemas.__all__, f"{name} missing from schemas.__all__"


def test_canonical_role_vocabulary_is_the_directive_set() -> None:
    assert {r.value for r in BillingOperatorRole} == {
        "billing_admin",
        "billing_supervisor",
        "billing_lead",
        "billing_operator",
        "coder",
        "ar_specialist",
        "denial_specialist",
        "biller",
        "founder",
    }


def test_permission_vocabulary_covers_grant_columns() -> None:
    # One-to-one with the billing_operator_agency_grants capability columns (§9.4).
    assert {p.value for p in BillingPermission} == {
        "claims_read",
        "claims_write",
        "coding_read",
        "coding_write",
        "submission_read",
        "submission_write",
        "denials_read",
        "denials_write",
        "ar_read",
        "ar_write",
        "payments_read",
        "payments_write",
        "patient_financial_read",
        "patient_financial_write",
        "documents_read",
        "documents_write",
        "analytics_read",
        "agency_admin",
    }


def test_blocked_reason_has_honest_none_default() -> None:
    assert BillingAccessBlockedReason.NONE.value == "none"


def test_access_context_granted_case_constructs() -> None:
    ctx = BillingAccessContextV2(
        authenticated_user_id="user-1",
        billing_organization_id="org-1",
        billing_organization_name="FusionEMS Quantum Billing",
        membership_id="mem-1",
        operator_role=BillingOperatorRole.BILLING_OPERATOR,
        mfa=BillingMfaState(satisfied=True),
        permitted_agencies=[
            BillingAgencyScope(
                agency_tenant_id="agency-a", agency_display_name="Agency A"
            ),
            BillingAgencyScope(
                agency_tenant_id="agency-b", agency_display_name="Agency B"
            ),
        ],
    )
    assert ctx.access_blocked is False
    assert ctx.block_reason is BillingAccessBlockedReason.NONE
    assert ctx.destination_route == "/billing/portal"
    assert [a.agency_tenant_id for a in ctx.permitted_agencies] == [
        "agency-a",
        "agency-b",
    ]
    assert ctx.mfa.satisfied is True


def test_access_context_blocked_case_names_an_honest_reason() -> None:
    ctx = BillingAccessContextV2(
        authenticated_user_id="user-2",
        mfa=BillingMfaState(satisfied=False),
        access_blocked=True,
        block_reason=BillingAccessBlockedReason.NO_BILLING_MEMBERSHIP,
    )
    assert ctx.access_blocked is True
    assert ctx.block_reason is BillingAccessBlockedReason.NO_BILLING_MEMBERSHIP
    # No fabricated organization/agency data on a blocked context.
    assert ctx.billing_organization_id is None
    assert ctx.operator_role is None
    assert ctx.permitted_agencies == []


def test_agency_grant_carries_permission_subset() -> None:
    grant = BillingAgencyGrant(
        grant_id="grant-1",
        membership_id="mem-1",
        agency_tenant_id="agency-a",
        status=BillingGrantStatus.ACTIVE,
        permissions=[BillingPermission.CLAIMS_READ, BillingPermission.CLAIMS_WRITE],
        agency_admin=False,
    )
    assert BillingPermission.CLAIMS_WRITE in grant.permissions
    assert BillingPermission.AR_WRITE not in grant.permissions
    assert grant.status is BillingGrantStatus.ACTIVE


def test_portfolio_scope_is_a_list_not_a_synthetic_tenant() -> None:
    portfolio = BillingPortfolioScope(
        agencies=[
            BillingAgencyScope(
                agency_tenant_id="agency-a", agency_display_name="Agency A"
            ),
        ]
    )
    assert len(portfolio.agencies) == 1
    assert portfolio.agencies[0].agency_tenant_id == "agency-a"


def test_selector_entry_and_enums_construct() -> None:
    entry = BillingAgencySelectorEntry(
        agency_tenant_id="agency-a",
        agency_display_name="Agency A",
        relationship_status=BillingAgencyRelationshipStatus.ACTIVE,
    )
    assert entry.relationship_status is BillingAgencyRelationshipStatus.ACTIVE
    summary = BillingOrganizationSummary(
        organization_id="org-1",
        organization_name="FusionEMS Quantum Billing",
        organization_slug="fusionems-quantum",
        operating_mode=BillingOperatingMode.SOLO,
        status=BillingOrganizationStatus.ACTIVE,
    )
    assert summary.operating_mode is BillingOperatingMode.SOLO
    membership = BillingOrganizationMembership(
        membership_id="mem-1",
        organization_id="org-1",
        user_id="user-1",
        role=BillingOperatorRole.BILLING_ADMIN,
        status=BillingMembershipStatus.ACTIVE,
    )
    assert membership.role is BillingOperatorRole.BILLING_ADMIN


def test_legacy_v1_billing_contracts_still_importable() -> None:
    # Additive migration: V1 remains until consumers move to V2.
    from adaptix_contracts.schemas.billing_auth_contracts import (
        BillingAccessResolution,
        BillingRole,
    )

    assert BillingRole.SOLO_BILLER.value == "solo_biller"
    assert BillingAccessResolution is not None
