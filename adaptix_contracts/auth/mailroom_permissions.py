"""Canonical Mailroom permission scopes.

Core mints these onto the authenticated session. Mailroom enforces them
server-side. Ordinary viewer / field roles receive none of the write scopes,
so they cannot initiate paid PostGrid mail.
"""

from __future__ import annotations

from collections.abc import Iterable

MAILROOM_READ = "mailroom:read"
MAILROOM_SEND = "mailroom:send"
MAILROOM_CANCEL = "mailroom:cancel"
MAILROOM_CERTIFIED_SEND = "mailroom:certified:send"
MAILROOM_ADMIN = "mailroom:admin"

MAILROOM_PERMISSIONS: frozenset[str] = frozenset(
    {
        MAILROOM_READ,
        MAILROOM_SEND,
        MAILROOM_CANCEL,
        MAILROOM_CERTIFIED_SEND,
        MAILROOM_ADMIN,
    }
)

# Paid-mail initiation. Viewer / field / crew must never receive these.
MAILROOM_WRITE_PERMISSIONS: frozenset[str] = frozenset(
    {
        MAILROOM_SEND,
        MAILROOM_CANCEL,
        MAILROOM_CERTIFIED_SEND,
        MAILROOM_ADMIN,
    }
)

_ADMIN_ROLES: frozenset[str] = frozenset(
    {"admin", "agency_admin", "tenant_admin", "super_admin", "owner", "founder"}
)
_BILLING_ROLES: frozenset[str] = frozenset({"billing_admin", "billing_operator"})
_READ_ROLES: frozenset[str] = frozenset({"supervisor", "cad_supervisor"})


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
    normalized = {str(role).strip().lower() for role in roles if str(role).strip()}
    if is_founder or "founder" in normalized:
        return sorted(MAILROOM_PERMISSIONS)
    granted: set[str] = set()
    if normalized & _ADMIN_ROLES:
        granted.update(MAILROOM_PERMISSIONS)
    if normalized & _BILLING_ROLES:
        granted.update(
            {MAILROOM_READ, MAILROOM_SEND, MAILROOM_CANCEL, MAILROOM_CERTIFIED_SEND}
        )
    if normalized & _READ_ROLES:
        granted.add(MAILROOM_READ)
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
