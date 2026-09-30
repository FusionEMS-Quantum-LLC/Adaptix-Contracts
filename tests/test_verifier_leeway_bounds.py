"""Verifier leeway and clock-skew bounds: no bound value may switch expiry off.

Every Contracts verifier that takes a time tolerance compared it straight
against the clock: the S2S service token and platform token leeway (handed to
PyJWT), the Cognito direct-bearer clock skew in the module entitlement gate
(also handed to PyJWT), the gateway signed-context clock skew and the legacy
gateway identity clock skew. ``inf`` and ``nan`` make those comparisons false,
so a token or context that expired ten years ago verified. ``True`` read as
one second, a float slipped through as a number, a negative value silently
shortened the window, and a str or None escaped as a raw ``TypeError``.

Each is now refused with a plain ``ValueError`` naming the parameter, raised
before anything is decoded or compared. It is a programming or configuration
error, so it is deliberately NOT any verifier's authentication error class
(every one of those is itself a ``ValueError`` subclass, so the exact type is
asserted).

GUARD tests pin the int path: ``0`` and the default still reject the expired
token or context with the verifier's documented error, and a fresh one still
verifies.

Keys and HMAC secrets are generated inside the tests; nothing here is a real
credential.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

import adaptix_contracts.auth.module_entitlement_gate as meg
from adaptix_contracts import gateway_signature as gs
from adaptix_contracts.auth.cognito import AdaptixCognitoConfig
from adaptix_contracts.auth.platform_token import (
    PlatformServiceTokenAuthzError,
    PlatformServiceTokenClaims,
    PlatformServiceTokenError,
    issue_platform_service_token,
    verify_platform_service_token,
    verify_platform_service_token_with_keyset,
)
from adaptix_contracts.auth.service_token import (
    ServiceTokenAuthzError,
    ServiceTokenClaims,
    ServiceTokenError,
    issue_service_token,
    verify_service_token,
    verify_service_token_with_keyset,
)
from adaptix_contracts.environment import ENVIRONMENT_ENV
from adaptix_contracts.gateway_identity import (
    GatewayIdentityError,
    GatewayIdentityExpired,
    sign_legacy_identity,
    verify_legacy_identity,
)
from adaptix_contracts.gateway_keys import GATEWAY_PUBLIC_KEYS_ENV
from adaptix_contracts.gateway_signature import (
    GATEWAY_EXPECTED_AUDIENCE_ENV,
    GATEWAY_SHARED_SECRET_ENV,
    GATEWAY_SIGNATURE_REQUIRE_PATH_ENV,
    GATEWAY_TRUST_MODE_ENV,
    GatewaySignatureError,
    verify_gateway_signature,
    verify_gateway_signature_for_request,
)

# --------------------------------------------------------------------------
# Shared fixtures and helpers
# --------------------------------------------------------------------------

#: Each value an untyped caller (a bound read from an environment variable or
#: a JSON config, say) could hand a verifier in place of an int of seconds.
BAD_BOUNDS = pytest.mark.parametrize(
    "bad",
    [float("inf"), float("nan"), True, 5.0, "5", None, -1],
    ids=["inf", "nan", "true", "integral-float", "str", "none", "negative"],
)

#: GUARD: an explicit int 0, and the default (the parameter omitted).
INT_LEEWAY = pytest.mark.parametrize(
    "bound", [{"leeway_seconds": 0}, {}], ids=["zero", "default"]
)
INT_SKEW = pytest.mark.parametrize(
    "bound", [{"clock_skew_seconds": 0}, {}], ids=["zero", "default"]
)

#: Every authentication/authorization error class these verifiers raise. Each
#: is a ValueError subclass, so a bound error must be checked by exact type.
AUTH_ERRORS: tuple[type[Exception], ...] = (
    ServiceTokenError,
    ServiceTokenAuthzError,
    PlatformServiceTokenError,
    PlatformServiceTokenAuthzError,
    GatewaySignatureError,
    GatewayIdentityError,
)

TEN_YEARS = timedelta(days=3650)
TEN_YEARS_SECONDS = 315_360_000
KID = "leeway-bounds-test-kid"
ISSUER = "adaptix-operations"
AUDIENCE = "adaptix-cad"
SUBJECT = "adaptix-operations"
SCOPE = "scene-dispatch:create"
TENANT = "33333333-3333-3333-3333-333333333333"
PLATFORM_ISSUER = "adaptix-core"
PLATFORM_AUDIENCE = "adaptix-calendar"
PLATFORM_SCOPE = "mail:send-marketing"

COGNITO_POOL_ID = "us-east-1_leewaybounds"
COGNITO_CLIENT_ID = "leeway-bounds-client-id"
COGNITO_ISSUER = f"https://cognito-idp.us-east-1.amazonaws.com/{COGNITO_POOL_ID}"
COGNITO_ENV_VARS = (
    "COGNITO_REGION",
    "COGNITO_USER_POOL_ID",
    "COGNITO_CLIENT_ID",
    "COGNITO_CLIENT_ID_WEB",
    "COGNITO_ISSUER",
    "COGNITO_JWKS_URL",
)

GATEWAY_AUDIENCE = "adaptix-core"
USER_ID = "11111111-1111-1111-1111-111111111111"
GATEWAY_TENANT = "22222222-2222-2222-2222-222222222222"


def assert_programming_error(excinfo: pytest.ExceptionInfo[ValueError]) -> None:
    """The bound error is a plain ValueError, never an auth decision (401/403)."""
    assert type(excinfo.value) is ValueError
    assert not isinstance(excinfo.value, AUTH_ERRORS)


def name_pattern(name: str) -> str:
    return re.escape(name)


@pytest.fixture(scope="module")
def rsa_keypair() -> tuple[str, str]:
    """One RSA-2048 keypair for the module -> (private_pem, public_pem)."""
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


@pytest.fixture
def hmac_secret() -> str:
    return secrets.token_urlsafe(32)


# The verifiers are annotated ``int``; the bound tests stand for the untyped
# caller the runtime guard exists for, so they call through ``Callable[..., T]``
# (the same device tests/test_service_token_actor_mfa_assurance.py uses) rather
# than asking the type checker to accept a float where an int belongs. The
# GUARD fresh-token tests call the typed functions directly.
VERIFY_SERVICE: Callable[..., ServiceTokenClaims] = verify_service_token
VERIFY_SERVICE_KEYSET: Callable[..., ServiceTokenClaims] = (
    verify_service_token_with_keyset
)
VERIFY_PLATFORM: Callable[..., PlatformServiceTokenClaims] = (
    verify_platform_service_token
)
VERIFY_PLATFORM_KEYSET: Callable[..., PlatformServiceTokenClaims] = (
    verify_platform_service_token_with_keyset
)
VERIFY_GATEWAY: Callable[..., dict[str, object]] = verify_gateway_signature
VERIFY_GATEWAY_FOR_REQUEST: Callable[..., dict[str, object]] = (
    verify_gateway_signature_for_request
)
VERIFY_LEGACY: Callable[..., None] = verify_legacy_identity


# --------------------------------------------------------------------------
# adaptix_contracts.auth.service_token
# --------------------------------------------------------------------------


def _service_token(private_pem: str, *, now: datetime | None = None) -> str:
    return issue_service_token(
        private_key_pem=private_pem,
        issuer=ISSUER,
        audience=AUDIENCE,
        subject=SUBJECT,
        tenant_id=TENANT,
        scope=SCOPE,
        kid=KID,
        now=now,
    )


def _expired_service_token(private_pem: str) -> str:
    return _service_token(private_pem, now=datetime.now(UTC) - TEN_YEARS)


def service_verify(token: str, public_pem: str, **bound: object) -> ServiceTokenClaims:
    return VERIFY_SERVICE(
        token,
        public_key_pem=public_pem,
        expected_issuer=ISSUER,
        expected_audience=AUDIENCE,
        expected_subject=SUBJECT,
        required_scope=SCOPE,
        expected_tenant_id=TENANT,
        **bound,
    )


def service_verify_keyset(
    token: str, trusted_keys: dict[str, str], **bound: object
) -> ServiceTokenClaims:
    return VERIFY_SERVICE_KEYSET(
        token,
        trusted_keys=trusted_keys,
        expected_issuer=ISSUER,
        expected_audience=AUDIENCE,
        expected_subject=SUBJECT,
        required_scope=SCOPE,
        expected_tenant_id=TENANT,
        **bound,
    )


@BAD_BOUNDS
def test_verify_service_token_refuses_bad_leeway(
    rsa_keypair: tuple[str, str], bad: object
) -> None:
    private_pem, public_pem = rsa_keypair
    token = _expired_service_token(private_pem)
    with pytest.raises(ValueError, match=name_pattern("leeway_seconds")) as excinfo:
        service_verify(token, public_pem, leeway_seconds=bad)
    assert_programming_error(excinfo)


@BAD_BOUNDS
def test_verify_service_token_with_keyset_refuses_bad_leeway(
    rsa_keypair: tuple[str, str], bad: object
) -> None:
    private_pem, public_pem = rsa_keypair
    token = _expired_service_token(private_pem)
    with pytest.raises(ValueError, match=name_pattern("leeway_seconds")) as excinfo:
        service_verify_keyset(token, {KID: public_pem}, leeway_seconds=bad)
    assert_programming_error(excinfo)


@INT_LEEWAY
def test_guard_service_token_int_leeway_still_rejects_expired(
    rsa_keypair: tuple[str, str], bound: dict[str, int]
) -> None:
    private_pem, public_pem = rsa_keypair
    token = _expired_service_token(private_pem)
    with pytest.raises(ServiceTokenError, match="service token expired") as excinfo:
        service_verify(token, public_pem, **bound)
    assert type(excinfo.value) is ServiceTokenError
    with pytest.raises(ServiceTokenError, match="service token expired") as excinfo:
        service_verify_keyset(token, {KID: public_pem}, **bound)
    assert type(excinfo.value) is ServiceTokenError


def test_guard_service_token_fresh_token_still_verifies(
    rsa_keypair: tuple[str, str],
) -> None:
    private_pem, public_pem = rsa_keypair
    token = _service_token(private_pem)
    claims = verify_service_token(
        token,
        public_key_pem=public_pem,
        expected_issuer=ISSUER,
        expected_audience=AUDIENCE,
        expected_subject=SUBJECT,
        required_scope=SCOPE,
        expected_tenant_id=TENANT,
    )
    assert claims.tenant_id == TENANT
    keyset_claims = verify_service_token_with_keyset(
        token,
        trusted_keys={KID: public_pem},
        expected_issuer=ISSUER,
        expected_audience=AUDIENCE,
        expected_subject=SUBJECT,
        required_scope=SCOPE,
        expected_tenant_id=TENANT,
    )
    assert keyset_claims.jti == claims.jti


# --------------------------------------------------------------------------
# adaptix_contracts.auth.platform_token
# --------------------------------------------------------------------------


def _platform_token(private_pem: str, *, now: datetime | None = None) -> str:
    return issue_platform_service_token(
        private_key_pem=private_pem,
        issuer=PLATFORM_ISSUER,
        audience=PLATFORM_AUDIENCE,
        subject=PLATFORM_ISSUER,
        scope=PLATFORM_SCOPE,
        kid=KID,
        now=now,
    )


def _expired_platform_token(private_pem: str) -> str:
    return _platform_token(private_pem, now=datetime.now(UTC) - TEN_YEARS)


def platform_verify(
    token: str, public_pem: str, **bound: object
) -> PlatformServiceTokenClaims:
    return VERIFY_PLATFORM(
        token,
        public_key_pem=public_pem,
        expected_issuer=PLATFORM_ISSUER,
        expected_audience=PLATFORM_AUDIENCE,
        expected_subject=PLATFORM_ISSUER,
        required_scope=PLATFORM_SCOPE,
        **bound,
    )


def platform_verify_keyset(
    token: str, trusted_keys: dict[str, str], **bound: object
) -> PlatformServiceTokenClaims:
    return VERIFY_PLATFORM_KEYSET(
        token,
        trusted_keys=trusted_keys,
        expected_issuer=PLATFORM_ISSUER,
        expected_audience=PLATFORM_AUDIENCE,
        expected_subject=PLATFORM_ISSUER,
        required_scope=PLATFORM_SCOPE,
        **bound,
    )


@BAD_BOUNDS
def test_verify_platform_service_token_refuses_bad_leeway(
    rsa_keypair: tuple[str, str], bad: object
) -> None:
    private_pem, public_pem = rsa_keypair
    token = _expired_platform_token(private_pem)
    with pytest.raises(ValueError, match=name_pattern("leeway_seconds")) as excinfo:
        platform_verify(token, public_pem, leeway_seconds=bad)
    assert_programming_error(excinfo)


@BAD_BOUNDS
def test_verify_platform_service_token_with_keyset_refuses_bad_leeway(
    rsa_keypair: tuple[str, str], bad: object
) -> None:
    private_pem, public_pem = rsa_keypair
    token = _expired_platform_token(private_pem)
    with pytest.raises(ValueError, match=name_pattern("leeway_seconds")) as excinfo:
        platform_verify_keyset(token, {KID: public_pem}, leeway_seconds=bad)
    assert_programming_error(excinfo)


@INT_LEEWAY
def test_guard_platform_token_int_leeway_still_rejects_expired(
    rsa_keypair: tuple[str, str], bound: dict[str, int]
) -> None:
    private_pem, public_pem = rsa_keypair
    token = _expired_platform_token(private_pem)
    expired = "platform service token expired"
    with pytest.raises(PlatformServiceTokenError, match=expired) as excinfo:
        platform_verify(token, public_pem, **bound)
    assert type(excinfo.value) is PlatformServiceTokenError
    with pytest.raises(PlatformServiceTokenError, match=expired) as excinfo:
        platform_verify_keyset(token, {KID: public_pem}, **bound)
    assert type(excinfo.value) is PlatformServiceTokenError


def test_guard_platform_token_fresh_token_still_verifies(
    rsa_keypair: tuple[str, str],
) -> None:
    private_pem, public_pem = rsa_keypair
    token = _platform_token(private_pem)
    claims = verify_platform_service_token(
        token,
        public_key_pem=public_pem,
        expected_issuer=PLATFORM_ISSUER,
        expected_audience=PLATFORM_AUDIENCE,
        expected_subject=PLATFORM_ISSUER,
        required_scope=PLATFORM_SCOPE,
    )
    assert claims.token_use == "platform-s2s"
    keyset_claims = verify_platform_service_token_with_keyset(
        token,
        trusted_keys={KID: public_pem},
        expected_issuer=PLATFORM_ISSUER,
        expected_audience=PLATFORM_AUDIENCE,
        expected_subject=PLATFORM_ISSUER,
        required_scope=PLATFORM_SCOPE,
    )
    assert keyset_claims.jti == claims.jti


# --------------------------------------------------------------------------
# adaptix_contracts.auth.module_entitlement_gate (Cognito direct bearer)
# --------------------------------------------------------------------------


def _cognito_token(private_pem: str, *, issued_at: int) -> str:
    """An RS256 token shaped like a real Cognito access token."""
    payload: dict[str, object] = {
        "sub": str(uuid4()),
        "iss": COGNITO_ISSUER,
        "token_use": "access",
        "client_id": COGNITO_CLIENT_ID,
        "iat": issued_at,
        "exp": issued_at + 3600,
    }
    return jwt.encode(payload, private_pem, algorithm="RS256")


@pytest.fixture
def cognito_env(
    monkeypatch: pytest.MonkeyPatch, rsa_keypair: tuple[str, str]
) -> Iterator[None]:
    """A configured pool whose JWKS resolves to the generated test key."""
    _, public_pem = rsa_keypair
    monkeypatch.setenv("COGNITO_REGION", "us-east-1")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", COGNITO_POOL_ID)
    monkeypatch.setenv("COGNITO_CLIENT_ID", COGNITO_CLIENT_ID)
    monkeypatch.setenv("COGNITO_ISSUER", COGNITO_ISSUER)
    monkeypatch.setenv("COGNITO_JWKS_URL", f"{COGNITO_ISSUER}/.well-known/jwks.json")

    def _signing_key(token: str, config: AdaptixCognitoConfig) -> str:
        del token, config
        return public_pem

    monkeypatch.setattr(meg, "_cognito_signing_key", _signing_key)
    yield


def _use_cognito_clock_skew(monkeypatch: pytest.MonkeyPatch, skew: object) -> None:
    """Make ``from_env`` return the real env-built config with ``skew`` on it.

    ``from_env`` never sets the skew today, so this stands for any path that
    does (a future environment variable, a caller-built config): the dataclass
    does not validate the field and is mutable.
    """
    config = AdaptixCognitoConfig.from_env()
    monkeypatch.setattr(config, "clock_skew_seconds", skew)

    def _from_env() -> AdaptixCognitoConfig:
        return config

    monkeypatch.setattr(AdaptixCognitoConfig, "from_env", _from_env)


@BAD_BOUNDS
@pytest.mark.usefixtures("cognito_env")
def test_direct_bearer_refuses_bad_cognito_clock_skew(
    monkeypatch: pytest.MonkeyPatch, rsa_keypair: tuple[str, str], bad: object
) -> None:
    private_pem, _ = rsa_keypair
    token = _cognito_token(private_pem, issued_at=int(time.time()) - TEN_YEARS_SECONDS)
    _use_cognito_clock_skew(monkeypatch, bad)
    with pytest.raises(
        ValueError, match=name_pattern("AdaptixCognitoConfig.clock_skew_seconds")
    ) as excinfo:
        meg._verify_direct_bearer_claims(token)
    assert_programming_error(excinfo)


@pytest.mark.parametrize("skew", [0, None], ids=["zero", "default"])
@pytest.mark.usefixtures("cognito_env")
def test_guard_direct_bearer_int_skew_still_rejects_expired(
    monkeypatch: pytest.MonkeyPatch, rsa_keypair: tuple[str, str], skew: int | None
) -> None:
    private_pem, _ = rsa_keypair
    token = _cognito_token(private_pem, issued_at=int(time.time()) - TEN_YEARS_SECONDS)
    if skew is not None:
        _use_cognito_clock_skew(monkeypatch, skew)
    with pytest.raises(HTTPException) as excinfo:
        meg._verify_direct_bearer_claims(token)
    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == {
        "code": "invalid_bearer_token",
        "message": "Authorization bearer token could not be verified.",
    }


@pytest.mark.usefixtures("cognito_env")
def test_guard_direct_bearer_fresh_token_still_verifies(
    rsa_keypair: tuple[str, str],
) -> None:
    private_pem, _ = rsa_keypair
    token = _cognito_token(private_pem, issued_at=int(time.time()))
    claims = meg._verify_direct_bearer_claims(token)
    assert claims["client_id"] == COGNITO_CLIENT_ID


# --------------------------------------------------------------------------
# adaptix_contracts.gateway_signature (signed gateway-v1 context)
# --------------------------------------------------------------------------


@pytest.fixture
def gateway_env(monkeypatch: pytest.MonkeyPatch, hmac_secret: str) -> Iterator[None]:
    """Legacy HMAC trust mode, a pinned audience, non-production, clean cache."""
    monkeypatch.setenv(GATEWAY_SHARED_SECRET_ENV, hmac_secret)
    monkeypatch.setenv(GATEWAY_TRUST_MODE_ENV, "hmac")
    monkeypatch.setenv(GATEWAY_EXPECTED_AUDIENCE_ENV, GATEWAY_AUDIENCE)
    monkeypatch.delenv(GATEWAY_PUBLIC_KEYS_ENV, raising=False)
    monkeypatch.delenv(GATEWAY_SIGNATURE_REQUIRE_PATH_ENV, raising=False)
    monkeypatch.delenv(ENVIRONMENT_ENV, raising=False)
    gs.reset_gateway_replay_cache_for_tests()
    yield
    gs.reset_gateway_replay_cache_for_tests()


def _gateway_context(secret: str, *, issued_at: int) -> tuple[str, str]:
    payload: dict[str, object] = {
        "iss": "adaptix-gateway",
        "aud": GATEWAY_AUDIENCE,
        "user_id": USER_ID,
        "tenant_id": GATEWAY_TENANT,
        "iat": issued_at,
        "exp": issued_at + 60,
        "jti": str(uuid4()),
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ctx = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    sig = hmac.new(secret.encode("utf-8"), ctx.encode("ascii"), hashlib.sha256)
    return ctx, sig.hexdigest()


def _expired_gateway_context(secret: str) -> tuple[str, str]:
    return _gateway_context(secret, issued_at=int(time.time()) - TEN_YEARS_SECONDS)


def _request() -> SimpleNamespace:
    """The request attributes ``verify_gateway_signature_for_request`` reads."""
    return SimpleNamespace(
        method="GET",
        url=SimpleNamespace(path="/api/v1/core/thing"),
        state=SimpleNamespace(),
    )


def gateway_verify(
    ctx: str, sig: str, secret: str, **bound: object
) -> dict[str, object]:
    return VERIFY_GATEWAY(
        context_b64=ctx, signature_hex=sig, shared_secret=secret, **bound
    )


def gateway_verify_for_request(
    request: SimpleNamespace, ctx: str, sig: str, secret: str, **bound: object
) -> dict[str, object]:
    return VERIFY_GATEWAY_FOR_REQUEST(
        request, context_b64=ctx, signature_hex=sig, shared_secret=secret, **bound
    )


@BAD_BOUNDS
@pytest.mark.usefixtures("gateway_env")
def test_verify_gateway_signature_refuses_bad_clock_skew(
    hmac_secret: str, bad: object
) -> None:
    ctx, sig = _expired_gateway_context(hmac_secret)
    with pytest.raises(ValueError, match=name_pattern("clock_skew_seconds")) as excinfo:
        gateway_verify(ctx, sig, hmac_secret, clock_skew_seconds=bad)
    assert_programming_error(excinfo)


@BAD_BOUNDS
@pytest.mark.usefixtures("gateway_env")
def test_verify_gateway_signature_for_request_refuses_bad_clock_skew(
    hmac_secret: str, bad: object
) -> None:
    ctx, sig = _expired_gateway_context(hmac_secret)
    with pytest.raises(ValueError, match=name_pattern("clock_skew_seconds")) as excinfo:
        gateway_verify_for_request(
            _request(), ctx, sig, hmac_secret, clock_skew_seconds=bad
        )
    assert_programming_error(excinfo)


@BAD_BOUNDS
@pytest.mark.usefixtures("gateway_env")
def test_verify_gateway_signature_for_request_refuses_bad_skew_even_when_cached(
    hmac_secret: str, bad: object
) -> None:
    # A request whose assertion was already verified once (with the default
    # skew) must not hand that principal back to a call carrying a bad bound.
    ctx, sig = _gateway_context(hmac_secret, issued_at=int(time.time()))
    request = _request()
    verify_gateway_signature_for_request(
        request, context_b64=ctx, signature_hex=sig, shared_secret=hmac_secret
    )
    with pytest.raises(ValueError, match=name_pattern("clock_skew_seconds")) as excinfo:
        gateway_verify_for_request(
            request, ctx, sig, hmac_secret, clock_skew_seconds=bad
        )
    assert_programming_error(excinfo)


@INT_SKEW
@pytest.mark.usefixtures("gateway_env")
def test_guard_gateway_int_skew_still_rejects_expired(
    hmac_secret: str, bound: dict[str, int]
) -> None:
    ctx, sig = _expired_gateway_context(hmac_secret)
    with pytest.raises(GatewaySignatureError, match="context expired") as excinfo:
        gateway_verify(ctx, sig, hmac_secret, **bound)
    assert type(excinfo.value) is GatewaySignatureError
    with pytest.raises(GatewaySignatureError, match="context expired") as excinfo:
        gateway_verify_for_request(_request(), ctx, sig, hmac_secret, **bound)
    assert type(excinfo.value) is GatewaySignatureError


@pytest.mark.usefixtures("gateway_env")
def test_guard_gateway_fresh_context_still_verifies(hmac_secret: str) -> None:
    ctx, sig = _gateway_context(hmac_secret, issued_at=int(time.time()))
    payload = verify_gateway_signature(
        context_b64=ctx, signature_hex=sig, shared_secret=hmac_secret
    )
    assert payload["tenant_id"] == GATEWAY_TENANT

    ctx2, sig2 = _gateway_context(hmac_secret, issued_at=int(time.time()))
    request_payload = verify_gateway_signature_for_request(
        _request(), context_b64=ctx2, signature_hex=sig2, shared_secret=hmac_secret
    )
    assert request_payload["tenant_id"] == GATEWAY_TENANT


# --------------------------------------------------------------------------
# adaptix_contracts.gateway_identity (legacy identity HMAC)
# --------------------------------------------------------------------------


def legacy_verify(secret: str, *, issued_at: int | None, **bound: object) -> None:
    email = "leeway.bounds@example.test"
    timestamp, signature = sign_legacy_identity(
        user_id=USER_ID,
        tenant_id=GATEWAY_TENANT,
        email=email,
        shared_secret=secret,
        now=issued_at,
    )
    VERIFY_LEGACY(
        tenant_id=GATEWAY_TENANT,
        user_id=USER_ID,
        email=email,
        timestamp=timestamp,
        signature=signature,
        shared_secret=secret,
        **bound,
    )


@BAD_BOUNDS
def test_verify_legacy_identity_refuses_bad_clock_skew(
    hmac_secret: str, bad: object
) -> None:
    issued_at = int(time.time()) - TEN_YEARS_SECONDS
    with pytest.raises(ValueError, match=name_pattern("clock_skew_seconds")) as excinfo:
        legacy_verify(hmac_secret, issued_at=issued_at, clock_skew_seconds=bad)
    assert_programming_error(excinfo)


@INT_SKEW
def test_guard_legacy_identity_int_skew_still_rejects_expired(
    hmac_secret: str, bound: dict[str, int]
) -> None:
    issued_at = int(time.time()) - TEN_YEARS_SECONDS
    with pytest.raises(GatewayIdentityExpired):
        legacy_verify(hmac_secret, issued_at=issued_at, **bound)


def test_guard_legacy_identity_fresh_timestamp_still_verifies(
    hmac_secret: str,
) -> None:
    timestamp, signature = sign_legacy_identity(
        user_id=USER_ID,
        tenant_id=GATEWAY_TENANT,
        email="leeway.bounds@example.test",
        shared_secret=hmac_secret,
    )
    verify_legacy_identity(
        tenant_id=GATEWAY_TENANT,
        user_id=USER_ID,
        email="leeway.bounds@example.test",
        timestamp=timestamp,
        signature=signature,
        shared_secret=hmac_secret,
    )


# --------------------------------------------------------------------------
# The bound is judged before anything is read
# --------------------------------------------------------------------------


def test_bound_is_checked_before_the_token_or_context_is_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Each input below would otherwise fail with the verifier's own auth error
    # (a garbage token, an empty keyset, an empty context, a blank secret, an
    # unconfigured Cognito pool). The bound error must win, because it is the
    # call itself that is wrong.
    inf = float("inf")
    with pytest.raises(ValueError, match="leeway_seconds") as e1:
        service_verify("not-a-jwt", "", leeway_seconds=inf)
    assert_programming_error(e1)
    with pytest.raises(ValueError, match="leeway_seconds") as e2:
        service_verify_keyset("not-a-jwt", {}, leeway_seconds=inf)
    assert_programming_error(e2)
    with pytest.raises(ValueError, match="leeway_seconds") as e3:
        platform_verify("not-a-jwt", "", leeway_seconds=inf)
    assert_programming_error(e3)
    with pytest.raises(ValueError, match="leeway_seconds") as e4:
        platform_verify_keyset("not-a-jwt", {}, leeway_seconds=inf)
    assert_programming_error(e4)
    with pytest.raises(ValueError, match="clock_skew_seconds") as e5:
        gateway_verify("", "", "", clock_skew_seconds=inf)
    assert_programming_error(e5)
    with pytest.raises(ValueError, match="clock_skew_seconds") as e6:
        gateway_verify_for_request(_request(), "", "", "", clock_skew_seconds=inf)
    assert_programming_error(e6)
    with pytest.raises(ValueError, match="clock_skew_seconds") as e7:
        VERIFY_LEGACY(
            tenant_id=GATEWAY_TENANT,
            user_id=USER_ID,
            email="leeway.bounds@example.test",
            timestamp="",
            signature="",
            shared_secret="",
            clock_skew_seconds=inf,
        )
    assert_programming_error(e7)

    for var in COGNITO_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    _use_cognito_clock_skew(monkeypatch, inf)
    with pytest.raises(ValueError, match="clock_skew_seconds") as e8:
        meg._verify_direct_bearer_claims("not-a-jwt")
    assert_programming_error(e8)
