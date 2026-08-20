"""The module-entitlement gate is a SECOND gateway-context verifier.

``auth_contracts.get_auth_context`` is the well-known one, and the D-053/D-034
repair landed there in 2.31.0. ``module_entitlement_gate._gateway_context_claims``
verifies the same headers for the 402 entitlement decision and was missed, so it
carried both original defects until 2.33.0:

1. it never forwarded ``X-Adaptix-Auth-Key-Id``, so a gateway-v2 context could
   not select a public key and fell through to the legacy HMAC path;
2. it gated verification on ``ADAPTIX_GATEWAY_SHARED_SECRET`` alone, so a
   service that had completed the migration -- public keys present, shared
   secret withdrawn, exactly what rollout step 3 produces -- answered 503 on
   every gated route.

Together those made the gate the component that would have broken the fleet by
following the rollout's own instructions. These tests are the seam coverage:
they exercise the REAL FastAPI dependency through a gated route, not the
verifier in isolation.

The last class is the load-bearing one for the gateway's own v2 work: it signs
the gateway's genuine 20-field payload (which ``GatewayClaims`` cannot express
-- it omits falsy claims and does not model ``session_jti`` at all) and proves
the Contracts verifier accepts the extra claims and that ``module_entitlements``
survives verification into the entitlement decision.
"""

from __future__ import annotations

import base64
import json
import time
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from adaptix_contracts.auth.module_entitlement_gate import require_module_entitlement
from adaptix_contracts.gateway_keys import (
    GATEWAY_PUBLIC_KEYS_ENV,
    GATEWAY_SIGNING_KEY_ID_ENV,
    GATEWAY_SIGNING_PRIVATE_KEY_ENV,
    b64url_encode,
    build_jwks,
    generate_signing_keypair,
    load_signing_key,
    reset_public_keyset_cache,
)
from adaptix_contracts.gateway_signature import (
    ENVIRONMENT_ENV,
    GATEWAY_EXPECTED_AUDIENCE_ENV,
    GATEWAY_SHARED_SECRET_ENV,
    GATEWAY_TRUST_MODE_ENV,
)

KID = "gw-gate-seam-1"
AUDIENCE = "adaptix-billing"
MODULE = "billing"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch):
    for var in (
        GATEWAY_PUBLIC_KEYS_ENV,
        GATEWAY_SIGNING_PRIVATE_KEY_ENV,
        GATEWAY_SIGNING_KEY_ID_ENV,
        GATEWAY_SHARED_SECRET_ENV,
        GATEWAY_EXPECTED_AUDIENCE_ENV,
        GATEWAY_TRUST_MODE_ENV,
        ENVIRONMENT_ENV,
    ):
        monkeypatch.delenv(var, raising=False)
    reset_public_keyset_cache()
    yield
    reset_public_keyset_cache()


@pytest.fixture()
def gated_client() -> TestClient:
    """A real route behind the real gate dependency."""
    app = FastAPI()

    @app.get(
        "/api/v1/billing/thing",
        dependencies=[Depends(require_module_entitlement(MODULE))],
    )
    def _thing() -> dict:
        return {"ok": True}

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def asymmetric_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """The D-053 END STATE: public keys present, shared secret ABSENT.

    This is precisely what a service's task definition looks like after the
    rollout removes ``ADAPTIX_GATEWAY_SHARED_SECRET``.
    """
    pem, jwks_entry = generate_signing_keypair(KID)
    monkeypatch.setenv(GATEWAY_SIGNING_PRIVATE_KEY_ENV, pem)
    monkeypatch.setenv(GATEWAY_SIGNING_KEY_ID_ENV, KID)
    monkeypatch.setenv(GATEWAY_PUBLIC_KEYS_ENV, build_jwks([jwks_entry]))
    monkeypatch.setenv(GATEWAY_TRUST_MODE_ENV, "asymmetric")
    monkeypatch.setenv(GATEWAY_EXPECTED_AUDIENCE_ENV, AUDIENCE)
    monkeypatch.delenv(GATEWAY_SHARED_SECRET_ENV, raising=False)
    reset_public_keyset_cache()


