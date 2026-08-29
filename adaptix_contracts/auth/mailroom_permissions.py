"""Canonical Mailroom permission scopes.

Core mints these onto the authenticated session. Mailroom enforces them
server-side. Ordinary viewer / field roles receive none of the write scopes,
so they cannot initiate paid PostGrid mail.
"""

from __future__ import annotations

from collections.abc import Iterable

from adaptix_contracts.auth.permissions import (
    MAILROOM_ADMIN,
    MAILROOM_CANCEL,
    MAILROOM_CERTIFIED_SEND,
    MAILROOM_PERMISSIONS,
    MAILROOM_READ,
    MAILROOM_SEND,
    MAILROOM_WRITE_PERMISSIONS,
)

_ADMIN_ROLES: frozenset[str] = frozenset(
    {"admin", "agency_admin", "tenant_admin", "super_admin", "owner", "founder"}
)
_BILLING_ROLES: frozenset[str] = frozenset({"billing_admin", "billing_operator"})
_READ_ROLES: frozenset[str] = frozenset({"supervisor", "cad_supervisor"})
_BILLING_SCOPES: frozenset[str] = frozenset(
    {MAILROOM_READ, MAILROOM_SEND, MAILROOM_CANCEL, MAILROOM_CERTIFIED_SEND}
)
_ROLE_GRANTS: tuple[tuple[frozenset[str], frozenset[str]], ...] = (
    (_ADMIN_ROLES, MAILROOM_PERMISSIONS),
    (_BILLING_ROLES, _BILLING_SCOPES),
    (_READ_ROLES, frozenset({MAILROOM_READ})),
)


def _normalized_roles(roles: Iterable[str]) -> set[str]:
    return {str(role).strip().lower() for role in roles if str(role).strip()}


def mailroom_permissions_for_roles(
    roles: Iterable[str],
    *,
    is_founder: bool = False,
) -> list[str]:
    """Return the mailroom scopes Core must mint for these roles.

    Founder and tenant administrators receive the full set. Billing operators
    may send statements and certified mail. Supervisors may read delivery
    state. Viewer / field / crew receive nothing.
    """
    normalized = _normalized_roles(roles)
    if is_founder or "founder" in normalized:
        return sorted(MAILROOM_PERMISSIONS)
    granted: set[str] = set()
    for role_set, scopes in _ROLE_GRANTS:
        if normalized & role_set:
            granted.update(scopes)
    return sorted(granted)


__all__ = [
    "MAILROOM_ADMIN",
    "MAILROOM_CANCEL",
    "MAILROOM_CERTIFIED_SEND",
    "MAILROOM_PERMISSIONS",
    "MAILROOM_READ",
    "MAILROOM_SEND",
    "MAILROOM_WRITE_PERMISSIONS",
    "mailroom_permissions_for_roles",
]
