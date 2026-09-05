"""Canonical Gateway identity-signature protocol.

Proves the shared package signs and verifies both the modern context scheme
and the legacy ``{ts}.{user_id}.{tenant_id}.{email}`` HMAC that Office Ally
and the Gateway still exchange. A service-local copy of either algorithm is
a defect.
"""

from __future__ import annotations

import time

import pytest

from adaptix_contracts.auth.mailroom_permissions import (
    MAILROOM_ADMIN,
    MAILROOM_SEND,
    mailroom_permissions_for_roles,
)
from adaptix_contracts.gateway_identity import (
    LEGACY_TIMESTAMP_TOLERANCE_SECONDS,
    GatewayIdentityExpired,
    GatewayIdentityInvalidTimestamp,
    GatewayIdentityMismatch,
    GatewayIdentityMissing,
    GatewayIdentitySecretMissing,
    canonical_legacy_payload,
    sign_legacy_identity,
    verify_gateway_signature,
    verify_legacy_identity,
)
from adaptix_contracts.gateway_signing import sign_gateway_context

SECRET = "unit-test-gateway-shared-secret-32-bytes-plus"


def test_legacy_sign_then_verify_roundtrip() -> None:
    ts, sig = sign_legacy_identity(
        user_id="user-1",
        tenant_id="tenant-1",
        email="user@example.test",
        shared_secret=SECRET,
    )
    verify_legacy_identity(
        tenant_id="tenant-1",
        user_id="user-1",
        email="user@example.test",
        timestamp=ts,
        signature=sig,
        shared_secret=SECRET,
    )


def test_legacy_payload_is_timestamp_dot_identity() -> None:
    assert (
        canonical_legacy_payload(
            timestamp="1700000000",
            user_id="u",
            tenant_id="t",
            email="e@x.test",
        )
        == b"1700000000.u.t.e@x.test"
    )


def test_legacy_missing_signature_is_rejected() -> None:
    with pytest.raises(GatewayIdentityMissing):
        verify_legacy_identity(
            tenant_id="t",
            user_id="u",
            email="e",
            timestamp="",
            signature="",
            shared_secret=SECRET,
        )


def test_legacy_forged_signature_is_rejected() -> None:
    ts, _sig = sign_legacy_identity(
        user_id="u", tenant_id="t", email="e", shared_secret=SECRET
    )
    with pytest.raises(GatewayIdentityMismatch):
        verify_legacy_identity(
            tenant_id="t",
            user_id="u",
            email="e",
            timestamp=ts,
            signature="deadbeef" * 8,
            shared_secret=SECRET,
        )


def test_legacy_non_ascii_signature_rejects_without_raising() -> None:
    """A 64-char signature containing a non-hex, non-ASCII byte must reject cleanly.

    Regression for a real crash: ``hmac.compare_digest`` raises ``TypeError``
    on a ``str`` operand containing any non-ASCII character. The prior
    implementation compared the caller-supplied ``signature`` (fully
    attacker-controlled -- the ``X-Adaptix-Gateway-Signature`` header on an
    ALB-direct, pre-auth request) with no shape validation at all, so a
    single crafted request turned a should-be-``GatewayIdentityMismatch``
    into an unhandled ``TypeError``. Must raise ``GatewayIdentityMismatch``,
    not crash.
    """
    ts, _sig = sign_legacy_identity(
        user_id="u", tenant_id="t", email="e", shared_secret=SECRET
    )
    with pytest.raises(GatewayIdentityMismatch):
        verify_legacy_identity(
            tenant_id="t",
            user_id="u",
            email="e",
            timestamp=ts,
            signature="é" * 64,
            shared_secret=SECRET,
        )


def test_legacy_non_hex_ascii_signature_is_rejected() -> None:
    """64 ASCII characters that are not hex digits must also reject cleanly."""
    ts, _sig = sign_legacy_identity(
        user_id="u", tenant_id="t", email="e", shared_secret=SECRET
    )
    with pytest.raises(GatewayIdentityMismatch):
        verify_legacy_identity(
            tenant_id="t",
            user_id="u",
            email="e",
            timestamp=ts,
            signature="g" * 64,
            shared_secret=SECRET,
        )


def test_legacy_cross_tenant_replay_is_rejected() -> None:
    ts, sig = sign_legacy_identity(
        user_id="u", tenant_id="tenant-a", email="e", shared_secret=SECRET
    )
    with pytest.raises(GatewayIdentityMismatch):
        verify_legacy_identity(
            tenant_id="tenant-b",
            user_id="u",
            email="e",
            timestamp=ts,
            signature=sig,
            shared_secret=SECRET,
        )


def test_legacy_expired_timestamp_is_rejected() -> None:
    old = int(time.time()) - LEGACY_TIMESTAMP_TOLERANCE_SECONDS - 10
    ts, sig = sign_legacy_identity(
        user_id="u", tenant_id="t", email="e", shared_secret=SECRET, now=old
    )
    with pytest.raises(GatewayIdentityExpired):
        verify_legacy_identity(
            tenant_id="t",
            user_id="u",
            email="e",
            timestamp=ts,
            signature=sig,
            shared_secret=SECRET,
        )


def test_legacy_non_integer_timestamp_is_rejected() -> None:
    with pytest.raises(GatewayIdentityInvalidTimestamp):
        verify_legacy_identity(
            tenant_id="t",
            user_id="u",
            email="e",
            timestamp="not-a-number",
            signature="ab" * 32,
            shared_secret=SECRET,
        )


def test_legacy_empty_secret_fails_closed() -> None:
    with pytest.raises(GatewayIdentitySecretMissing):
        sign_legacy_identity(user_id="u", tenant_id="t", email="e", shared_secret="")


def test_modern_sign_verify_still_roundtrips_through_this_package() -> None:
    ctx, sig = sign_gateway_context(
        shared_secret=SECRET,
        user_id="user-1",
        tenant_id="tenant-1",
        aud="adaptix-payments",
    )
    payload = verify_gateway_signature(
        context_b64=ctx, signature_hex=sig, shared_secret=SECRET
    )
    assert payload["user_id"] == "user-1"
    assert payload["tenant_id"] == "tenant-1"


def test_viewer_and_field_cannot_initiate_paid_mail() -> None:
    assert mailroom_permissions_for_roles(["viewer"]) == []
    assert mailroom_permissions_for_roles(["field_user"]) == []
    assert mailroom_permissions_for_roles(["crew_member"]) == []
    assert MAILROOM_SEND not in mailroom_permissions_for_roles(["operator"])


def test_admin_and_billing_can_send_mail() -> None:
    admin = mailroom_permissions_for_roles(["admin"])
    assert MAILROOM_SEND in admin
    assert MAILROOM_ADMIN in admin
    billing = mailroom_permissions_for_roles(["billing_operator"])
    assert MAILROOM_SEND in billing
    assert MAILROOM_ADMIN not in billing
