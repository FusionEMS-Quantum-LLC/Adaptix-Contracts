"""Attacker-controlled junk must produce a 401, never an unauthenticated 500.

Starlette decodes header bytes as latin-1, so a caller controls whether a header
carries a byte above 0x7F. Two places in the verifier turned that into a crash
rather than a rejection:

* ``hmac.compare_digest`` raises ``TypeError`` -- not a verification failure --
  when either argument is a ``str`` containing a non-ASCII character;
* both schemes encode the context as ASCII, which raises ``UnicodeEncodeError``.

Neither is a ``GatewaySignatureError``, so both escaped the contract every
caller relies on. A caller that catches ``GatewaySignatureError`` and answers
401 instead saw a bare exception propagate, which FastAPI turns into a 500 --
on every gateway-authenticated route, from an unauthenticated request, with one
byte.

Core-Service had already found and fixed this in its own verifier copy. The
canonical verifier had not, so adopting it fleet-wide would have reintroduced
the defect everywhere Core had closed it. These tests keep that from happening
again.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import pytest

from adaptix_contracts import gateway_signature
from adaptix_contracts.gateway_signature import (
    ENVIRONMENT_ENV,
    GATEWAY_EXPECTED_AUDIENCE_ENV,
    GATEWAY_SHARED_SECRET_ENV,
    GATEWAY_TRUST_MODE_ENV,
    GatewaySignatureError,
    verify_gateway_signature,
)

SECRET = "s" * 48
AUDIENCE = "adaptix-core"


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch):
    for var in (
        GATEWAY_EXPECTED_AUDIENCE_ENV,
        GATEWAY_TRUST_MODE_ENV,
        ENVIRONMENT_ENV,
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv(GATEWAY_SHARED_SECRET_ENV, SECRET)
    gateway_signature._WARN_ONCE["audience_unpinned"] = False
    yield


def _context() -> str:
    now = int(time.time())
    payload = {
        "iss": "adaptix-gateway",
        "aud": AUDIENCE,
        "user_id": "11111111-1111-1111-1111-111111111111",
        "tenant_id": "22222222-2222-2222-2222-222222222222",
        "iat": now,
        "exp": now + 60,
    }
    return (
        base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        )
        .decode("ascii")
        .rstrip("=")
    )


def _hmac(context_b64: str) -> str:
    return hmac.new(
        SECRET.encode("utf-8"), context_b64.encode("ascii"), hashlib.sha256
    ).hexdigest()


@pytest.mark.parametrize(
    "signature",
    [
        "édeadbeef",
        "deadbeefé",
        "Ã©" + "ab" * 8,
        "é" * 64,
    ],
    ids=["leading", "trailing", "utf8-pair", "all-non-ascii"],
)
def test_a_non_ascii_signature_is_rejected_not_a_crash(signature: str) -> None:
    """One 0xE9 in the signature header used to raise TypeError -> 500."""
    with pytest.raises(GatewaySignatureError):
        verify_gateway_signature(
            context_b64=_context(),
            signature_hex=signature,
            shared_secret=SECRET,
            auth_path="gateway-v1",
        )


@pytest.mark.parametrize(
    "prefix", ["é", "Ã©", "€"], ids=["latin1", "utf8-pair", "euro"]
)
def test_a_non_ascii_context_is_rejected_not_a_crash(prefix: str) -> None:
    """Both schemes encode the context as ASCII -> UnicodeEncodeError -> 500."""
    ctx = _context()
    with pytest.raises(GatewaySignatureError):
        verify_gateway_signature(
            context_b64=prefix + ctx,
            signature_hex=_hmac(ctx),
            shared_secret=SECRET,
            auth_path="gateway-v1",
        )


def test_a_non_ascii_context_is_rejected_on_the_v2_path_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The asymmetric path encodes the context as ASCII as well.

    Checked without any key material configured: the context is validated
    before scheme dispatch, so this must be a rejection rather than a crash
    regardless of how the request would otherwise have been verified.
    """
    with pytest.raises(GatewaySignatureError):
        verify_gateway_signature(
            context_b64="é" + _context(),
            signature_hex="c2lnbmF0dXJl",
            auth_path="gateway-v2",
            key_id="gw-1",
        )


@pytest.mark.parametrize(
    "signature",
    ["not-hex-at-all", "zz" * 32, "dead beef", "0x1234", "-1", "  "],
    ids=["words", "out-of-range", "space", "prefixed", "negative", "blank"],
)
def test_a_non_hex_signature_is_rejected(signature: str) -> None:
    """A hex digest and nothing else. Shape is checked before comparison."""
    with pytest.raises(GatewaySignatureError):
        verify_gateway_signature(
            context_b64=_context(),
            signature_hex=signature,
            shared_secret=SECRET,
            auth_path="gateway-v1",
        )


def test_a_correct_signature_still_verifies() -> None:
    """The guards must not reject legitimate traffic.

    Both the upper- and lower-case forms of a hex digest are accepted, as
    before -- the comparison has always been case-insensitive.
    """
    ctx = _context()
    sig = _hmac(ctx)
    for form in (sig, sig.upper()):
        payload = verify_gateway_signature(
            context_b64=ctx,
            signature_hex=form,
            shared_secret=SECRET,
            auth_path="gateway-v1",
        )
        assert payload["aud"] == AUDIENCE


def test_surrounding_whitespace_on_a_signature_is_still_tolerated() -> None:
    """Header values may arrive padded; that was accepted before and still is."""
    ctx = _context()
    payload = verify_gateway_signature(
        context_b64=ctx,
        signature_hex=f"  {_hmac(ctx)}  ",
        shared_secret=SECRET,
        auth_path="gateway-v1",
    )
    assert payload["user_id"] == "11111111-1111-1111-1111-111111111111"


@pytest.mark.parametrize(
    "literal", ["Infinity", "-Infinity", "NaN"], ids=["inf", "-inf", "nan"]
)
@pytest.mark.parametrize("claim", ["exp", "iat", "roles"], ids=["exp", "iat", "other"])
def test_a_non_rfc_json_constant_is_rejected(literal: str, claim: str) -> None:
    """Python's JSON decoder accepts constants RFC 8259 does not define.

    ``int(float("inf"))`` raises ``OverflowError`` -- not a ``ValueError`` --
    so a context carrying ``{"exp": Infinity}`` escaped this module's error
    contract entirely and surfaced as a 500 rather than a 401. ``NaN`` reached
    the same cast and every downstream comparison silently returned False.

    No Adaptix producer emits these, so they are refused at the decode boundary
    rather than defended against at each individual claim -- checked here on an
    unrelated claim too, since the next consumer to cast a claim should not have
    to rediscover this.
    """
    now = int(time.time())
    fields = {
        "iss": '"adaptix-gateway"',
        "aud": f'"{AUDIENCE}"',
        "user_id": '"11111111-1111-1111-1111-111111111111"',
        "tenant_id": '"22222222-2222-2222-2222-222222222222"',
        "iat": str(now),
        "exp": str(now + 60),
        "roles": '["admin"]',
    }
    fields[claim] = literal
    raw = "{" + ",".join(f'"{k}":{v}' for k, v in fields.items()) + "}"
    ctx = base64.urlsafe_b64encode(raw.encode()).decode("ascii").rstrip("=")

    with pytest.raises(GatewaySignatureError):
        verify_gateway_signature(
            context_b64=ctx,
            signature_hex=_hmac(ctx),
            shared_secret=SECRET,
            auth_path="gateway-v1",
        )
