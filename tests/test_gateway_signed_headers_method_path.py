"""``build_gateway_signed_headers`` can sign the method/path binding (Adaptix-Governance #347).

The gateway signs ``method`` (upper-cased) and ``path`` (query string and
fragment stripped) into every context it forwards, and
``gateway_signature._verify_method_path_binding`` compares them with the
request the destination receives. A service-to-service caller signing with
``build_gateway_signed_headers`` could not put either claim in its context, so
a destination that sets ``ADAPTIX_GATEWAY_SIGNATURE_REQUIRE_PATH`` refused
every such call ("the signed context carries no method/path binding"). The
2026-10-18 ruling on Adaptix-Governance #347 gives the builder keyword-only
``method`` and ``path`` that sign the same binding; a caller that omits them
keeps today's unbound context, byte for byte.

The round trips run the real producer against the real verifier mounted as a
FastAPI dependency, so the destination compares the claims with the request
FastAPI actually hands it. Every request carries a freshly signed context
(its own ``jti``): the verifier's replay guard refuses a second use of one
context, and a refusal for that reason would hide the binding check.
"""

from __future__ import annotations

import base64
import json
import secrets
from collections.abc import Iterator
from typing import Annotated
from uuid import uuid4

import pytest
from _asgi_client import ASGIClient
from fastapi import Depends, FastAPI

from adaptix_contracts import gateway_signature
from adaptix_contracts.auth_contracts import AuthContext, get_auth_context
from adaptix_contracts.gateway_keys import (
    GATEWAY_PUBLIC_KEYS_ENV,
    GATEWAY_SIGNING_KEY_ID_ENV,
    GATEWAY_SIGNING_PRIVATE_KEY_ENV,
    build_jwks,
    generate_signing_keypair,
    reset_public_keyset_cache,
)
from adaptix_contracts.gateway_signature import (
    GATEWAY_EXPECTED_AUDIENCE_ENV,
    GATEWAY_SHARED_SECRET_ENV,
    GATEWAY_SIGNATURE_REQUIRE_PATH_ENV,
    GATEWAY_TRUST_MODE_ENV,
    GatewaySignatureError,
)
from adaptix_contracts.gateway_signing import (
    HEADER_AUTH_CONTEXT,
    HEADER_AUTH_PATH,
    GatewayClaims,
    build_gateway_signed_headers,
)

_AUD = "adaptix-media"
_KID = "gw-binding-test-1"
# A fresh secret each run: there is no literal to mistake for a real credential.
_SECRET = secrets.token_urlsafe(32)


def _signed_payload(headers: dict[str, str]) -> dict[str, object]:
    context_b64 = headers[HEADER_AUTH_CONTEXT]
    raw = base64.urlsafe_b64decode(context_b64 + "=" * (-len(context_b64) % 4))
    payload: dict[str, object] = json.loads(raw)
    return payload


def _headers(*, method: str | None = None, path: str | None = None) -> dict[str, str]:
    """A freshly signed context for a synthetic principal, bound as asked."""
    return build_gateway_signed_headers(
        user_id=str(uuid4()),
        tenant_id=str(uuid4()),
        aud=_AUD,
        shared_secret=_SECRET,
        jti=str(uuid4()),
        method=method,
        path=path,
    )


