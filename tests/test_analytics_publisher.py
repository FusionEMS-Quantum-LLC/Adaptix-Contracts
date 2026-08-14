"""Contract tests for :mod:`adaptix_contracts.analytics_publisher`.

Covers the payload-catalog invariants (typo-drift guard between this file and
the Analytics-Service KPI catalog) and the publisher's real HTTP behavior:
signed-identity headers, retry-then-give-up, non-retryable 4xx, cross-tenant
batch splitting.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from unittest.mock import patch

import httpx
import pytest

from adaptix_contracts.analytics_events import (
    ALL_EVENT_TYPES,
    BILLING_CLAIM_OUTCOME,
    EMS_RESPONSE_TIME,
    PAYLOAD_CONTRACTS,
    payload_contract,
)
from adaptix_contracts.analytics_publisher import (
    AnalyticsEvent,
    AnalyticsPublisher,
    AnalyticsPublisherError,
)

_SECRET = "unit-test-secret-not-a-real-key"
_TENANT_A = "11111111-1111-1111-1111-111111111111"
_TENANT_B = "22222222-2222-2222-2222-222222222222"


# ---------------------------------------------------------------------------
# Catalog invariants
# ---------------------------------------------------------------------------


def test_every_event_has_a_payload_contract():
    for et in ALL_EVENT_TYPES:
        assert et in PAYLOAD_CONTRACTS
        contract = PAYLOAD_CONTRACTS[et]
        assert contract.event_type == et
        assert contract.value_field
        assert contract.unit
        if contract.unit == "category" or contract.unit == "boolean":
            assert contract.rate_truthy is not None, et


def test_event_type_constants_are_unique_and_dotted():
    seen: set[str] = set()
    for et in ALL_EVENT_TYPES:
        assert "." in et, f"event_type {et!r} must be namespaced with a dot"
        assert et not in seen, f"duplicate event_type {et!r}"
        seen.add(et)


def test_payload_contract_raises_on_unknown():
    with pytest.raises(KeyError):
        payload_contract("nope.does_not_exist")


# ---------------------------------------------------------------------------
# Publisher happy path — signed headers reach the mock server
# ---------------------------------------------------------------------------


def _mock_transport(*, expect_status: int = 202, response_body: dict | None = None):
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(
            {
                "url": str(request.url),
                "headers": dict(request.headers),
                "body": request.content.decode("utf-8"),
            }
        )
        return httpx.Response(expect_status, json=response_body or {"accepted": 1})

    return httpx.MockTransport(handler), captured


@pytest.mark.asyncio
async def test_publish_signs_identity_and_hits_ingest_path():
    transport, captured = _mock_transport()
    client = httpx.AsyncClient(
        transport=transport, base_url="http://analytics.adaptix.internal:8022"
    )
    with patch.dict(
        os.environ, {"ADAPTIX_GATEWAY_SHARED_SECRET": _SECRET}, clear=False
    ):
        publisher = AnalyticsPublisher("test-domain-service", client=client)
        ok = await publisher.publish(
            EMS_RESPONSE_TIME,
            tenant_id=_TENANT_A,
            payload={"minutes": 7.0},
            occurred_at=datetime(2026, 8, 14, 12, 0, tzinfo=UTC),
        )
    await client.aclose()
    assert ok is True
    assert len(captured) == 1
    call = captured[0]
    assert call["url"].endswith("/api/v1/analytics/events")
    assert call["headers"]["x-adaptix-auth-context"]
    assert call["headers"]["x-adaptix-auth-signature"]
    assert call["headers"]["x-adaptix-auth-path"] == "gateway-v1"
    assert call["headers"]["x-tenant-id"] == _TENANT_A
    # httpx serializes JSON without whitespace; check membership without spaces.
    assert '"event_type":"ems.response_time"' in call["body"]
    assert '"minutes":7.0' in call["body"]


@pytest.mark.asyncio
async def test_missing_secret_raises_publisher_error():
    transport, _ = _mock_transport()
    client = httpx.AsyncClient(
        transport=transport, base_url="http://analytics.adaptix.internal:8022"
    )
    with patch.dict(os.environ, {"ADAPTIX_GATEWAY_SHARED_SECRET": ""}, clear=False):
        publisher = AnalyticsPublisher("test-domain-service", client=client)
        with pytest.raises(AnalyticsPublisherError):
            await publisher.publish(
                EMS_RESPONSE_TIME,
                tenant_id=_TENANT_A,
                payload={"minutes": 7.0},
                raise_on_error=True,
            )
    await client.aclose()


@pytest.mark.asyncio
async def test_unknown_event_type_raises_value_error():
    transport, _ = _mock_transport()
    client = httpx.AsyncClient(
        transport=transport, base_url="http://analytics.adaptix.internal:8022"
    )
    with patch.dict(
        os.environ, {"ADAPTIX_GATEWAY_SHARED_SECRET": _SECRET}, clear=False
    ):
        publisher = AnalyticsPublisher("test-domain-service", client=client)
        with pytest.raises(ValueError):
            await publisher.publish(
                "not.a.real.event",
                tenant_id=_TENANT_A,
                payload={"minutes": 1.0},
            )
    await client.aclose()


@pytest.mark.asyncio
async def test_missing_value_field_raises_value_error():
    transport, _ = _mock_transport()
    client = httpx.AsyncClient(
        transport=transport, base_url="http://analytics.adaptix.internal:8022"
    )
    with patch.dict(
        os.environ, {"ADAPTIX_GATEWAY_SHARED_SECRET": _SECRET}, clear=False
    ):
        publisher = AnalyticsPublisher("test-domain-service", client=client)
        with pytest.raises(ValueError):
            # payload is missing the required "minutes" field
            await publisher.publish(
                EMS_RESPONSE_TIME,
                tenant_id=_TENANT_A,
                payload={"foo": 1.0},
            )
    await client.aclose()


@pytest.mark.asyncio
async def test_batch_splits_by_tenant_and_returns_true_when_all_ok():
    transport, captured = _mock_transport()
    client = httpx.AsyncClient(
        transport=transport, base_url="http://analytics.adaptix.internal:8022"
    )
    with patch.dict(
        os.environ, {"ADAPTIX_GATEWAY_SHARED_SECRET": _SECRET}, clear=False
    ):
        publisher = AnalyticsPublisher("test-domain-service", client=client)
        events = [
            AnalyticsEvent(
                event_type=EMS_RESPONSE_TIME,
                tenant_id=_TENANT_A,
                payload={"minutes": 5.0},
                occurred_at=datetime.now(UTC),
            ),
            AnalyticsEvent(
                event_type=EMS_RESPONSE_TIME,
                tenant_id=_TENANT_B,
                payload={"minutes": 6.0},
                occurred_at=datetime.now(UTC),
            ),
            AnalyticsEvent(
                event_type=BILLING_CLAIM_OUTCOME,
                tenant_id=_TENANT_A,
                payload={"outcome": "denied"},
                occurred_at=datetime.now(UTC),
            ),
        ]
        ok = await publisher.publish_batch(events)
    await client.aclose()
    assert ok is True
    tenants_hit = {c["headers"]["x-tenant-id"] for c in captured}
    assert tenants_hit == {_TENANT_A, _TENANT_B}


@pytest.mark.asyncio
async def test_retries_then_gives_up_returning_false():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(503, json={"detail": "service unavailable"})

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(
        transport=transport, base_url="http://analytics.adaptix.internal:8022"
    )
    with patch.dict(
        os.environ, {"ADAPTIX_GATEWAY_SHARED_SECRET": _SECRET}, clear=False
    ):
        publisher = AnalyticsPublisher(
            "test-domain-service", client=client, max_retries=1
        )
        ok = await publisher.publish(
            EMS_RESPONSE_TIME,
            tenant_id=_TENANT_A,
            payload={"minutes": 7.0},
        )
    await client.aclose()
    assert ok is False
    assert call_count["n"] == 2  # initial + 1 retry


@pytest.mark.asyncio
async def test_non_retryable_4xx_does_not_retry():
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(422, json={"detail": "bad payload"})

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(
        transport=transport, base_url="http://analytics.adaptix.internal:8022"
    )
    with patch.dict(
        os.environ, {"ADAPTIX_GATEWAY_SHARED_SECRET": _SECRET}, clear=False
    ):
        publisher = AnalyticsPublisher(
            "test-domain-service", client=client, max_retries=3
        )
        ok = await publisher.publish(
            EMS_RESPONSE_TIME,
            tenant_id=_TENANT_A,
            payload={"minutes": 7.0},
        )
    await client.aclose()
    assert ok is False
    assert call_count["n"] == 1  # no retry on 4xx (except 429)


@pytest.mark.asyncio
async def test_raise_on_error_flag_bubbles_publisher_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "boom"})

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(
        transport=transport, base_url="http://analytics.adaptix.internal:8022"
    )
    with patch.dict(
        os.environ, {"ADAPTIX_GATEWAY_SHARED_SECRET": _SECRET}, clear=False
    ):
        publisher = AnalyticsPublisher(
            "test-domain-service", client=client, max_retries=0
        )
        with pytest.raises(AnalyticsPublisherError):
            await publisher.publish(
                EMS_RESPONSE_TIME,
                tenant_id=_TENANT_A,
                payload={"minutes": 7.0},
                raise_on_error=True,
            )
    await client.aclose()
