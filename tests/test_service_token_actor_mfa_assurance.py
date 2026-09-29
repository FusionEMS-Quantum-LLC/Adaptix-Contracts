"""Actor MFA assurance on the canonical S2S service token (5.30.0).

Defect D6: Adaptix-EPCR-Service knows, at request time, that the clinician's
gateway-signed context carries a verified second factor, but the RS256 service
token it sends to Adaptix-Narcotics-Service had no claim to carry that fact.
Narcotics' DEA chart routes therefore refused every call (403 mfa_required)
while ``DEA_MFA_ENFORCEMENT_ENABLED`` is on. The gateway context itself cannot
be relayed: it is audience-pinned to adaptix-epcr, bound to method and path,
single-use by jti, and expires after 60 seconds.

These tests prove the additive ``actor_mfa_verified_at`` claim and its one
canonical freshness check:

* the claim round-trips through ``issue_service_token`` and both verifiers,
  and is covered by the RS256 signature;
* tokens without it still verify, and the schema version is unchanged;
* the issuer refuses a malformed, non-positive, future or actor-less value;
* a trusted-signed token carrying a malformed value is a clean 401
  (``ServiceTokenError``), never an escaped ``pydantic.ValidationError``;
* ``require_fresh_actor_mfa_assurance`` enforces exact age and future bounds
  with stable machine-readable reasons, and a non-positive max age can never
  disable it;
* a receiver on an older Contracts pin (no such field) still validates the
  token, so shipping the claim cannot break unupgraded services.

The module is imported as ``st`` and every new name is read from it inside the
test body, so each test fails on its own against a Contracts build that lacks
the claim (a direct ``from ... import`` would turn the whole file into one
collection error instead of per-test evidence).
"""

from __future__ import annotations

import base64
import json
import pickle
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import BaseModel, Field, ValidationError

import adaptix_contracts.auth as auth_pkg
from adaptix_contracts.auth import service_token as st

ISS = "adaptix-epcr"
SUB = "adaptix-epcr"
AUD = "adaptix-narcotics"
SCOPE = "narcotics.chart:write"
TENANT = "tenant-7f3a"
ACTOR = "user-42"
KID = "epcr-s2s-1"

# Fixed, timezone-aware clock for the helper boundary tests.
FIXED_NOW = datetime(2026, 9, 29, 12, 0, 0, tzinfo=UTC)
FIXED_NOW_TS = int(FIXED_NOW.timestamp())


def _keypair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    pub = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return priv, pub


@pytest.fixture(scope="module")
def keys() -> tuple[str, str]:
    return _keypair()


def _issue(
    priv: str,
    *,
    actor_sub: str | None = ACTOR,
    actor_mfa_verified_at: int | None = None,
    now: datetime | None = None,
) -> str:
    return st.issue_service_token(
        private_key_pem=priv,
        issuer=ISS,
        audience=AUD,
        subject=SUB,
        tenant_id=TENANT,
        scope=SCOPE,
        kid=KID,
        actor_sub=actor_sub,
        actor_mfa_verified_at=actor_mfa_verified_at,
        now=now,
    )


def _verify(token: str, pub: str) -> st.ServiceTokenClaims:
    return st.verify_service_token(
        token,
        public_key_pem=pub,
        expected_issuer=ISS,
        expected_audience=AUD,
        expected_subject=SUB,
        required_scope=SCOPE,
        expected_tenant_id=TENANT,
    )


def _verify_keyset(token: str, pub: str) -> st.ServiceTokenClaims:
    return st.verify_service_token_with_keyset(
        token,
        trusted_keys={KID: pub},
        expected_issuer=ISS,
        expected_audience=AUD,
        expected_subject=SUB,
        required_scope=SCOPE,
        expected_tenant_id=TENANT,
    )


def _unverified_payload(token: str) -> dict[str, object]:
    return jwt.decode(token, options={"verify_signature": False})


def _mint_trusted(priv: str, extra: dict[str, object]) -> str:
    """Sign a token directly with the TRUSTED key, bypassing the issuer's guards.

    Models a misbehaving but trusted issuer: the signature is valid, so the
    verifier's own type handling is the only defence.
    """
    now = int(time.time())
    payload: dict[str, object] = {
        "iss": ISS,
        "aud": AUD,
        "sub": SUB,
        "tenant_id": TENANT,
        "scope": SCOPE,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "nbf": now,
        "exp": now + 60,
        "ver": st.SERVICE_TOKEN_VERSION,
        "actor_sub": ACTOR,
        **extra,
    }
    return jwt.encode(payload, priv, algorithm="RS256", headers={"kid": KID})


