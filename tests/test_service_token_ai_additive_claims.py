"""Backward-compatibility + additive-claim tests for the canonical S2S token.

Step 1 of the AdaptixCore Claude + External MCP directive extends the service
token additively with optional ``workspace_key``, ``delegation_grant_id`` and
``tool_call_id``. These tests prove:

* an OLD token (no new claims) still verifies unchanged — no trust-model change;
* the NEW optional claims round-trip when supplied;
* the schema version is NOT bumped (additive, so old tokens stay valid);
* identity/authz metadata only — the token schema carries no PHI fields.
"""

from __future__ import annotations

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from adaptix_contracts.auth.service_token import (
    SERVICE_TOKEN_VERSION,
    ServiceTokenClaims,
    issue_service_token,
    verify_service_token,
)


def _keypair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    pub = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return priv, pub


VERIFY_KW = dict(
    expected_issuer="adaptix-mcp",
    expected_audience="adaptix-billing",
    expected_subject="adaptix-mcp",
    required_scope="claims.search",
)


def test_old_token_without_new_claims_still_verifies() -> None:
    priv, pub = _keypair()
    token = issue_service_token(
        private_key_pem=priv,
        issuer="adaptix-mcp",
        audience="adaptix-billing",
        subject="adaptix-mcp",
        tenant_id="tenant-123",
        scope="claims.search",
    )
    claims = verify_service_token(token, public_key_pem=pub, **VERIFY_KW)
    assert claims.tenant_id == "tenant-123"
    assert claims.workspace_key is None
    assert claims.delegation_grant_id is None
    assert claims.tool_call_id is None
    # Version is unchanged — additive claims do not bump the required version.
    assert claims.ver == SERVICE_TOKEN_VERSION


def test_new_optional_claims_roundtrip() -> None:
    priv, pub = _keypair()
    token = issue_service_token(
        private_key_pem=priv,
        issuer="adaptix-mcp",
        audience="adaptix-billing",
        subject="adaptix-mcp",
        tenant_id="tenant-123",
        scope="claims.search",
        workspace_key="founder",
        delegation_grant_id="grant-abc",
        tool_call_id="call-xyz",
        actor_sub="user-42",
        correlation_id="corr-1",
    )
    claims = verify_service_token(token, public_key_pem=pub, **VERIFY_KW)
    assert claims.workspace_key == "founder"
    assert claims.delegation_grant_id == "grant-abc"
    assert claims.tool_call_id == "call-xyz"
    assert claims.actor_sub == "user-42"
    assert claims.correlation_id == "corr-1"


def test_new_claims_absent_from_payload_when_not_supplied() -> None:
    priv, _pub = _keypair()
    token = issue_service_token(
        private_key_pem=priv,
        issuer="adaptix-mcp",
        audience="adaptix-billing",
        subject="adaptix-mcp",
        tenant_id="tenant-123",
        scope="claims.search",
    )
    raw = jwt.decode(token, options={"verify_signature": False})
    # Additive claims are omitted (not null) when unset — keeps tokens minimal.
    assert "workspace_key" not in raw
    assert "delegation_grant_id" not in raw
    assert "tool_call_id" not in raw


def test_token_schema_has_no_phi_fields() -> None:
    """Identity/authz metadata only — no patient/clinical fields may exist."""

    forbidden_substrings = (
        "patient",
        "dob",
        "mrn",
        "ssn",
        "name",
        "medical",
        "diagnos",
        "prompt",
        "payload",
        "claim_detail",
    )
    field_names = set(ServiceTokenClaims.model_fields.keys())
    for fname in field_names:
        low = fname.lower()
        for bad in forbidden_substrings:
            assert bad not in low, f"service token field {fname!r} looks like PHI"


def test_tampered_new_claim_fails_signature() -> None:
    priv, pub = _keypair()
    token = issue_service_token(
        private_key_pem=priv,
        issuer="adaptix-mcp",
        audience="adaptix-billing",
        subject="adaptix-mcp",
        tenant_id="tenant-123",
        scope="claims.search",
        workspace_key="founder",
    )
    # Forge a different workspace_key by re-encoding with an attacker key.
    attacker_priv, _ = _keypair()
    raw = jwt.decode(token, options={"verify_signature": False})
    raw["workspace_key"] = "victim-workspace"
    forged = jwt.encode(raw, attacker_priv, algorithm="RS256")
    with pytest.raises(Exception):
        verify_service_token(forged, public_key_pem=pub, **VERIFY_KW)
