"""Tests for the shared module entitlement gate's gateway-identity support.

Covers the non-breaking change that lets the gate trust the gateway's
HMAC-signed auth context (the worker / service-to-service path where the
gateway strips the raw Authorization bearer) while preserving the legacy
direct-bearer path unchanged.

Paths under test:
  1. Gateway-verified context present  -> gate passes WITHOUT a raw bearer.
  2. Gateway-verified context for a NON-entitled tenant (not system/founder)
     -> 402 module_not_entitled (entitlement still enforced for real tenants).
  3. Gateway context present but signature INVALID -> 401 (tampered).
  4. Legacy direct bearer carrying the entitlement -> still passes (no regression).
  5. Neither gateway context nor bearer -> 401 missing_bearer_token (unchanged).
  6. System-principal tenant via verified context -> bypasses the gate.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from uuid import uuid4

import jwt as pyjwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from adaptix_contracts.auth.module_entitlement_gate import (
    _SYSTEM_PRINCIPAL_TENANT_ID,
    require_module_entitlement,
)

_SECRET = "gate-test-shared-secret"  # noqa: S105 — test-only fixture


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _sign_gateway_context(
    *,
    user_id: str,
    tenant_id: str,
    roles: list[str] | None = None,
    is_founder: bool = False,
    module_entitlements: list[str] | None = None,
    secret: str = _SECRET,
    iat: int | None = None,
    exp: int | None = None,
    iss: str = "adaptix-gateway",
) -> tuple[str, str]:
    """Produce (context_b64, signature_hex) exactly like the gateway producer."""
    now = int(time.time())
    payload = {
        "sub": user_id,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "agency_id": "",
        "email": "system@adaptixcore.com",
        "roles": list(roles or []),
        "scopes": [],
        "is_founder": is_founder,
        "module_entitlements": list(module_entitlements or []),
        "iss": iss,
        "aud": "adaptix-billing",
        "iat": now if iat is None else iat,
        "exp": (now + 60) if exp is None else exp,
        "jti": str(uuid4()),
    }
    serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    ctx = _b64url(serialized)
    sig = hmac.new(
        secret.encode("utf-8"), ctx.encode("ascii"), hashlib.sha256
    ).hexdigest()
    return ctx, sig


def _bearer_with_claims(**claims) -> str:
    """Unsigned-decodable bearer (gate decodes with verify_signature=False)."""
    return pyjwt.encode(claims, "irrelevant", algorithm="HS256")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ADAPTIX_GATEWAY_SHARED_SECRET", _SECRET)
    monkeypatch.delenv("ADAPTIX_GATEWAY_EXPECTED_AUDIENCE", raising=False)
    app = FastAPI()

    @app.get(
        "/api/v1/billing/thing",
        dependencies=[Depends(require_module_entitlement("billing"))],
    )
    def _thing() -> dict:
        return {"ok": True}

    return TestClient(app)


def _gw_headers(ctx: str, sig: str) -> dict[str, str]:
    return {
        "x-adaptix-auth-context": ctx,
        "x-adaptix-auth-signature": sig,
        "x-adaptix-auth-path": "gateway-v1",
    }


def test_gateway_identity_entitled_tenant_passes_without_bearer(
    client: TestClient,
) -> None:
    # A real tenant whose verified context carries the 'billing' entitlement.
    ctx, sig = _sign_gateway_context(
        user_id=str(uuid4()),
        tenant_id=str(uuid4()),
        roles=["agency_admin"],
        module_entitlements=["billing"],
    )
    resp = client.get("/api/v1/billing/thing", headers=_gw_headers(ctx, sig))
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"ok": True}


def test_gateway_identity_system_principal_bypasses(client: TestClient) -> None:
    # System worker tenant — no subscription entitlement, but platform principal.
    ctx, sig = _sign_gateway_context(
        user_id=str(uuid4()),
        tenant_id=_SYSTEM_PRINCIPAL_TENANT_ID,
        roles=["billing_operator"],
    )
    resp = client.get("/api/v1/billing/thing", headers=_gw_headers(ctx, sig))
    assert resp.status_code == 200, resp.text


def test_gateway_identity_founder_role_bypasses(client: TestClient) -> None:
    ctx, sig = _sign_gateway_context(
        user_id=str(uuid4()),
        tenant_id=str(uuid4()),
        roles=["founder"],
    )
    resp = client.get("/api/v1/billing/thing", headers=_gw_headers(ctx, sig))
    assert resp.status_code == 200, resp.text


def test_gateway_identity_non_entitled_tenant_is_402(client: TestClient) -> None:
    # Real tenant, verified context, but NOT entitled and NOT platform principal.
    ctx, sig = _sign_gateway_context(
        user_id=str(uuid4()),
        tenant_id=str(uuid4()),
        roles=["agency_admin"],
        module_entitlements=["cad"],
    )
    resp = client.get("/api/v1/billing/thing", headers=_gw_headers(ctx, sig))
    assert resp.status_code == 402, resp.text
    assert resp.json()["detail"]["code"] == "module_not_entitled"


def test_tampered_gateway_signature_is_401(client: TestClient) -> None:
    ctx, sig = _sign_gateway_context(
        user_id=str(uuid4()),
        tenant_id=_SYSTEM_PRINCIPAL_TENANT_ID,
        roles=["billing_operator"],
    )
    bad_sig = "0" * len(sig)
    resp = client.get("/api/v1/billing/thing", headers=_gw_headers(ctx, bad_sig))
    assert resp.status_code == 401, resp.text
    assert resp.json()["detail"]["code"] == "invalid_gateway_signature"


def test_legacy_bearer_with_entitlement_still_passes(client: TestClient) -> None:
    token = _bearer_with_claims(
        sub=str(uuid4()),
        tid=str(uuid4()),
        module_entitlements=["billing"],
    )
    resp = client.get(
        "/api/v1/billing/thing", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200, resp.text


def test_legacy_bearer_founder_still_passes(client: TestClient) -> None:
    token = _bearer_with_claims(sub=str(uuid4()), tid=str(uuid4()), is_founder=True)
    resp = client.get(
        "/api/v1/billing/thing", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200, resp.text


def test_no_identity_at_all_is_401_missing_bearer(client: TestClient) -> None:
    resp = client.get("/api/v1/billing/thing")
    assert resp.status_code == 401, resp.text
    assert resp.json()["detail"]["code"] == "missing_bearer_token"


def test_gateway_signature_present_but_no_secret_falls_back_to_bearer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # When the shared secret is unset, an unverifiable gateway context falls back
    # to the bearer path (fail-open to legacy), so a missing bearer is 401.
    monkeypatch.delenv("ADAPTIX_GATEWAY_SHARED_SECRET", raising=False)
    app = FastAPI()

    @app.get(
        "/api/v1/billing/thing",
        dependencies=[Depends(require_module_entitlement("billing"))],
    )
    def _thing() -> dict:
        return {"ok": True}

    c = TestClient(app)
    ctx, sig = _sign_gateway_context(
        user_id=str(uuid4()), tenant_id=_SYSTEM_PRINCIPAL_TENANT_ID, roles=["system"]
    )
    resp = c.get("/api/v1/billing/thing", headers=_gw_headers(ctx, sig))
    assert resp.status_code == 401, resp.text
    assert resp.json()["detail"]["code"] == "missing_bearer_token"