@pytest.fixture(autouse=True)
def _clean_gateway_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Legacy HMAC by default, outside production, the flag off, a pinned audience."""
    for name in (
        GATEWAY_PUBLIC_KEYS_ENV,
        GATEWAY_SIGNING_PRIVATE_KEY_ENV,
        GATEWAY_SIGNING_KEY_ID_ENV,
        GATEWAY_TRUST_MODE_ENV,
        GATEWAY_SIGNATURE_REQUIRE_PATH_ENV,
        "ENVIRONMENT",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(GATEWAY_SHARED_SECRET_ENV, _SECRET)
    monkeypatch.setenv(GATEWAY_EXPECTED_AUDIENCE_ENV, _AUD)
    reset_public_keyset_cache()
    gateway_signature.reset_gateway_replay_cache_for_tests()
    yield
    reset_public_keyset_cache()
    gateway_signature.reset_gateway_replay_cache_for_tests()


@pytest.fixture
def require_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(GATEWAY_SIGNATURE_REQUIRE_PATH_ENV, "true")


@pytest.fixture
def gateway_v2(monkeypatch: pytest.MonkeyPatch) -> None:
    """The asymmetric end state: this process signs v2, the destination holds public keys only."""
    pem, entry = generate_signing_keypair(_KID)
    monkeypatch.setenv(GATEWAY_SIGNING_PRIVATE_KEY_ENV, pem)
    monkeypatch.setenv(GATEWAY_SIGNING_KEY_ID_ENV, _KID)
    monkeypatch.setenv(GATEWAY_PUBLIC_KEYS_ENV, build_jwks([entry]))
    monkeypatch.setenv(GATEWAY_TRUST_MODE_ENV, "asymmetric")
    monkeypatch.delenv(GATEWAY_SHARED_SECRET_ENV, raising=False)
    monkeypatch.setenv(GATEWAY_SIGNATURE_REQUIRE_PATH_ENV, "true")
    reset_public_keyset_cache()


@pytest.fixture
def destination() -> ASGIClient:
    """Routes behind the real verifier, mounted the way services mount it."""
    app = FastAPI()

    async def _who(ctx: AuthContext) -> dict[str, str]:
        return {"user_id": str(ctx.user_id)}

    @app.get("/catalogue")
    async def get_catalogue(
        ctx: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> dict[str, str]:
        return await _who(ctx)

    @app.post("/catalogue")
    async def post_catalogue(
        ctx: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> dict[str, str]:
        return await _who(ctx)

    @app.get("/other")
    async def get_other(
        ctx: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> dict[str, str]:
        return await _who(ctx)

    return ASGIClient(app)


# ── The signed claims ─────────────────────────────────────────────────────


def test_omitting_method_and_path_keeps_today_s_context_byte_for_byte() -> None:
    user_id, tenant_id = str(uuid4()), str(uuid4())

    unbound = build_gateway_signed_headers(
        user_id=user_id,
        tenant_id=tenant_id,
        aud=_AUD,
        shared_secret=_SECRET,
        jti="jti-fixed",
        now=1_800_000_000,
    )
    explicit_none = build_gateway_signed_headers(
        user_id=user_id,
        tenant_id=tenant_id,
        aud=_AUD,
        shared_secret=_SECRET,
        jti="jti-fixed",
        now=1_800_000_000,
        method=None,
        path=None,
    )

    assert explicit_none == unbound
    payload = _signed_payload(unbound)
    assert "method" not in payload
    assert "path" not in payload


def test_method_and_path_are_signed_as_the_gateway_signs_them() -> None:
    headers = _headers(method="post", path="/catalogue?page=2#top")

    payload = _signed_payload(headers)

    assert payload["method"] == "POST"
    assert payload["path"] == "/catalogue"


def test_gateway_claims_carry_the_binding_too() -> None:
    claims = GatewayClaims(
        user_id="user-1",
        tenant_id="tenant-1",
        aud=_AUD,
        method=" get ",
        path="/catalogue",
    )

    payload = claims.payload()

    assert payload["method"] == "GET"
    assert payload["path"] == "/catalogue"


@pytest.mark.parametrize(
    ("binding", "reason"),
    [
        ({"method": "GET"}, "together"),
        ({"path": "/catalogue"}, "together"),
        ({"method": "  ", "path": "/catalogue"}, "method"),
        ({"method": "GET", "path": ""}, "path"),
        ({"method": "GET", "path": "catalogue"}, "path"),
        ({"method": "GET", "path": "https://media.internal/catalogue"}, "path"),
    ],
)
def test_a_binding_the_verifier_would_refuse_is_refused_when_signing(
    binding: dict[str, str], reason: str
) -> None:
    with pytest.raises(GatewaySignatureError, match=reason):
        _ = _headers(method=binding.get("method"), path=binding.get("path"))


# ── Round trips through the verifier ──────────────────────────────────────


@pytest.mark.usefixtures("require_path")
def test_a_context_bound_to_get_catalogue_is_served_there_with_require_path(
    destination: ASGIClient,
) -> None:
    headers = _headers(method="GET", path="/catalogue")

    resp = destination.get("/catalogue", headers=headers)

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"user_id": headers["X-User-Id"]}


@pytest.mark.usefixtures("require_path")
def test_a_context_bound_to_get_catalogue_is_refused_on_another_route(
    destination: ASGIClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("WARNING", logger="adaptix_contracts"):
        other_path = destination.get(
            "/other", headers=_headers(method="GET", path="/catalogue")
        )
        other_method = destination.post(
            "/catalogue", headers=_headers(method="GET", path="/catalogue")
        )

    assert other_path.status_code == 401
    assert other_method.status_code == 401
    assert "does not match request path" in caplog.text
    assert "does not match request method" in caplog.text


@pytest.mark.usefixtures("require_path")
def test_a_query_string_does_not_break_the_binding(destination: ASGIClient) -> None:
    resp = destination.get(
        "/catalogue?page=2", headers=_headers(method="GET", path="/catalogue?page=2")
    )

    assert resp.status_code == 200, resp.text


def test_an_unbound_context_is_served_only_while_the_flag_is_off(
    destination: ASGIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Why callers must pass the binding before a destination turns the flag on."""
    served = destination.get("/catalogue", headers=_headers())
    monkeypatch.setenv(GATEWAY_SIGNATURE_REQUIRE_PATH_ENV, "true")
    refused = destination.get("/catalogue", headers=_headers())

    assert served.status_code == 200, served.text
    assert refused.status_code == 401


@pytest.mark.usefixtures("gateway_v2")
def test_a_gateway_v2_context_carries_the_binding(destination: ASGIClient) -> None:
    headers = _headers(method="GET", path="/catalogue")

    served = destination.get("/catalogue", headers=headers)
    refused = destination.get(
        "/other", headers=_headers(method="GET", path="/catalogue")
    )

    assert headers[HEADER_AUTH_PATH] == "gateway-v2"
    assert served.status_code == 200, served.text
    assert refused.status_code == 401
