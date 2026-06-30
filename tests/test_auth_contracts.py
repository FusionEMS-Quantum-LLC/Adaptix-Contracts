"""Security regression tests for AWS API Gateway header auth contracts.

Tests verify that:
- Valid X-User-Id / X-Tenant-Id headers produce a correct AuthContext.
- Missing or invalid headers raise HTTP 401.
- X-Is-Founder flag and role normalisation work correctly.
- The AuthContext is frozen (immutable).
- AdaptixAuthContext legacy behaviour is preserved.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import time
from uuid import uuid4

import pytest
from fastapi import HTTPException, status

from adaptix_contracts.auth_contracts import (
    get_auth_context,
)
from adaptix_contracts.auth.context import AdaptixAuthContext


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


def test_get_auth_context_accepts_valid_gateway_headers() -> None:
    user_id = uuid4()
    tenant_id = uuid4()
    email = "admin@example.test"

    auth = asyncio.run(
        get_auth_context(
            x_user_id=str(user_id),
            x_tenant_id=str(tenant_id),
            x_user_email=email,
            x_user_roles="billing_admin,user",
            x_is_founder="false",
        )
    )

    assert auth.user_id == user_id
    assert auth.tenant_id == tenant_id
    assert auth.email == email
    assert "billing_admin" in auth.roles
    assert "user" in auth.roles
    assert auth.is_founder is False


def test_get_auth_context_is_founder_flag_true() -> None:
    user_id = uuid4()
    tenant_id = uuid4()

    auth = asyncio.run(
        get_auth_context(
            x_user_id=str(user_id),
            x_tenant_id=str(tenant_id),
            x_user_email="founder@adaptix.test",
            x_user_roles="admin",
            x_is_founder="true",
        )
    )

    assert auth.is_founder is True
    assert "founder" in auth.roles


def test_get_auth_context_founder_via_role() -> None:
    """When X-User-Roles contains 'founder', is_founder should be True."""
    user_id = uuid4()
    tenant_id = uuid4()

    auth = asyncio.run(
        get_auth_context(
            x_user_id=str(user_id),
            x_tenant_id=str(tenant_id),
            x_user_email="founder@adaptix.test",
            x_user_roles="founder,super_admin",
            x_is_founder="false",
        )
    )

    assert auth.is_founder is True
    assert "founder" in auth.roles


def test_get_auth_context_empty_roles_default() -> None:
    user_id = uuid4()
    tenant_id = uuid4()

    auth = asyncio.run(
        get_auth_context(
            x_user_id=str(user_id),
            x_tenant_id=str(tenant_id),
        )
    )

    assert auth.roles == []
    assert auth.is_founder is False
    assert auth.email == ""


def test_get_auth_context_whitespace_stripped() -> None:
    user_id = uuid4()
    tenant_id = uuid4()

    auth = asyncio.run(
        get_auth_context(
            x_user_id=f"  {user_id}  ",
            x_tenant_id=f"  {tenant_id}  ",
            x_user_email="  user@test.com  ",
            x_user_roles="  admin , user  ",
        )
    )

    assert auth.user_id == user_id
    assert auth.tenant_id == tenant_id
    assert "admin" in auth.roles
    assert "user" in auth.roles


# ---------------------------------------------------------------------------
# Rejection tests
# ---------------------------------------------------------------------------


def test_get_auth_context_fails_without_user_id() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_auth_context(
                x_user_id=None,
                x_tenant_id=str(uuid4()),
            )
        )

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "X-User-Id" in str(exc_info.value.detail)


def test_get_auth_context_fails_without_tenant_id() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_auth_context(
                x_user_id=str(uuid4()),
                x_tenant_id=None,
            )
        )

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "X-Tenant-Id" in str(exc_info.value.detail)


def test_get_auth_context_fails_with_invalid_user_id_uuid() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_auth_context(
                x_user_id="not-a-uuid",
                x_tenant_id=str(uuid4()),
            )
        )

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "X-User-Id" in str(exc_info.value.detail)


def test_get_auth_context_fails_with_invalid_tenant_id_uuid() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_auth_context(
                x_user_id=str(uuid4()),
                x_tenant_id="not-a-uuid",
            )
        )

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "X-Tenant-Id" in str(exc_info.value.detail)


def test_get_auth_context_fails_with_empty_user_id() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_auth_context(
                x_user_id="   ",
                x_tenant_id=str(uuid4()),
            )
        )

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# Immutability test
# ---------------------------------------------------------------------------


def test_auth_context_is_frozen() -> None:
    user_id = uuid4()
    tenant_id = uuid4()

    auth = asyncio.run(
        get_auth_context(
            x_user_id=str(user_id),
            x_tenant_id=str(tenant_id),
        )
    )

    with pytest.raises(Exception):
        auth.user_id = uuid4()  # type: ignore[misc]


# ---------------------------------------------------------------------------
# AdaptixAuthContext legacy tests (must not regress)
# ---------------------------------------------------------------------------


def test_from_token_payload_rejects_missing_tenant_id() -> None:
    with pytest.raises(ValueError, match="tenant_id"):
        AdaptixAuthContext.from_token_payload(
            {
                "sub": str(uuid4()),
                "session_id": str(uuid4()),
            }
        )


def test_from_token_payload_rejects_missing_sub() -> None:
    with pytest.raises(ValueError, match="sub"):
        AdaptixAuthContext.from_token_payload(
            {
                "tenant_id": str(uuid4()),
                "session_id": str(uuid4()),
            }
        )


def test_from_token_payload_rejects_missing_session_id() -> None:
    with pytest.raises(ValueError, match="session_id"):
        AdaptixAuthContext.from_token_payload(
            {
                "tenant_id": str(uuid4()),
                "sub": str(uuid4()),
            }
        )


def test_from_token_payload_rejects_trusted_tenant_mismatch() -> None:
    with pytest.raises(ValueError, match="mismatch"):
        AdaptixAuthContext.from_token_payload(
            {
                "tenant_id": str(uuid4()),
                "sub": str(uuid4()),
                "session_id": str(uuid4()),
            },
            trusted_tenant_id=str(uuid4()),
        )


def test_from_token_payload_accepts_trusted_tenant_match() -> None:
    tenant_id = str(uuid4())
    context = AdaptixAuthContext.from_token_payload(
        {
            "tenant_id": tenant_id,
            "sub": str(uuid4()),
            "session_id": str(uuid4()),
            "roles": ["founder"],
        },
        trusted_tenant_id=tenant_id,
    )

    assert context.tenant_id == tenant_id


# ---------------------------------------------------------------------------
# F-24: gateway HMAC signature verification tests.
#
# The signer below reproduces the gateway producer
# (Adaptix-Core-Service/adaptix-gateway/backend/app/services/auth_context.py
#  -> sign_context) byte-for-byte so a "valid" context here is what the real
# gateway would emit, and a "tampered" one is what an attacker would produce.
# ---------------------------------------------------------------------------

_F24_SECRET = "f24-test-shared-secret"  # noqa: S105 — test-only fixture, not a real secret


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _sign_gateway_context(
    *,
    user_id: str,
    tenant_id: str,
    secret: str = _F24_SECRET,
    iat: int | None = None,
    exp: int | None = None,
    iss: str = "adaptix-gateway",
    aud: str = "adaptix-core",
    email: str = "user@example.test",
    roles: list[str] | None = None,
    is_founder: bool = False,
) -> tuple[str, str]:
    """Produce (context_b64, signature_hex) exactly like the gateway producer."""
    now = int(time.time())
    payload = {
        "sub": user_id,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "agency_id": "",
        "email": email,
        "roles": list(roles or []),
        "scopes": [],
        "is_founder": bool(is_founder),
        "iss": iss,
        "aud": aud,
        "iat": now if iat is None else iat,
        "exp": (now + 60) if exp is None else exp,
        "jti": str(uuid4()),
    }
    serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    context_b64 = _b64url_encode(serialized)
    sig = hmac.new(
        secret.encode("utf-8"), context_b64.encode("ascii"), hashlib.sha256
    ).hexdigest()
    return context_b64, sig


@pytest.fixture()
def _gateway_secret(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("ADAPTIX_GATEWAY_SHARED_SECRET", _F24_SECRET)
    # Ensure enforcement is OFF by default for these tests unless set explicitly.
    monkeypatch.delenv("ADAPTIX_GATEWAY_HMAC_ENFORCE", raising=False)
    monkeypatch.delenv("ADAPTIX_GATEWAY_EXPECTED_AUDIENCE", raising=False)
    return _F24_SECRET


def test_f24_valid_signature_with_secret_passes(_gateway_secret: str) -> None:
    """Valid gateway signature + secret -> passes; signed roles are authoritative."""
    user_id = uuid4()
    tenant_id = uuid4()
    # The signed context carries the role; the header agrees with it.
    ctx_b64, sig = _sign_gateway_context(
        user_id=str(user_id), tenant_id=str(tenant_id), roles=["paramedic"]
    )

    auth = asyncio.run(
        get_auth_context(
            x_user_id=str(user_id),
            x_tenant_id=str(tenant_id),
            x_user_email="user@example.test",
            x_user_roles="paramedic",
            x_adaptix_auth_context=ctx_b64,
            x_adaptix_auth_signature=sig,
            x_adaptix_auth_path="gateway-v1",
        )
    )

    assert auth.user_id == user_id
    assert auth.tenant_id == tenant_id
    assert "paramedic" in auth.roles


def test_f24_signed_roles_authoritative_over_spoofed_headers(
    _gateway_secret: str,
) -> None:
    """A verified signature makes signed roles/founder authoritative.

    Security invariant: with a valid gateway signature present, the spoofable
    X-User-Roles / X-Is-Founder headers MUST be ignored. An in-VPC actor who
    replays a valid signature for their OWN (non-founder) identity cannot add
    'founder' or extra roles by also sending spoofed headers.
    """
    user_id = uuid4()
    tenant_id = uuid4()
    # Signed context grants only 'paramedic' and is NOT founder.
    ctx_b64, sig = _sign_gateway_context(
        user_id=str(user_id),
        tenant_id=str(tenant_id),
        roles=["paramedic"],
        is_founder=False,
    )

    auth = asyncio.run(
        get_auth_context(
            x_user_id=str(user_id),
            x_tenant_id=str(tenant_id),
            # Spoofed escalation attempt via unsigned headers:
            x_user_roles="founder,billing_admin",
            x_is_founder="true",
            x_user_email="attacker@evil.test",
            x_adaptix_auth_context=ctx_b64,
            x_adaptix_auth_signature=sig,
            x_adaptix_auth_path="gateway-v1",
        )
    )

    # Authoritative signed claims win; spoofed header escalation is dropped.
    assert auth.roles == ["paramedic"]
    assert auth.is_founder is False
    assert "founder" not in {r.lower() for r in auth.roles}
    assert "billing_admin" not in auth.roles
    assert auth.email == "user@example.test"  # signed email, not the spoofed one


def test_f24_signed_is_founder_claim_honored(_gateway_secret: str) -> None:
    """A signed is_founder=True claim yields is_founder + 'founder' role."""
    user_id = uuid4()
    tenant_id = uuid4()
    ctx_b64, sig = _sign_gateway_context(
        user_id=str(user_id),
        tenant_id=str(tenant_id),
        roles=["admin"],
        is_founder=True,
    )

    auth = asyncio.run(
        get_auth_context(
            x_user_id=str(user_id),
            x_tenant_id=str(tenant_id),
            x_is_founder="false",  # header says NOT founder; signed claim wins
            x_adaptix_auth_context=ctx_b64,
            x_adaptix_auth_signature=sig,
            x_adaptix_auth_path="gateway-v1",
        )
    )

    assert auth.is_founder is True
    assert "founder" in {r.lower() for r in auth.roles}
    assert "admin" in auth.roles


def test_f24_signed_founder_role_sets_is_founder(_gateway_secret: str) -> None:
    """'founder' present in signed roles sets is_founder even if claim omitted."""
    user_id = uuid4()
    tenant_id = uuid4()
    ctx_b64, sig = _sign_gateway_context(
        user_id=str(user_id), tenant_id=str(tenant_id), roles=["founder", "super_admin"]
    )

    auth = asyncio.run(
        get_auth_context(
            x_user_id=str(user_id),
            x_tenant_id=str(tenant_id),
            x_adaptix_auth_context=ctx_b64,
            x_adaptix_auth_signature=sig,
            x_adaptix_auth_path="gateway-v1",
        )
    )

    assert auth.is_founder is True
    assert "founder" in {r.lower() for r in auth.roles}


def test_f24_tampered_signature_with_secret_rejected(_gateway_secret: str) -> None:
    """Invalid/tampered signature + secret -> 401."""
    user_id = uuid4()
    tenant_id = uuid4()
    ctx_b64, sig = _sign_gateway_context(user_id=str(user_id), tenant_id=str(tenant_id))
    tampered_sig = ("0" if sig[0] != "0" else "1") + sig[1:]

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_auth_context(
                x_user_id=str(user_id),
                x_tenant_id=str(tenant_id),
                x_adaptix_auth_context=ctx_b64,
                x_adaptix_auth_signature=tampered_sig,
                x_adaptix_auth_path="gateway-v1",
            )
        )

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_f24_absent_signature_enforce_false_passes_unchanged() -> None:
    """THE non-breaking proof: absent signature + enforce unset -> passes.

    No signature headers, no enforcement flag. Must return the SAME
    AuthContext as the pre-F-24 behavior (no 401). Secret may or may not be
    set — does not matter when no signature is present.
    """
    user_id = uuid4()
    tenant_id = uuid4()

    auth = asyncio.run(
        get_auth_context(
            x_user_id=str(user_id),
            x_tenant_id=str(tenant_id),
            x_user_email="user@example.test",
            x_user_roles="billing_admin,user",
            x_is_founder="false",
        )
    )

    assert auth.user_id == user_id
    assert auth.tenant_id == tenant_id
    assert auth.email == "user@example.test"
    assert "billing_admin" in auth.roles
    assert "user" in auth.roles
    assert auth.is_founder is False


def test_f24_absent_signature_enforce_true_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Absent signature + enforce=true -> 401."""
    monkeypatch.setenv("ADAPTIX_GATEWAY_HMAC_ENFORCE", "true")
    user_id = uuid4()
    tenant_id = uuid4()

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_auth_context(
                x_user_id=str(user_id),
                x_tenant_id=str(tenant_id),
            )
        )

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_f24_expired_signature_rejected(_gateway_secret: str) -> None:
    """Expired timestamp (replay window exceeded) -> 401."""
    user_id = uuid4()
    tenant_id = uuid4()
    now = int(time.time())
    # exp well outside the 5s clock-skew tolerance.
    ctx_b64, sig = _sign_gateway_context(
        user_id=str(user_id),
        tenant_id=str(tenant_id),
        iat=now - 120,
        exp=now - 60,
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_auth_context(
                x_user_id=str(user_id),
                x_tenant_id=str(tenant_id),
                x_adaptix_auth_context=ctx_b64,
                x_adaptix_auth_signature=sig,
                x_adaptix_auth_path="gateway-v1",
            )
        )

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_f24_signed_identity_mismatch_rejected(_gateway_secret: str) -> None:
    """Valid signature over a DIFFERENT identity than the headers -> 401."""
    header_user = uuid4()
    header_tenant = uuid4()
    # Signature is valid but signs a different user than the injected header.
    ctx_b64, sig = _sign_gateway_context(
        user_id=str(uuid4()), tenant_id=str(header_tenant)
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_auth_context(
                x_user_id=str(header_user),
                x_tenant_id=str(header_tenant),
                x_adaptix_auth_context=ctx_b64,
                x_adaptix_auth_signature=sig,
                x_adaptix_auth_path="gateway-v1",
            )
        )

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_f24_present_signature_no_secret_allows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Signature present but no shared secret configured -> allow (cannot verify)."""
    monkeypatch.delenv("ADAPTIX_GATEWAY_SHARED_SECRET", raising=False)
    monkeypatch.delenv("ADAPTIX_GATEWAY_HMAC_ENFORCE", raising=False)
    user_id = uuid4()
    tenant_id = uuid4()
    ctx_b64, sig = _sign_gateway_context(user_id=str(user_id), tenant_id=str(tenant_id))

    auth = asyncio.run(
        get_auth_context(
            x_user_id=str(user_id),
            x_tenant_id=str(tenant_id),
            x_adaptix_auth_context=ctx_b64,
            x_adaptix_auth_signature=sig,
            x_adaptix_auth_path="gateway-v1",
        )
    )

    assert auth.user_id == user_id
    assert auth.tenant_id == tenant_id


def test_f24_audience_pin_mismatch_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ADAPTIX_GATEWAY_EXPECTED_AUDIENCE is set, wrong aud -> 401."""
    monkeypatch.setenv("ADAPTIX_GATEWAY_SHARED_SECRET", _F24_SECRET)
    monkeypatch.setenv("ADAPTIX_GATEWAY_EXPECTED_AUDIENCE", "adaptix-epcr")
    user_id = uuid4()
    tenant_id = uuid4()
    # Context signed for adaptix-core but this service expects adaptix-epcr.
    ctx_b64, sig = _sign_gateway_context(
        user_id=str(user_id), tenant_id=str(tenant_id), aud="adaptix-core"
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_auth_context(
                x_user_id=str(user_id),
                x_tenant_id=str(tenant_id),
                x_adaptix_auth_context=ctx_b64,
                x_adaptix_auth_signature=sig,
                x_adaptix_auth_path="gateway-v1",
            )
        )

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
