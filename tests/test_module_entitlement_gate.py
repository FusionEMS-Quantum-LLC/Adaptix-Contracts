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
  4. Direct bearer path (no gateway context): a cryptographically VERIFIED
     Cognito user-pool token is accepted; a forged / unverifiable bearer, or an
     unconfigured verifier, fails CLOSED with 401 (previously the gate decoded
     the bearer with verify_signature=False and trusted forged claims).
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
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import adaptix_contracts.auth.module_entitlement_gate as meg
from adaptix_contracts.auth.module_entitlement_gate import (
    _SYSTEM_PRINCIPAL_TENANT_ID,
    require_module_entitlement,
)

_SECRET = "gate-test-shared-secret"  # noqa: S105 — test-only fixture

# Cognito app-client identifiers used across the direct-bearer verification
# tests. The gate binds a verified token to this exact pool + app client.
_COGNITO_POOL_ID = "us-east-1_gatetest"
_COGNITO_CLIENT_ID = "gate-test-client-id"  # noqa: S105 — test-only identifier
_COGNITO_ISSUER = f"https://cognito-idp.us-east-1.amazonaws.com/{_COGNITO_POOL_ID}"
_COGNITO_ENV_VARS = (
    "COGNITO_USER_POOL_ID",
    "COGNITO_CLIENT_ID",
    "COGNITO_CLIENT_ID_WEB",
    "COGNITO_ISSUER",
    "COGNITO_JWKS_URL",
    "COGNITO_REGION",
)


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


