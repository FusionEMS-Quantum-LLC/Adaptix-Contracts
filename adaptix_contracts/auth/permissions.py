"""Typed permission identifiers shared across Adaptix services.

Core owns whether a role is assignable and which permissions that role
receives. This module is the wire vocabulary so domain services do not
invent their own permission strings.
"""

from __future__ import annotations

from typing import Final

WORKSPACE_ADMIN_ACCESS: Final = "workspace:admin:access"
CORE_USERS_MANAGE: Final = "core:users:manage"
CORE_ROLES_MANAGE: Final = "core:roles:manage"

QA_REVIEW: Final = "qa:review"
QA_SUPERVISE: Final = "qa:supervise"
QA_PROTOCOL_MANAGE: Final = "qa:protocol:manage"

QA_PERMISSIONS: Final[frozenset[str]] = frozenset(
    {QA_REVIEW, QA_SUPERVISE, QA_PROTOCOL_MANAGE}
)
