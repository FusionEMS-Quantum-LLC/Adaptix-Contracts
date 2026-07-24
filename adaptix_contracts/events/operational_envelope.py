"""Adaptix Operational Event Envelope — versioned contract (schema_version 1.0).

The operational event backbone (Amazon EventBridge transport) requires a
provenance-complete envelope that the general-purpose ``AdaptixEventEnvelope``
(``events/envelope.py``) does not carry: ``source_record_id``,
``source_version``, ``observed_at`` and ``effective_at``. Rather than widen — and
thereby break — the existing envelope that other services already construct, this
module defines a distinct, explicitly versioned envelope dedicated to replayable
operational events. The two coexist; producers on the EventBridge backbone use
this one.

Every operational event MUST carry, per the Scheduling event-backbone directive::

    tenant_id, source_service, source_record_id, source_version,
    observed_at, effective_at, correlation_id, event_type, schema_version

The envelope is:

* tenant-scoped   — ``tenant_id`` is required and non-empty;
* idempotent      — ``idempotency_key`` is stable across retries so a consumer
                    (or an EventBridge Replay) can deduplicate a re-delivery;
* traceable       — ``correlation_id`` threads related events across services;
* replayable      — the full envelope is the EventBridge ``Detail`` payload, so an
                    Archive replay reconstructs the exact original event.

``schema_version`` is the contract version. Breaking changes to the required
field set or their semantics bump it; additive optional fields do not.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Final

from pydantic import BaseModel, Field, field_validator

#: Current operational-envelope contract version. Bump on any breaking change to
#: the required field set or the meaning of an existing field.
SCHEMA_VERSION: Final[str] = "1.0"

#: The nine fields every operational event MUST carry (directive invariant). Used
#: by the drift tests to assert the contract never silently loses a field.
REQUIRED_ENVELOPE_FIELDS: Final[tuple[str, ...]] = (
    "tenant_id",
    "source_service",
    "source_record_id",
    "source_version",
    "observed_at",
    "effective_at",
    "correlation_id",
    "event_type",
    "schema_version",
)


def _to_iso_utc(value: str | datetime) -> str:
    """Normalise a timestamp to an ISO-8601 string with an explicit UTC offset.

    Accepts a ``datetime`` (a naive value is interpreted as UTC) or an ISO-8601
    string (a trailing ``Z`` is accepted). Raises ``ValueError`` for anything
    that is not a parseable ISO-8601 instant — the envelope must never carry an
    ambiguous or unparseable timestamp.
    """
    if isinstance(value, datetime):
        aware = (
            value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        )
        return aware.astimezone(timezone.utc).isoformat()
    text = value.strip()
    if not text:
        raise ValueError("timestamp must not be empty")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


class OperationalEventEnvelope(BaseModel):
    """Versioned, provenance-complete envelope for the operational event backbone.

    Rules:

    * ``event_id`` uniquely identifies one event instance;
    * ``idempotency_key`` is stable for a given source state transition, so the
      same logical event delivered twice is deduplicated exactly once;
    * ``tenant_id`` is always set — every backbone event is tenant-scoped;
    * ``source_version`` is the optimistic-concurrency version of the source row
      at the moment the event was produced (>= 1).
    """

    schema_version: str = Field(
        default=SCHEMA_VERSION, description="Envelope contract version"
    )
    event_type: str = Field(
        ..., min_length=1, description="Canonical event type name from the registry"
    )
    event_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique event instance id",
    )
    tenant_id: str = Field(
        ..., min_length=1, description="Tenant scope — required for every event"
    )
    source_service: str = Field(
        ...,
        min_length=1,
        description="Service that produced the event (service registry slug)",
    )
    source_record_id: str = Field(
        ..., min_length=1, description="Primary key of the source record"
    )
    source_version: int = Field(
        ...,
        ge=1,
        description="Optimistic-concurrency version of the source record",
    )
    observed_at: str = Field(
        ..., description="ISO-8601 UTC instant the source recorded the change"
    )
    effective_at: str = Field(
        ..., description="ISO-8601 UTC instant the change takes effect"
    )
    correlation_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Trace id shared across related events",
    )
    idempotency_key: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Stable key for dedupe on retry/replay",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Event-specific data"
    )

    @field_validator("observed_at", "effective_at", mode="before")
    @classmethod
    def _normalise_timestamp(cls, value: str | datetime) -> str:
        return _to_iso_utc(value)

    @classmethod
    def create(
        cls,
        *,
        event_type: str,
        tenant_id: str,
        source_service: str,
        source_record_id: str,
        source_version: int,
        observed_at: str | datetime,
        effective_at: str | datetime,
        idempotency_key: str,
        payload: dict[str, Any] | None = None,
        correlation_id: str | None = None,
        event_id: str | None = None,
    ) -> OperationalEventEnvelope:
        """Construct a fully-formed operational event envelope.

        ``idempotency_key`` is mandatory here (unlike the field default) because
        the backbone's producer-side dedupe requires a deterministic key derived
        from the source state — never a random one.
        """
        return cls(
            event_type=event_type,
            tenant_id=tenant_id,
            source_service=source_service,
            source_record_id=source_record_id,
            source_version=source_version,
            observed_at=observed_at,  # type: ignore[arg-type]
            effective_at=effective_at,  # type: ignore[arg-type]
            idempotency_key=idempotency_key,
            payload=payload or {},
            correlation_id=correlation_id or str(uuid.uuid4()),
            event_id=event_id or str(uuid.uuid4()),
        )

    def to_detail_json(self) -> str:
        """Serialise to the JSON string used as the EventBridge ``Detail``."""
        return self.model_dump_json()


def assert_event_type_registered(envelope: OperationalEventEnvelope) -> None:
    """Raise ``ValueError`` if the envelope's ``event_type`` is not registered.

    The registry is imported lazily so this module stays import-cheap and free of
    any registry import-order coupling.
    """
    from adaptix_contracts.events.registry import is_registered

    if not is_registered(envelope.event_type):
        raise ValueError(f"event_type is not registered: {envelope.event_type!r}")


__all__ = [
    "REQUIRED_ENVELOPE_FIELDS",
    "SCHEMA_VERSION",
    "OperationalEventEnvelope",
    "assert_event_type_registered",
]
