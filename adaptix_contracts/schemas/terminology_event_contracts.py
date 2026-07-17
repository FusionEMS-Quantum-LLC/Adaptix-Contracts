"""Canonical terminology concept event contracts (SignalCore-based, versioned).

One shared definition of the terminology concept-lifecycle events so the
publisher (Terminology-Service) and consumers (Graph-Service, Cortex, ...) agree
byte-for-byte on the wire shape instead of re-deriving loose ``event_type``
strings on each side.

These events ride the canonical :class:`SignalCoreEvent` envelope (the platform
signal/event fan-out shape) with:

* ``source_service`` pinned to ``"terminology-service"``
* ``source_entity_type`` pinned to ``"concept"``
* ``source_entity_id`` = the concept id (stringified, matching the envelope's
  domain-agnostic ``str`` identifier convention)
* ``event_type`` = a member value of :class:`TerminologyEventType`
* ``payload`` = a :class:`TerminologyConceptEventPayload` dump

Backward-compatibility contract: the payload model is ``extra="allow"`` and the
validator only rejects an *unknown major* ``schema_version``. A newer publisher
may add payload fields (or bump the minor version) without breaking a lagging
consumer.

Note on naming: this module intentionally names its enum ``TerminologyEventType``
to match the terminology-service publisher vocabulary. The pre-existing
``terminology_contracts.TerminologyEventType`` (a broader domain-event set,
mapping/source/review included) already occupies that name on the package root,
so ``schemas/__init__`` re-exports this one aliased as
``TerminologyConceptEventType`` (mirroring the repo's ``PayerType as
ReferenceDataPayerType`` pattern). Import the unaliased name directly from this
module when you want the concept-lifecycle enum specifically.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from .signalcore_contracts import SignalCoreEvent

# ---------------------------------------------------------------------------
# Versioning / identity constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "1.0"
"""Wire schema version for terminology concept events. Minor bumps are additive."""

SOURCE_SERVICE = "terminology-service"
"""Canonical ``source_service`` value every terminology concept event carries."""

SOURCE_ENTITY_TYPE = "concept"
"""Canonical ``source_entity_type`` for terminology concept events."""

_EXPECTED_MAJOR = int(SCHEMA_VERSION.split(".", 1)[0])


# ---------------------------------------------------------------------------
# Event type vocabulary
# ---------------------------------------------------------------------------


class TerminologyEventType(str, Enum):
    """Canonical concept-lifecycle event types emitted by Terminology-Service."""

    CONCEPT_CREATED = "terminology.concept.created"
    CONCEPT_UPDATED = "terminology.concept.updated"
    CONCEPT_RETIRED = "terminology.concept.retired"
    CONCEPT_TERM_ADDED = "terminology.concept.term_added"
    CONCEPT_TERM_REMOVED = "terminology.concept.term_removed"
    CONCEPT_CODE_MAPPED = "terminology.concept.code_mapped"
    CONCEPT_SEMANTIC_TYPE_CHANGED = "terminology.concept.semantic_type_changed"
    CONCEPT_ENRICHED = "terminology.concept.enriched"


_KNOWN_EVENT_VALUES: frozenset[str] = frozenset(
    member.value for member in TerminologyEventType
)


# ---------------------------------------------------------------------------
# Payload
# ---------------------------------------------------------------------------


class TerminologyConceptEventPayload(BaseModel):
    """Typed payload carried inside a terminology concept ``SignalCoreEvent``.

    ``extra="allow"`` keeps the contract additive: a newer publisher may add
    payload fields a lagging consumer has not yet modelled without breaking the
    consumer's parse. ``concept_id`` is the only required field — every concept
    event is *about* a concept.
    """

    model_config = ConfigDict(extra="allow")

    concept_id: UUID
    concept_type: Optional[str] = None
    preferred_name: Optional[str] = None
    status: Optional[str] = None

    # concept.term_added / concept.term_removed
    term_id: Optional[UUID] = None
    term: Optional[str] = None
    term_type: Optional[str] = None

    # concept.code_mapped
    mapping_id: Optional[UUID] = None
    code_system: Optional[str] = None
    code: Optional[str] = None

    # concept.semantic_type_changed
    semantic_type: Optional[str] = None
    previous_semantic_type: Optional[str] = None

    # concept.updated / concept.enriched
    changed_fields: list[str] = Field(default_factory=list)
    enrichment: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_terminology_event(
    *,
    event_type: TerminologyEventType,
    tenant_id: UUID,
    payload: TerminologyConceptEventPayload | Mapping[str, Any],
    occurred_at: Optional[datetime] = None,
    event_id: Optional[UUID] = None,
    correlation_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> SignalCoreEvent:
    """Build a canonical :class:`SignalCoreEvent` for a terminology concept event.

    ``payload`` may be a :class:`TerminologyConceptEventPayload` or a mapping the
    same model can validate. The envelope's ``source_service``,
    ``source_entity_type``, ``source_entity_id`` and ``schema_version`` are set
    from the canonical constants so every publisher emits an identical shape.
    """

    if isinstance(payload, TerminologyConceptEventPayload):
        payload_model = payload
    else:
        payload_model = TerminologyConceptEventPayload.model_validate(dict(payload))

    return SignalCoreEvent(
        event_id=event_id if event_id is not None else uuid4(),
        tenant_id=tenant_id,
        source_service=SOURCE_SERVICE,
        source_entity_type=SOURCE_ENTITY_TYPE,
        source_entity_id=str(payload_model.concept_id),
        event_type=event_type.value,
        payload=payload_model.model_dump(mode="json", exclude_none=True),
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        schema_version=SCHEMA_VERSION,
        occurred_at=occurred_at if occurred_at is not None else datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


def _schema_major(version: str) -> int:
    try:
        return int(str(version).split(".", 1)[0])
    except (ValueError, TypeError) as exc:  # pragma: no cover - defensive
        raise ValueError(
            f"Malformed terminology event schema_version {version!r}."
        ) from exc


def validate_terminology_event(
    data: SignalCoreEvent | Mapping[str, Any],
) -> SignalCoreEvent:
    """Parse ``data`` into a :class:`SignalCoreEvent` and assert it is a valid,
    known terminology concept event.

    Raises:
        pydantic.ValidationError: if ``data`` is not a structurally valid
            :class:`SignalCoreEvent`.
        ValueError: if the major ``schema_version`` is unsupported, the
            ``source_service`` is not ``"terminology-service"``, or the
            ``event_type`` is not a known :class:`TerminologyEventType` value.
    """

    event = (
        data
        if isinstance(data, SignalCoreEvent)
        else SignalCoreEvent.model_validate(dict(data))
    )

    major = _schema_major(event.schema_version)
    if major != _EXPECTED_MAJOR:
        raise ValueError(
            f"Unsupported terminology event schema_version {event.schema_version!r}: "
            f"major version {major} != supported major {_EXPECTED_MAJOR}."
        )

    if event.source_service != SOURCE_SERVICE:
        raise ValueError(
            f"terminology event source_service must be {SOURCE_SERVICE!r}, "
            f"got {event.source_service!r}."
        )

    if event.event_type not in _KNOWN_EVENT_VALUES:
        raise ValueError(
            f"Unknown terminology event_type {event.event_type!r}. "
            f"Known values: {sorted(_KNOWN_EVENT_VALUES)}."
        )

    return event
