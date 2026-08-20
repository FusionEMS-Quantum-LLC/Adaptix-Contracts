"""Founder privilege floor on the UNSIGNED gateway path (AX5-00039).

``get_auth_context`` fails closed on unsigned requests in production by default
(``_gateway_hmac_enforce`` -> ``_is_production``). A service with a legitimate
UNSIGNED intra-VPC caller opts out with ``ADAPTIX_GATEWAY_HMAC_ENFORCE=false``.
That escape hatch re-opens the unsigned identity path, where ``X-Is-Founder``
and ``X-User-Roles`` are plain headers covered by no signature — so an in-VPC /
ALB-direct caller could send ``X-Is-Founder: true`` and be treated as the
platform owner, which lifts tenant scoping on founder-gated cross-tenant reads.

The floor: in PRODUCTION, ``founder`` is never granted from an unsigned request.
It rejects nothing — the caller keeps their ordinary roles — so it is safe to
run ahead of the per-service HMAC enforcement rollout.

These tests pin all four quadrants: {production, non-production} x {signed,
unsigned}, plus the "ordinary roles still work" no-regression case.
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

from adaptix_contracts.auth_contracts import get_auth_context

_SECRET = "floor-test-shared-secret"  # noqa: S105 — test-only fixture, not a real secret


@pytest.fixture(autouse=True)
def _deterministic_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit baseline: non-production, no enforcement, no secret, no aud pin."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("ADAPTIX_GATEWAY_HMAC_ENFORCE", raising=False)
    monkeypatch.delenv("ADAPTIX_GATEWAY_SHARED_SECRET", raising=False)
    monkeypatch.delenv("ADAPTIX_GATEWAY_EXPECTED_AUDIENCE", raising=False)


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _sign_context(
    *,
    user_id: str,
    tenant_id: str,
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
        "email": "founder@adaptix.test",
        "roles": list(roles or []),
        "scopes": [],
        "is_founder": bool(is_founder),
        "mfa_verified": False,
        "iss": "adaptix-gateway",
        "aud": "adaptix-core",
        "iat": now,
        "exp": now + 60,
        "jti": str(uuid4()),
    }
    serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    context_b64 = _b64url_encode(serialized)
    sig = hmac.new(
        _SECRET.encode("utf-8"), context_b64.encode("ascii"), hashlib.sha256
    ).hexdigest()
    return context_b64, sig


def _resolve(**kwargs: object):
    return asyncio.run(get_auth_context(**kwargs))  # type: ignore[arg-type]


def _production_unsigned(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production with the migration escape hatch on — the reachable case."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ADAPTIX_GATEWAY_HMAC_ENFORCE", "false")


# ---------------------------------------------------------------------------
# DENY — production, unsigned
# ---------------------------------------------------------------------------


def test_unsigned_x_is_founder_header_refused_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DENY: X-Is-Founder: true on an unsigned prod request grants nothing."""
    _production_unsigned(monkeypatch)
    auth = _resolve(
        x_user_id=str(uuid4()),
        x_tenant_id=str(uuid4()),
        x_user_roles="viewer",
        x_is_founder="true",
    )
    assert auth.is_founder is False
    assert "founder" not in {r.lower() for r in auth.roles}
    # The caller is NOT rejected — they keep their ordinary role.
    assert auth.roles == ["viewer"]


def test_unsigned_founder_role_header_refused_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DENY: 'founder' smuggled through X-User-Roles is stripped too.

    Both inputs are unsigned headers; closing only X-Is-Founder would leave the
    role list as an equivalent escalation path.
    """
    _production_unsigned(monkeypatch)
    auth = _resolve(
        x_user_id=str(uuid4()),
        x_tenant_id=str(uuid4()),
        x_user_roles="founder,billing_admin",
        x_is_founder="false",
    )
    assert auth.is_founder is False
    assert "founder" not in {r.lower() for r in auth.roles}
    assert auth.roles == ["billing_admin"]


def test_unsigned_founder_role_json_array_form_refused_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DENY: the Cognito JSON-array role form is stripped identically."""
    _production_unsigned(monkeypatch)
    auth = _resolve(
        x_user_id=str(uuid4()),
        x_tenant_id=str(uuid4()),
        x_user_roles='["founder","medic"]',
        x_is_founder="false",
    )
    assert auth.is_founder is False
    assert auth.roles == ["medic"]


