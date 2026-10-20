"""Claim-type handling in the gateway verifier (Contracts #408).

``gateway_signature`` used ``cast(...)`` to tell the type checker what a decoded
claim was, and a ``try/except TypeError`` around ``int()`` to survive a claim
that was not a number. Those are now explicit checks and a type guard. Nothing a
caller can observe changes, and these tests pin that:

* a signed context whose ``exp`` or ``iat`` is not a number is refused with
  ``GatewaySignatureError`` ("not integers"), never an unhandled ``TypeError``;
* the payload the verifier returns is proven by ``_is_verified_gateway_payload``
  and, if that proof ever failed, the verifier fails closed instead of handing
  back a value typed as verified that is not.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Iterator, Mapping
from uuid import uuid4

import pytest

from adaptix_contracts import gateway_signature
from adaptix_contracts.gateway_signature import (
    GatewaySignatureError,
    require_int_seconds,
    verify_gateway_signature_without_request_binding,
)

_SECRET = secrets.token_urlsafe(32)
_AUDIENCE = "adaptix-billing"


@pytest.fixture(autouse=True)
def _hmac_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("ADAPTIX_GATEWAY_SHARED_SECRET", _SECRET)
    monkeypatch.setenv("ADAPTIX_GATEWAY_TRUST_MODE", "hmac")
    monkeypatch.delenv("ADAPTIX_GATEWAY_EXPECTED_AUDIENCE", raising=False)
    monkeypatch.delenv("ADAPTIX_GATEWAY_SIGNATURE_REQUIRE_PATH", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    gateway_signature.reset_gateway_replay_cache_for_tests()
    yield
    gateway_signature.reset_gateway_replay_cache_for_tests()


def _signed(**overrides: object) -> tuple[str, str]:
    now = int(time.time())
    payload: dict[str, object] = {
        "sub": "user-1",
        "user_id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "iss": "adaptix-gateway",
        "aud": _AUDIENCE,
        "iat": now,
        "exp": now + 60,
        "jti": str(uuid4()),
    }
    payload.update(overrides)
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    context = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    signature = hmac.new(
        _SECRET.encode(), context.encode("ascii"), hashlib.sha256
    ).hexdigest()
    return context, signature


def _verify(context: str, signature: str) -> object:
    return verify_gateway_signature_without_request_binding(
        context_b64=context, signature_hex=signature, auth_path="gateway-v1"
    )


@pytest.mark.parametrize("claim", ["exp", "iat"])
@pytest.mark.parametrize("value", [[], [1], {}, {"a": 1}, "not-a-number", True, ""])
def test_a_non_numeric_time_claim_is_refused_not_raised_as_typeerror(
    claim: str, value: object
) -> None:
    """``int()`` of a JSON array/object raises TypeError, of a bad string
    ValueError; either must leave the verifier as ``GatewaySignatureError``.

    ``True`` and ``""`` are included deliberately: ``True`` is an ``int`` and
    passes the type check, so it must still land inside the lifetime window
    checks rather than crash; ``""`` is a ``str`` ``int()`` refuses.
    """
    context, signature = _signed(**{claim: value})
    try:
        _ = _verify(context, signature)
    except GatewaySignatureError:
        return
    # Reaching here means the verifier ACCEPTED the claim; the only value that
    # may be accepted is the bool, which is the integer 1 and sits outside the
    # freshness window, so it must have been refused above. Fail loudly.
    pytest.fail(f"{claim}={value!r} was accepted by the verifier")


def test_a_valid_context_still_verifies_and_returns_the_signed_claims() -> None:
    context, signature = _signed()
    verified = _verify(context, signature)
    assert isinstance(verified, dict)
    assert verified["iss"] == "adaptix-gateway"
    assert verified["aud"] == _AUDIENCE


def test_the_verifier_fails_closed_if_the_payload_proof_is_lost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The return type is proven by a guard, not asserted by a cast.

    The guard cannot be false after the checks that precede it. If it ever were
    (a check removed, a claim shape changed), the verifier must refuse rather
    than return a value typed as verified. Fails on the previous ``cast``, which
    had no such guard to patch.
    """

    def _never_verified(_payload: Mapping[str, object]) -> bool:
        return False

    # Patch the module object the imported verifier runs in. A dotted-string
    # target resolves through ``sys.modules``, which another test may have
    # replaced, leaving this verifier's own globals untouched.
    monkeypatch.setattr(
        gateway_signature, "_is_verified_gateway_payload", _never_verified
    )
    context, signature = _signed()
    with pytest.raises(GatewaySignatureError, match="lost a required claim"):
        _ = _verify(context, signature)


@pytest.mark.parametrize(
    "value", [None, "5", 1.5, float("inf"), float("nan"), True, False, [], b"5"]
)
def test_a_bound_that_is_not_an_int_is_a_plain_valueerror(value: object) -> None:
    """The wrong-type branch is exactly ``ValueError`` (Contracts #408).

    That is the documented contract: "a plain ``ValueError`` and not any
    verifier's own error class", asserted by ``test_verifier_leeway_bounds``
    for every verifier. The engine's TRY004 prefers ``TypeError`` here; a
    subclass of both was tried and changes the exact type those tests pin
    (55 failures), so the rule is left to a predicate helper and the type stays.
    ``bool`` is an ``int`` subclass and is refused too.
    """
    with pytest.raises(ValueError, match="must be an int number of seconds") as caught:
        require_int_seconds(value, "leeway_seconds")
    assert type(caught.value) is ValueError


@pytest.mark.parametrize(
    ("value", "positive", "message"),
    [
        (-1, False, "must not be negative"),
        (0, True, "must be a positive number of seconds"),
        (-5, True, "must be a positive number of seconds"),
    ],
)
def test_a_range_violation_stays_a_plain_valueerror_and_not_a_typeerror(
    value: int, positive: bool, message: str
) -> None:
    """A value of the right type that is out of range is not a type error."""
    with pytest.raises(ValueError, match=message) as caught:
        require_int_seconds(value, "leeway_seconds", positive=positive)
    assert not isinstance(caught.value, TypeError)


@pytest.mark.parametrize(("value", "positive"), [(0, False), (1, True), (300, False)])
def test_a_valid_bound_is_accepted(value: int, positive: bool) -> None:
    require_int_seconds(value, "leeway_seconds", positive=positive)
