"""D-053 acceptance tests: issuer-bound asymmetric gateway trust.

The defect: the gateway's symmetric HMAC signing key was distributed to every
verifying service, so ``covers_privilege`` proved only "a holder of the
fleet-wide secret", never "the gateway". These tests prove the corrected
property end-to-end at the contracts layer:

* A gateway-v2 context signs with a private key and verifies with a public key.
* **Compromise of Service A's configuration provides zero capability to forge a
  context accepted by Service B** — the register's acceptance sentence,
  exercised literally in ``TestVerifierCompromiseYieldsNothing``.
* A header cannot downgrade verification (no v2→HMAC path exists).
* ``asymmetric`` mode refuses legacy symmetric contexts outright.
* Audience pinning is mandatory in production (D-034) and startup fails
  loudly when the pin or key material is missing.
"""

from __future__ import annotations

import base64
import hashlib
import hmac as hmac_mod
import json
import time

import pytest

from adaptix_contracts import gateway_keys, gateway_signature
from adaptix_contracts.gateway_keys import (
    GATEWAY_PUBLIC_KEYS_ENV,
    GATEWAY_SIGNING_KEY_ID_ENV,
    GATEWAY_SIGNING_PRIVATE_KEY_ENV,
    GatewayKeyError,
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
    GatewaySignatureError,
    GatewayVerifierConfigurationError,
    assert_gateway_verifier_ready,
    gateway_trust_mode,
    verify_gateway_signature,
)
from adaptix_contracts.gateway_signing import (
    GatewayClaims,
    build_gateway_signed_headers,
    sign_claims_asymmetric,
)

