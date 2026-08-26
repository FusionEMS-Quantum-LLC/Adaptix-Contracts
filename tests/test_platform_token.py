"""Tests for the canonical Adaptix TENANT-LESS platform S2S token.

Covers the full issue/verify contract, the required auth truth table (mirrors
test_service_token.py's), the keyset verifier (mirrors
test_service_token_keyset.py's kid/algorithm/rotation coverage), replay
behavior (default TTL-only vs. the optional reject_replayed_jti hook), and
concurrent verification.

The cross-boundary invariant (a platform token rejected by the tenant-bound
verifier and vice versa) lives in test_platform_token_tenant_boundary.py.
"""

from __future__ import annotations

import threading
import time
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from adaptix_contracts.auth.platform_token import (
    LEEWAY_SECONDS,
    PLATFORM_TOKEN_VERSION,
    TOKEN_USE,
    PlatformServiceTokenAuthzError,
    PlatformServiceTokenClaims,
    PlatformServiceTokenError,
    issue_platform_service_token,
    verify_platform_service_token,
    verify_platform_service_token_with_keyset,
)

_ISS = "adaptix-core"
_SUB = "adaptix-core"
_AUD = "adaptix-calendar"
_SCOPE = "mail:send-marketing"


def _keypair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    pub = (
        key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return priv, pub


@pytest.fixture(scope="module")
def keys() -> tuple[str, str]:
    return _keypair()


def _issue(priv: str, **over) -> str:
    kw = dict(
        private_key_pem=priv,
        issuer=_ISS,
        audience=_AUD,
        subject=_SUB,
        scope=_SCOPE,
        correlation_id="corr-1",
    )
    kw.update(over)
    return issue_platform_service_token(**kw)


def _verify(token: str, pub: str, **over) -> PlatformServiceTokenClaims:
    kw = dict(
        public_key_pem=pub,
        expected_issuer=_ISS,
        expected_audience=_AUD,
        expected_subject=_SUB,
        required_scope=_SCOPE,
    )
    kw.update(over)
    return verify_platform_service_token(token, **kw)


# --------------------------------------------------------------------------
# Issue/verify roundtrip + auth truth table (mirrors test_service_token.py)
# --------------------------------------------------------------------------


def test_valid_roundtrip(keys):
    priv, pub = keys
    claims = _verify(_issue(priv), pub)
    assert claims.token_use == TOKEN_USE
    assert claims.aud == _AUD
    assert claims.sub == _SUB
    assert claims.scope == _SCOPE
    assert claims.ver == PLATFORM_TOKEN_VERSION
    assert claims.jti
    assert claims.correlation_id == "corr-1"
    # No tenant_id attribute exists on this model at all.
    assert not hasattr(claims, "tenant_id")


def test_claims_model_has_no_tenant_id_field():
    # Structural assertion on the schema itself, independent of any token.
    assert "tenant_id" not in PlatformServiceTokenClaims.model_fields


def test_missing_token_401(keys):
    _, pub = keys
    with pytest.raises(PlatformServiceTokenError):
        _verify("", pub)


def test_invalid_signature_401(keys):
    priv, _ = keys
    _, other_pub = _keypair()
    with pytest.raises(PlatformServiceTokenError):
        _verify(_issue(priv), other_pub)


def test_expired_401(keys):
    priv, pub = keys
    past = datetime.now(UTC) - timedelta(minutes=10)
    token = _issue(priv, ttl_seconds=1, now=past)
    with pytest.raises(PlatformServiceTokenError):
        _verify(token, pub)


def test_not_yet_valid_401(keys):
    priv, pub = keys
    future = datetime.now(UTC) + timedelta(minutes=10)
    token = _issue(priv, now=future)
    with pytest.raises(PlatformServiceTokenError):
        _verify(token, pub)


def test_untrusted_issuer_401(keys):
    priv, pub = keys
    token = _issue(priv, issuer="evil-issuer")
    with pytest.raises(PlatformServiceTokenError):
        _verify(token, pub)


def test_unsupported_version_401(keys):
    priv, pub = keys
    now = int(datetime.now(UTC).timestamp())
    payload = {
        "token_use": TOKEN_USE,
        "iss": _ISS,
        "aud": _AUD,
        "sub": _SUB,
        "scope": _SCOPE,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "nbf": now,
        "exp": now + 120,
        "ver": 999,
    }
    token = jwt.encode(payload, priv, algorithm="RS256")
    with pytest.raises(PlatformServiceTokenError):
        _verify(token, pub)


def test_missing_token_use_401(keys):
    # Structurally valid, correctly signed, but not shaped like a platform
    # token at all (no token_use claim) -- e.g. a hand-crafted or foreign
    # payload. Must fail closed with PlatformServiceTokenError, not silently
    # validate.
    priv, pub = keys
    now = int(datetime.now(UTC).timestamp())
    payload = {
        "iss": _ISS,
        "aud": _AUD,
        "sub": _SUB,
        "scope": _SCOPE,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "nbf": now,
        "exp": now + 120,
        "ver": PLATFORM_TOKEN_VERSION,
    }
    token = jwt.encode(payload, priv, algorithm="RS256")
    with pytest.raises(PlatformServiceTokenError, match="not a platform service token"):
        _verify(token, pub)


def test_wrong_token_use_401(keys):
    priv, pub = keys
    now = int(datetime.now(UTC).timestamp())
    payload = {
        "token_use": "something-else",
        "iss": _ISS,
        "aud": _AUD,
        "sub": _SUB,
        "scope": _SCOPE,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "nbf": now,
        "exp": now + 120,
        "ver": PLATFORM_TOKEN_VERSION,
    }
    token = jwt.encode(payload, priv, algorithm="RS256")
    with pytest.raises(PlatformServiceTokenError, match="not a platform service token"):
        _verify(token, pub)


def test_stray_tenant_id_claim_rejected_401(keys):
    # Defense in depth: even though issue_platform_service_token can never
    # produce this (no tenant_id parameter exists), a hand-crafted payload
    # that smuggles a tenant_id in alongside a valid token_use must still be
    # refused outright rather than silently accepted with the claim dropped.
    priv, pub = keys
    now = int(datetime.now(UTC).timestamp())
    payload = {
        "token_use": TOKEN_USE,
        "iss": _ISS,
        "aud": _AUD,
        "sub": _SUB,
        "scope": _SCOPE,
        "tenant_id": str(uuid.uuid4()),
        "jti": uuid.uuid4().hex,
        "iat": now,
        "nbf": now,
        "exp": now + 120,
        "ver": PLATFORM_TOKEN_VERSION,
    }
    token = jwt.encode(payload, priv, algorithm="RS256")
    with pytest.raises(PlatformServiceTokenError, match="tenant_id"):
        _verify(token, pub)


def test_wrong_audience_403(keys):
    priv, pub = keys
    token = _issue(priv, audience="adaptix-somewhereelse")
    with pytest.raises(PlatformServiceTokenAuthzError):
        _verify(token, pub)


def test_wrong_subject_403(keys):
    priv, pub = keys
    token = _issue(priv, subject="adaptix-somethingelse")
    with pytest.raises(PlatformServiceTokenAuthzError):
        _verify(token, pub)


def test_missing_scope_403(keys):
    priv, pub = keys
    token = _issue(priv, scope="mail:read")
    with pytest.raises(PlatformServiceTokenAuthzError):
        _verify(token, pub)  # verifier requires mail:send-marketing


def test_issue_requires_identity_inputs(keys):
    priv, _ = keys
    with pytest.raises(PlatformServiceTokenError):
        issue_platform_service_token(
            private_key_pem=priv,
            issuer=_ISS,
            audience=_AUD,
            subject=_SUB,
            scope="",
        )


def test_leeway_seconds_constant_matches_service_token_default():
    assert LEEWAY_SECONDS == 5


# --------------------------------------------------------------------------
# Keyset verifier (mirrors test_service_token_keyset.py)
# --------------------------------------------------------------------------


def _issue_kid(priv: str, kid: str, *, audience: str = _AUD) -> str:
    return issue_platform_service_token(
        private_key_pem=priv,
        issuer=_ISS,
        subject=_SUB,
        audience=audience,
        scope=_SCOPE,
        kid=kid,
    )


def _verify_keyset(token: str, keys_map: dict[str, str], **over):
    kw = dict(
        trusted_keys=keys_map,
        expected_issuer=_ISS,
        expected_audience=_AUD,
        expected_subject=_SUB,
        required_scope=_SCOPE,
    )
    kw.update(over)
    return verify_platform_service_token_with_keyset(token, **kw)


def test_valid_kid_resolves_and_verifies():
    priv, pub = _keypair()
    claims = _verify_keyset(_issue_kid(priv, "k1"), {"k1": pub})
    assert claims.token_use == TOKEN_USE
    assert claims.aud == _AUD


def test_rotation_previous_key_still_verifies():
    p1, pub1 = _keypair()
    p2, pub2 = _keypair()
    token_k1 = _issue_kid(p1, "k1")
    claims = _verify_keyset(token_k1, {"k2": pub2, "k1": pub1})
    assert claims.token_use == TOKEN_USE
    assert _verify_keyset(_issue_kid(p2, "k2"), {"k2": pub2, "k1": pub1})


def test_missing_kid_rejected():
    priv, pub = _keypair()
    token = issue_platform_service_token(
        private_key_pem=priv,
        issuer=_ISS,
        subject=_SUB,
        audience=_AUD,
        scope=_SCOPE,
    )  # no kid -> no kid header
    with pytest.raises(PlatformServiceTokenError) as exc:
        _verify_keyset(token, {"k1": pub})
    assert "KID_MISSING" in str(exc.value)


def test_unknown_kid_rejected():
    priv, pub = _keypair()
    token = _issue_kid(priv, "k9")  # kid not in keyset
    with pytest.raises(PlatformServiceTokenError) as exc:
        _verify_keyset(token, {"k1": pub})
    assert "KID_UNKNOWN" in str(exc.value)


def test_wrong_algorithm_rejected():
    _, pub = _keypair()
    token = jwt.encode(
        {
            "token_use": TOKEN_USE,
            "iss": _ISS,
            "sub": _SUB,
            "aud": _AUD,
            "scope": _SCOPE,
            "jti": uuid.uuid4().hex,
            "iat": 1,
            "exp": 9999999999,
            "ver": PLATFORM_TOKEN_VERSION,
        },
        "shared-secret-that-is-long-enough-for-hs256",
        algorithm="HS256",
        headers={"kid": "k1"},
    )
    with pytest.raises(PlatformServiceTokenError) as exc:
        _verify_keyset(token, {"k1": pub})
    assert "ALGORITHM_REJECTED" in str(exc.value)


def test_empty_keyset_rejected():
    priv, _ = _keypair()
    with pytest.raises(PlatformServiceTokenError) as exc:
        _verify_keyset(_issue_kid(priv, "k1"), {})
    assert "KEYSET_EMPTY" in str(exc.value)


def test_bad_signature_kid_present_rejected():
    priv, _ = _keypair()
    _, other_pub = _keypair()
    with pytest.raises(PlatformServiceTokenError):
        _verify_keyset(_issue_kid(priv, "k1"), {"k1": other_pub})


def test_wrong_audience_is_authz_403():
    priv, pub = _keypair()
    token = _issue_kid(priv, "k1", audience="adaptix-somewhereelse")
    with pytest.raises(PlatformServiceTokenAuthzError):
        _verify_keyset(token, {"k1": pub})


def test_error_codes_are_platform_namespaced_not_service_namespaced():
    # The whole point of sharing _s2s_keyset via a code_prefix parameter
    # (rather than a hardcoded string) is that the two verifiers' error
    # codes never collide -- a monitoring rule keyed on "SERVICE_TOKEN_"
    # must never fire for a platform-token failure and vice versa.
    priv, pub = _keypair()
    token = issue_platform_service_token(
        private_key_pem=priv, issuer=_ISS, subject=_SUB, audience=_AUD, scope=_SCOPE
    )
    with pytest.raises(PlatformServiceTokenError) as exc:
        _verify_keyset(token, {"k1": pub})
    message = str(exc.value)
    assert message.startswith("PLATFORM_TOKEN_")
    assert not message.startswith("SERVICE_TOKEN_")


# --------------------------------------------------------------------------
# Replay behavior: default TTL-only vs. optional reject_replayed_jti hook
# --------------------------------------------------------------------------


def test_replay_within_ttl_succeeds_by_default():
    """Pins the fleet-convention default: no jti tracking, TTL-bounded only."""
    priv, pub = _keypair()
    token = _issue(priv)
    first = _verify(token, pub)
    second = _verify(token, pub)  # same token, same jti, verified again
    assert first.jti == second.jti


def test_replay_rejected_when_hook_enabled():
    priv, pub = _keypair()
    token = _issue(priv)

    seen: set[str] = set()

    def reject_replayed_jti(jti: str) -> bool:
        if jti in seen:
            return True
        seen.add(jti)
        return False

    first = _verify(token, pub, reject_replayed_jti=reject_replayed_jti)
    assert first.jti
    with pytest.raises(PlatformServiceTokenError, match="replay"):
        _verify(token, pub, reject_replayed_jti=reject_replayed_jti)


def test_replay_hook_does_not_affect_distinct_tokens():
    priv, pub = _keypair()
    token_a = _issue(priv)
    token_b = _issue(priv)
    assert token_a != token_b

    seen: set[str] = set()

    def reject_replayed_jti(jti: str) -> bool:
        if jti in seen:
            return True
        seen.add(jti)
        return False

    claims_a = _verify(token_a, pub, reject_replayed_jti=reject_replayed_jti)
    claims_b = _verify(token_b, pub, reject_replayed_jti=reject_replayed_jti)
    assert claims_a.jti != claims_b.jti


def test_replay_hook_requires_jti_present():
    # A token missing jti entirely can't be replay-checked meaningfully;
    # must fail closed rather than silently treating "no jti" as "not seen".
    priv, pub = _keypair()
    now = int(datetime.now(UTC).timestamp())
    payload = {
        "token_use": TOKEN_USE,
        "iss": _ISS,
        "aud": _AUD,
        "sub": _SUB,
        "scope": _SCOPE,
        "iat": now,
        "nbf": now,
        "exp": now + 120,
        "ver": PLATFORM_TOKEN_VERSION,
        # no jti
    }
    token = jwt.encode(payload, priv, algorithm="RS256")

    def reject_replayed_jti(jti: str) -> bool:
        return False

    with pytest.raises(PlatformServiceTokenError, match="jti"):
        _verify(token, pub, reject_replayed_jti=reject_replayed_jti)


# --------------------------------------------------------------------------
# Concurrent verification
# --------------------------------------------------------------------------


def test_concurrent_verification_of_distinct_valid_tokens():
    """Many threads verifying many DIFFERENT valid tokens concurrently must
    all succeed independently -- proves the verify path has no accidental
    shared mutable state / is safe to call from a thread pool."""
    priv, pub = _keypair()
    tokens = [_issue(priv) for _ in range(32)]
    results: list[PlatformServiceTokenClaims | Exception] = [None] * len(tokens)  # type: ignore[list-item]

    def worker(i: int) -> None:
        try:
            results[i] = _verify(tokens[i], pub)
        except Exception as exc:  # noqa: BLE001 - captured for assertion below
            results[i] = exc

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(len(tokens))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert all(isinstance(r, PlatformServiceTokenClaims) for r in results), results
    jtis = {r.jti for r in results}  # type: ignore[union-attr]
    assert len(jtis) == len(tokens)  # every token had a distinct jti, all verified


def test_verify_platform_service_token_concurrent_replay_dedupe_is_race_safe():
    """The SAME token, verified from many threads at once, with an ATOMIC
    dedupe callback (a lock-protected check-and-set, standing in for a real
    atomic store like Redis SETNX): exactly one verification must succeed
    and every other must be rejected as a replay. This is the property the
    docstring on verify_platform_service_token promises an atomic callback
    buys you."""
    priv, pub = _keypair()
    token = _issue(priv)

    seen: set[str] = set()
    lock = threading.Lock()

    def atomic_reject_replayed_jti(jti: str) -> bool:
        with lock:
            if jti in seen:
                return True
            seen.add(jti)
            return False

    outcomes: list[str] = []
    outcomes_lock = threading.Lock()

    def worker() -> None:
        try:
            _verify(token, pub, reject_replayed_jti=atomic_reject_replayed_jti)
            outcome = "accepted"
        except PlatformServiceTokenError:
            outcome = "rejected"
        with outcomes_lock:
            outcomes.append(outcome)

    threads = [threading.Thread(target=worker) for _ in range(25)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert len(outcomes) == 25
    assert outcomes.count("accepted") == 1
    assert outcomes.count("rejected") == 24


def test_verify_platform_service_token_naive_non_atomic_dedupe_is_not_race_safe():
    """Demonstrates the exact race the docstring warns about: a
    read-then-write (non-atomic) callback can let a replayed token through
    more than once under concurrency. This test pins the FAILURE MODE of a
    non-atomic callback (not a feature of this module) so the atomicity
    requirement in the docs is verifiably real and not just a claim.

    The artificial sleep between "read" and "write" deterministically widens
    the race window (every thread's read happens well before any thread's
    write), so this does not depend on getting lucky with OS thread
    scheduling.
    """
    priv, pub = _keypair()
    token = _issue(priv)

    seen: set[str] = set()

    # Deliberately NOT atomic: check and record are two separate operations
    # with a window between them where a concurrent caller can slip through.
    def naive_reject_replayed_jti(jti: str) -> bool:
        already_seen = jti in seen
        time.sleep(0.05)  # deliberately widen the read-then-write race window
        if not already_seen:
            seen.add(jti)
        return already_seen

    outcomes: list[str] = []
    outcomes_lock = threading.Lock()
    barrier = threading.Barrier(10, timeout=5)

    def worker() -> None:
        barrier.wait()  # all 10 threads enter the callback at ~the same time
        try:
            _verify(token, pub, reject_replayed_jti=naive_reject_replayed_jti)
            outcome = "accepted"
        except PlatformServiceTokenError:
            outcome = "rejected"
        with outcomes_lock:
            outcomes.append(outcome)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert len(outcomes) == 10
    # The whole point: with a non-atomic callback, MORE THAN ONE concurrent
    # call observes "not seen" and is accepted -- the race the atomic
    # version above closes.
    assert outcomes.count("accepted") > 1