def _claims(
    *, actor_sub: str | None = ACTOR, actor_mfa_verified_at: int | None
) -> st.ServiceTokenClaims:
    return st.ServiceTokenClaims(
        iss=ISS,
        aud=AUD,
        sub=SUB,
        tenant_id=TENANT,
        scope=SCOPE,
        jti=uuid.uuid4().hex,
        iat=FIXED_NOW_TS,
        exp=FIXED_NOW_TS + 120,
        actor_sub=actor_sub,
        actor_mfa_verified_at=actor_mfa_verified_at,
    )


# --------------------------------------------------------------------------
# Issue / verify round trip
# --------------------------------------------------------------------------


def test_claim_round_trips_through_issue_and_both_verifiers(
    keys: tuple[str, str],
) -> None:
    priv, pub = keys
    verified_at = int(time.time()) - 30
    token = _issue(priv, actor_mfa_verified_at=verified_at)

    raw = _unverified_payload(token)
    assert raw["actor_mfa_verified_at"] == verified_at
    assert type(raw["actor_mfa_verified_at"]) is int

    for claims in (_verify(token, pub), _verify_keyset(token, pub)):
        assert claims.actor_mfa_verified_at == verified_at
        assert claims.actor_sub == ACTOR
        # Additive: the required schema version does not move.
        assert claims.ver == st.SERVICE_TOKEN_VERSION == 1


def test_token_without_claim_still_verifies_and_reads_none(
    keys: tuple[str, str],
) -> None:
    priv, pub = keys
    token = _issue(priv)

    # Omitted, not null, when the issuer has no assurance to state.
    assert "actor_mfa_verified_at" not in _unverified_payload(token)

    for claims in (_verify(token, pub), _verify_keyset(token, pub)):
        assert claims.actor_mfa_verified_at is None


def test_claims_field_is_optional_identity_assurance_only() -> None:
    field = st.ServiceTokenClaims.model_fields["actor_mfa_verified_at"]
    assert field.is_required() is False
    assert field.default is None


def test_trusted_token_with_json_null_claim_reads_as_absent(
    keys: tuple[str, str],
) -> None:
    priv, pub = keys
    token = _mint_trusted(priv, {"actor_mfa_verified_at": None})
    claims = _verify_keyset(token, pub)
    assert claims.actor_mfa_verified_at is None


# --------------------------------------------------------------------------
# Issuer guards
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_value",
    [True, False, 1.5, 1700000000.0, "1700000000", 0, -1],
    ids=["true", "false", "float", "integral-float", "str", "zero", "negative"],
)
def test_issue_refuses_malformed_or_non_positive_value(
    keys: tuple[str, str], bad_value: object
) -> None:
    priv, _pub = keys
    # An untyped caller (for example a value lifted straight out of a JSON
    # context) can hand the issuer anything; the runtime guard must refuse it.
    issue: Callable[..., str] = st.issue_service_token
    with pytest.raises(st.ServiceTokenError):
        issue(
            private_key_pem=priv,
            issuer=ISS,
            audience=AUD,
            subject=SUB,
            tenant_id=TENANT,
            scope=SCOPE,
            kid=KID,
            actor_sub=ACTOR,
            actor_mfa_verified_at=bad_value,
        )


def test_issue_refuses_observation_later_than_issued_at_plus_leeway(
    keys: tuple[str, str],
) -> None:
    priv, _pub = keys
    iat = FIXED_NOW_TS
    with pytest.raises(st.ServiceTokenError):
        _issue(
            priv,
            actor_mfa_verified_at=iat + st.LEEWAY_SECONDS + 1,
            now=FIXED_NOW,
        )

    # Exactly at the clock-skew allowance is accepted.
    token = _issue(priv, actor_mfa_verified_at=iat + st.LEEWAY_SECONDS, now=FIXED_NOW)
    assert _unverified_payload(token)["actor_mfa_verified_at"] == (
        iat + st.LEEWAY_SECONDS
    )