KID = "gw-test-1"
OTHER_KID = "gw-test-2"
SHARED_SECRET = "x" * 48  # legacy HMAC secret for dual/hmac-mode tests


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Every test starts from a clean gateway-auth environment."""
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
    gateway_signature._WARN_ONCE["audience_unpinned"] = False
    yield
    reset_public_keyset_cache()


@pytest.fixture()
def keypair(monkeypatch):
    """Provision a gateway keypair: private into the 'gateway', public fleet-wide."""
    pem, jwks_entry = generate_signing_keypair(KID)
    monkeypatch.setenv(GATEWAY_SIGNING_PRIVATE_KEY_ENV, pem)
    monkeypatch.setenv(GATEWAY_SIGNING_KEY_ID_ENV, KID)
    monkeypatch.setenv(GATEWAY_PUBLIC_KEYS_ENV, build_jwks([jwks_entry]))
    reset_public_keyset_cache()
    return pem, jwks_entry


def _claims(**overrides) -> GatewayClaims:
    kwargs = {
        "user_id": "user-1",
        "tenant_id": "tenant-1",
        "aud": "adaptix-epcr",
        "jti": "jti-1",
    }
    kwargs.update(overrides)
    return GatewayClaims(**kwargs)


def _sign_v2(**overrides):
    """Sign a well-formed v2 context as the gateway would."""
    return sign_claims_asymmetric(_claims(**overrides))


def _hmac_context(payload: dict, secret: str) -> tuple[str, str]:
    """Mint a raw legacy-HMAC (context, signature) pair for attack scenarios."""
    b64 = (
        base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        )
        .rstrip(b"=")
        .decode()
    )
    sig = hmac_mod.new(secret.encode(), b64.encode(), hashlib.sha256).hexdigest()
    return b64, sig


class TestAsymmetricRoundTrip:
    def test_sign_verify_roundtrip(self, monkeypatch, keypair):
        monkeypatch.setenv(GATEWAY_EXPECTED_AUDIENCE_ENV, "adaptix-epcr")
        ctx, sig, kid = _sign_v2()
        payload = verify_gateway_signature(
            context_b64=ctx, signature_hex=sig, auth_path="gateway-v2", key_id=kid
        )
        assert payload["user_id"] == "user-1"
        assert payload["tenant_id"] == "tenant-1"
        assert payload["aud"] == "adaptix-epcr"
        assert payload["iss"] == "adaptix-gateway"
        assert payload["jti"] == "jti-1"

    def test_headers_helper_emits_v2(self, monkeypatch, keypair):
        monkeypatch.setenv(GATEWAY_EXPECTED_AUDIENCE_ENV, "adaptix-epcr")
        headers = build_gateway_signed_headers(
            user_id="user-1", tenant_id="tenant-1", aud="adaptix-epcr"
        )
        assert headers["X-Adaptix-Auth-Path"] == "gateway-v2"
        assert headers["X-Adaptix-Auth-Key-Id"] == KID
        payload = verify_gateway_signature(
            context_b64=headers["X-Adaptix-Auth-Context"],
            signature_hex=headers["X-Adaptix-Auth-Signature"],
            auth_path=headers["X-Adaptix-Auth-Path"],
            key_id=headers["X-Adaptix-Auth-Key-Id"],
        )
        assert payload["tenant_id"] == "tenant-1"
        # jti auto-generated when not supplied — required on v2.
        assert payload["jti"]

    def test_tampered_context_rejected(self, monkeypatch, keypair):
        monkeypatch.setenv(GATEWAY_EXPECTED_AUDIENCE_ENV, "adaptix-epcr")
        ctx, sig, kid = _sign_v2()
        # Re-encode with is_founder=true — signature no longer matches.
        doc = json.loads(gateway_keys.b64url_decode(ctx))
        doc["is_founder"] = True
        forged = gateway_keys.b64url_encode(
            json.dumps(doc, separators=(",", ":"), sort_keys=True).encode()
        )
        with pytest.raises(GatewaySignatureError):
            verify_gateway_signature(
                context_b64=forged,
                signature_hex=sig,
                auth_path="gateway-v2",
                key_id=kid,
            )

    def test_expired_context_rejected(self, monkeypatch, keypair):
        monkeypatch.setenv(GATEWAY_EXPECTED_AUDIENCE_ENV, "adaptix-epcr")
        ctx, sig, kid = _sign_v2(now=int(time.time()) - 3600, ttl_seconds=60)
        with pytest.raises(GatewaySignatureError, match="expired"):
            verify_gateway_signature(
                context_b64=ctx,
                signature_hex=sig,
                auth_path="gateway-v2",
                key_id=kid,
            )

    def test_v2_requires_jti(self, monkeypatch, keypair):
        """A v2 context missing jti is refused, even correctly signed.

        ``sign_claims_asymmetric`` always fills jti, so the jti-less context is
        signed by hand here with the same private key.
        """
        monkeypatch.setenv(GATEWAY_EXPECTED_AUDIENCE_ENV, "adaptix-epcr")
        ctx = _claims(jti=None).context_b64()
        kid, private_key = load_signing_key()
        sig = gateway_keys.b64url_encode(private_key.sign(ctx.encode("ascii")))
        with pytest.raises(GatewaySignatureError, match="jti"):
            verify_gateway_signature(
                context_b64=ctx,
                signature_hex=sig,
                auth_path="gateway-v2",
                key_id=kid,
            )


class TestVerifierCompromiseYieldsNothing:
    """The D-053 acceptance property, literally.

    Service A's full configuration is: the gateway PUBLIC keyset, its own
    audience pin, and (during migration) the legacy shared secret. An attacker
    with all of it must not be able to mint a context Service B accepts in
    asymmetric mode.
    """

    def test_public_material_cannot_sign(self, monkeypatch, keypair):
        # Attacker holds everything Service A holds: public JWKS + legacy secret.
        monkeypatch.setenv(GATEWAY_SHARED_SECRET_ENV, SHARED_SECRET)
        # Strip the private key — Service A never had it.
        monkeypatch.delenv(GATEWAY_SIGNING_PRIVATE_KEY_ENV, raising=False)

        # 1. Attacker cannot produce a v2 signature at all without the private key.
        with pytest.raises(GatewayKeyError):
            load_signing_key()

        # Service B: asymmetric-only, pinned to its own audience.
        monkeypatch.setenv(GATEWAY_TRUST_MODE_ENV, "asymmetric")
        monkeypatch.setenv(GATEWAY_EXPECTED_AUDIENCE_ENV, "adaptix-billing")

        # 2. Best remaining move: HMAC-sign a founder context with the shared
        #    secret (exactly what D-053 allowed). Service B refuses it.
        forged_b64, forged_sig = _hmac_context(
            {
                "iss": "adaptix-gateway",
                "aud": "adaptix-billing",
                "user_id": "attacker",
                "tenant_id": "tenant-1",
                "is_founder": True,
                "roles": ["founder"],
                "iat": int(time.time()),
                "exp": int(time.time()) + 60,
                "jti": "forged",
            },
            SHARED_SECRET,
        )
        with pytest.raises(GatewaySignatureError):
            verify_gateway_signature(
                context_b64=forged_b64,
                signature_hex=forged_sig,
                auth_path="gateway-v1",
            )

        # 3. Claiming the forged HMAC blob is "v2" doesn't help either.
        with pytest.raises(GatewaySignatureError):
            verify_gateway_signature(
                context_b64=forged_b64,
                signature_hex=forged_sig,
                auth_path="gateway-v2",
                key_id=KID,
            )

    def test_wrong_private_key_rejected(self, monkeypatch, keypair):
        """A key the attacker generated themselves fails, even reusing the kid."""
        monkeypatch.setenv(GATEWAY_TRUST_MODE_ENV, "asymmetric")
        monkeypatch.setenv(GATEWAY_EXPECTED_AUDIENCE_ENV, "adaptix-epcr")

        attacker_pem, _entry = generate_signing_keypair(KID)  # same kid, wrong key
        monkeypatch.setenv(GATEWAY_SIGNING_PRIVATE_KEY_ENV, attacker_pem)
        ctx, sig, kid = _sign_v2()
        with pytest.raises(GatewaySignatureError, match="signature mismatch"):
            verify_gateway_signature(
                context_b64=ctx,
                signature_hex=sig,
                auth_path="gateway-v2",
                key_id=kid,
            )


class TestNoHeaderDowngrade:
    def test_v2_context_never_verified_by_hmac(self, monkeypatch, keypair):
        """Presenting key_id forces asymmetric verification even in dual mode."""
        monkeypatch.setenv(GATEWAY_SHARED_SECRET_ENV, SHARED_SECRET)
        monkeypatch.setenv(GATEWAY_TRUST_MODE_ENV, "dual")
        monkeypatch.setenv(GATEWAY_EXPECTED_AUDIENCE_ENV, "adaptix-epcr")

        ctx, _sig, kid = _sign_v2()
        # HMAC "signature" over the v2 context using the fleet secret.
        hmac_sig = hmac_mod.new(
            SHARED_SECRET.encode(), ctx.encode(), hashlib.sha256
        ).hexdigest()
        with pytest.raises(GatewaySignatureError):
            verify_gateway_signature(
                context_b64=ctx,
                signature_hex=hmac_sig,
                auth_path="gateway-v2",
                key_id=kid,
            )

    def test_asymmetric_mode_rejects_legacy_v1(self, monkeypatch, keypair):
        monkeypatch.setenv(GATEWAY_TRUST_MODE_ENV, "asymmetric")
        monkeypatch.setenv(GATEWAY_EXPECTED_AUDIENCE_ENV, "adaptix-epcr")
        monkeypatch.setenv(GATEWAY_SHARED_SECRET_ENV, SHARED_SECRET)

        b64, sig = _hmac_context(
            {
                "iss": "adaptix-gateway",
                "aud": "adaptix-epcr",
                "user_id": "u",
                "tenant_id": "t",
                "iat": int(time.time()),
                "exp": int(time.time()) + 60,
            },
            SHARED_SECRET,
        )
        with pytest.raises(GatewaySignatureError, match="rejected"):
            verify_gateway_signature(
                context_b64=b64, signature_hex=sig, auth_path="gateway-v1"
            )


class TestCrossServiceReplay:
    def test_context_for_service_a_rejected_by_service_b(self, monkeypatch, keypair):
        """D-034: a validly signed context for A is refused by B's pin."""
        monkeypatch.setenv(GATEWAY_EXPECTED_AUDIENCE_ENV, "adaptix-billing")
        ctx, sig, kid = _sign_v2(aud="adaptix-epcr")  # minted for EPCR
        with pytest.raises(GatewaySignatureError, match="audience"):
            verify_gateway_signature(
                context_b64=ctx,
                signature_hex=sig,
                auth_path="gateway-v2",
                key_id=kid,
            )

    def test_production_requires_audience_pin(self, monkeypatch, keypair):
        monkeypatch.setenv(ENVIRONMENT_ENV, "production")
        ctx, sig, kid = _sign_v2()
        with pytest.raises(
            GatewayVerifierConfigurationError, match="required in production"
        ):
            verify_gateway_signature(
                context_b64=ctx,
                signature_hex=sig,
                auth_path="gateway-v2",
                key_id=kid,
            )


