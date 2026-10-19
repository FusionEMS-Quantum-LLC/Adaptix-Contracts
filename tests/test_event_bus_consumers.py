"""Regression coverage for the Core event-bus consumer registry and deprecation path."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import adaptix_contracts
from adaptix_contracts import event_consumers
from adaptix_contracts.event_consumers import (
    BILLING_SERVICE_CONSUMER,
    CAD_SERVICE_CONSUMER,
    COMMUNICATIONS_SERVICE_CONSUMER,
    EPCR_SERVICE_CONSUMER,
    HOSPITAL_SERVICE_CONSUMER,
    KNOWN_EVENT_BUS_CONSUMERS,
    TRANSPORT_SERVICE_CONSUMER,
    is_known_event_bus_consumer,
)
from adaptix_contracts.event_contracts import EventBusPublisherClient


def test_known_event_bus_consumer_registry_is_exactly_the_current_audited_set() -> None:
    assert KNOWN_EVENT_BUS_CONSUMERS == {
        BILLING_SERVICE_CONSUMER,
        CAD_SERVICE_CONSUMER,
        COMMUNICATIONS_SERVICE_CONSUMER,
        EPCR_SERVICE_CONSUMER,
        HOSPITAL_SERVICE_CONSUMER,
        TRANSPORT_SERVICE_CONSUMER,
    }


def test_is_known_event_bus_consumer_recognizes_canonical_names() -> None:
    assert is_known_event_bus_consumer(BILLING_SERVICE_CONSUMER) is True
    assert is_known_event_bus_consumer(COMMUNICATIONS_SERVICE_CONSUMER) is True
    assert COMMUNICATIONS_SERVICE_CONSUMER == "communications-service"
    assert is_known_event_bus_consumer(TRANSPORT_SERVICE_CONSUMER) is True
    assert TRANSPORT_SERVICE_CONSUMER == "transport-service"
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


def _release_parts(version: str) -> tuple[int, int, int]:
    major, minor, patch = (int(part) for part in version.split("."))
    return major, minor, patch


def test_legacy_shared_queue_removal_target_is_a_major_release_not_yet_shipped() -> (
    None
):
    """The FutureWarning names the release that removes the omitted-consumer path.

    That promise was wrong twice: it named 2.9.0, then 3.0.0, and 3.0.0, 4.0.0
    and 5.0.0 all shipped with the path still accepted (Contracts #184). A
    removal target at or below the package's own major version is a promise
    that already failed, so this fails the release that bumps the major without
    either removing the path or re-targeting it on purpose.
    """
    removal = EventBusPublisherClient.LEGACY_SHARED_QUEUE_REMOVAL_VERSION
    major, minor, patch = _release_parts(removal)

    # DEPRECATION_POLICY.md: narrowing accepted values needs a major release.
    assert (minor, patch) == (0, 0)
    assert major > _release_parts(adaptix_contracts.__version__)[0]


def _readme_text() -> str:
    return (Path(__file__).resolve().parents[1] / "README.md").read_text(
        encoding="utf-8"
    )


def _single_spaced(text: str) -> str:
    return " ".join(text.split())


def test_legacy_shared_queue_removal_target_is_the_same_everywhere_it_is_promised() -> (
    None
):
    removal = EventBusPublisherClient.LEGACY_SHARED_QUEUE_REMOVAL_VERSION

    assert f"the removal target is `{removal}`" in _single_spaced(_readme_text())
    assert f"the hard break moved to {removal}" in _single_spaced(
        event_consumers.__doc__ or ""
    )


def test_readme_lists_every_registered_consumer_name() -> None:
    readme = _readme_text()

    for name in sorted(KNOWN_EVENT_BUS_CONSUMERS):
        assert f'= "{name}"`' in readme, name
