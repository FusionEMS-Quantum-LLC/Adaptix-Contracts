"""``build_gateway_signed_headers`` output is accepted by ``get_auth_context`` as-is.

The producer and the canonical verifier must agree on the WHOLE request shape,
not only the signature. ``get_auth_context`` refuses a signed context unless
``X-User-Id`` / ``X-Tenant-Id`` are present and equal to the signed claims, and
the builder used to emit only the ``X-Adaptix-Auth-*`` headers, so a
service-to-service caller using it alone was refused with 401 by every
destination that resolves callers through the contracts verifier (issue #369;
in production, AI-Service's Cortex registry probe).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from adaptix_contracts.auth_contracts import AuthContext, get_auth_context
from adaptix_contracts.gateway_signing import (
    HEADER_TENANT_ID,
    HEADER_USER_ID,
    build_gateway_signed_headers,
)

_SECRET = "signed-headers-identity-unit-test-hmac-material"
_AUD = "adaptix-media"


@pytest.fixture
def destination(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """A route behind the real verifier, configured as production configures it."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ADAPTIX_GATEWAY_HMAC_ENFORCE", "true")
    monkeypatch.setenv("ADAPTIX_GATEWAY_EXPECTED_AUDIENCE", _AUD)
    monkeypatch.setenv("ADAPTIX_GATEWAY_SHARED_SECRET", _SECRET)

    app = FastAPI()

    @app.get("/catalogue")
    async def catalogue(
        ctx: AuthContext = Depends(get_auth_context),
    ) -> dict[str, object]:
        return {
            "user_id": str(ctx.user_id),
            "tenant_id": str(ctx.tenant_id),
            "scopes": list(ctx.scopes),
        }

    return TestClient(app)


def test_the_builder_s_headers_alone_are_accepted(destination: TestClient) -> None:
    user_id, tenant_id = str(uuid4()), str(uuid4())
    headers = build_gateway_signed_headers(
        user_id=user_id,
        tenant_id=tenant_id,
        aud=_AUD,
        shared_secret=_SECRET,
        scopes=["cortex:registry:read"],
    )

    resp = destination.get("/catalogue", headers=headers)

    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "scopes": ["cortex:registry:read"],
    }


def test_without_the_identity_headers_the_verifier_still_refuses(
    destination: TestClient,
) -> None:
    """The control: what callers sent before this fix is the production 401."""
    headers = build_gateway_signed_headers(
        user_id=str(uuid4()), tenant_id=str(uuid4()), aud=_AUD, shared_secret=_SECRET
    )
    del headers[HEADER_USER_ID]
    del headers[HEADER_TENANT_ID]

    resp = destination.get("/catalogue", headers=headers)

    assert resp.status_code == 401
    assert "Missing gateway identity headers" in resp.json()["detail"]


def test_identity_headers_that_disagree_with_the_signed_claims_are_refused(
    destination: TestClient,
) -> None:
    """A caller cannot use the plain headers to claim another principal."""
    headers = build_gateway_signed_headers(
        user_id=str(uuid4()), tenant_id=str(uuid4()), aud=_AUD, shared_secret=_SECRET
    )
    headers[HEADER_USER_ID] = str(uuid4())

    resp = destination.get("/catalogue", headers=headers)

    assert resp.status_code == 401