def _gateway_payload(
    *,
    tenant_id: str,
    module_entitlements: list[str],
    roles: list[str] | None = None,
    is_founder: bool = False,
    session_jti: str = "",
) -> dict:
    """The gateway's REAL 20-field payload, field for field.

    Copied from ``adaptix-gateway .../services/auth_context.py::sign_context``.
    ``GatewayClaims`` cannot produce this shape -- it omits ``is_founder`` and
    the demo block when falsy and has no ``session_jti``/``module_entitlements``
    fields -- which is why the gateway keeps building its own payload and only
    the signing scheme is shared.
    """
    now = int(time.time())
    user_id = str(uuid4())
    return {
        "sub": user_id,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "agency_id": "",
        "email": "u@example.test",
        "roles": list(roles or []),
        "scopes": [],
        "module_entitlements": list(module_entitlements),
        "is_founder": is_founder,
        "mfa_verified": False,
        "iss": "adaptix-gateway",
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + 60,
        "jti": str(uuid4()),
        "session_jti": session_jti,
        "is_demo": False,
        "demo_session_id": "",
        "demo_lease_id": "",
        "demo_persona": "",
    }


def _sign_v2(payload: dict) -> tuple[str, str, str]:
    """Ed25519-sign an ARBITRARY payload, exactly as the gateway will.

    Returns ``(context_b64, signature_b64, kid)``.
    """
    serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    context_b64 = (
        base64.urlsafe_b64encode(serialized.encode("utf-8")).decode("ascii").rstrip("=")
    )
    kid, private_key = load_signing_key()
    return context_b64, b64url_encode(private_key.sign(context_b64.encode("ascii"))), kid


def _v2_headers(ctx: str, sig: str, kid: str) -> dict[str, str]:
    return {
        "x-adaptix-auth-context": ctx,
        "x-adaptix-auth-signature": sig,
        "x-adaptix-auth-path": "gateway-v2",
        "x-adaptix-auth-key-id": kid,
    }


class TestKeysOnlyServiceStaysUp:
    """The migrated end state must serve traffic, not 503."""

    def test_v2_context_passes_the_gate_with_no_shared_secret(
        self, gated_client: TestClient, asymmetric_only: None
    ) -> None:
        # Before 2.33.0 this returned 503 in production and fell through to the
        # bearer path (401) elsewhere: the gate required a shared secret that
        # rollout step 3 had already removed.
        ctx, sig, kid = _sign_v2(
            _gateway_payload(tenant_id=str(uuid4()), module_entitlements=[MODULE])
        )
        resp = gated_client.get(
            "/api/v1/billing/thing", headers=_v2_headers(ctx, sig, kid)
        )
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"ok": True}

    def test_v2_context_still_enforces_the_entitlement(
        self, gated_client: TestClient, asymmetric_only: None
    ) -> None:
        """Verifying a v2 context must not become a bypass of the 402."""
        ctx, sig, kid = _sign_v2(
            _gateway_payload(tenant_id=str(uuid4()), module_entitlements=["cad"])
        )
        resp = gated_client.get(
            "/api/v1/billing/thing", headers=_v2_headers(ctx, sig, kid)
        )
        assert resp.status_code == 402, resp.text
        assert resp.json()["detail"]["required_module"] == MODULE

    def test_v2_founder_still_bypasses(
        self, gated_client: TestClient, asymmetric_only: None
    ) -> None:
        ctx, sig, kid = _sign_v2(
            _gateway_payload(
                tenant_id=str(uuid4()), module_entitlements=[], is_founder=True
            )
        )
        resp = gated_client.get(
            "/api/v1/billing/thing", headers=_v2_headers(ctx, sig, kid)
        )
        assert resp.status_code == 200, resp.text


