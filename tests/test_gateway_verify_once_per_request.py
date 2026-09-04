"""AUTH-REPLAY-VERIFY-ONCE-001 -- verify the gateway assertion once per request.

Contracts >= 5.2.0 records each verified gateway assertion as single-use. A
legitimate request whose one assertion was verified by two authentication-
dependent checks -- the module entitlement gate, then ``get_auth_context`` --
had its SECOND verification rejected as a replay, 401-ing a legitimate request.

``verify_gateway_signature_for_request`` scopes verification to the request:
the first authentication-dependent check verifies (and records replay) once and
binds the principal to ``request.state``; later checks in the SAME request reuse
it. A genuinely separate request has a fresh scope and verifies independently,
so cross-request replay protection is unchanged.

These tests pin: (1) the exact production failure now passes and the assertion
is verified exactly once; (2) genuine cross-request replay is still rejected;
(3) authorization negatives still deny; (4) a verified principal never leaks
between requests.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from adaptix_contracts import gateway_signature
from adaptix_contracts.auth.module_entitlement_gate import require_module_entitlement
from adaptix_contracts.auth_contracts import AuthContext, get_auth_context

_SECRET = "verify-once-unit-test-hmac-material-not-a-real-value"
_AUD = "adaptix-billing"


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _sign(
    *,
    user_id: str,
    tenant_id: str,
    module_entitlements: list[str] | None = None,
    jti: str | None = None,
    secret: str = _SECRET,
) -> tuple[str, str]:
    now = int(time.time())
    payload = {
        "sub": user_id,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "agency_id": "",
        "email": "system@adaptixcore.com",
        "roles": [],
        "scopes": [],
        "is_founder": False,
        "module_entitlements": list(module_entitlements or []),
        "iss": "adaptix-gateway",
        "aud": _AUD,
        "iat": now,
        "exp": now + 60,
        "jti": jti or str(uuid4()),
    }
    ctx = _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    sig = hmac.new(secret.encode(), ctx.encode("ascii"), hashlib.sha256).hexdigest()
    return ctx, sig


def _headers(ctx: str, sig: str, user_id: str, tenant_id: str) -> dict[str, str]:
    # A real gateway request carries BOTH the signed context and the injected
    # identity headers; get_auth_context cross-checks them.
    return {
        "X-User-Id": user_id,
        "X-Tenant-Id": tenant_id,
        "X-Adaptix-Auth-Context": ctx,
        "X-Adaptix-Auth-Signature": sig,
        "X-Adaptix-Auth-Path": "gateway-v1",
    }


def _gated_app() -> FastAPI:
    """A route guarded by BOTH the entitlement gate AND get_auth_context.

    This is the exact shape that 401-ed before the fix: the router-level gate
    verifies the assertion, then the route's get_auth_context verifies the same
    assertion again.
    """
    app = FastAPI()

    @app.get(
        "/api/v1/billing/thing",
        dependencies=[Depends(require_module_entitlement("billing"))],
    )
    def _thing(auth: AuthContext = Depends(get_auth_context)) -> dict:
        return {"tenant": str(auth.tenant_id), "user": str(auth.user_id)}

    return app


@pytest.fixture(autouse=True)
def _hmac_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ADAPTIX_GATEWAY_SHARED_SECRET", _SECRET)
    monkeypatch.delenv("ADAPTIX_GATEWAY_EXPECTED_AUDIENCE", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    gateway_signature.reset_gateway_replay_cache_for_tests()
    yield
    gateway_signature.reset_gateway_replay_cache_for_tests()


def _count_verifications(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """Spy that counts REAL cryptographic verifications, delegating to the real one."""
    calls = {"n": 0}
    real = gateway_signature.verify_gateway_signature

    def counting(**kw):
        calls["n"] += 1
        return real(**kw)

    monkeypatch.setattr(gateway_signature, "verify_gateway_signature", counting)
    return calls


def test_one_request_two_checks_verifies_once_and_succeeds(monkeypatch):
    """The exact production failure: entitlement gate + get_auth_context on one
    request. It must succeed, and the assertion must be verified EXACTLY once."""
    calls = _count_verifications(monkeypatch)
    uid, tid = str(uuid4()), str(uuid4())
    ctx, sig = _sign(user_id=uid, tenant_id=tid, module_entitlements=["billing"])

    client = TestClient(_gated_app(), raise_server_exceptions=False)
    resp = client.get("/api/v1/billing/thing", headers=_headers(ctx, sig, uid, tid))

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"tenant": tid, "user": uid}
    # Two authentication-dependent checks ran, but the crypto verify happened ONCE.
    got = calls["n"]
    assert got == 1, f"expected exactly one verification, got {got}"


def test_missing_entitlement_still_denies(monkeypatch):
    """Verify-once must not weaken authorization: no billing entitlement is denied."""
    uid, tid = str(uuid4()), str(uuid4())
    ctx, sig = _sign(user_id=uid, tenant_id=tid, module_entitlements=["epcr"])
    client = TestClient(_gated_app(), raise_server_exceptions=False)
    resp = client.get("/api/v1/billing/thing", headers=_headers(ctx, sig, uid, tid))
    # The gate answers 402 Payment Required for a tenant whose subscription
    # lacks the module (not 403) -- the point is it DENIES, and verify-once did
    # not turn a real authorization denial into an allow.
    assert resp.status_code == 402, resp.text


def test_genuine_cross_request_replay_is_rejected(monkeypatch):
    """A SECOND request reusing the same assertion (same jti) must be rejected as
    a replay. This proves verify-once-per-request did not become
    verify-once-per-process/token/user."""
    calls = _count_verifications(monkeypatch)
    uid, tid = str(uuid4()), str(uuid4())
    ctx, sig = _sign(user_id=uid, tenant_id=tid, module_entitlements=["billing"])
    client = TestClient(_gated_app(), raise_server_exceptions=False)
    h = _headers(ctx, sig, uid, tid)

    first = client.get("/api/v1/billing/thing", headers=h)
    assert first.status_code == 200, first.text
    assert calls["n"] == 1

    # Second, genuinely separate HTTP request replays the same assertion.
    second = client.get("/api/v1/billing/thing", headers=h)
    assert second.status_code == 401, second.text
    # It DID verify again (fresh request scope) and the replay guard caught it.
    assert calls["n"] == 2


def test_a_new_request_with_a_fresh_assertion_verifies_independently(monkeypatch):
    calls = _count_verifications(monkeypatch)
    uid, tid = str(uuid4()), str(uuid4())
    client = TestClient(_gated_app(), raise_server_exceptions=False)

    for _ in range(3):
        ctx, sig = _sign(user_id=uid, tenant_id=tid, module_entitlements=["billing"])
        resp = client.get("/api/v1/billing/thing", headers=_headers(ctx, sig, uid, tid))
        assert resp.status_code == 200, resp.text
    # Three distinct requests, three distinct assertions -> three verifications,
    # one per request. No cross-request reuse.
    assert calls["n"] == 3


def test_verified_principal_does_not_leak_between_requests(monkeypatch):
    """Two different users' requests must each resolve their OWN principal; a
    verified principal from one request must never be observed by another."""
    client = TestClient(_gated_app(), raise_server_exceptions=False)
    seen = []
    for _ in range(4):
        uid, tid = str(uuid4()), str(uuid4())
        ctx, sig = _sign(user_id=uid, tenant_id=tid, module_entitlements=["billing"])
        resp = client.get("/api/v1/billing/thing", headers=_headers(ctx, sig, uid, tid))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body == {"tenant": tid, "user": uid}, "principal leaked across requests"
        seen.append((body["user"], body["tenant"]))
    assert len(set(seen)) == 4  # every request saw only its own identity


def test_invalid_signature_denies_before_authorization(monkeypatch):
    uid, tid = str(uuid4()), str(uuid4())
    ctx, _sig = _sign(user_id=uid, tenant_id=tid, module_entitlements=["billing"])
    bad_sig = "0" * 64  # well-formed hex, wrong value
    client = TestClient(_gated_app(), raise_server_exceptions=False)
    resp = client.get("/api/v1/billing/thing", headers=_headers(ctx, bad_sig, uid, tid))
    assert resp.status_code == 401, resp.text


def test_expired_assertion_denies(monkeypatch):
    uid, tid = str(uuid4()), str(uuid4())
    now = int(time.time())
    payload = {
        "sub": uid,
        "user_id": uid,
        "tenant_id": tid,
        "agency_id": "",
        "email": "system@adaptixcore.com",
        "roles": [],
        "scopes": [],
        "is_founder": False,
        "module_entitlements": ["billing"],
        "iss": "adaptix-gateway",
        "aud": _AUD,
        "iat": now - 3600,
        "exp": now - 1800,
        "jti": str(uuid4()),
    }
    ctx = _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    sig = hmac.new(_SECRET.encode(), ctx.encode("ascii"), hashlib.sha256).hexdigest()
    client = TestClient(_gated_app(), raise_server_exceptions=False)
    resp = client.get("/api/v1/billing/thing", headers=_headers(ctx, sig, uid, tid))
    assert resp.status_code == 401, resp.text


def test_no_request_scope_falls_back_to_direct_verify(monkeypatch):
    """A non-HTTP caller (request=None) still verifies fully and records replay,
    so there is no scope-less bypass."""
    gateway_signature.reset_gateway_replay_cache_for_tests()
    uid, tid = str(uuid4()), str(uuid4())
    ctx, sig = _sign(user_id=uid, tenant_id=tid, module_entitlements=["billing"])
    # First direct verify with no request -> succeeds and records the jti.
    p1 = gateway_signature.verify_gateway_signature_for_request(
        None,
        context_b64=ctx,
        signature_hex=sig,
        shared_secret=_SECRET,
        auth_path="gateway-v1",
    )
    assert p1["user_id"] == uid
    # Second direct verify of the SAME assertion with no request scope -> the
    # replay guard still fires (no request to fold into).
    with pytest.raises(gateway_signature.GatewaySignatureError):
        gateway_signature.verify_gateway_signature_for_request(
            None,
            context_b64=ctx,
            signature_hex=sig,
            shared_secret=_SECRET,
            auth_path="gateway-v1",
        )
