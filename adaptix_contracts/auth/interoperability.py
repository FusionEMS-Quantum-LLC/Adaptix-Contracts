"""Canonical service-token scopes for interoperability exchange.

These constants centralize the tenant-bound Core -> service claims used by the
interagency exchange fabric. Keep them action-style because they are used with
``adaptix_contracts.auth.service_token`` scopes, not user-facing RBAC scopes.
"""

from __future__ import annotations

INTEROPERABILITY_PAYLOAD_READ_SCOPE = "interoperability-payload:read"
INTEROPERABILITY_IDENTITY_READ_SCOPE = "interoperability-identity:read"
INTEROPERABILITY_CONSENT_READ_SCOPE = "interoperability-consent:read"

INTEROPERABILITY_SCOPES = frozenset(
    {
        INTEROPERABILITY_PAYLOAD_READ_SCOPE,
        INTEROPERABILITY_IDENTITY_READ_SCOPE,
        INTEROPERABILITY_CONSENT_READ_SCOPE,
    }
)

__all__ = [
    "INTEROPERABILITY_CONSENT_READ_SCOPE",
    "INTEROPERABILITY_IDENTITY_READ_SCOPE",
    "INTEROPERABILITY_PAYLOAD_READ_SCOPE",
    "INTEROPERABILITY_SCOPES",
]
