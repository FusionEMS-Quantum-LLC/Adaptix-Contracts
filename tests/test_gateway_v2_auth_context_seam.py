"""The seam between the gateway-v2 trust primitives and ``get_auth_context``.

``gateway_signature`` / ``gateway_keys`` / ``gateway_signing`` are exercised in
depth by ``test_gateway_asymmetric_trust``, and the Cortex Live demo claims by
``test_auth_contracts`` — but only over the legacy gateway-v1 path. Nothing
covered their COMPOSITION: a gateway-v2 context arriving at the FastAPI
dependency that every Adaptix service actually depends on.

That gap hid three defects, all fixed by the change these tests guard:

* the producer (``GatewayClaims``) could not express ``is_founder``,
  ``mfa_verified`` or the four demo claims at all, so gateway-v2 silently
  dropped them — ``is_demo`` degrading OPEN into an ordinary session;
* ``get_auth_context`` never accepted or forwarded ``X-Adaptix-Auth-Key-Id``,
  so no gateway-v2 context could be verified through it;
* verification was gated on a shared secret existing, so a service in the
  asymmetric end-state — the documented rollout removes that secret — would
  503 on every signed request.

These are end-state tests: they must keep passing once the fleet holds public
keys only.
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
from fastapi import HTTPException

from adaptix_contracts import gateway_signature
from adaptix_contracts.auth_contracts import get_auth_context
from adaptix_contracts.gateway_keys import (
    GATEWAY_PUBLIC_KEYS_ENV,
    GATEWAY_SIGNING_KEY_ID_ENV,
    GATEWAY_SIGNING_PRIVATE_KEY_ENV,
    build_jwks,
    generate_signing_keypair,
    reset_public_keyset_cache,
)
from adaptix_contracts.gateway_signature import (
    ENVIRONMENT_ENV,
    GATEWAY_EXPECTED_AUDIENCE_ENV,
    GATEWAY_SHARED_SECRET_ENV,
    GATEWAY_TRUST_MODE_ENV,
    GatewaySignatureError,
)
from adaptix_contracts.gateway_signing import GatewayClaims, sign_claims_asymmetric

KID = "gw-seam-1"
AUDIENCE = "adaptix-core"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in (
        GATEWAY_PUBLIC_KEYS_ENV,
        GATEWAY_SIGNING_PRIVATE_KEY_ENV,
        GATEWAY_SIGNING_KEY_ID_ENV,
        GATEWAY_SHARED_SECRET_ENV,
        GATEWAY_EXPECTED_AUDIENCE_ENV,
        GATEWAY_TRUST_MODE_ENV,
        ENVIRONMENT_ENV,
        "ADAPTIX_GATEWAY_HMAC_ENFORCE",
    ):
        monkeypatch.delenv(var, raising=False)
    reset_public_keyset_cache()
    gateway_signature._WARN_ONCE["audience_unpinned"] = False
    yield
    reset_public_keyset_cache()


@pytest.fixture()
def asymmetric_only(monkeypatch):
    """The D-053 END STATE: public keys present, shared secret ABSENT.

    This is what a domain service looks like after rollout step 3 removes
    ``ADAPTIX_GATEWAY_SHARED_SECRET`` from its task definition.
    """
    pem, jwks_entry = generate_signing_keypair(KID)
    monkeypatch.setenv(GATEWAY_SIGNING_PRIVATE_KEY_ENV, pem)
    monkeypatch.setenv(GATEWAY_SIGNING_KEY_ID_ENV, KID)
    monkeypatch.setenv(GATEWAY_PUBLIC_KEYS_ENV, build_jwks([jwks_entry]))
    monkeypatch.setenv(GATEWAY_TRUST_MODE_ENV, "asymmetric")
    monkeypatch.setenv(GATEWAY_EXPECTED_AUDIENCE_ENV, AUDIENCE)
    monkeypatch.delenv(GATEWAY_SHARED_SECRET_ENV, raising=False)
    reset_public_keyset_cache()


def _call(user_id, tenant_id, ctx, sig, kid):
    return asyncio.run(
        get_auth_context(
            x_user_id=str(user_id),
            x_tenant_id=str(tenant_id),
            x_adaptix_auth_context=ctx,
            x_adaptix_auth_signature=sig,
            x_adaptix_auth_path="gateway-v2",
            x_adaptix_auth_key_id=kid,
        )
    )


def _sign_v1(user_id: str, tenant_id: str) -> tuple[str, str]:
    """Mint a legacy HMAC (v1) context, as the pre-v2 gateway does."""
    now = int(time.time())
    payload = {
        "sub": user_id,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "email": "u@example.test",
        "roles": ["paramedic"],
        "scopes": [],
        "is_founder": False,
        "mfa_verified": False,
        "iss": "adaptix-gateway",
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + 60,
    }
    b64 = (
        base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        )
        .rstrip(b"=")
        .decode()
    )
    sig = hmac.new("s".encode() * 48, b64.encode(), hashlib.sha256).hexdigest()
    return b64, sig


def _sign(user_id, tenant_id, **overrides):
    return sign_claims_asymmetric(
        GatewayClaims(
            user_id=str(user_id),
            tenant_id=str(tenant_id),
            aud=AUDIENCE,
            jti=str(uuid4()),
            **overrides,
        )
    )


class TestV2ReachesTheDependency:
    """A gateway-v2 context must verify through the real service entry point."""

    def test_v2_context_verifies_without_any_shared_secret(self, asymmetric_only):
        """Rollout step 3 (secret removed) must not 503 the service."""
        user_id, tenant_id = uuid4(), uuid4()
        ctx, sig, kid = _sign(user_id, tenant_id, roles=["paramedic"])

        auth = _call(user_id, tenant_id, ctx, sig, kid)

        assert auth.user_id == user_id
        assert auth.tenant_id == tenant_id
        assert auth.roles == ["paramedic"]

    def test_signed_roles_are_authoritative_over_spoofable_headers(
        self, asymmetric_only
    ):
        """The v2 path must ignore raw role headers exactly as v1 does."""
        user_id, tenant_id = uuid4(), uuid4()
        ctx, sig, kid = _sign(user_id, tenant_id, roles=["paramedic"])

        auth = asyncio.run(
            get_auth_context(
                x_user_id=str(user_id),
                x_tenant_id=str(tenant_id),
                x_user_roles="founder,admin",
                x_is_founder="true",
                x_adaptix_auth_context=ctx,
                x_adaptix_auth_signature=sig,
                x_adaptix_auth_path="gateway-v2",
                x_adaptix_auth_key_id=kid,
            )
        )

        assert auth.roles == ["paramedic"]
        assert auth.is_founder is False

    def test_identity_mismatch_defense_applies_to_v2(self, asymmetric_only):
        """A valid v2 signature over a DIFFERENT identity is still a tamper."""
        signed_user, tenant_id = uuid4(), uuid4()
        ctx, sig, kid = _sign(signed_user, tenant_id)

        with pytest.raises(HTTPException) as exc:
            _call(uuid4(), tenant_id, ctx, sig, kid)

        assert exc.value.status_code == 401


class TestClaimsSurviveTheV2Path:
    """Every claim the verifier consumes must survive signing under v2."""

    def test_founder_survives(self, asymmetric_only):
        user_id, tenant_id = uuid4(), uuid4()
        ctx, sig, kid = _sign(user_id, tenant_id, is_founder=True)

        auth = _call(user_id, tenant_id, ctx, sig, kid)

        assert auth.is_founder is True
        assert "founder" in auth.roles

    def test_mfa_verified_survives(self, asymmetric_only):
        user_id, tenant_id = uuid4(), uuid4()
        ctx, sig, kid = _sign(user_id, tenant_id, mfa_verified=True)

        auth = _call(user_id, tenant_id, ctx, sig, kid)

        assert auth.mfa_verified is True

    def test_demo_session_survives_and_does_not_degrade_open(self, asymmetric_only):
        """The defect that degraded OPEN: a demo session must stay a demo session."""
        user_id, tenant_id = uuid4(), uuid4()
        demo_session, demo_lease = uuid4(), uuid4()
        ctx, sig, kid = _sign(
            user_id,
            tenant_id,
            roles=["agency_admin"],
            is_demo=True,
            demo_session_id=str(demo_session),
            demo_lease_id=str(demo_lease),
            demo_persona="agency_admin",
        )

        auth = _call(user_id, tenant_id, ctx, sig, kid)

        assert auth.is_demo is True
        assert auth.demo_session_id == demo_session
        assert auth.demo_lease_id == demo_lease
        assert auth.demo_persona == "agency_admin"
        assert auth.is_founder is False

    def test_no_lease_demo_session_roundtrips_with_agency(self, asymmetric_only):
        """The no-lease family (founder Platform Demo Mode / public synthetic
        sessions) signs and verifies with the synthetic agency intact."""
        user_id, tenant_id = uuid4(), uuid4()
        demo_session = uuid4()
        ctx, sig, kid = _sign(
            user_id,
            tenant_id,
            roles=["dispatcher"],
            is_demo=True,
            demo_session_id=str(demo_session),
            demo_persona="dispatcher",
            demo_agency_id="demo-agency-metro",
        )

        auth = _call(user_id, tenant_id, ctx, sig, kid)

        assert auth.is_demo is True
        assert auth.demo_session_id == demo_session
        assert auth.demo_lease_id is None
        assert auth.demo_persona == "dispatcher"
        assert auth.demo_agency_id == "demo-agency-metro"

    def test_ordinary_context_stays_non_demo(self, asymmetric_only):
        """Absence of demo claims must not be readable as a demo session."""
        user_id, tenant_id = uuid4(), uuid4()
        ctx, sig, kid = _sign(user_id, tenant_id)

        auth = _call(user_id, tenant_id, ctx, sig, kid)

        assert auth.is_demo is False
        assert auth.demo_session_id is None
        assert auth.demo_lease_id is None
        assert auth.demo_persona is None
        assert auth.mfa_verified is False


class TestProducerRefusesWhatTheVerifierRejects:
    """A producer mistake must fail at signing, not as a 401 storm downstream."""

    def test_demo_plus_founder_flag_refused(self):
        with pytest.raises(GatewaySignatureError, match="founder"):
            GatewayClaims(
                user_id="u",
                tenant_id="t",
                aud=AUDIENCE,
                is_founder=True,
                is_demo=True,
                demo_session_id=str(uuid4()),
                demo_lease_id=str(uuid4()),
                demo_persona="agency_admin",
            ).validated()

    def test_demo_plus_founder_role_refused(self):
        """The verifier derives founder from a role too — so must the producer."""
        with pytest.raises(GatewaySignatureError, match="founder"):
            GatewayClaims(
                user_id="u",
                tenant_id="t",
                aud=AUDIENCE,
                roles=["Founder"],
                is_demo=True,
                demo_session_id=str(uuid4()),
                demo_lease_id=str(uuid4()),
                demo_persona="agency_admin",
            ).validated()

    def test_malformed_demo_session_refused(self):
        with pytest.raises(GatewaySignatureError, match="demo_session_id"):
            GatewayClaims(
                user_id="u",
                tenant_id="t",
                aud=AUDIENCE,
                is_demo=True,
                demo_session_id="not-a-uuid",
                demo_lease_id=str(uuid4()),
                demo_persona="agency_admin",
            ).validated()

    def test_empty_persona_refused(self):
        with pytest.raises(GatewaySignatureError, match="demo_persona"):
            GatewayClaims(
                user_id="u",
                tenant_id="t",
                aud=AUDIENCE,
                is_demo=True,
                demo_session_id=str(uuid4()),
                demo_lease_id=str(uuid4()),
                demo_persona="   ",
            ).validated()

    def test_leased_demo_with_agency_refused(self):
        """demo_agency_id may not accompany a lease (verifier: mixed families)."""
        with pytest.raises(GatewaySignatureError, match="demo_agency_id"):
            GatewayClaims(
                user_id="u",
                tenant_id="t",
                aud=AUDIENCE,
                is_demo=True,
                demo_session_id=str(uuid4()),
                demo_lease_id=str(uuid4()),
                demo_persona="agency_admin",
                demo_agency_id="demo-agency-metro",
            ).validated()

    def test_no_lease_demo_with_malformed_session_refused(self):
        with pytest.raises(GatewaySignatureError, match="demo_session_id"):
            GatewayClaims(
                user_id="u",
                tenant_id="t",
                aud=AUDIENCE,
                is_demo=True,
                demo_session_id="not-a-uuid",
                demo_persona="dispatcher",
            ).validated()

    def test_no_lease_demo_may_be_founder(self):
        """Founder Platform Demo Mode: founder + is_demo without a lease signs."""
        claims = GatewayClaims(
            user_id="u",
            tenant_id="t",
            aud=AUDIENCE,
            is_founder=True,
            is_demo=True,
            demo_persona="founder",
        ).validated()
        payload = claims.payload()
        assert payload["is_demo"] is True
        assert payload["is_founder"] is True
        assert "demo_lease_id" not in payload

    def test_demo_detail_without_is_demo_refused(self):
        """Detail without the flag would silently downgrade to an ordinary session."""
        with pytest.raises(GatewaySignatureError, match="is_demo=True"):
            GatewayClaims(
                user_id="u",
                tenant_id="t",
                aud=AUDIENCE,
                demo_session_id=str(uuid4()),
                demo_lease_id=str(uuid4()),
                demo_persona="agency_admin",
            ).validated()


class TestPayloadByteCompatibility:
    """The legacy HMAC path keeps byte-identical payloads for unchanged callers."""

    def test_unset_claims_emit_no_keys(self):
        payload = GatewayClaims(
            user_id="u", tenant_id="t", aud=AUDIENCE, jti="j", now=1_700_000_000
        ).payload()

        for absent in (
            "is_founder",
            "mfa_verified",
            "is_demo",
            "demo_session_id",
            "demo_lease_id",
            "demo_persona",
        ):
            assert absent not in payload

    def test_false_booleans_emit_no_keys(self):
        """Explicit False must stay absent, not become ``false``."""
        payload = GatewayClaims(
            user_id="u",
            tenant_id="t",
            aud=AUDIENCE,
            jti="j",
            now=1_700_000_000,
            is_founder=False,
            mfa_verified=False,
            is_demo=False,
        ).payload()

        assert "is_founder" not in payload
        assert "mfa_verified" not in payload
        assert "is_demo" not in payload


class TestStrayKeyIdRoutesStricter:
    """Forwarding the key-id header has one deliberate, non-no-op consequence.

    ``_is_v2_request`` treats any non-empty ``key_id`` as a claim of gateway-v2.
    Before the header was forwarded, routing depended on ``auth_path`` alone, so
    a legacy v1 request carrying a stray key-id used to verify by HMAC and pass.
    It is now rejected on an hmac-mode service.

    That is the intended direction: claiming v2 can only ever force STRICTER
    verification, never weaker, which is what guarantees no header downgrades a
    verifier. Pinned here so the change stays deliberate.
    """

    @pytest.fixture()
    def hmac_service(self, monkeypatch):
        monkeypatch.setenv(GATEWAY_SHARED_SECRET_ENV, "s" * 48)
        monkeypatch.setenv(GATEWAY_TRUST_MODE_ENV, "hmac")

    def _v1_request(self, key_id):
        user_id, tenant_id = uuid4(), uuid4()
        ctx, sig = _sign_v1(str(user_id), str(tenant_id))
        return asyncio.run(
            get_auth_context(
                x_user_id=str(user_id),
                x_tenant_id=str(tenant_id),
                x_adaptix_auth_context=ctx,
                x_adaptix_auth_signature=sig,
                x_adaptix_auth_path="gateway-v1",
                x_adaptix_auth_key_id=key_id,
            )
        )

    def test_v1_without_key_id_still_passes_unchanged(self, hmac_service):
        """The normal legacy path must be untouched."""
        auth = self._v1_request(None)

        assert auth.roles == ["paramedic"]

    def test_v1_with_stray_key_id_is_now_rejected(self, hmac_service):
        """Documented in CHANGELOG 2.31.0 under 'one deliberate behavior change'."""
        with pytest.raises(HTTPException) as exc:
            self._v1_request("some-kid")

        assert exc.value.status_code == 401


class TestNoVerificationMaterialStillFailsClosed:
    """Removing the secret must not become a way to skip verification."""

    def test_production_without_secret_or_keys_is_503(self, monkeypatch):
        monkeypatch.setenv(ENVIRONMENT_ENV, "production")
        user_id, tenant_id = uuid4(), uuid4()

        with pytest.raises(HTTPException) as exc:
            _call(user_id, tenant_id, "ctx", "sig", KID)

        assert exc.value.status_code == 503

    def test_v2_claim_without_keys_is_rejected_not_trusted(self, monkeypatch):
        """hmac-mode service + v2-claiming headers -> refused, never trusted."""
        monkeypatch.setenv(GATEWAY_SHARED_SECRET_ENV, "s" * 48)
        monkeypatch.setenv(GATEWAY_TRUST_MODE_ENV, "hmac")
        user_id, tenant_id = uuid4(), uuid4()

        with pytest.raises(HTTPException) as exc:
            _call(user_id, tenant_id, "ctx", "sig", KID)

        assert exc.value.status_code == 401