@pytest.mark.parametrize("actor_sub", [None, "", "   "], ids=["none", "empty", "blank"])
def test_issue_refuses_claim_without_actor_sub(
    keys: tuple[str, str], actor_sub: str | None
) -> None:
    priv, _pub = keys
    with pytest.raises(st.ServiceTokenError):
        _issue(
            priv,
            actor_sub=actor_sub,
            actor_mfa_verified_at=int(time.time()) - 10,
        )


# --------------------------------------------------------------------------
# Verifier: malformed trusted claim is a clean 401
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_value",
    [True, False, 1.5, "123", 0, -5, [1], {"t": 1}],
    ids=["true", "false", "float", "str", "zero", "negative", "list", "object"],
)
def test_trusted_token_with_malformed_claim_is_service_token_error(
    keys: tuple[str, str], bad_value: object
) -> None:
    priv, pub = keys
    token = _mint_trusted(priv, {"actor_mfa_verified_at": bad_value})

    # ServiceTokenError (401), never pydantic.ValidationError (an unhandled 500
    # for a caller that correctly catches only this module's errors).
    with pytest.raises(st.ServiceTokenError, match="actor_mfa_verified_at"):
        _verify(token, pub)
    with pytest.raises(st.ServiceTokenError, match="actor_mfa_verified_at"):
        _verify_keyset(token, pub)


def test_changing_claim_after_signing_fails_signature(keys: tuple[str, str]) -> None:
    priv, pub = keys
    stale = int(time.time()) - 3600
    token = _issue(priv, actor_mfa_verified_at=stale)

    header_b64, payload_b64, signature_b64 = token.split(".")
    payload = json.loads(
        base64.urlsafe_b64decode(payload_b64 + "=" * (-len(payload_b64) % 4))
    )
    # Make a stale assurance look fresh without re-signing.
    payload["actor_mfa_verified_at"] = int(time.time())
    forged_payload = (
        base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode())
        .rstrip(b"=")
        .decode("ascii")
    )
    forged = f"{header_b64}.{forged_payload}.{signature_b64}"

    with pytest.raises(st.ServiceTokenError, match="InvalidSignatureError"):
        _verify(forged, pub)
    with pytest.raises(st.ServiceTokenError, match="InvalidSignatureError"):
        _verify_keyset(forged, pub)
    # The untouched token still verifies and still carries the stale value.
    assert _verify_keyset(token, pub).actor_mfa_verified_at == stale


# --------------------------------------------------------------------------
# require_fresh_actor_mfa_assurance
# --------------------------------------------------------------------------


def test_helper_passes_at_exact_max_age() -> None:
    max_age = 300
    claims = _claims(actor_mfa_verified_at=FIXED_NOW_TS - max_age)
    assert (
        st.require_fresh_actor_mfa_assurance(
            claims, max_age_seconds=max_age, now=FIXED_NOW
        )
        == FIXED_NOW_TS - max_age
    )


def test_helper_rejects_one_second_past_max_age_as_stale() -> None:
    max_age = 300
    claims = _claims(actor_mfa_verified_at=FIXED_NOW_TS - max_age - 1)
    with pytest.raises(st.ServiceTokenMfaAssuranceError) as excinfo:
        st.require_fresh_actor_mfa_assurance(
            claims, max_age_seconds=max_age, now=FIXED_NOW
        )
    assert excinfo.value.reason == "actor_mfa_assurance_stale"
    # A 403, catchable by every existing ServiceTokenAuthzError handler.
    assert isinstance(excinfo.value, st.ServiceTokenAuthzError)
    assert not isinstance(excinfo.value, st.ServiceTokenError)
    assert str(excinfo.value).startswith("actor_mfa_assurance_stale")


def test_helper_passes_exactly_at_future_leeway() -> None:
    claims = _claims(actor_mfa_verified_at=FIXED_NOW_TS + st.LEEWAY_SECONDS)
    assert (
        st.require_fresh_actor_mfa_assurance(claims, max_age_seconds=300, now=FIXED_NOW)
        == FIXED_NOW_TS + st.LEEWAY_SECONDS
    )