@pytest.fixture(scope="module")
def rsa_keypair() -> tuple[str, str]:
    """One RSA-2048 keypair for the whole module -> (private_pem, public_pem)."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    return private_pem, public_pem


def _set_cognito_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COGNITO_REGION", "us-east-1")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", _COGNITO_POOL_ID)
    monkeypatch.setenv("COGNITO_CLIENT_ID", _COGNITO_CLIENT_ID)
    monkeypatch.setenv("COGNITO_ISSUER", _COGNITO_ISSUER)
    monkeypatch.setenv("COGNITO_JWKS_URL", f"{_COGNITO_ISSUER}/.well-known/jwks.json")


def _clear_cognito_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in _COGNITO_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def _cognito_token(
    private_pem: str,
    *,
    token_use: str = "access",
    client_id: str = _COGNITO_CLIENT_ID,
    iss: str = _COGNITO_ISSUER,
    exp_delta: int = 300,
    **extra_claims,
) -> str:
    """Mint an RS256 token shaped like a real Cognito access/id token."""
    now = int(time.time())
    payload: dict = {
        "sub": str(uuid4()),
        "iss": iss,
        "token_use": token_use,
        "iat": now,
        "exp": now + exp_delta,
        **extra_claims,
    }
    if token_use == "id":
        payload.setdefault("aud", client_id)
    else:
        payload.setdefault("client_id", client_id)
    return pyjwt.encode(payload, private_pem, algorithm="RS256")


def _bearer_app() -> FastAPI:
    app = FastAPI()

    @app.get(
        "/api/v1/billing/thing",
        dependencies=[Depends(require_module_entitlement("billing"))],
    )
    def _thing() -> dict:
        return {"ok": True}

    return app


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
    """A forged HS256 bearer (attacker-style: not RS256-signed by the pool).

    Used to prove the gate now REJECTS such a token instead of trusting its
    (forgeable) ``is_founder`` / ``module_entitlements`` claims.
    """
    return pyjwt.encode(
        claims,
        "irrelevant-but-long-enough-test-secret-123456",
        algorithm="HS256",
    )


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


def test_direct_verified_bearer_with_entitlement_passes(
    monkeypatch: pytest.MonkeyPatch, rsa_keypair: tuple[str, str]
) -> None:
    # A cryptographically valid Cognito access token carrying the 'billing'
    # entitlement is accepted on the direct-service path.
    private_pem, public_pem = rsa_keypair
    _set_cognito_env(monkeypatch)
    monkeypatch.setattr(meg, "_cognito_signing_key", lambda token, config: public_pem)
    token = _cognito_token(private_pem, module_entitlements=["billing"])
    c = TestClient(_bearer_app())
    resp = c.get("/api/v1/billing/thing", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"ok": True}


def test_direct_verified_bearer_founder_passes(
    monkeypatch: pytest.MonkeyPatch, rsa_keypair: tuple[str, str]
) -> None:
    # A cryptographically valid token whose VERIFIED claims carry is_founder
    # bypasses the gate (identical intent to the gateway founder bypass).
    private_pem, public_pem = rsa_keypair
    _set_cognito_env(monkeypatch)
    monkeypatch.setattr(meg, "_cognito_signing_key", lambda token, config: public_pem)
    token = _cognito_token(private_pem, is_founder=True)
    c = TestClient(_bearer_app())
    resp = c.get("/api/v1/billing/thing", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text


def test_direct_forged_bearer_is_rejected_401(
    monkeypatch: pytest.MonkeyPatch, rsa_keypair: tuple[str, str]
) -> None:
    # THE FIX: a forged HS256 bearer claiming is_founder + entitlements is no
    # longer trusted. Cognito is configured and a real JWKS key is available,
    # but the token is not RS256-signed by the pool, so it fails closed with 401.
    private_pem, public_pem = rsa_keypair
    _set_cognito_env(monkeypatch)
    monkeypatch.setattr(meg, "_cognito_signing_key", lambda token, config: public_pem)
    forged = _bearer_with_claims(
        sub=str(uuid4()),
        tid=str(uuid4()),
        is_founder=True,
        module_entitlements=["billing"],
    )
    c = TestClient(_bearer_app())
    resp = c.get("/api/v1/billing/thing", headers={"Authorization": f"Bearer {forged}"})
    assert resp.status_code == 401, resp.text
    assert resp.json()["detail"]["code"] == "invalid_bearer_token"


def test_direct_bearer_rejected_when_verifier_unconfigured_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No Cognito config -> the gate cannot verify a direct bearer and MUST fail
    # closed (401), never trusting the unverified claims.
    _clear_cognito_env(monkeypatch)
    forged = _bearer_with_claims(sub=str(uuid4()), tid=str(uuid4()), is_founder=True)
    c = TestClient(_bearer_app())
    resp = c.get("/api/v1/billing/thing", headers={"Authorization": f"Bearer {forged}"})
    assert resp.status_code == 401, resp.text
    assert resp.json()["detail"]["code"] == "bearer_verifier_not_configured"


def test_direct_bearer_wrong_issuer_rejected_401(
    monkeypatch: pytest.MonkeyPatch, rsa_keypair: tuple[str, str]
) -> None:
    # Correctly RS256-signed by the pool key, but minted with a foreign issuer
    # -> rejected (401). Proves issuer pinning.
    private_pem, public_pem = rsa_keypair
    _set_cognito_env(monkeypatch)
    monkeypatch.setattr(meg, "_cognito_signing_key", lambda token, config: public_pem)
    token = _cognito_token(
        private_pem,
        iss="https://evil.example.com/pool",
        module_entitlements=["billing"],
    )
    c = TestClient(_bearer_app())
    resp = c.get("/api/v1/billing/thing", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401, resp.text
    assert resp.json()["detail"]["code"] == "invalid_bearer_token"


def test_direct_bearer_wrong_app_client_rejected_401(
    monkeypatch: pytest.MonkeyPatch, rsa_keypair: tuple[str, str]
) -> None:
    # Validly signed by the pool + correct issuer, but minted for a DIFFERENT
    # app client -> rejected (audience / app-client binding).
    private_pem, public_pem = rsa_keypair
    _set_cognito_env(monkeypatch)
    monkeypatch.setattr(meg, "_cognito_signing_key", lambda token, config: public_pem)
    token = _cognito_token(
        private_pem, client_id="some-other-client", module_entitlements=["billing"]
    )
    c = TestClient(_bearer_app())
    resp = c.get("/api/v1/billing/thing", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401, resp.text
    assert resp.json()["detail"]["code"] == "invalid_bearer_token"


def test_no_identity_at_all_is_401_missing_bearer(client: TestClient) -> None:
    resp = client.get("/api/v1/billing/thing")
    assert resp.status_code == 401, resp.text
    assert resp.json()["detail"]["code"] == "missing_bearer_token"


def test_gateway_signature_present_but_no_secret_falls_back_to_bearer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # NON-PRODUCTION: when the shared secret is unset, an unverifiable gateway
    # context falls back to the bearer path (fail-open to legacy), so a missing
    # bearer is 401.
    monkeypatch.delenv("ADAPTIX_GATEWAY_SHARED_SECRET", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
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


def test_gateway_signature_present_but_no_secret_is_503_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # PRODUCTION: a signed request that cannot be verified must not be trusted
    # and must not silently fall back to the unverified-bearer path — 503
    # fail-closed (same posture as get_auth_context behavior 3).
    monkeypatch.delenv("ADAPTIX_GATEWAY_SHARED_SECRET", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
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
    assert resp.status_code == 503, resp.text
    assert resp.json()["detail"]["code"] == "gateway_secret_not_configured"
    # Even a bearer alongside the unverifiable signature must not rescue it:
    # the signed context takes precedence and verification is impossible.
    bearer = _bearer_with_claims(
        module_entitlements=["billing"], tenant_id=str(uuid4())
    )
    resp2 = c.get(
        "/api/v1/billing/thing",
        headers={**_gw_headers(ctx, sig), "Authorization": f"Bearer {bearer}"},
    )
    assert resp2.status_code == 503, resp2.text


def test_prod_absent_signature_forged_bearer_is_401_not_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # PRODUCTION + no gateway secret + NO signature headers: the 503 (which
    # applies only when a signature is PRESENT but unverifiable) does NOT apply
    # here. The direct bearer is instead verified and, being forged with no
    # Cognito configured, fails closed with 401 — never a trusted 200.
    monkeypatch.delenv("ADAPTIX_GATEWAY_SHARED_SECRET", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    _clear_cognito_env(monkeypatch)

    c = TestClient(_bearer_app())
    token = _bearer_with_claims(module_entitlements=["billing"], tenant_id=str(uuid4()))
    resp = c.get("/api/v1/billing/thing", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401, resp.text
    assert resp.json()["detail"]["code"] == "bearer_verifier_not_configured"
