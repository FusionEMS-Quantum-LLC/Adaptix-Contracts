"""The entitlement gate's claim readers and its typed factories (5.42.0).

Driven through FastAPI over httpx's ASGI transport with real RS256 tokens whose
signature the gate verifies. The pool's signing key is the one seam replaced,
as in ``tests/test_module_entitlement_gate.py``.

* An access token's ``client_id`` is read only as one string. A list, even one
  naming the configured client, is refused 401; before 5.42.0 it raised an
  unhashable-list ``TypeError``, which a service answers 500.
* An id token's ``aud`` may be one string or a list (RFC 7519 section 4.1.3);
  either way it must name the configured app client.
* With no entitlements in the claims, the gate reads
  ``request.state.module_entitlements``, which Core's auth dependency fills
  from the tenant row for Cognito tokens. Entitlements in the claims win.
* Each factory returns an :class:`EntitlementGate` named for what it gates, and
  the module exports every public name.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

import httpx
import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI, Request, Response
from pydantic import TypeAdapter

import adaptix_contracts.auth.module_entitlement_gate as meg
from adaptix_contracts.auth.cognito import AdaptixCognitoConfig
from adaptix_contracts.auth.module_entitlement_gate import (
    EntitlementGate,
    require_any_module_entitlement,
    require_capability_entitlement,
    require_module_entitlement,
)

POOL_ID = "us-east-1_claimshapes"
CLIENT_ID = "claim-shapes-client"
ISSUER = f"https://cognito-idp.us-east-1.amazonaws.com/{POOL_ID}"
POOL_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


_DETAIL: TypeAdapter[dict[str, object]] = TypeAdapter(dict[str, object])


def _pool_signing_key(_token: str, _config: AdaptixCognitoConfig) -> rsa.RSAPublicKey:
    """The pool's public key, for every token: the gate's JWKS lookup, replaced."""
    return POOL_KEY.public_key()


@pytest.fixture(autouse=True)
def cognito_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = {
        "COGNITO_REGION": "us-east-1",
        "COGNITO_USER_POOL_ID": POOL_ID,
        "COGNITO_CLIENT_ID": CLIENT_ID,
        "COGNITO_ISSUER": ISSUER,
        "COGNITO_JWKS_URL": f"{ISSUER}/.well-known/jwks.json",
    }
    for name, value in pool.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("COGNITO_CLIENT_ID_WEB", raising=False)
    monkeypatch.setattr(meg, "_cognito_signing_key", _pool_signing_key)


def _token(token_use: str = "access", **claims: object) -> str:
    """A token the pool signed, with ``claims`` over a valid base.

    An access token names its client in ``client_id``; an id token names it in
    ``aud``, which each id-token test supplies.
    """
    issued = int(time.time())
    body: dict[str, object] = {
        "sub": str(uuid4()),
        "iss": ISSUER,
        "token_use": token_use,
        "iat": issued,
        "exp": issued + 300,
    }
    if token_use == "access":
        body["client_id"] = CLIENT_ID
    body.update(claims)
    return pyjwt.encode(body, POOL_KEY, algorithm="RS256")


def _app(gate: EntitlementGate, tenant_row: list[str] | str | None = None) -> FastAPI:
    """One gated route. ``tenant_row`` is what Core's auth dependency would put
    on ``request.state.module_entitlements``; ``None`` sets nothing."""
    app = FastAPI()

    if tenant_row is not None:

        @app.middleware("http")
        async def _tenant_row(
            request: Request, call_next: Callable[[Request], Awaitable[Response]]
        ) -> Response:
            request.state.module_entitlements = tenant_row
            return await call_next(request)

    @app.get("/gated", dependencies=[Depends(gate)])
    async def _gated() -> dict[str, bool]:
        return {"ok": True}

    return app


async def _call(app: FastAPI, token: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://gate.test"
    ) as http:
        return await http.get("/gated", headers={"Authorization": f"Bearer {token}"})


def _detail(response: httpx.Response, status: int) -> dict[str, object]:
    """The gate's error detail, from an answer with ``status``."""
    assert response.status_code == status, response.text
    return _DETAIL.validate_python(response.json()["detail"])


async def test_an_access_token_whose_client_id_is_a_list_is_refused_401() -> None:
    token = _token(client_id=[CLIENT_ID], module_entitlements=["billing"])

    response = await _call(_app(require_module_entitlement("billing")), token)

    assert _detail(response, 401)["code"] == "invalid_bearer_token"


@pytest.mark.parametrize(
    ("aud", "status"),
    [
        (CLIENT_ID, 200),
        ([CLIENT_ID, "another-client"], 200),
        (["another-client"], 401),
        ([7, ""], 401),
        ("", 401),
    ],
    ids=["one-string", "list-naming-it", "list-without-it", "no-string", "empty"],
)
async def test_an_id_token_binds_the_client_through_aud(
    aud: object, status: int
) -> None:
    token = _token("id", aud=aud, module_entitlements=["billing"])

    response = await _call(_app(require_module_entitlement("billing")), token)

    assert response.status_code == status, response.text


@pytest.mark.parametrize(
    ("tenant_row", "status"),
    [
        (["billing"], 200),
        (["  Billing "], 200),
        (["cad"], 402),
        ("billing", 402),
    ],
    ids=["entitled", "normalised", "other-module", "not-a-list"],
)
async def test_without_claim_entitlements_the_gate_reads_the_tenant_row(
    tenant_row: list[str] | str, status: int
) -> None:
    response = await _call(
        _app(require_module_entitlement("billing"), tenant_row), _token()
    )

    assert response.status_code == status, response.text


async def test_with_no_entitlement_anywhere_the_denial_lists_none() -> None:
    response = await _call(_app(require_module_entitlement("billing")), _token())

    detail = _detail(response, 402)
    assert (
        detail["code"],
        detail["required_module"],
        detail["current_entitlements"],
    ) == (
        "module_not_entitled",
        "billing",
        [],
    )


async def test_entitlements_in_the_claims_win_over_the_tenant_row() -> None:
    token = _token(module_entitlements=["cad"])

    response = await _call(
        _app(require_module_entitlement("billing"), ["billing"]), token
    )

    assert _detail(response, 402)["current_entitlements"] == ["cad"]


async def test_the_any_of_gate_reads_the_tenant_row_too() -> None:
    gate = require_any_module_entitlement("mdt", "crewlink")

    allowed = await _call(_app(gate, ["crewlink"]), _token())
    denied = await _call(_app(gate, ["cad"]), _token())

    assert allowed.status_code == 200, allowed.text
    assert _detail(denied, 402)["required_modules"] == ["mdt", "crewlink"]


def test_each_factory_returns_a_gate_named_for_what_it_gates() -> None:
    gates: list[tuple[EntitlementGate, str]] = [
        (require_module_entitlement("billing"), "require_module_entitlement_billing"),
        (
            require_any_module_entitlement("mdt", "crewlink"),
            "require_any_module_entitlement_mdt_crewlink",
        ),
        (
            require_capability_entitlement("epcr.ambient_capture"),
            "require_capability_entitlement_epcr_ambient_capture",
        ),
    ]

    assert [gate.__name__ for gate, _ in gates] == [name for _, name in gates]


def test_the_module_exports_every_public_name() -> None:
    assert set(meg.__all__) == {
        "AUDIT_ACTION",
        "EntitlementGate",
        "require_any_module_entitlement",
        "require_capability_entitlement",
        "require_module_entitlement",
    }