def test_helper_rejects_future_beyond_leeway() -> None:
    claims = _claims(actor_mfa_verified_at=FIXED_NOW_TS + st.LEEWAY_SECONDS + 1)
    with pytest.raises(st.ServiceTokenMfaAssuranceError) as excinfo:
        st.require_fresh_actor_mfa_assurance(claims, max_age_seconds=300, now=FIXED_NOW)
    assert excinfo.value.reason == "actor_mfa_assurance_in_future"


def test_helper_honours_explicit_leeway() -> None:
    claims = _claims(actor_mfa_verified_at=FIXED_NOW_TS + 1)
    with pytest.raises(st.ServiceTokenMfaAssuranceError) as excinfo:
        st.require_fresh_actor_mfa_assurance(
            claims, max_age_seconds=300, now=FIXED_NOW, leeway_seconds=0
        )
    assert excinfo.value.reason == "actor_mfa_assurance_in_future"


def test_helper_rejects_absent_claim_as_missing() -> None:
    claims = _claims(actor_mfa_verified_at=None)
    with pytest.raises(st.ServiceTokenMfaAssuranceError) as excinfo:
        st.require_fresh_actor_mfa_assurance(claims, max_age_seconds=300, now=FIXED_NOW)
    assert excinfo.value.reason == "actor_mfa_assurance_missing"


@pytest.mark.parametrize("actor_sub", [None, "", "   "], ids=["none", "empty", "blank"])
def test_helper_rejects_empty_actor_sub_as_missing(actor_sub: str | None) -> None:
    claims = _claims(actor_sub=actor_sub, actor_mfa_verified_at=FIXED_NOW_TS - 1)
    with pytest.raises(st.ServiceTokenMfaAssuranceError) as excinfo:
        st.require_fresh_actor_mfa_assurance(claims, max_age_seconds=300, now=FIXED_NOW)
    assert excinfo.value.reason == "actor_mfa_assurance_missing"


def test_helper_rejects_unvalidated_bool_as_missing() -> None:
    # Pydantic does not validate attribute assignment on this model, so a
    # consumer can put a bool on it; True must never read as epoch second 1.
    claims = _claims(actor_mfa_verified_at=FIXED_NOW_TS - 1)
    claims.actor_mfa_verified_at = True
    with pytest.raises(st.ServiceTokenMfaAssuranceError) as excinfo:
        st.require_fresh_actor_mfa_assurance(claims, max_age_seconds=300, now=FIXED_NOW)
    assert excinfo.value.reason == "actor_mfa_assurance_missing"


@pytest.mark.parametrize("max_age", [0, -1, -300])
def test_helper_non_positive_max_age_is_a_programming_error(max_age: int) -> None:
    claims = _claims(actor_mfa_verified_at=FIXED_NOW_TS - 1)
    with pytest.raises(ValueError, match="max_age_seconds") as excinfo:
        st.require_fresh_actor_mfa_assurance(
            claims, max_age_seconds=max_age, now=FIXED_NOW
        )
    # A plain programming error, never mistaken for an authz decision.
    assert not isinstance(excinfo.value, st.ServiceTokenAuthzError)


def test_helper_negative_leeway_is_a_programming_error() -> None:
    claims = _claims(actor_mfa_verified_at=FIXED_NOW_TS - 1)
    with pytest.raises(ValueError, match="leeway_seconds"):
        st.require_fresh_actor_mfa_assurance(
            claims, max_age_seconds=300, now=FIXED_NOW, leeway_seconds=-1
        )


def test_helper_rejects_naive_now() -> None:
    # A naive datetime's .timestamp() is read as host-local time; on a host
    # east of UTC that would make a stale assurance look fresh.
    claims = _claims(actor_mfa_verified_at=FIXED_NOW_TS - 1)
    with pytest.raises(ValueError, match="timezone-aware"):
        st.require_fresh_actor_mfa_assurance(
            claims, max_age_seconds=300, now=FIXED_NOW.replace(tzinfo=None)
        )


def test_helper_accepts_non_utc_aware_now() -> None:
    # The same instant expressed at a UTC-5 offset gives the same decision.
    claims = _claims(actor_mfa_verified_at=FIXED_NOW_TS - 60)
    offset_now = FIXED_NOW.astimezone(timezone(timedelta(hours=-5)))
    assert (
        st.require_fresh_actor_mfa_assurance(claims, max_age_seconds=60, now=offset_now)
        == FIXED_NOW_TS - 60
    )


