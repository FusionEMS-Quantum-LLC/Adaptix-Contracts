"""``get_auth_context``'s ``request`` parameter, supplied through ``_inbound_request``.

Fix-forward of Contracts #404 (Lane R's review, comment 6250216294). The
parameter was ``request: Request = None  # type: ignore[assignment]``, which
hid a real finding (pyright reportArgumentType, mypy assignment). It is now
``Annotated[Request | None, Depends(_inbound_request)] = None``. These tests pin
the behaviour that change must keep, with ADAPTIX_GATEWAY_SIGNATURE_REQUIRE_PATH
on unless a test says otherwise:

- mounted as a FastAPI dependency, the real inbound request reaches the
  verifier: a context signed for one route is served there and refused on
  another;
- called directly with ``request=``, the binding is checked against it;
- called directly without ``request``, a bound context fails closed under the
  flag, and is accepted with the flag off, as before.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Iterator
from typing import Annotated
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import Depends, FastAPI, HTTPException, Request

from adaptix_contracts import gateway_signature
from adaptix_contracts.auth_contracts import AuthContext, get_auth_context
from adaptix_contracts.gateway_signature import (
    GATEWAY_SHARED_SECRET_ENV,
    GATEWAY_SIGNATURE_REQUIRE_PATH_ENV,
    GATEWAY_TRUST_MODE_ENV,
)

# A fresh secret each run: there is no literal to mistake for a real credential.
_SECRET = secrets.token_urlsafe(32)
_USER = str(uuid4())
_TENANT = str(uuid4())
_SIGNED_PATH = "/api/v1/probe/signed"
_OTHER_PATH = "/api/v1/probe/other"
_INVALID = "Gateway auth context signature is invalid."
# Every verification failure answers the same 401 detail, so each refusal test
# also asserts the logged reason: a 401 for any other cause must not pass.
_PATH_MISMATCH = f"does not match request path '{_OTHER_PATH}'"
_NO_REQUEST = "was not given request_method/request_path"
_AUTH_LOGGER = "adaptix_contracts.auth_contracts"


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _sign(method: str, path: str) -> tuple[str, str]:
    """A gateway-v1 context bound to ``method`` and ``path``, and its HMAC."""
    now = int(time.time())
    payload = {
        "iss": "adaptix-gateway",
        # The verifier refuses an audience that names no live Adaptix service.
        "aud": "adaptix-core",
        "user_id": _USER,
        "tenant_id": _TENANT,
        "method": method,
        "path": path,
        "iat": now,
        "exp": now + 60,
        "jti": str(uuid4()),
    }
    ctx = _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    sig = hmac.new(_SECRET.encode(), ctx.encode("ascii"), hashlib.sha256).hexdigest()
    return ctx, sig


def _headers(ctx: str, sig: str) -> dict[str, str]:
    return {
        "X-User-Id": _USER,
        "X-Tenant-Id": _TENANT,
        "X-Adaptix-Auth-Context": ctx,
        "X-Adaptix-Auth-Signature": sig,
        "X-Adaptix-Auth-Path": "gateway-v1",
    }


def _request(method: str, path: str) -> Request:
    """A Starlette request for a direct call, carrying only method and path."""
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "raw_path": path.encode(),
            "root_path": "",
            "scheme": "http",
            "server": ("testserver", 80),
            "query_string": b"",
            "headers": [],
        }
    )


async def _probe(
    ctx: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, str]:
    return {"user_id": str(ctx.user_id)}


def _app() -> FastAPI:
    app = FastAPI()
    app.add_api_route(_SIGNED_PATH, _probe, methods=["GET"])
    app.add_api_route(_OTHER_PATH, _probe, methods=["GET"])
    return app


def _get(app: FastAPI, path: str, headers: dict[str, str]) -> httpx.Response:
    """One GET through the real ASGI app, so FastAPI resolves the dependency."""

    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.get(path, headers=headers)

    return asyncio.run(send())


async def _call_directly(ctx: str, sig: str, request: Request | None) -> AuthContext:
    return await get_auth_context(
        x_user_id=_USER,
        x_tenant_id=_TENANT,
        x_adaptix_auth_context=ctx,
        x_adaptix_auth_signature=sig,
        x_adaptix_auth_path="gateway-v1",
        request=request,
    )


@pytest.fixture(autouse=True)
def _hmac_require_path(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv(GATEWAY_SHARED_SECRET_ENV, _SECRET)
    monkeypatch.setenv(GATEWAY_SIGNATURE_REQUIRE_PATH_ENV, "true")
    monkeypatch.delenv(GATEWAY_TRUST_MODE_ENV, raising=False)
    # The production posture: the signed audience is verified, not just read.
    monkeypatch.setenv("ADAPTIX_GATEWAY_EXPECTED_AUDIENCE", "adaptix-core")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    gateway_signature.reset_gateway_replay_cache_for_tests()
    yield
    gateway_signature.reset_gateway_replay_cache_for_tests()


def test_mounted_dependency_hands_the_real_request_to_the_verifier(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Under REQUIRE_PATH a missing request fails closed, so 200 on the signed
    route proves the request arrived; a path-mismatch 401 on another route
    proves its path was compared."""
    caplog.set_level("WARNING", logger=_AUTH_LOGGER)
    app = _app()

    served = _get(app, _SIGNED_PATH, _headers(*_sign("GET", _SIGNED_PATH)))
    assert served.status_code == 200
    assert served.json() == {"user_id": _USER}
    assert caplog.text == ""

    refused = _get(app, _OTHER_PATH, _headers(*_sign("GET", _SIGNED_PATH)))
    assert refused.status_code == 401
    assert refused.json() == {"detail": _INVALID}
    assert _PATH_MISMATCH in caplog.text
    assert _NO_REQUEST not in caplog.text


def test_direct_call_with_a_request_checks_the_binding_against_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("WARNING", logger=_AUTH_LOGGER)
    ctx, sig = _sign("GET", _SIGNED_PATH)
    auth = asyncio.run(_call_directly(ctx, sig, _request("GET", _SIGNED_PATH)))
    assert auth.user_id == UUID(_USER)
    assert auth.tenant_id == UUID(_TENANT)
    assert caplog.text == ""

    ctx, sig = _sign("GET", _SIGNED_PATH)
    with pytest.raises(HTTPException) as refused:
        _ = asyncio.run(_call_directly(ctx, sig, _request("GET", _OTHER_PATH)))
    assert refused.value.status_code == 401
    assert refused.value.detail == _INVALID
    assert _PATH_MISMATCH in caplog.text


def test_direct_call_without_a_request_fails_closed_under_require_path(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("WARNING", logger=_AUTH_LOGGER)
    ctx, sig = _sign("GET", _SIGNED_PATH)
    with pytest.raises(HTTPException) as refused:
        _ = asyncio.run(_call_directly(ctx, sig, None))
    assert refused.value.status_code == 401
    assert refused.value.detail == _INVALID
    assert _NO_REQUEST in caplog.text


def test_direct_call_without_a_request_is_accepted_with_the_flag_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pre-rollout contract: with the flag off and nothing to compare
    against, a bound context is accepted (the binding cannot be checked)."""
    monkeypatch.delenv(GATEWAY_SIGNATURE_REQUIRE_PATH_ENV)
    ctx, sig = _sign("GET", _SIGNED_PATH)
    auth = asyncio.run(_call_directly(ctx, sig, None))
    assert auth.user_id == UUID(_USER)
