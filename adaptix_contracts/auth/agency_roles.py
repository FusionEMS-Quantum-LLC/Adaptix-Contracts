"""Shared agency-role vocabulary for cross-repository consumers.

Adaptix-Core-Service remains the assignment authority. Its catalog and
permission intersection in ``core_app/agency_roles.py`` decide which agency
roles may be persisted. This module is the typed contract other repositories
import so they do not independently re-list agency or platform roles.

Occupation titles such as ``paramedic`` / ``emt`` are NOT agency-assignable
roles. They may appear on domain permission matrices. They must not be treated
as a second global role catalog.
"""

from __future__ import annotations

from enum import Enum
from typing import Final


class AgencyRole(str, Enum):
    """Canonical agency roles assignable through Core self-service surfaces."""

    TENANT_ADMIN = "tenant_admin"
    AGENCY_ADMIN = "agency_admin"
    ADMIN = "admin"
    SUPERVISOR = "supervisor"
    CAD_SUPERVISOR = "cad_supervisor"
    DISPATCHER = "dispatcher"
    CREW_MEMBER = "crew_member"
    BILLING_ADMIN = "billing_admin"
    BILLING_OPERATOR = "billing_operator"
    OPERATOR = "operator"
    FIELD_USER = "field_user"
    MEDICAL_DIRECTOR = "medical_director"
    ASSISTANT_MEDICAL_DIRECTOR = "assistant_medical_director"
    QA_REVIEWER = "qa_reviewer"
    VIEWER = "viewer"


class PlatformOnlyRole(str, Enum):
    """Roles that must never be assignable through agency-facing paths."""

    FOUNDER = "founder"
    SUPER_ADMIN = "super_admin"
    PLATFORM_ADMIN = "platform_admin"


AGENCY_ROLE_VALUES: Final[frozenset[str]] = frozenset(role.value for role in AgencyRole)
PLATFORM_ONLY_ROLES: Final[frozenset[str]] = frozenset(
    role.value for role in PlatformOnlyRole
)


def normalize_role(role: str | None) -> str | None:
    """Return the canonical spelling (strip + lower) or ``None``.

    Hyphenated forms such as ``agency-admin`` are rejected by callers that
    require an exact catalog key. Normalization is deliberate and narrow so
    every consumer interprets the same input the same way.
    """
    if role is None:
        return None
    canonical = role.strip().lower()
    return canonical or None


def is_platform_only(role: str | None) -> bool:
    canonical = normalize_role(role)
    return canonical is not None and canonical in PLATFORM_ONLY_ROLES


def is_agency_role(role: str | None) -> bool:
    canonical = normalize_role(role)
    return canonical is not None and canonical in AGENCY_ROLE_VALUES