def test_helper_default_clock_end_to_end(keys: tuple[str, str]) -> None:
    priv, pub = keys
    verified_at = int(time.time()) - 5
    claims = _verify_keyset(_issue(priv, actor_mfa_verified_at=verified_at), pub)
    assert (
        st.require_fresh_actor_mfa_assurance(claims, max_age_seconds=300) == verified_at
    )

    old = int((datetime.now(UTC) - timedelta(hours=1)).timestamp())
    stale_claims = _verify_keyset(_issue(priv, actor_mfa_verified_at=old), pub)
    with pytest.raises(st.ServiceTokenMfaAssuranceError) as excinfo:
        st.require_fresh_actor_mfa_assurance(stale_claims, max_age_seconds=300)
    assert excinfo.value.reason == "actor_mfa_assurance_stale"


def test_assurance_error_survives_pickling() -> None:
    err = st.ServiceTokenMfaAssuranceError("actor_mfa_assurance_stale", "too old")
    clone = pickle.loads(pickle.dumps(err))
    assert type(clone) is st.ServiceTokenMfaAssuranceError
    assert clone.reason == "actor_mfa_assurance_stale"
    assert clone.detail == "too old"
    assert str(clone) == str(err)


def test_public_exports() -> None:
    assert (
        auth_pkg.require_fresh_actor_mfa_assurance
        is st.require_fresh_actor_mfa_assurance
    )
    assert auth_pkg.ServiceTokenMfaAssuranceError is st.ServiceTokenMfaAssuranceError
    for name in (
        "require_fresh_actor_mfa_assurance",
        "ServiceTokenMfaAssuranceError",
        "ActorMfaAssuranceReason",
    ):
        assert name in auth_pkg.__all__


# --------------------------------------------------------------------------
# Older receivers
# --------------------------------------------------------------------------


class _ServiceTokenClaimsV529(BaseModel):
    """ServiceTokenClaims exactly as adaptix-contracts 5.29.0 shipped it.

    Same fields, same default (ignore-extra) model config, and no
    ``actor_mfa_verified_at``: a receiver still pinned to 5.29.0 or earlier.
    """

    iss: str = Field(...)
    aud: str = Field(...)
    sub: str = Field(...)
    tenant_id: str = Field(...)
    scope: str = Field(...)
    jti: str = Field(...)
    iat: int = Field(...)
    exp: int = Field(...)
    nbf: int | None = Field(default=None)
    actor_sub: str | None = Field(default=None)
    correlation_id: str | None = Field(default=None)
    scene_request_id: str | None = Field(default=None)
    workspace_key: str | None = Field(default=None)
    delegation_grant_id: str | None = Field(default=None)
    tool_call_id: str | None = Field(default=None)
    ver: int = Field(default=1)


def test_older_receiver_ignores_the_claim(keys: tuple[str, str]) -> None:
    priv, pub = keys
    # The copy is honest: it is the current claim set minus the new field.
    assert set(_ServiceTokenClaimsV529.model_fields) == (
        set(st.ServiceTokenClaims.model_fields) - {"actor_mfa_verified_at"}
    )

    token = _issue(priv, actor_mfa_verified_at=int(time.time()) - 30)
    raw = jwt.decode(
        token,
        pub,
        algorithms=["RS256"],
        audience=AUD,
        issuer=ISS,
        options={"require": ["exp", "iat", "aud", "iss", "sub", "jti"]},
    )
    old = _ServiceTokenClaimsV529(**raw)
    assert old.tenant_id == TENANT
    assert old.actor_sub == ACTOR
    assert "actor_mfa_verified_at" not in old.model_dump()


# --------------------------------------------------------------------------
# require_fresh_actor_mfa_assurance: the bounds themselves must be ints
# --------------------------------------------------------------------------
#
# ``max_age_seconds <= 0`` and ``leeway_seconds < 0`` are both False for
# float('inf') and float('nan'), and so is every freshness comparison against
# them, so a float bound switched the check off. ``True`` passed as 1 and a
# str or None escaped as a raw TypeError. Each is now the documented
# programming-error ValueError, raised before any claim is judged.


