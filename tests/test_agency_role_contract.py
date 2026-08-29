"""Shared agency-role contract: one vocabulary, no competing catalogs."""

from __future__ import annotations

import pytest

from adaptix_contracts.auth.agency_roles import (
    AGENCY_ROLE_VALUES,
    PLATFORM_ONLY_ROLES,
    AgencyRole,
    PlatformOnlyRole,
    is_agency_role,
    is_platform_only,
    normalize_role,
)
from adaptix_contracts.auth.context import AdaptixRole


def test_agency_role_values_match_enum() -> None:
    assert AGENCY_ROLE_VALUES == {role.value for role in AgencyRole}


def test_platform_only_roles_are_exactly_the_three_platform_owners() -> None:
    assert PLATFORM_ONLY_ROLES == {"founder", "super_admin", "platform_admin"}
    assert PLATFORM_ONLY_ROLES == {role.value for role in PlatformOnlyRole}


def test_agency_and_platform_sets_are_disjoint() -> None:
    assert AGENCY_ROLE_VALUES.isdisjoint(PLATFORM_ONLY_ROLES)


@pytest.mark.parametrize("role", sorted(AGENCY_ROLE_VALUES))
def test_every_agency_role_is_recognized_on_the_wire(role: str) -> None:
    assert AdaptixRole(role).value == role
    assert is_agency_role(role) is True
    assert is_platform_only(role) is False


@pytest.mark.parametrize("role", sorted(PLATFORM_ONLY_ROLES))
def test_platform_roles_are_recognized_but_not_agency_roles(role: str) -> None:
    assert AdaptixRole(role).value == role
    assert is_platform_only(role) is True
    assert is_agency_role(role) is False


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Agency_Admin ", "agency_admin"),
        ("OPERATOR", "operator"),
        ("Viewer", "viewer"),
        ("agency_admin", "agency_admin"),
    ],
)
def test_normalize_role_is_case_and_whitespace_tolerant(
    raw: str, expected: str
) -> None:
    assert normalize_role(raw) == expected
    assert is_agency_role(raw) is True


def test_normalize_rejects_empty_and_does_not_invent_hyphen_aliases() -> None:
    assert normalize_role(None) is None
    assert normalize_role("") is None
    assert normalize_role("   ") is None
    assert normalize_role("agency-admin") == "agency-admin"
    assert is_agency_role("agency-admin") is False


def test_occupation_titles_are_not_agency_assignable() -> None:
    for occupation in (
        "paramedic",
        "emt",
        "firefighter",
        "pilot",
        "billing_specialist",
        "workforce_manager",
        "inventory_manager",
        "narcotics_officer",
        "read_only",
    ):
        assert occupation not in AGENCY_ROLE_VALUES
        assert is_agency_role(occupation) is False
        assert AdaptixRole(occupation).value == occupation


def test_qa_clinical_roles_are_agency_vocabulary() -> None:
    assert is_agency_role("qa_reviewer") is True
    assert is_agency_role("assistant_medical_director") is True
    assert AdaptixRole("qa_reviewer").value == "qa_reviewer"


def test_qa_permission_ids_are_stable() -> None:
    from adaptix_contracts.auth.permissions import (
        QA_PERMISSIONS,
        QA_PROTOCOL_MANAGE,
        QA_REVIEW,
        QA_SUPERVISE,
        CORE_USERS_MANAGE,
        WORKSPACE_ADMIN_ACCESS,
        PermissionId,
    )

    assert QA_REVIEW == "qa:review"
    assert QA_SUPERVISE == "qa:supervise"
    assert QA_PROTOCOL_MANAGE == "qa:protocol:manage"
    assert QA_PERMISSIONS == {QA_REVIEW, QA_SUPERVISE, QA_PROTOCOL_MANAGE}
    assert CORE_USERS_MANAGE == "core:users:manage"
    assert WORKSPACE_ADMIN_ACCESS == "workspace:admin:access"
    assert PermissionId.QA_REVIEW.value == QA_REVIEW
    assert PermissionId.CORE_USERS_MANAGE.value == CORE_USERS_MANAGE


def test_mailroom_permission_ids_are_stable() -> None:
    from adaptix_contracts.auth.permissions import (
        MAILROOM_ADMIN,
        MAILROOM_CANCEL,
        MAILROOM_CERTIFIED_SEND,
        MAILROOM_PERMISSIONS,
        MAILROOM_READ,
        MAILROOM_SEND,
        MAILROOM_WRITE_PERMISSIONS,
        PermissionId,
    )

    assert MAILROOM_READ == "mailroom:read"
    assert MAILROOM_SEND == "mailroom:send"
    assert MAILROOM_CANCEL == "mailroom:cancel"
    assert MAILROOM_CERTIFIED_SEND == "mailroom:certified:send"
    assert MAILROOM_ADMIN == "mailroom:admin"
    assert MAILROOM_PERMISSIONS == {
        MAILROOM_READ,
        MAILROOM_SEND,
        MAILROOM_CANCEL,
        MAILROOM_CERTIFIED_SEND,
        MAILROOM_ADMIN,
    }
    assert MAILROOM_WRITE_PERMISSIONS == {
        MAILROOM_SEND,
        MAILROOM_CANCEL,
        MAILROOM_CERTIFIED_SEND,
        MAILROOM_ADMIN,
    }
    assert PermissionId.MAILROOM_SEND.value == MAILROOM_SEND
