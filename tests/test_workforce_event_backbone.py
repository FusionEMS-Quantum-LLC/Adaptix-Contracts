"""Drift + contract guards for Labor-produced workforce.shift.* facts.

Mirrors the style established by ``test_scheduling_service_registration.py``
(PR #112): every registered event's ``source_service`` must resolve to a real
``ServiceDefinition``, and the versioned envelope must keep carrying every field
the directive mandates.

Covered here:

* ``workforce.shift.created`` and ``workforce.shift.cancelled`` are registered
  and their ``source_service`` resolves to the live Labor service (slug
  ``labor``);
* they are Labor-produced facts that keep the ``workforce.shift.*`` names CAD
  already listens for, NOT one of the 27 ``schedule.*`` events that carry
  ``source_service="scheduling"``;
* ``OperationalEventEnvelope`` (schema_version 1.0) carries all nine mandated
  fields, is tenant-scoped, idempotent, traceable and round-trips losslessly.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from adaptix_contracts.events.operational_envelope import (
    REQUIRED_ENVELOPE_FIELDS,
    SCHEMA_VERSION,
    OperationalEventEnvelope,
    assert_event_type_registered,
)
from adaptix_contracts.events.registry import (
    ALL_EVENTS,
    WORKFORCE_SHIFT_CANCELLED,
    WORKFORCE_SHIFT_CREATED,
    is_registered,
    producer_of,
)
from adaptix_contracts.scheduling.events import ALL_SCHEDULING_EVENTS
from adaptix_contracts.schemas.service_registry import (
    LABOR_SERVICE,
    SERVICE_BY_SLUG,
)


def _resolve_source_service(source_service: str):
    """Same resolution the PR #112 drift guard uses (slug or ``adaptix-`` name)."""
    if source_service in SERVICE_BY_SLUG:
        return SERVICE_BY_SLUG[source_service]
    if source_service.startswith("adaptix-"):
        return SERVICE_BY_SLUG.get(source_service.removeprefix("adaptix-"))
    return None


# ---------------------------------------------------------------------------
# Registry registration + reconciliation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("constant", "event_type"),
    [
        (WORKFORCE_SHIFT_CREATED, "workforce.shift.created"),
        (WORKFORCE_SHIFT_CANCELLED, "workforce.shift.cancelled"),
    ],
)
def test_workforce_shift_event_is_registered_to_labor(
    constant: str, event_type: str
) -> None:
    assert constant == event_type
    assert is_registered(event_type) is True
    assert ALL_EVENTS[event_type] == {
        "version": "1.0",
        "source_service": "labor",
    }
    assert producer_of(event_type) is LABOR_SERVICE


def test_workforce_event_source_service_resolves_to_labor_service() -> None:
    for event_type in (WORKFORCE_SHIFT_CREATED, WORKFORCE_SHIFT_CANCELLED):
        meta = ALL_EVENTS[event_type]
        assert _resolve_source_service(meta["source_service"]) is LABOR_SERVICE


def test_workforce_event_is_not_a_scheduling_event() -> None:
    # Reconciliation: Labor produces these facts; they are not schedule.* events
    # that declare source_service="scheduling".
    for event_type in (WORKFORCE_SHIFT_CREATED, WORKFORCE_SHIFT_CANCELLED):
        assert event_type not in ALL_SCHEDULING_EVENTS
        assert not event_type.startswith("schedule.")


# ---------------------------------------------------------------------------
# Envelope contract — the nine mandated fields
# ---------------------------------------------------------------------------


def _valid_kwargs() -> dict:
    return dict(
        event_type=WORKFORCE_SHIFT_CANCELLED,
        tenant_id="tenant-123",
        source_service="labor",
        source_record_id="shift-abc",
        source_version=2,
        observed_at="2026-07-24T20:00:00+00:00",
        effective_at="2026-07-24T20:00:00+00:00",
        idempotency_key="workforce.shift.cancelled:tenant-123:shift-abc:2",
    )


def test_envelope_declares_all_required_fields() -> None:
    fields = set(OperationalEventEnvelope.model_fields)
    for required in REQUIRED_ENVELOPE_FIELDS:
        assert required in fields, f"envelope dropped mandated field {required!r}"


def test_envelope_roundtrips_losslessly() -> None:
    env = OperationalEventEnvelope(**_valid_kwargs(), payload={"old": "scheduled"})
    detail = env.to_detail_json()
    restored = OperationalEventEnvelope.model_validate_json(detail)
    assert restored == env
    assert restored.schema_version == SCHEMA_VERSION
    assert restored.payload == {"old": "scheduled"}


def test_envelope_requires_tenant_id() -> None:
    kwargs = _valid_kwargs()
    kwargs["tenant_id"] = ""
    with pytest.raises(ValidationError):
        OperationalEventEnvelope(**kwargs)


def test_envelope_requires_source_record_id() -> None:
    kwargs = _valid_kwargs()
    kwargs["source_record_id"] = ""
    with pytest.raises(ValidationError):
        OperationalEventEnvelope(**kwargs)


def test_source_version_must_be_positive() -> None:
    kwargs = _valid_kwargs()
    kwargs["source_version"] = 0
    with pytest.raises(ValidationError):
        OperationalEventEnvelope(**kwargs)


def test_timestamps_normalised_to_utc_iso() -> None:
    kwargs = _valid_kwargs()
    kwargs["observed_at"] = datetime(2026, 7, 24, 20, 0, 0, tzinfo=timezone.utc)
    kwargs["effective_at"] = "2026-07-24T20:00:00Z"
    env = OperationalEventEnvelope(**kwargs)
    assert env.observed_at == "2026-07-24T20:00:00+00:00"
    assert env.effective_at == "2026-07-24T20:00:00+00:00"


def test_bad_timestamp_rejected() -> None:
    kwargs = _valid_kwargs()
    kwargs["observed_at"] = "not-a-timestamp"
    with pytest.raises(ValidationError):
        OperationalEventEnvelope(**kwargs)


def test_schema_version_defaults_to_current() -> None:
    env = OperationalEventEnvelope(**_valid_kwargs())
    assert env.schema_version == SCHEMA_VERSION == "1.0"


def test_idempotency_key_preserved() -> None:
    env = OperationalEventEnvelope(**_valid_kwargs())
    assert env.idempotency_key == "workforce.shift.cancelled:tenant-123:shift-abc:2"


def test_assert_event_type_registered() -> None:
    env = OperationalEventEnvelope(**_valid_kwargs())
    assert_event_type_registered(env)  # registered — no raise

    kwargs = _valid_kwargs()
    kwargs["event_type"] = "workforce.shift.teleported"
    bogus = OperationalEventEnvelope(**kwargs)
    with pytest.raises(ValueError):
        assert_event_type_registered(bogus)