@pytest.mark.parametrize(
    "bad_max_age",
    [float("inf"), float("nan"), True, 300.0, 300.5, "300", None],
    ids=["inf", "nan", "true", "integral-float", "float", "str", "none"],
)
def test_helper_refuses_non_int_max_age_as_programming_error(
    bad_max_age: object,
) -> None:
    # 10**8 seconds (about three years) old: stale under any int max age.
    claims = _claims(actor_mfa_verified_at=FIXED_NOW_TS - 10**8)
    # An untyped caller (for example a max age read straight out of an
    # environment variable or a JSON config) can hand the helper anything; the
    # runtime guard must refuse it rather than let the comparison decide.
    require: Callable[..., int] = st.require_fresh_actor_mfa_assurance
    with pytest.raises(ValueError, match="max_age_seconds") as excinfo:
        require(claims, max_age_seconds=bad_max_age, now=FIXED_NOW)
    # A plain programming error, never mistaken for an authz decision (the
    # 403 error is itself a ValueError subclass, so this is checked by type).
    assert not isinstance(excinfo.value, st.ServiceTokenAuthzError)


@pytest.mark.parametrize(
    "bad_leeway",
    [float("inf"), float("nan"), True, 5.0, "5", None],
    ids=["inf", "nan", "true", "integral-float", "str", "none"],
)
def test_helper_refuses_non_int_leeway_as_programming_error(
    bad_leeway: object,
) -> None:
    # 10**8 seconds in the future: beyond any int leeway.
    claims = _claims(actor_mfa_verified_at=FIXED_NOW_TS + 10**8)
    require: Callable[..., int] = st.require_fresh_actor_mfa_assurance
    with pytest.raises(ValueError, match="leeway_seconds") as excinfo:
        require(claims, max_age_seconds=300, now=FIXED_NOW, leeway_seconds=bad_leeway)
    assert not isinstance(excinfo.value, st.ServiceTokenAuthzError)


def test_helper_int_bounds_still_decide_exactly() -> None:
    # The int path is unchanged: the same stale and future claims used above
    # are refused with their machine-readable reasons, not a ValueError.
    stale = _claims(actor_mfa_verified_at=FIXED_NOW_TS - 10**8)
    with pytest.raises(st.ServiceTokenMfaAssuranceError) as excinfo:
        st.require_fresh_actor_mfa_assurance(stale, max_age_seconds=300, now=FIXED_NOW)
    assert excinfo.value.reason == "actor_mfa_assurance_stale"

    future = _claims(actor_mfa_verified_at=FIXED_NOW_TS + 10**8)
    with pytest.raises(st.ServiceTokenMfaAssuranceError) as excinfo:
        st.require_fresh_actor_mfa_assurance(
            future, max_age_seconds=300, now=FIXED_NOW, leeway_seconds=5
        )
    assert excinfo.value.reason == "actor_mfa_assurance_in_future"


# --------------------------------------------------------------------------
# ServiceTokenClaims.actor_mfa_verified_at is strict
# --------------------------------------------------------------------------


def _claims_payload(actor_mfa_verified_at: object) -> dict[str, object]:
    return {
        "iss": ISS,
        "aud": AUD,
        "sub": SUB,
        "tenant_id": TENANT,
        "scope": SCOPE,
        "jti": uuid.uuid4().hex,
        "iat": FIXED_NOW_TS,
        "exp": FIXED_NOW_TS + 120,
        "actor_sub": ACTOR,
        "actor_mfa_verified_at": actor_mfa_verified_at,
    }


def test_claims_model_accepts_int_actor_mfa_verified_at() -> None:
    # Positive control: the payload below is otherwise valid, so a refusal of
    # the lax values can only come from the actor_mfa_verified_at field.
    claims = st.ServiceTokenClaims.model_validate(_claims_payload(1700000000))
    assert claims.actor_mfa_verified_at == 1700000000


@pytest.mark.parametrize(
    "lax_value",
    ["1700000000", True, 1700000000.0],
    ids=["numeric-str", "true", "integral-float"],
)
def test_claims_model_refuses_lax_actor_mfa_verified_at(lax_value: object) -> None:
    # Pydantic's lax int mode would coerce each of these into a positive epoch
    # second; ``strict=True`` on the field is the only thing refusing them.
    with pytest.raises(ValidationError) as excinfo:
        st.ServiceTokenClaims.model_validate(_claims_payload(lax_value))
    assert [error["loc"] for error in excinfo.value.errors()] == [
        ("actor_mfa_verified_at",)
    ]
