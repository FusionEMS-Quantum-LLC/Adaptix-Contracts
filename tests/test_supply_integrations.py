"""Integration tests for supply domain integrations.

Tests the shared NotificationClient, AnalyticsClient, and AuditClient with mock
services.

READ THIS BEFORE ADDING A TEST HERE. These tests patch httpx.AsyncClient, force a
success response, and assert `result is True`. They assert nothing about the URL,
the headers, or the request body. The deleted SearchClient tests were written the
same way, and that is exactly why a client wrong on all three at once â€” wrong path,
wrong auth header, wrong payload shape â€” passed this suite for its entire life
without ever indexing a row. A test that mocks the transport and asserts only the
return value measures nothing about the contract.

If you extend this file, assert on the call arguments: `mock_post.call_args` gives
you the URL, `headers=`, and `json=` actually sent. Compare them against the
receiving service's route, its auth dependency, and its request model.
"""

import base64
import json
import os
import pytest
import httpx
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from unittest.mock import AsyncMock, Mock, patch

pytest_plugins = ("pytest_asyncio",)


def _mock_success_response(payload: dict | None = None) -> Mock:
    response = Mock()
    response.raise_for_status = Mock()
    response.json = Mock(return_value=payload or {})
    return response


# Captured at import time, before any test patches `httpx.AsyncClient` --
# `_capturing_async_client` below must build the real client through THIS
# name, never through `httpx.AsyncClient` directly. While a test's
# `patch("httpx.AsyncClient", ...)` is active, `httpx.AsyncClient` resolves
# to that patch, so a factory that calls `httpx.AsyncClient(...)` on itself
# calls right back into its own patch and recurses without end.
_RealAsyncClient = httpx.AsyncClient


