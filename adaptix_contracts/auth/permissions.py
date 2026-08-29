"""Stable permission IDs that Core mints onto signed identity.

These strings are the only permission names domain services should check.
They are not a role catalog and they are not assignable through agency
self-service. Core still decides which role receives which ID.
"""

from __future__ import annotations

from enum import Enum
from typing import Final


class PermissionId(str, Enum):
    """Wire identifiers for Core-issued permissions."""

    WORKSPACE_ADMIN_ACCESS = "workspace:admin:access"
    CORE_USERS_MANAGE = "core:users:manage"
    CORE_ROLES_MANAGE = "core:roles:manage"
    QA_REVIEW = "qa:review"
    QA_SUPERVISE = "qa:supervise"
    QA_PROTOCOL_MANAGE = "qa:protocol:manage"


WORKSPACE_ADMIN_ACCESS: Final[str] = PermissionId.WORKSPACE_ADMIN_ACCESS.value
CORE_USERS_MANAGE: Final[str] = PermissionId.CORE_USERS_MANAGE.value
CORE_ROLES_MANAGE: Final[str] = PermissionId.CORE_ROLES_MANAGE.value

QA_REVIEW: Final[str] = PermissionId.QA_REVIEW.value
QA_SUPERVISE: Final[str] = PermissionId.QA_SUPERVISE.value
QA_PROTOCOL_MANAGE: Final[str] = PermissionId.QA_PROTOCOL_MANAGE.value

QA_PERMISSIONS: Final[frozenset[str]] = frozenset(
    {
        PermissionId.QA_REVIEW.value,
        PermissionId.QA_SUPERVISE.value,
        PermissionId.QA_PROTOCOL_MANAGE.value,
    }
)
