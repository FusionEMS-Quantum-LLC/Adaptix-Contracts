"""The Core event-bus field widths have exactly one owner.

LABOR-CORE-CORRELATION-ID-WIDTH-MISMATCH-001.

Three services independently declared a width for the same bus field --
Labor ``varchar(300)``, Core ``varchar(255)``, CAD ``varchar(100)`` -- and
nothing asserted that they agreed, so the narrowest hop silently defined the
platform limit. ``adaptix_contracts.events.bus_limits`` now owns the number.

These tests pin the two properties that make that ownership real:

1. The constant is importable at a stable path, because every consumer's
   model and migration reads it from there.
2. The constant is at least as wide as the key the widest producer actually
   emits, computed from the producer's formula rather than hard-coded, so
   nobody can shrink the constant to a convenient number without this test
   going red.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from pydantic import ValidationError

from adaptix_contracts.events import BUS_CORRELATION_ID_MAX_LENGTH
from adaptix_contracts.events.envelope import AdaptixEventEnvelope
from adaptix_contracts.events.operational_envelope import OperationalEventEnvelope
from adaptix_contracts.events.bus_limits import (
    BUS_CORRELATION_ID_MAX_LENGTH as BUS_CORRELATION_ID_MAX_LENGTH_DIRECT,
)

# ---------------------------------------------------------------------------
# The widest declared producer, mirrored from its source
# ---------------------------------------------------------------------------
#
# Adaptix-Labor-Service, backend/labor_app/shift_outbox.py:
#     SHIFT_CREATED   = "workforce.shift.created"
#     SHIFT_CANCELLED = "workforce.shift.cancelled"
#     created_idempotency_key(shift)   ->
#         f"{SHIFT_CREATED}:{shift.tenant_id}:{shift.id}:{stamp}"
#     cancelled_idempotency_key(shift) ->
#         f"{SHIFT_CANCELLED}:{shift.tenant_id}:{shift.id}:{stamp}"
#     idempotency_key: Mapped[str] = mapped_column(String(300), nullable=False)
#
# and backend/labor_app/shift_outbox_relay.py, which publishes that key to the
# Core bus as the event's correlation_id:
#     "correlation_id": row.idempotency_key

LABOR_DECLARED_IDEMPOTENCY_KEY_WIDTH = 300
LABOR_SHIFT_CREATED = "workforce.shift.created"
LABOR_SHIFT_CANCELLED = "workforce.shift.cancelled"


def labor_correlation_id(event_type: str) -> str:
    """Build a key exactly the way Labor's relay does."""

    tenant_id = str(uuid.uuid4())
    shift_id = str(uuid.uuid4())
    stamp = datetime.now(UTC).isoformat()
    return f"{event_type}:{tenant_id}:{shift_id}:{stamp}"


def test_the_constant_is_the_widest_declared_producer_column() -> None:
    """The ceiling is the producer's schema, not the lengths seen in prod."""

    assert BUS_CORRELATION_ID_MAX_LENGTH == LABOR_DECLARED_IDEMPOTENCY_KEY_WIDTH


@pytest.mark.parametrize(
    "event_type",
    [LABOR_SHIFT_CREATED, LABOR_SHIFT_CANCELLED],
    ids=["shift.created", "shift.cancelled"],
)
def test_a_real_producer_key_fits_inside_the_constant(event_type: str) -> None:
    """Computed from the producer formula so it cannot rot into a literal."""

    key = labor_correlation_id(event_type)
    assert len(key) <= BUS_CORRELATION_ID_MAX_LENGTH


def test_the_constant_is_not_sized_to_todays_observed_lengths() -> None:
    """130/132 chars are what the current formula emits, not the contract.

    Sizing to the observed sample is the mistake that dropped every Labor
    shift event in CAD. Keep real headroom above it.
    """

    longest_observed = max(
        len(labor_correlation_id(LABOR_SHIFT_CREATED)),
        len(labor_correlation_id(LABOR_SHIFT_CANCELLED)),
    )
    assert BUS_CORRELATION_ID_MAX_LENGTH > longest_observed