def _capturing_async_client(captured: dict):
    """A patch target for `httpx.AsyncClient` that is a REAL AsyncClient bound
    to an `httpx.MockTransport`, not a Mock.

    `patch("httpx.AsyncClient")` + a fully-mocked `.post()` (the pattern the
    rest of this file uses) replaces `client.post(...)` itself, so the real
    request is never built and httpx's JSON encoder never runs. That is
    exactly how this suite passed `cost=25.00` / `waste_forecast=50.00` --
    plain floats, not the `Decimal` the functions are typed to require --
    while `AnalyticsClient.publish_waste_event` and
    `NotificationClient.send_expiration_alert` had been silently dropping
    every call made with a real `Decimal` (`TypeError: Object of type
    Decimal is not JSON serializable`, swallowed by `_post_event` /
    `_post_notification`'s broad `except Exception`).

    Routing through `httpx.MockTransport` instead keeps the real
    `AsyncClient.post` -> request-encoding path intact -- including the JSON
    serialisation that a Mock skips -- while still never touching the
    network. `captured` receives the exact bytes that would have gone over
    the wire.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content
        captured["url"] = str(request.url)
        return httpx.Response(200, json={})

    def factory(*args, **kwargs):
        # Forward the caller's own constructor arguments (e.g. `timeout=`) so
        # this stays a faithful stand-in rather than silently dropping
        # configuration the real call site passed.
        return _RealAsyncClient(*args, **kwargs, transport=httpx.MockTransport(handler))

    return factory


@pytest.mark.asyncio
async def test_notification_client_low_stock_alert():
    """Test sending low-stock alert notification."""
    from adaptix_contracts.supply_integrations import NotificationClient

    tenant_id = uuid4()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = _mock_success_response({"id": "notif-123"})

        mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await NotificationClient.send_low_stock_alert(
            tenant_id=tenant_id,
            recipient_user_id="user-123",
            item_name="Saline 0.9%",
            current_stock=5,
            par_level=20,
            recommended_quantity=15,
            unit="boxes",
            cost_estimate=75.00,
        )

        assert result is True


@pytest.mark.asyncio
async def test_notification_client_expiration_alert():
    """Test sending expiration alert notification.

    Regression coverage for a real bug: `waste_forecast` is typed `Decimal`,
    and the payload used to carry that Decimal straight into `json=`, which
    httpx cannot serialise. That raised inside `_post_notification`, was
    swallowed by its broad `except Exception`, and this call silently
    returned False -- while every prior version of this test passed a float
    and never exercised real JSON encoding, so it stayed green throughout.
    Passing a real `Decimal` through a real transport catches both defects.
    """
    from adaptix_contracts.supply_integrations import NotificationClient

    tenant_id = uuid4()
    expiration_date = datetime.now(timezone.utc)
    captured: dict = {}

    with patch("httpx.AsyncClient", side_effect=_capturing_async_client(captured)):
        result = await NotificationClient.send_expiration_alert(
            tenant_id=tenant_id,
            recipient_user_id="user-123",
            item_name="Saline 0.9%",
            expiration_date=expiration_date,
            current_stock=10,
            waste_forecast=Decimal("50.00"),
        )

        assert result is True
        body = json.loads(captured["body"])
        assert body["waste_forecast"] == "50.00", (
            "an exact quantity must serialise as a JSON string, matching this "
            "package's wire convention since 2.37.0 -- not a JSON number, which "
            "cannot represent Decimal exactly"
        )


@pytest.mark.asyncio
async def test_notification_client_recall_alert():
    """Test sending medication recall alert."""
    from adaptix_contracts.supply_integrations import NotificationClient

    tenant_id = uuid4()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = _mock_success_response()

        mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await NotificationClient.send_recall_alert(
            tenant_id=tenant_id,
            recipient_user_id="user-123",
            item_name="Medication X",
            recall_id="FDA-2026-001",
            affected_lots=["LOT-001", "LOT-002"],
            recommended_action="Quarantine and return to vendor",
        )

        assert result is True


@pytest.mark.asyncio
async def test_notification_client_discrepancy_alert():
    """Test sending narcotics discrepancy alert."""
    from adaptix_contracts.supply_integrations import NotificationClient

    tenant_id = uuid4()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = _mock_success_response()

        mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await NotificationClient.send_discrepancy_alert(
            tenant_id=tenant_id,
            recipient_user_id="user-123",
            substance_name="Fentanyl",
            missing_quantity=5,
            unit="vials",
            escalation_flag=True,
        )

        assert result is True


@pytest.mark.asyncio
async def test_analytics_client_publish_usage_event():
    """Test publishing usage event to analytics."""
    from adaptix_contracts.supply_integrations import AnalyticsClient

    tenant_id = uuid4()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = _mock_success_response()

        mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await AnalyticsClient.publish_usage_event(
            tenant_id=tenant_id,
            unit_id="unit-123",
            event_type="stock_adjusted",
            quantity=10,
            cost=50.00,
            metadata={"reason": "restock"},
        )

        assert result is True


@pytest.mark.asyncio
async def test_analytics_client_publish_waste_event():
    """Test publishing waste event to analytics.

    Regression coverage for a real bug: `cost` is typed `Decimal`, and the
    payload used to carry that Decimal straight into `json=`, which httpx
    cannot serialise. That raised inside `_post_event`, was swallowed by its
    broad `except Exception`, and this call silently returned False -- a
    controlled-substance waste event dropped, not published -- while every
    prior version of this test passed a float and never exercised real JSON
    encoding, so it stayed green throughout. Passing a real `Decimal` through
    a real transport catches both defects.
    """
    from adaptix_contracts.supply_integrations import AnalyticsClient

    tenant_id = uuid4()
    captured: dict = {}

    with patch("httpx.AsyncClient", side_effect=_capturing_async_client(captured)):
        result = await AnalyticsClient.publish_waste_event(
            tenant_id=tenant_id,
            unit_id="unit-123",
            waste_reason="expired",
            quantity=5,
            cost=Decimal("25.00"),
        )

        assert result is True
        body = json.loads(captured["body"])
        assert body["cost"] == "25.00", (
            "an exact quantity must serialise as a JSON string, matching this "
            "package's wire convention since 2.37.0 -- not a JSON number, which "
            "cannot represent Decimal exactly"
        )


@pytest.mark.asyncio
async def test_analytics_client_publish_risk_event():
    """Test publishing risk event to analytics."""
    from adaptix_contracts.supply_integrations import AnalyticsClient

    tenant_id = uuid4()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = _mock_success_response()

        mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await AnalyticsClient.publish_risk_event(
            tenant_id=tenant_id,
            unit_id="unit-123",
            risk_type="expiration_risk",
            risk_score=75.5,
            risk_level="yellow",
        )

        assert result is True


# ---------------------------------------------------------------------------
# AuditClient -- contract tests.
#
# These follow the instruction in this module's docstring: assert on the URL,
# the headers and the body actually sent, compared against the receiving
# service's route, auth dependency and request model.
#
# Every test below FAILS against the pre-2026-09-05 AuditClient, which POSTed
# to /api/v1/audit/entries (a route that exists nowhere) at http://audit:8000
# (a name Cloud Map does not publish) carrying an empty `Authorization: Bearer`
# (the service requires a signed gateway context). That is the point: the
# previous tests asserted only `result is True` and passed against all three
# faults for the client's entire life.
# ---------------------------------------------------------------------------

_GW_SECRET = "test-gateway-shared-secret-value"


def _audit_capture(captured: dict, statuses=None):
    """Patch target for httpx.AsyncClient capturing url, headers and body.

    Unlike `_capturing_async_client` above this also records headers and can
    return a scripted sequence of status codes, which is what the retry and
    non-retryable-4xx assertions need.
    """
    seq = list(statuses or [201])
    captured.setdefault("calls", [])

    def handler(request: httpx.Request) -> httpx.Response:
        captured["calls"].append(
            {
                "url": str(request.url),
                "headers": dict(request.headers),
                "body": request.content,
            }
        )
        status = seq.pop(0) if seq else 201
        return httpx.Response(status, json={})

    def factory(*args, **kwargs):
        return _RealAsyncClient(*args, **kwargs, transport=httpx.MockTransport(handler))

    return factory


def _decoded_context(headers: dict) -> dict:
    """Return the decoded signed gateway context the client sent."""
    raw_ctx = headers.get("x-adaptix-auth-context")
    assert raw_ctx, f"no signed gateway context header; sent {sorted(headers)}"
    padded = raw_ctx + "=" * (-len(raw_ctx) % 4)
    return json.loads(base64.urlsafe_b64decode(padded.encode()))


@pytest.mark.asyncio
async def test_audit_client_targets_the_real_ingest_route():
    """The default destination must be the route the Audit service serves.

    Adaptix-Audit-Service backend/audit_app/api/audit.py mounts
    APIRouter(prefix="/api/v1/audit") and defines @router.post("/events").
    Cloud Map publishes the service as `audit.adaptix.internal` (port 8000).
    """
    from adaptix_contracts.supply_integrations import AuditClient

    captured: dict = {}
    with patch.dict(
        os.environ, {"ADAPTIX_GATEWAY_SHARED_SECRET": _GW_SECRET}, clear=False
    ):
        with patch.dict(os.environ, {"AUDIT_SERVICE_URL": ""}, clear=False):
            os.environ.pop("AUDIT_SERVICE_URL", None)
            with patch("httpx.AsyncClient", _audit_capture(captured)):
                result = await AuditClient.log_mutation(
                    tenant_id=uuid4(),
                    entity_type="narcotic_vial",
                    entity_id="vial-1",
                    action="vial_created",
                )

    assert result is True
    url = captured["calls"][0]["url"]
    assert url == "http://audit.adaptix.internal:8000/api/v1/audit/events", url
    assert "/api/v1/audit/entries" not in url


@pytest.mark.asyncio
async def test_audit_client_sends_signed_context_not_bearer_token():
    """The service requires a signed gateway context pinned to its audience.

    backend/audit_app/api/gateway_auth.py verifies the signed context and
    compares `aud` against a hardcoded EXPECTED_AUDIENCE ("adaptix-audit"),
    and explicitly refuses to fall back to plain headers. An
    `Authorization: Bearer` built from an unset token is rejected.
    """
    from adaptix_contracts.supply_integrations import AuditClient

    captured: dict = {}
    with patch.dict(
        os.environ, {"ADAPTIX_GATEWAY_SHARED_SECRET": _GW_SECRET}, clear=False
    ):
        with patch("httpx.AsyncClient", _audit_capture(captured)):
            await AuditClient.log_mutation(
                tenant_id=uuid4(),
                entity_type="narcotic_vial",
                entity_id="vial-1",
                action="vial_created",
            )

    headers = captured["calls"][0]["headers"]
    assert "authorization" not in {k.lower() for k in headers}, (
        "the audit rail must not send a Bearer token; the service verifies a "
        "signed gateway context"
    )
    assert headers.get("x-adaptix-auth-signature"), "context was not signed"
    assert _decoded_context(headers)["aud"] == "adaptix-audit"


@pytest.mark.asyncio
async def test_audit_client_body_validates_as_audit_ingest_request():
    """The body must be the model the route actually accepts.

    `ingest_event(request: AuditIngestRequest, ...)`. The old payload sent
    entity_type / entity_id / before_state / after_state, none of which are
    fields on that model.
    """
    from adaptix_contracts.schemas.audit_contracts import AuditIngestRequest
    from adaptix_contracts.supply_integrations import AuditClient

    tenant_id = uuid4()
    captured: dict = {}
    with patch.dict(
        os.environ, {"ADAPTIX_GATEWAY_SHARED_SECRET": _GW_SECRET}, clear=False
    ):
        with patch("httpx.AsyncClient", _audit_capture(captured)):
            await AuditClient.log_mutation(
                tenant_id=tenant_id,
                entity_type="inventory_item",
                entity_id="item-123",
                action="stock_adjusted",
                before_state={"stock": 15},
                after_state={"stock": 5},
                reason="usage",
            )

    body = json.loads(captured["calls"][0]["body"])
    # Round-trips through the receiving model -- the real 422 gate.
    parsed = AuditIngestRequest.model_validate(body)
    assert str(parsed.tenant_id) == str(tenant_id)
    assert parsed.action == "stock_adjusted"
    assert parsed.resource_type == "inventory_item"
    assert parsed.resource_id == "item-123"
    # `changes` is the structured diff; `metadata` is producer context. The
    # model documents that conflating the two is a defect.
    assert parsed.changes == {"before": {"stock": 15}, "after": {"stock": 5}}
    assert parsed.metadata["reason"] == "usage"


@pytest.mark.asyncio
async def test_audit_client_preserves_non_uuid_actor_instead_of_inventing_one():
    """A non-UUID actor is kept verbatim, never replaced with a fabricated id.

    Callers in this package have always passed plain strings while
    AuditIngestRequest.actor_user_id is a UUID. Inventing a UUID would put a
    false actor on an immutable legal record; dropping it would lose evidence.
    """
    from adaptix_contracts.schemas.audit_contracts import (
        AuditActorType,
        AuditIngestRequest,
    )
    from adaptix_contracts.supply_integrations import AuditClient

    captured: dict = {}
    with patch.dict(
        os.environ, {"ADAPTIX_GATEWAY_SHARED_SECRET": _GW_SECRET}, clear=False
    ):
        with patch("httpx.AsyncClient", _audit_capture(captured)):
            await AuditClient.log_mutation(
                tenant_id=uuid4(),
                entity_type="inventory_item",
                entity_id="item-123",
                action="stock_adjusted",
                actor_user_id="user-123",
            )

    parsed = AuditIngestRequest.model_validate(json.loads(captured["calls"][0]["body"]))
    assert parsed.actor_user_id is None
    assert parsed.actor_type is AuditActorType.SERVICE
    assert parsed.metadata["actor_user_id_raw"] == "user-123"


@pytest.mark.asyncio
async def test_audit_client_passes_through_a_real_uuid_actor():
    from adaptix_contracts.schemas.audit_contracts import (
        AuditActorType,
        AuditIngestRequest,
    )
    from adaptix_contracts.supply_integrations import AuditClient

    actor = uuid4()
    captured: dict = {}
    with patch.dict(
        os.environ, {"ADAPTIX_GATEWAY_SHARED_SECRET": _GW_SECRET}, clear=False
    ):
        with patch("httpx.AsyncClient", _audit_capture(captured)):
            await AuditClient.log_mutation(
                tenant_id=uuid4(),
                entity_type="inventory_item",
                entity_id="item-123",
                action="stock_adjusted",
                actor_user_id=str(actor),
            )

    parsed = AuditIngestRequest.model_validate(json.loads(captured["calls"][0]["body"]))
    assert parsed.actor_user_id == actor
    assert parsed.actor_type is AuditActorType.USER
    assert "actor_user_id_raw" not in parsed.metadata


@pytest.mark.asyncio
async def test_audit_client_does_not_retry_a_producer_defect():
    """A non-429 4xx is the producer's fault. Retrying hides it."""
    from adaptix_contracts.supply_integrations import AuditClient

    captured: dict = {}
    with patch.dict(
        os.environ, {"ADAPTIX_GATEWAY_SHARED_SECRET": _GW_SECRET}, clear=False
    ):
        with patch(
            "httpx.AsyncClient", _audit_capture(captured, statuses=[422, 422, 422])
        ):
            result = await AuditClient.log_mutation(
                tenant_id=uuid4(),
                entity_type="inventory_item",
                entity_id="item-123",
                action="stock_adjusted",
            )

    assert result is False
    assert len(captured["calls"]) == 1, "a 422 must not be retried"