class TestReadinessGate:
    def test_ready_ok(self, monkeypatch, keypair):
        monkeypatch.setenv(GATEWAY_TRUST_MODE_ENV, "asymmetric")
        monkeypatch.setenv(GATEWAY_EXPECTED_AUDIENCE_ENV, "adaptix-epcr")
        assert_gateway_verifier_ready()  # no raise

    def test_asymmetric_without_keys_fails_startup(self, monkeypatch):
        monkeypatch.setenv(GATEWAY_TRUST_MODE_ENV, "asymmetric")
        monkeypatch.setenv(GATEWAY_EXPECTED_AUDIENCE_ENV, "adaptix-epcr")
        with pytest.raises(GatewayVerifierConfigurationError):
            assert_gateway_verifier_ready()

    def test_production_without_pin_fails_startup(self, monkeypatch, keypair):
        monkeypatch.setenv(ENVIRONMENT_ENV, "production")
        monkeypatch.setenv(GATEWAY_TRUST_MODE_ENV, "asymmetric")
        with pytest.raises(GatewayVerifierConfigurationError):
            assert_gateway_verifier_ready()

    def test_unknown_trust_mode_fails_startup(self, monkeypatch):
        monkeypatch.setenv(GATEWAY_TRUST_MODE_ENV, "sideways")
        with pytest.raises(GatewayVerifierConfigurationError):
            gateway_trust_mode()

    def test_malformed_jwks_is_loud_not_silent(self, monkeypatch):
        monkeypatch.setenv(GATEWAY_PUBLIC_KEYS_ENV, "{not json")
        reset_public_keyset_cache()
        with pytest.raises(GatewayKeyError):
            gateway_keys.load_public_keyset()