class TestKeyIdIsActuallyForwarded:
    """Without the key-id forward the gate cannot select a verification key."""

    def test_wrong_kid_is_rejected_not_ignored(
        self, gated_client: TestClient, asymmetric_only: None
    ) -> None:
        """A kid naming no known key must fail, proving the kid is consulted."""
        ctx, sig, _kid = _sign_v2(
            _gateway_payload(tenant_id=str(uuid4()), module_entitlements=[MODULE])
        )
        resp = gated_client.get(
            "/api/v1/billing/thing",
            headers=_v2_headers(ctx, sig, "gw-not-a-real-kid"),
        )
        assert resp.status_code == 401, resp.text

    def test_tampered_v2_context_is_rejected(
        self, gated_client: TestClient, asymmetric_only: None
    ) -> None:
        """A present-but-invalid signature never falls through to bearer."""
        payload = _gateway_payload(
            tenant_id=str(uuid4()), module_entitlements=["cad"]
        )
        ctx, sig, kid = _sign_v2(payload)
        forged = dict(payload, module_entitlements=[MODULE])
        forged_ctx = (
            base64.urlsafe_b64encode(
                json.dumps(forged, separators=(",", ":"), sort_keys=True).encode()
            )
            .decode("ascii")
            .rstrip("=")
        )
        resp = gated_client.get(
            "/api/v1/billing/thing", headers=_v2_headers(forged_ctx, sig, kid)
        )
        assert resp.status_code == 401, resp.text


class TestFailClosedPostureIsPreserved:
    """Widening the gate to accept keys must not widen it to accept nothing."""

    def test_production_with_no_verification_material_still_503s(
        self, gated_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ENVIRONMENT_ENV, "production")
        # Neither a shared secret nor a public keyset: unverifiable.
        ctx = base64.urlsafe_b64encode(b'{"x":1}').decode().rstrip("=")
        resp = gated_client.get(
            "/api/v1/billing/thing", headers=_v2_headers(ctx, "deadbeef", KID)
        )
        assert resp.status_code == 503, resp.text
        assert resp.json()["detail"]["code"] == "gateway_secret_not_configured"

    def test_hmac_trust_mode_refuses_a_v2_claiming_context(
        self, gated_client: TestClient, asymmetric_only: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Headers may select a STRICTER scheme, never a weaker one.

        Pinned to ``hmac`` the gate must refuse a v2 context outright rather
        than quietly verifying it against the public keyset.
        """
        monkeypatch.setenv(GATEWAY_TRUST_MODE_ENV, "hmac")
        monkeypatch.setenv(GATEWAY_SHARED_SECRET_ENV, "s" * 48)
        ctx, sig, kid = _sign_v2(
            _gateway_payload(tenant_id=str(uuid4()), module_entitlements=[MODULE])
        )
        resp = gated_client.get(
            "/api/v1/billing/thing", headers=_v2_headers(ctx, sig, kid)
        )
        assert resp.status_code == 401, resp.text


class TestGatewayPayloadShapeSurvivesVerification:
    """The gateway's real 20-field payload must verify and keep its claims.

    This is the proof obligation the gateway's v2 work rests on: the gateway
    signs its OWN payload shape (not ``GatewayClaims``), so the extra claims it
    carries must pass the Contracts verifier untouched and the entitlement
    decision must still read ``module_entitlements`` off the verified payload.
    """

    def test_full_gateway_payload_verifies_and_entitlement_is_read(
        self, gated_client: TestClient, asymmetric_only: None
    ) -> None:
        payload = _gateway_payload(
            tenant_id=str(uuid4()),
            module_entitlements=[MODULE, "cad"],
            roles=["agency_admin"],
            session_jti=str(uuid4()),
        )
        assert len(payload) == 20, "the gateway payload shape changed"
        ctx, sig, kid = _sign_v2(payload)
        resp = gated_client.get(
            "/api/v1/billing/thing", headers=_v2_headers(ctx, sig, kid)
        )
        # 200 proves BOTH that the verifier tolerated the eight extra claims
        # and that module_entitlements survived verification into the decision.
        assert resp.status_code == 200, resp.text

    def test_empty_session_jti_is_carried_not_rejected(
        self, gated_client: TestClient, asymmetric_only: None
    ) -> None:
        """``session_jti: ""`` is the gateway's documented no-session value.

        It must sign and verify as an empty string. A verifier that rejected it
        would break every request from a caller with no session identity.
        """
        payload = _gateway_payload(
            tenant_id=str(uuid4()), module_entitlements=[MODULE], session_jti=""
        )
        assert payload["session_jti"] == ""
        ctx, sig, kid = _sign_v2(payload)
        resp = gated_client.get(
            "/api/v1/billing/thing", headers=_v2_headers(ctx, sig, kid)
        )
        assert resp.status_code == 200, resp.text
