"""Canonical Core event-bus consumer names.

These names are the audited, currently known fan-out consumer identifiers for
``adaptix_contracts.event_contracts.EventBusPublisherClient``. Add names here
only when current fleet code or runtime evidence proves the consumer exists; do
not invent speculative placeholders.

The 2.8.0 migration path keeps the legacy "omit consumer => shared queue" shape
temporarily for not-yet-migrated callers, and 2.9.0 still keeps it: removing it
narrows accepted values, which ``DEPRECATION_POLICY.md`` reserves for a major
release, so the hard break moved to 3.0.0. Omitting the consumer still emits
``FutureWarning`` today, so callers should import one of these constants and
pass it explicitly now.
"""

from __future__ import annotations

from typing import Final, Literal

__all__ = [
    "BILLING_SERVICE_CONSUMER",
    "CAD_SERVICE_CONSUMER",
    "COMMUNICATIONS_SERVICE_CONSUMER",
    "EPCR_SERVICE_CONSUMER",
    "HOSPITAL_SERVICE_CONSUMER",
    "KNOWN_EVENT_BUS_CONSUMERS",
    "KnownEventBusConsumerName",
    "TRANSPORT_SERVICE_CONSUMER",
    "is_known_event_bus_consumer",
]


BILLING_SERVICE_CONSUMER: Final[str] = "billing-service"
CAD_SERVICE_CONSUMER: Final[str] = "cad-service"
# Adaptix-Communications-Service polls the fan-out under this name for the
# Family-Bridge event types (epcr.chart.created, epcr.chart.patient_identified,
# the transport destination/arrival events and patient.nok.consent_changed).
# Added 2026-09-08 with the poller that consumes it (FB-T5-001); before that,
# nothing delivered those events to Communications durably.
COMMUNICATIONS_SERVICE_CONSUMER: Final[str] = "communications-service"
EPCR_SERVICE_CONSUMER: Final[str] = "epcr-service"
HOSPITAL_SERVICE_CONSUMER: Final[str] = "hospital-service"
# Adaptix-Transport-Service polls the fan-out under this name for
# ``cad.case.created`` (backend/transportlink_app/background_worker.py lines
# 100 and 147 at bf98ccbc8873, started from main.py line 380). It already
# polled under this name before the constant existed; naming it here makes
# it canonical so its subscriptions can be declared in event_subscriptions.
TRANSPORT_SERVICE_CONSUMER: Final[str] = "transport-service"

KnownEventBusConsumerName = Literal[
    "billing-service",
    "cad-service",
    "communications-service",
    "epcr-service",
    "hospital-service",
    "transport-service",
]

KNOWN_EVENT_BUS_CONSUMERS: frozenset[str] = frozenset(
    {
        BILLING_SERVICE_CONSUMER,
        CAD_SERVICE_CONSUMER,
        COMMUNICATIONS_SERVICE_CONSUMER,
        EPCR_SERVICE_CONSUMER,
        HOSPITAL_SERVICE_CONSUMER,
        TRANSPORT_SERVICE_CONSUMER,
    }
)


def is_known_event_bus_consumer(consumer: str | None) -> bool:
    """Return whether ``consumer`` is one of the currently known canonical names."""

    if not consumer:
        return False
    return consumer.strip().lower() in KNOWN_EVENT_BUS_CONSUMERS