class TestRotation:
    def test_previous_and_active_keys_both_verify(self, monkeypatch):
        old_pem, old_entry = generate_signing_keypair(KID)
        new_pem, new_entry = generate_signing_keypair(OTHER_KID)
        monkeypatch.setenv(GATEWAY_PUBLIC_KEYS_ENV, build_jwks([old_entry, new_entry]))
        monkeypatch.setenv(GATEWAY_EXPECTED_AUDIENCE_ENV, "adaptix-epcr")
        reset_public_keyset_cache()

        for pem, kid in ((old_pem, KID), (new_pem, OTHER_KID)):
            monkeypatch.setenv(GATEWAY_SIGNING_PRIVATE_KEY_ENV, pem)
            monkeypatch.setenv(GATEWAY_SIGNING_KEY_ID_ENV, kid)
            ctx, sig, used_kid = _sign_v2()
            assert used_kid == kid
            payload = verify_gateway_signature(
                context_b64=ctx,
                signature_hex=sig,
                auth_path="gateway-v2",
                key_id=used_kid,
            )
            assert payload["user_id"] == "user-1"

    def test_unknown_kid_reports_distribution_fault(self, monkeypatch, keypair):
        monkeypatch.setenv(GATEWAY_EXPECTED_AUDIENCE_ENV, "adaptix-epcr")
        ctx, sig, _kid = _sign_v2()
        with pytest.raises(GatewayVerifierConfigurationError, match="kid"):
            verify_gateway_signature(
                context_b64=ctx,
                signature_hex=sig,
                auth_path="gateway-v2",
                key_id="gw-never-published",
            )
