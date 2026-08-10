"""Drift + contract guards for the Workforce operational event backbone (Phase 1).

Mirrors the style established by ``test_scheduling_service_registration.py``
(PR #112): every registered event's ``source_service`` must resolve to a real
``ServiceDefinition``, and the versioned envelope must keep carrying every field
the directive mandates.

Covered here:

* ``workforce.shift.cancelled`` is registered and its ``source_service`` resolves
  to the live Workforce service (slug ``workforce``);
* it is a workforce-owned event, NOT one of the 27 ``schedule.*`` events that
  carry ``source_service="scheduling"`` — the reconciliation the prior finding
  asked for;
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
    WORKFORCE_SHIFT_CANCELLED,
    ALL_EVENTS,
    is_registered,
)
from adaptix_contracts.scheduling.events import ALL_SCHEDULING_EVENTS
from adaptix_contracts.schemas.service_registry import (
    SERVICE_BY_SLUG,
    WORKFORCE_SERVICE,
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


def test_workforce_shift_cancelled_is_registered() -> None:
    assert WORKFORCE_SHIFT_CANCELLED == "workforce.shift.cancelled"
    assert is_registered(WORKFORCE_SHIFT_CANCELLED) is True
    assert ALL_EVENTS[WORKFORCE_SHIFT_CANCELLED] == {
        "version": "1.0",
        "source_service": "workforce",
    }


def test_workforce_event_source_service_resolves_to_workforce_service() -> None:
    meta = ALL_EVENTS[WORKFORCE_SHIFT_CANCELLED]
    assert _resolve_source_service(meta["source_service"]) is WORKFORCE_SERVICE


def test_workforce_event_is_not_a_scheduling_event() -> None:
    # Reconciliation: the event is workforce-owned, not one of the 27 schedule.*
    # events that declare source_service="scheduling".
    assert WORKFORCE_SHIFT_CANCELLED not in ALL_SCHEDULING_EVENTS
    assert not WORKFORCE_SHIFT_CANCELLED.startswith("schedule.")


# ---------------------------------------------------------------------------
# Envelope contract — the nine mandated fields
# ---------------------------------------------------------------------------


def _valid_kwargs() -> dict:
    return dict(
        event_type=WORKFORCE_SHIFT_CANCELLED,
        tenant_id="tenant-123",
        source_service="workforce",
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