@pytest.mark.asyncio
async def test_audit_client_retries_transient_failure_then_succeeds():
    from adaptix_contracts.supply_integrations import AuditClient

    captured: dict = {}
    with patch.dict(
        os.environ, {"ADAPTIX_GATEWAY_SHARED_SECRET": _GW_SECRET}, clear=False
    ):
        with patch("httpx.AsyncClient", _audit_capture(captured, statuses=[503, 201])):
            result = await AuditClient.log_mutation(
                tenant_id=uuid4(),
                entity_type="inventory_item",
                entity_id="item-123",
                action="stock_adjusted",
            )

    assert result is True
    assert len(captured["calls"]) == 2


@pytest.mark.asyncio
async def test_audit_client_gives_up_returning_false_after_retries():
    from adaptix_contracts.supply_integrations import AuditClient

    captured: dict = {}
    with patch.dict(
        os.environ, {"ADAPTIX_GATEWAY_SHARED_SECRET": _GW_SECRET}, clear=False
    ):
        with patch(
            "httpx.AsyncClient", _audit_capture(captured, statuses=[503, 503, 503])
        ):
            result = await AuditClient.log_mutation(
                tenant_id=uuid4(),
                entity_type="inventory_item",
                entity_id="item-123",
                action="stock_adjusted",
            )

    assert result is False
    assert len(captured["calls"]) == 3, "two retries after the first attempt"