def test_unsigned_founder_case_insensitive_refused_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DENY: casing cannot smuggle the role past the floor."""
    _production_unsigned(monkeypatch)
    auth = _resolve(
        x_user_id=str(uuid4()),
        x_tenant_id=str(uuid4()),
        x_user_roles="FoUnDeR",
        x_is_founder="false",
    )
    assert auth.is_founder is False
    assert auth.roles == []


@pytest.mark.parametrize("env_value", ["production", "prod", "PRODUCTION", "Prod"])
def test_floor_applies_to_every_production_env_spelling(
    monkeypatch: pytest.MonkeyPatch, env_value: str
) -> None:
    """DENY: the floor tracks the same _is_production() spellings as the module."""
    monkeypatch.setenv("ENVIRONMENT", env_value)
    monkeypatch.setenv("ADAPTIX_GATEWAY_HMAC_ENFORCE", "false")
    auth = _resolve(
        x_user_id=str(uuid4()),
        x_tenant_id=str(uuid4()),
        x_is_founder="true",
    )
    assert auth.is_founder is False


def test_demotion_is_logged_at_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A refused founder claim must be observable, not silent."""
    _production_unsigned(monkeypatch)
    with caplog.at_level("WARNING", logger="adaptix_contracts.auth_contracts"):
        _resolve(
            x_user_id=str(uuid4()),
            x_tenant_id=str(uuid4()),
            x_is_founder="true",
        )
    assert any(
        "founder privilege refused on an UNSIGNED gateway context" in r.message
        for r in caplog.records
    )


# ---------------------------------------------------------------------------
# ALLOW — the floor must not break legitimate traffic
# ---------------------------------------------------------------------------


def test_signed_founder_context_still_grants_founder_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ALLOW: a real gateway-signed founder context is unaffected in production.

    This is the path production founders actually arrive on, so it proves the
    floor is not a founder-surface outage.
    """
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ADAPTIX_GATEWAY_SHARED_SECRET", _SECRET)
    # D-034: the audience pin is mandatory in production; the happy path pins it.
    monkeypatch.setenv("ADAPTIX_GATEWAY_EXPECTED_AUDIENCE", "adaptix-core")
    user_id, tenant_id = str(uuid4()), str(uuid4())
    ctx, sig = _sign_context(
        user_id=user_id,
        tenant_id=tenant_id,
        roles=["founder"],
        is_founder=True,
    )
    auth = _resolve(
        x_user_id=user_id,
        x_tenant_id=tenant_id,
        x_adaptix_auth_context=ctx,
        x_adaptix_auth_signature=sig,
    )
    assert auth.is_founder is True
    assert "founder" in {r.lower() for r in auth.roles}


def test_signed_founder_survives_even_with_the_escape_hatch_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ALLOW: enforcement=false does not weaken the SIGNED founder path."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ADAPTIX_GATEWAY_HMAC_ENFORCE", "false")
    monkeypatch.setenv("ADAPTIX_GATEWAY_SHARED_SECRET", _SECRET)
    # D-034: the audience pin is mandatory in production; the happy path pins it.
    monkeypatch.setenv("ADAPTIX_GATEWAY_EXPECTED_AUDIENCE", "adaptix-core")
    user_id, tenant_id = str(uuid4()), str(uuid4())
    ctx, sig = _sign_context(
        user_id=user_id, tenant_id=tenant_id, roles=["founder"], is_founder=True
    )
    auth = _resolve(
        x_user_id=user_id,
        x_tenant_id=tenant_id,
        x_adaptix_auth_context=ctx,
        x_adaptix_auth_signature=sig,
    )
    assert auth.is_founder is True


def test_ordinary_unsigned_roles_are_untouched_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ALLOW: non-founder callers are not rejected and keep every role.

    The floor refuses ELEVATION only. If it rejected or emptied ordinary roles
    it would be an authorization outage for every service on the escape hatch.
    """
    _production_unsigned(monkeypatch)
    auth = _resolve(
        x_user_id=str(uuid4()),
        x_tenant_id=str(uuid4()),
        x_user_email="medic@adaptix.test",
        x_user_roles='["medic","dispatcher"]',
    )
    assert auth.is_founder is False
    assert auth.roles == ["medic", "dispatcher"]
    assert auth.email == "medic@adaptix.test"


def test_non_production_unsigned_founder_still_works(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ALLOW: dev/test ergonomics are deliberately unchanged.

    The fleet's test suites simulate a founder with headers alone. Applying the
    floor outside production would turn this one change into a fleet-wide CI
    break with no production security benefit.
    """
    monkeypatch.setenv("ENVIRONMENT", "development")
    auth = _resolve(
        x_user_id=str(uuid4()),
        x_tenant_id=str(uuid4()),
        x_is_founder="true",
    )
    assert auth.is_founder is True
    assert "founder" in {r.lower() for r in auth.roles}


def test_unset_environment_unsigned_founder_still_works() -> None:
    """ALLOW: an unset ENVIRONMENT is non-production, so behaviour is unchanged."""
    auth = _resolve(
        x_user_id=str(uuid4()),
        x_tenant_id=str(uuid4()),
        x_is_founder="true",
    )
    assert auth.is_founder is True


def test_floor_does_not_reject_the_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """ALLOW: identity still resolves — the floor must never raise.

    Raising here is what would 401 every not-yet-signing caller fleet-wide; that
    is the sequenced rollout, not this change.
    """
    _production_unsigned(monkeypatch)
    user_id, tenant_id = str(uuid4()), str(uuid4())
    auth = _resolve(
        x_user_id=user_id,
        x_tenant_id=tenant_id,
        x_is_founder="true",
    )
    assert str(auth.user_id) == user_id
    assert str(auth.tenant_id) == tenant_id
