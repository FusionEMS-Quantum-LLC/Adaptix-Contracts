"""Event contracts for the Adaptix platform.

Contains event schemas, validators, and registry for cross-service events.
"""

from __future__ import annotations
import builtins
import os
import warnings
from collections.abc import Callable
from typing import Any, Optional

import httpx

from adaptix_contracts.event_consumers import (
    BILLING_SERVICE_CONSUMER as BILLING_SERVICE_CONSUMER,
    CAD_SERVICE_CONSUMER as CAD_SERVICE_CONSUMER,
    EPCR_SERVICE_CONSUMER as EPCR_SERVICE_CONSUMER,
    HOSPITAL_SERVICE_CONSUMER as HOSPITAL_SERVICE_CONSUMER,
    KNOWN_EVENT_BUS_CONSUMERS as KNOWN_EVENT_BUS_CONSUMERS,
    KnownEventBusConsumerName as KnownEventBusConsumerName,
    is_known_event_bus_consumer as is_known_event_bus_consumer,
)


class EventMetadata:
    """Metadata for an event.

    Contains information about the event source, timing, and context.
    """

    def __init__(
        self,
        tenant_id: str,
        timestamp: str,
        source_service: str,
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.timestamp = timestamp
        self.source_service = source_service
        self.correlation_id = correlation_id
        self.trace_id = trace_id

    def dict(self) -> builtins.dict[str, Any]:
        """Convert the metadata to a dictionary.

        Returns:
            A dictionary representation of the metadata.
        """
        return {
            "tenant_id": self.tenant_id,
            "timestamp": self.timestamp,
            "source_service": self.source_service,
            "correlation_id": self.correlation_id,
            "trace_id": self.trace_id,
        }


class EventSchema:
    """Schema for an event.

    Contains the event type, metadata, and payload.
    """

    def __init__(
        self,
        event_type: str,
        metadata: EventMetadata,
        payload: builtins.dict[str, Any],
    ) -> None:
        self.event_type = event_type
        self.metadata = metadata
        self.payload = payload

    def dict(self) -> builtins.dict[str, Any]:
        """Convert the event to a dictionary.

        Returns:
            A dictionary representation of the event.
        """
        return {
            "event_type": self.event_type,
            "metadata": self.metadata.dict(),
            "payload": self.payload,
        }


class EventValidator:
    """Validator for event schemas.

    Ensures that events conform to the expected schema.
    """

    def validate_event(self, event: EventSchema) -> None:
        """Validate an event schema.

        Args:
            event: The event to validate.

        Raises:
            ValueError: If the event is invalid.
        """
        if not event.event_type:
            raise ValueError("Event type is required")

        if not event.metadata:
            raise ValueError("Metadata is required")

        if not event.metadata.tenant_id:
            raise ValueError("Tenant ID is required in metadata")

        if not event.metadata.timestamp:
            raise ValueError("Timestamp is required in metadata")

        if not event.metadata.source_service:
            raise ValueError("Source service is required in metadata")

        # Payload validation is type-specific and done by consumers


class LocalEventConsumerRegistry:
    """Registry for local event consumers.

    Used for in-process event handling during development or testing.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, set[Callable[[EventSchema], Any]]] = {}

    def register(self, event_type: str, handler: Callable[[EventSchema], Any]) -> None:
        """Register a handler for a specific event type.

        Args:
            event_type: The type of event to handle.
            handler: The function to call when an event of this type is received.
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = set()

        self._handlers[event_type].add(handler)

    def unregister(
        self, event_type: str, handler: Callable[[EventSchema], Any]
    ) -> None:
        """Unregister a handler for a specific event type.

        Args:
            event_type: The type of event to stop handling.
            handler: The handler to unregister.
        """
        if event_type in self._handlers and handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)

            if not self._handlers[event_type]:
                del self._handlers[event_type]

    async def process_event(self, event: EventSchema) -> None:
        """Process an event by calling all registered handlers.

        Args:
            event: The event to process.
        """
        if event.event_type in self._handlers:
            for handler in self._handlers[event.event_type]:
                await handler(event)

    def get_handlers(self, event_type: str) -> list[Callable[[EventSchema], Any]]:
        """Return registered handlers for an event type."""
        return list(self._handlers.get(event_type, set()))

    def list_registrations(self) -> dict[str, list[str]]:
        """Return event registrations for operational diagnostics."""
        return {
            event_type: [
                getattr(handler, "__qualname__", repr(handler)) for handler in handlers
            ]
            for event_type, handlers in self._handlers.items()
        }


