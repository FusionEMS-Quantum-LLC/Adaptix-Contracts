"""Regression coverage for the Core event-bus consumer registry and deprecation path."""

from __future__ import annotations

from typing import Any

import pytest

from adaptix_contracts.event_consumers import (
    BILLING_SERVICE_CONSUMER,
    CAD_SERVICE_CONSUMER,
    EPCR_SERVICE_CONSUMER,
    HOSPITAL_SERVICE_CONSUMER,
    KNOWN_EVENT_BUS_CONSUMERS,
    is_known_event_bus_consumer,
)
from adaptix_contracts.event_contracts import EventBusPublisherClient


def test_known_event_bus_consumer_registry_is_exactly_the_current_audited_set() -> None:
    assert KNOWN_EVENT_BUS_CONSUMERS == {
        BILLING_SERVICE_CONSUMER,
        CAD_SERVICE_CONSUMER,
        EPCR_SERVICE_CONSUMER,
        HOSPITAL_SERVICE_CONSUMER,
    }


def test_is_known_event_bus_consumer_recognizes_canonical_names() -> None:
    assert is_known_event_bus_consumer(BILLING_SERVICE_CONSUMER) is True
    assert is_known_event_bus_consumer(f"  {EPCR_SERVICE_CONSUMER}  ") is True
    assert is_known_event_bus_consumer("unknown-service") is False
    assert is_known_event_bus_consumer(None) is False


@pytest.mark.parametrize(
    ("operation", "invoke"),
    [
        (
            "get_pending_events_unfiltered",
            lambda: EventBusPublisherClient.get_pending_events_unfiltered(limit=5),
        ),
        (
            "mark_delivered",
            lambda: EventBusPublisherClient.mark_delivered(None, "evt-1"),
        ),
        (
            "mark_failed",
            lambda: EventBusPublisherClient.mark_failed(None, "evt-1", "boom"),
        ),
    ],
)
async def test_omitted_consumer_emits_future_warning(
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
    invoke,
) -> None:
    async def _fake_request(*_args: Any, **_kwargs: Any) -> dict[str, list[Any]] | None:
        return {"items": []}

    monkeypatch.setattr(
        EventBusPublisherClient, "_request", staticmethod(_fake_request)
    )

    with pytest.warns(
        FutureWarning,
        match=rf"EventBusPublisherClient\.{operation} called without a consumer name",
    ):
        await invoke()


@pytest.mark.parametrize(
    "invoke",
    [
        lambda: EventBusPublisherClient.get_pending_events_unfiltered(consumer="   "),
        lambda: EventBusPublisherClient.mark_delivered(None, "evt-1", consumer="   "),
        lambda: EventBusPublisherClient.mark_failed(
            None,
            "evt-1",
            "boom",
            consumer="   ",
        ),
    ],
)
async def test_blank_consumer_is_rejected(invoke) -> None:
    with pytest.raises(ValueError, match="consumer must be a non-empty string"):
        await invoke()
