"""Ledger item 1, gap 2: single-process replay protection.

Before this, a captured signed context (headers copied off the wire) could be
replayed verbatim any number of times within its 60-second TTL. This is a
FIRST layer only — a per-process, bounded, jti-keyed cache — and does not
protect a horizontally-scaled service across its own instances; see the
module docstring in ``adaptix_contracts.gateway_signature`` for why, and
``TestHonestScopeOfProtection`` below for a test that pins that limitation so
it cannot silently regress into an overclaim.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from uuid import uuid4

import pytest

from adaptix_contracts import gateway_signature as gs
from adaptix_contracts.gateway_signature import (
    GATEWAY_SHARED_SECRET_ENV,
    GATEWAY_SIGNATURE_REQUIRE_PATH_ENV,
    GATEWAY_TRUST_MODE_ENV,
    GatewaySignatureError,
    verify_gateway_signature,
)

_SECRET = "unit-test-hmac-material-not-a-real-value"


def _sign(**overrides: object) -> tuple[str, str]:
    now = int(time.time())
    payload: dict[str, object] = {
        "iss": "adaptix-gateway",
        "aud": "adaptix-core",
        "user_id": "11111111-1111-1111-1111-111111111111",
        "tenant_id": "22222222-2222-2222-2222-222222222222",
        "iat": now,
        "exp": now + 60,
        "jti": str(uuid4()),
    }
    payload.update(overrides)
    payload = {k: v for k, v in payload.items() if v is not None}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ctx = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    sig = hmac.new(
        _SECRET.encode("utf-8"), ctx.encode("ascii"), hashlib.sha256
    ).hexdigest()
    return ctx, sig


@pytest.fixture(autouse=True)
def _hmac_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(GATEWAY_SHARED_SECRET_ENV, _SECRET)
    monkeypatch.delenv(GATEWAY_TRUST_MODE_ENV, raising=False)
    monkeypatch.delenv(GATEWAY_SIGNATURE_REQUIRE_PATH_ENV, raising=False)
    gs.reset_gateway_replay_cache_for_tests()
    yield
    gs.reset_gateway_replay_cache_for_tests()


class TestReplayIsRejected:
    def test_second_verify_of_the_same_context_is_rejected(self) -> None:
        ctx, sig = _sign()
        # First presentation: a legitimate, single use of the context.
        verify_gateway_signature(
            context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
        )
        # Second presentation of the IDENTICAL wire bytes: a replay.
        with pytest.raises(GatewaySignatureError, match="replay"):
            verify_gateway_signature(
                context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
            )

    def test_two_distinct_contexts_both_verify(self) -> None:
        """Different jti -> independent requests, neither is a replay of the other."""
        ctx1, sig1 = _sign()
        ctx2, sig2 = _sign()
        verify_gateway_signature(
            context_b64=ctx1, signature_hex=sig1, shared_secret=_SECRET
        )
        verify_gateway_signature(
            context_b64=ctx2, signature_hex=sig2, shared_secret=_SECRET
        )

    def test_context_without_jti_is_not_replay_tracked(self) -> None:
        """Pre-jti v1 producers are not newly broken: nothing to key the
        cache on, so the same jti-less context verifies more than once, same
        as before this change."""
        ctx, sig = _sign(jti=None)
        verify_gateway_signature(
            context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
        )
        verify_gateway_signature(
            context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
        )

    def test_replay_is_rejected_before_any_downstream_effect_state_changes(
        self,
    ) -> None:
        """A tampered replay (bit-flipped payload with the ORIGINAL
        signature) fails on the signature check first, not the replay check —
        confirms replay tracking never becomes a way to probe forged
        contexts for "was this jti used before"."""
        ctx, sig = _sign()
        verify_gateway_signature(
            context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
        )
        # Decode via the same helper gateway_signature itself uses internally.
        from adaptix_contracts.gateway_keys import b64url_decode

        doc = json.loads(b64url_decode(ctx))
        doc["tenant_id"] = "99999999-9999-9999-9999-999999999999"
        tampered_ctx = (
            base64.urlsafe_b64encode(
                json.dumps(doc, separators=(",", ":"), sort_keys=True).encode()
            )
            .rstrip(b"=")
            .decode()
        )
        with pytest.raises(GatewaySignatureError, match="signature mismatch"):
            verify_gateway_signature(
                context_b64=tampered_ctx, signature_hex=sig, shared_secret=_SECRET
            )


class TestReplayCacheExpiry:
    def test_expired_entry_is_pruned_and_the_jti_can_be_reused(self) -> None:
        """The cache entry's own TTL is the context's ``exp``, not a fixed
        wall-clock duration. Once that has passed, the slot is freed instead
        of permanently blacklisting the jti."""
        jti = str(uuid4())
        now = int(time.time())
        ctx, sig = _sign(jti=jti, iat=now, exp=now + 5)
        verify_gateway_signature(
            context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
        )

        # Simulate the entry having already expired without waiting 5s real
        # time: poke the recorded expiry directly, exactly as pruning reads
        # it (`_replay_seen[jti] = exp`).
        gs._replay_seen[jti] = now - 1

        # A SECOND, freshly-minted context that happens to reuse the same jti
        # (e.g. a producer bug, or simply this test) is no longer a replay
        # once the prior entry has expired.
        ctx2, sig2 = _sign(jti=jti)
        verify_gateway_signature(
            context_b64=ctx2, signature_hex=sig2, shared_secret=_SECRET
        )

    def test_unexpired_entry_still_blocks_replay(self) -> None:
        jti = str(uuid4())
        now = int(time.time())
        ctx, sig = _sign(jti=jti, iat=now, exp=now + 60)
        verify_gateway_signature(
            context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
        )
        with pytest.raises(GatewaySignatureError, match="replay"):
            verify_gateway_signature(
                context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
            )


class TestReplayCacheBounded:
    def test_full_cache_fails_closed_rather_than_silently_disabling_tracking(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(gs, "_MAX_REPLAY_CACHE_ENTRIES", 2)
        for _ in range(2):
            ctx, sig = _sign()
            verify_gateway_signature(
                context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
            )

        ctx, sig = _sign()
        with pytest.raises(GatewaySignatureError, match="cache is full"):
            verify_gateway_signature(
                context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
            )

    def test_cache_has_room_again_once_entries_expire(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(gs, "_MAX_REPLAY_CACHE_ENTRIES", 1)
        now = int(time.time())
        ctx, sig = _sign(exp=now + 5)
        verify_gateway_signature(
            context_b64=ctx, signature_hex=sig, shared_secret=_SECRET
        )

        # Force every currently-recorded entry to look expired, exactly as
        # real time passing would.
        for k in list(gs._replay_seen):
            gs._replay_seen[k] = now - 1

        ctx2, sig2 = _sign()
        verify_gateway_signature(
            context_b64=ctx2, signature_hex=sig2, shared_secret=_SECRET
        )


class TestHonestScopeOfProtection:
    def test_module_docstring_states_this_is_per_process_only(self) -> None:
        """Pins the documented limitation so a future edit cannot silently
        upgrade the docstring's claim past what the implementation (a
        plain in-process dict) actually provides."""
        assert "per-process" in gs.__doc__
        assert "does not protect" in gs.__doc__
