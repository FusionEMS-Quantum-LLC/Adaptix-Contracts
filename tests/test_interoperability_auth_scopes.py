from __future__ import annotations

from adaptix_contracts.auth import (
    INTEROPERABILITY_CONSENT_READ_SCOPE,
    INTEROPERABILITY_IDENTITY_READ_SCOPE,
    INTEROPERABILITY_PAYLOAD_READ_SCOPE,
    INTEROPERABILITY_SCOPES,
)


def test_interoperability_scopes_are_canonical_action_scopes() -> None:
    assert INTEROPERABILITY_PAYLOAD_READ_SCOPE == "interoperability-payload:read"
    assert INTEROPERABILITY_IDENTITY_READ_SCOPE == "interoperability-identity:read"
    assert INTEROPERABILITY_CONSENT_READ_SCOPE == "interoperability-consent:read"
    assert INTEROPERABILITY_SCOPES == frozenset(
        {
            "interoperability-payload:read",
            "interoperability-identity:read",
            "interoperability-consent:read",
        }
    )


def test_interoperability_scope_registry_is_immutable() -> None:
    assert isinstance(INTEROPERABILITY_SCOPES, frozenset)