def test_both_import_paths_resolve_to_the_same_owner() -> None:
    """Consumers import either path; they must not be able to disagree."""

    assert BUS_CORRELATION_ID_MAX_LENGTH is BUS_CORRELATION_ID_MAX_LENGTH_DIRECT


# ---------------------------------------------------------------------------
# The envelope enforces the ceiling, so the producer hears about it
# ---------------------------------------------------------------------------
#
# LABOR-CORE-CORRELATION-ID-WIDTH-MISMATCH-001, second half. Owning the number
# stops the three services disagreeing; it does not stop a producer emitting a
# key none of them can store. Without a bound on the envelope the first thing
# to notice an over-length id is whichever consumer is narrowest, at INSERT,
# after the event has already been published and acknowledged -- which is the
# shape of the original CAD outage. The bound belongs where the key is built.


def _envelope_kwargs(correlation_id: str) -> dict[str, str]:
    return {
        "event_type": LABOR_SHIFT_CREATED,
        "tenant_id": str(uuid.uuid4()),
        "source_service": "adaptix-labor",
        "correlation_id": correlation_id,
    }


def _operational_kwargs(correlation_id: str) -> dict[str, str]:
    stamp = datetime.now(UTC).isoformat()
    return {
        **_envelope_kwargs(correlation_id),
        "source_record_id": str(uuid.uuid4()),
        "source_version": "1",
        "observed_at": stamp,
        "effective_at": stamp,
    }


@pytest.mark.parametrize(
    ("model", "kwargs"),
    [
        (AdaptixEventEnvelope, _envelope_kwargs),
        (OperationalEventEnvelope, _operational_kwargs),
    ],
    ids=["AdaptixEventEnvelope", "OperationalEventEnvelope"],
)
def test_an_envelope_accepts_a_correlation_id_at_exactly_the_ceiling(
    model: type, kwargs: object
) -> None:
    """The ceiling is inclusive: 300 is allowed, because 300 is the contract."""

    at_the_limit = "c" * BUS_CORRELATION_ID_MAX_LENGTH
    built = model(**kwargs(at_the_limit))  # type: ignore[operator]
    assert built.correlation_id == at_the_limit


@pytest.mark.parametrize(
    ("model", "kwargs"),
    [
        (AdaptixEventEnvelope, _envelope_kwargs),
        (OperationalEventEnvelope, _operational_kwargs),
    ],
    ids=["AdaptixEventEnvelope", "OperationalEventEnvelope"],
)
def test_an_envelope_refuses_a_correlation_id_one_character_over(
    model: type, kwargs: object
) -> None:
    """Refused at publish, not silently dropped at the narrowest consumer."""

    too_long = "c" * (BUS_CORRELATION_ID_MAX_LENGTH + 1)
    with pytest.raises(ValidationError) as caught:
        model(**kwargs(too_long))  # type: ignore[operator]
    assert "correlation_id" in str(caught.value)


@pytest.mark.parametrize(
    "event_type",
    [LABOR_SHIFT_CREATED, LABOR_SHIFT_CANCELLED],
    ids=["shift.created", "shift.cancelled"],
)
def test_a_real_producer_key_still_passes_the_envelope(event_type: str) -> None:
    """The bound must not reject what the widest producer actually emits."""

    key = labor_correlation_id(event_type)
    assert AdaptixEventEnvelope(**_envelope_kwargs(key)).correlation_id == key


def test_the_envelope_bound_is_read_from_the_owner_not_a_literal() -> None:
    """A second copy of the number would be the defect this card is about."""

    for model in (AdaptixEventEnvelope, OperationalEventEnvelope):
        field = model.model_fields["correlation_id"]
        lengths = [
            getattr(item, "max_length", None)
            for item in field.metadata
            if getattr(item, "max_length", None) is not None
        ]
        assert lengths == [BUS_CORRELATION_ID_MAX_LENGTH]