class EventBusPublisherClient:
    """Contract-safe HTTP client for Core durable event bus operations.

    Domain workers use this client instead of importing Core internals or
    connecting to the Core database. Missing Core configuration is a hard
    runtime failure so delivery cannot be silently simulated.
    """

    LEGACY_SHARED_QUEUE_DEPRECATION_VERSION = "2.8.0"
    # Removing the omitted-consumer path NARROWS accepted values, which
    # DEPRECATION_POLICY.md reserves for a major release. 2.9.0 shipped without
    # the hard break; the removal target is the next major.
    LEGACY_SHARED_QUEUE_REMOVAL_VERSION = "3.0.0"

    @staticmethod
    def _consumer_param(
        consumer: str | None, *, operation: str
    ) -> builtins.dict[str, str] | None:
        if consumer is None:
            warnings.warn(
                f"EventBusPublisherClient.{operation} called without a consumer name. "
                "That uses Core's legacy shared queue, is deprecated for the "
                f"{EventBusPublisherClient.LEGACY_SHARED_QUEUE_DEPRECATION_VERSION} "
                "migration path, and will raise ValueError in adaptix-contracts "
                f"{EventBusPublisherClient.LEGACY_SHARED_QUEUE_REMOVAL_VERSION}. "
                "Import a canonical consumer constant from "
                "adaptix_contracts.event_consumers (for example "
                "EPCR_SERVICE_CONSUMER or HOSPITAL_SERVICE_CONSUMER) and pass it "
                "explicitly.",
                FutureWarning,
                stacklevel=3,
            )
            return None

        normalized_consumer = consumer.strip()
        if not normalized_consumer:
            raise ValueError("consumer must be a non-empty string when supplied")

        return {"consumer": normalized_consumer}

    @staticmethod
    def _configuration() -> tuple[str, str, float]:
        core_url = os.getenv("CORE_EVENT_BUS_URL", "").rstrip("/")
        token = os.getenv("CORE_EVENT_BUS_TOKEN", "") or os.getenv(
            "CORE_PROVISIONING_TOKEN", ""
        )
        timeout = float(os.getenv("CORE_EVENT_BUS_TIMEOUT_SECONDS", "5"))
        if not core_url or not token:
            raise RuntimeError(
                "CORE_EVENT_BUS_URL and CORE_EVENT_BUS_TOKEN must be configured for Core event bus delivery"
            )
        return core_url, token, timeout

    @staticmethod
    async def _request(method: str, path: str, **kwargs: Any) -> Any:
        core_url, token, timeout = EventBusPublisherClient._configuration()
        headers = dict(kwargs.pop("headers", {}) or {})
        headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method, f"{core_url}{path}", headers=headers, **kwargs
            )
        response.raise_for_status()
        if not response.content:
            return None
        return response.json()

    @staticmethod
    async def get_pending_events_unfiltered(
        _session: Any = None, limit: int = 100, consumer: str | None = None
    ) -> list[dict[str, Any]]:
        """Retrieve pending events from Core through the service-authenticated API.

        ``consumer`` selects Core's delivery model (see
        ``/api/core/internal/events/pending``):

        * **supplied** — FAN-OUT. Delivery is tracked per (event_id, consumer)
          in ``core_event_bus_deliveries``, so another service polling the same
          queue can never mark an event delivered out from under this
          subscriber. REQUIRED for any consumer that must not miss events (e.g.
          Billing minting claims from ``epcr.chart.finalized``).
        * **omitted** — legacy shared queue where the FIRST poller to ack an
          event removes it for everybody. Kept only for not-yet-migrated
          callers; unsafe for new consumers.

        The name reflects that the poll is intentionally unfiltered BY TENANT
        (workers pull cross-tenant queues); ``consumer`` adds per-subscriber
        delivery tracking without changing that.
        """
        params: dict[str, Any] = {"limit": limit}
        consumer_param = EventBusPublisherClient._consumer_param(
            consumer,
            operation="get_pending_events_unfiltered",
        )
        if consumer_param is not None:
            params.update(consumer_param)
        data = await EventBusPublisherClient._request(
            "GET",
            "/api/core/internal/events/pending",
            params=params,
        )
        return list(data.get("items", []))

    @staticmethod
    async def mark_delivered(
        _session: Any, event_id: Any, consumer: str | None = None
    ) -> None:
        """Mark an event delivered through Core's service-authenticated API.

        Supply the same ``consumer`` used when polling so the acknowledgement is
        recorded for THIS subscriber only (fan-out) and other subscribers still
        receive the event. Omitting it applies the legacy global flip.
        """
        consumer_param = EventBusPublisherClient._consumer_param(
            consumer,
            operation="mark_delivered",
        )
        await EventBusPublisherClient._request(
            "POST",
            f"/api/core/internal/events/{event_id}/delivered",
            params=consumer_param,
        )

    @staticmethod
    async def mark_failed(
        _session: Any, event_id: Any, error: str, consumer: str | None = None
    ) -> None:
        """Mark an event failed through Core's service-authenticated API.

        With ``consumer`` the failure and its retry count are recorded for THIS
        subscriber only; Core re-offers the event to that consumer until
        ``MAX_DELIVERY_ATTEMPTS`` is reached, leaving other subscribers
        unaffected.
        """
        consumer_param = EventBusPublisherClient._consumer_param(
            consumer,
            operation="mark_failed",
        )
        await EventBusPublisherClient._request(
            "POST",
            f"/api/core/internal/events/{event_id}/failed",
            json={"error": error},
            params=consumer_param,
        )


__all__ = [
    "EventBusPublisherClient",
    "BILLING_SERVICE_CONSUMER",
    "CAD_SERVICE_CONSUMER",
    "EPCR_SERVICE_CONSUMER",
    "EventMetadata",
    "EventSchema",
    "EventValidator",
    "HOSPITAL_SERVICE_CONSUMER",
    "KNOWN_EVENT_BUS_CONSUMERS",
    "KnownEventBusConsumerName",
    "LocalEventConsumerRegistry",
    "is_known_event_bus_consumer",
]