@pytest.mark.asyncio
async def test_audit_client_raise_on_error_surfaces_the_loss():
    """A caller that cannot tolerate a lost audit record can demand a raise."""
    from adaptix_contracts.supply_integrations import AuditClient, AuditPublisherError

    captured: dict = {}
    with patch.dict(
        os.environ, {"ADAPTIX_GATEWAY_SHARED_SECRET": _GW_SECRET}, clear=False
    ):
        with patch(
            "httpx.AsyncClient", _audit_capture(captured, statuses=[503, 503, 503])
        ):
            with pytest.raises(AuditPublisherError):
                await AuditClient.log_mutation(
                    tenant_id=uuid4(),
                    entity_type="narcotic_vial",
                    entity_id="vial-1",
                    action="vial_wasted",
                    raise_on_error=True,
                )


@pytest.mark.asyncio
async def test_audit_client_missing_signing_secret_raises_rather_than_silently_failing():
    """An unsigned audit rail cannot work. Say so instead of returning False."""
    from adaptix_contracts.supply_integrations import AuditClient, AuditPublisherError

    with patch.dict(os.environ, {"ADAPTIX_GATEWAY_SHARED_SECRET": ""}, clear=False):
        with pytest.raises(AuditPublisherError):
            await AuditClient.log_mutation(
                tenant_id=uuid4(),
                entity_type="inventory_item",
                entity_id="item-123",
                action="stock_adjusted",
            )


