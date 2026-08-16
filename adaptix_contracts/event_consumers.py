"""Canonical Core event-bus consumer names.

These names are the audited, currently known fan-out consumer identifiers for
``adaptix_contracts.event_contracts.EventBusPublisherClient``. Add names here
only when current fleet code or runtime evidence proves the consumer exists; do
not invent speculative placeholders.

The 2.8.0 migration path keeps the legacy "omit consumer => shared queue" shape
temporarily for not-yet-migrated callers. The 2.9.0 follow-up removes that
legacy path, so callers should import one of these constants and pass it
explicitly now.
"""

from __future__ import annotations

from typing import Final, Literal

__all__ = [
    "BILLING_SERVICE_CONSUMER",
    "CAD_SERVICE_CONSUMER",
    "EPCR_SERVICE_CONSUMER",
    "HOSPITAL_SERVICE_CONSUMER",
    "KNOWN_EVENT_BUS_CONSUMERS",
    "KnownEventBusConsumerName",
    "is_known_event_bus_consumer",
]


BILLING_SERVICE_CONSUMER: Final[str] = "billing-service"
CAD_SERVICE_CONSUMER: Final[str] = "cad-service"
EPCR_SERVICE_CONSUMER: Final[str] = "epcr-service"
HOSPITAL_SERVICE_CONSUMER: Final[str] = "hospital-service"

KnownEventBusConsumerName = Literal[
    "billing-service",
    "cad-service",
    "epcr-service",
    "hospital-service",
]

KNOWN_EVENT_BUS_CONSUMERS: frozenset[str] = frozenset(
    {
        BILLING_SERVICE_CONSUMER,
        CAD_SERVICE_CONSUMER,
        EPCR_SERVICE_CONSUMER,
        HOSPITAL_SERVICE_CONSUMER,
    }
)


def is_known_event_bus_consumer(consumer: str | None) -> bool:
    """Return whether ``consumer`` is one of the currently known canonical names."""

    if not consumer:
        return False
    return consumer.strip().lower() in KNOWN_EVENT_BUS_CONSUMERS
