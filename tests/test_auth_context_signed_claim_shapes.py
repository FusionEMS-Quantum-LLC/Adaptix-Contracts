"""Shapes of the signed ``roles``/``scopes`` claims, and the removed context-JWT builder.

Contracts #403 typed the decoded gateway payload in ``get_auth_context`` as
``Mapping[str, object]`` and reads each list claim through
``_json_narrowing.is_json_list`` (which is ``isinstance(value, list)``). These
tests pin what that path does, so the typing change provably changed nothing:

* a list claim is stripped item by item, and empty items are dropped;
* a claim that is not a JSON array (a string, an object, a number) yields no
  roles or scopes at all; it is never split or coerced;
* founder is still derived from the signed ``is_founder`` flag.

They also pin ``build_gateway_context_jwt``: it accepts any keyword arguments
and always raises the same ``RuntimeError``.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import secrets
import time
from uuid import UUID, uuid4

import pytest

from adaptix_contracts.auth_contracts import (
    AuthContext,
    build_gateway_context_jwt,
    get_auth_context,
)

#: A fresh signing key per test run: nothing here depends on its value, only on
#: the test signing with the same key the service verifies with.
_SECRET = secrets.token_hex(32)
_REMOVED = (
    "build_gateway_context_jwt has been removed. "
    "AWS API Gateway injects X-User-Id / X-Tenant-Id / X-User-Roles headers "
    "after validating the Bearer JWT. No custom context JWT is needed."
)


@pytest.fixture(autouse=True)
def _signed_non_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-production, enforcement unset, a shared secret configured, no audience pin."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("ADAPTIX_GATEWAY_HMAC_ENFORCE", raising=False)
    monkeypatch.delenv("ADAPTIX_GATEWAY_EXPECTED_AUDIENCE", raising=False)
    monkeypatch.setenv("ADAPTIX_GATEWAY_SHARED_SECRET", _SECRET)


def _signed(
    user_id: UUID, tenant_id: UUID, claims: dict[str, object]
) -> tuple[str, str]:
    """(context_b64, signature_hex) for a gateway-v1 context, signed like the gateway."""
    now = int(time.time())
    payload: dict[str, object] = {
        "sub": str(user_id),
        "user_id": str(user_id),
        "tenant_id": str(tenant_id),
        "email": "claims@example.test",
        "iss": "adaptix-gateway",
        "aud": "adaptix-core",
        "iat": now,
        "exp": now + 60,
        "jti": str(uuid4()),
        **claims,
    }
    serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    context_b64 = base64.urlsafe_b64encode(serialized).decode("ascii").rstrip("=")
    signature = hmac.new(
        _SECRET.encode("utf-8"), context_b64.encode("ascii"), hashlib.sha256
    ).hexdigest()
    return context_b64, signature


def _resolve(claims: dict[str, object]) -> AuthContext:
    user_id = uuid4()
    tenant_id = uuid4()
    context_b64, signature = _signed(user_id, tenant_id, claims)
    return asyncio.run(
        get_auth_context(
            x_user_id=str(user_id),
            x_tenant_id=str(tenant_id),
            x_user_roles="spoofed_header_role",
            x_adaptix_auth_context=context_b64,
            x_adaptix_auth_signature=signature,
            x_adaptix_auth_path="gateway-v1",
        )
    )


def test_signed_list_claims_are_stripped_and_blank_items_dropped() -> None:
    auth = _resolve(
        {"roles": [" medic ", "", "  ", "dispatcher"], "scopes": ["a.read ", ""]}
    )

    assert auth.roles == ["medic", "dispatcher"]
    assert auth.scopes == ["a.read"]
    assert auth.is_founder is False


@pytest.mark.parametrize(
    "not_an_array",
    ["medic,founder", {"0": "founder"}, 7, True],
    ids=["string", "object", "number", "boolean"],
)
def test_signed_claims_that_are_not_arrays_yield_nothing(not_an_array: object) -> None:
    auth = _resolve({"roles": not_an_array, "scopes": not_an_array})

    assert auth.roles == []
    assert auth.scopes == []
    assert auth.is_founder is False


def test_signed_founder_flag_still_adds_the_founder_role() -> None:
    auth = _resolve({"roles": "not-a-list", "is_founder": True})

    assert auth.roles == ["founder"]
    assert auth.is_founder is True


def test_build_gateway_context_jwt_raises_without_arguments() -> None:
    with pytest.raises(RuntimeError) as raised:
        build_gateway_context_jwt()

    assert str(raised.value) == _REMOVED


def test_build_gateway_context_jwt_raises_for_any_keyword_arguments() -> None:
    with pytest.raises(RuntimeError) as raised:
        build_gateway_context_jwt(user_id="u", tenant_id="t", kwargs={"x": 1})

    assert str(raised.value) == _REMOVED