@pytest.mark.asyncio
async def test_audit_client_log_approval_uses_the_same_contract():
    from adaptix_contracts.schemas.audit_contracts import AuditIngestRequest
    from adaptix_contracts.supply_integrations import AuditClient

    captured: dict = {}
    with patch.dict(
        os.environ, {"ADAPTIX_GATEWAY_SHARED_SECRET": _GW_SECRET}, clear=False
    ):
        with patch("httpx.AsyncClient", _audit_capture(captured)):
            result = await AuditClient.log_approval(
                tenant_id=uuid4(),
                entity_type="narcotic_discrepancy",
                entity_id="disc-123",
                approver_user_id=str(uuid4()),
                approval_type="supervisor_review",
                reason="Discrepancy resolved",
            )

    assert result is True
    assert captured["calls"][0]["url"].endswith("/api/v1/audit/events")
    parsed = AuditIngestRequest.model_validate(json.loads(captured["calls"][0]["body"]))
    assert parsed.action == "approval_supervisor_review"
    assert parsed.metadata["approval_type"] == "supervisor_review"
    assert parsed.metadata["reason"] == "Discrepancy resolved"


@pytest.mark.asyncio
async def test_integration_graceful_degradation_no_config():
    """Test that integrations degrade gracefully when not configured."""
    from adaptix_contracts.supply_integrations import NotificationClient

    tenant_id = uuid4()

    with patch.dict("os.environ", {}, clear=True):
        # Without configuration, should return False gracefully
        result = await NotificationClient.send_low_stock_alert(
            tenant_id=tenant_id,
            recipient_user_id="user-123",
            item_name="Item",
            current_stock=1,
            par_level=10,
            recommended_quantity=9,
        )

        assert result is False


@pytest.mark.asyncio
async def test_integration_handles_network_errors():
    """Test that integrations handle network errors gracefully."""
    from adaptix_contracts.supply_integrations import NotificationClient

    tenant_id = uuid4()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.ConnectError("Connection failed")
        )
        mock_client_class.return_value = mock_client

        result = await NotificationClient.send_low_stock_alert(
            tenant_id=tenant_id,
            recipient_user_id="user-123",
            item_name="Item",
            current_stock=1,
            par_level=10,
            recommended_quantity=9,
        )

        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
