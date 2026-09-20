"""Field widths of the Core event bus envelope, owned in ONE place.

Every service that persists a value it received on the Core event bus has to
declare a column for it, and until now each one picked its own number:

===================================  =======================================
Declared width                       Where
===================================  =======================================
``varchar(300)``                     ``Adaptix-Labor-Service``
                                     ``labor_app/shift_outbox.py``
                                     ``LaborShiftOutboxEvent.idempotency_key``
``varchar(255)``                     ``Adaptix-Core-Service``
                                     ``core_app/event_bus.py``
                                     ``event_outbox`` / ``event_inbox``
``varchar(100)`` -> ``varchar(300)`` ``Adaptix-CAD-Service``
                                     ``cad_workforce_sync_events`` /
                                     ``cad_fleet_sync_events``
                                     (widened by CAD migration 075)
===================================  =======================================

Nothing asserted that those three agreed, so the NARROWEST hop silently
defined the real platform limit and the defect only surfaced at whichever
service happened to be narrowest. CAD already learned this the expensive way
(CAD-WORKFORCE-SYNC-CORRELATION-ID-TRUNCATION-001: every Labor shift event
dropped against a ``varchar(100)``). Widening one more service in isolation
would set up the same failure again.

This module is the single owner. A service that stores a bus ``correlation_id``
declares its column from ``BUS_CORRELATION_ID_MAX_LENGTH`` and asserts the
equality in its own test suite, so a drift is a red build rather than a
production event loss.

BUS_CORRELATION_ID_MAX_LENGTH
-----------------------------
The widest ``correlation_id`` any current Core event-bus PRODUCER is permitted
to emit -- measured against the producer's declared schema, not against the
lengths observed in production.

The widest declared producer is Labor-Service.
``labor_app/shift_outbox_relay.py`` publishes
``"correlation_id": row.idempotency_key``, and ``labor_app/shift_outbox.py``
declares ``LaborShiftOutboxEvent.idempotency_key = mapped_column(String(300),
nullable=False)``. Labor's own table will accept and store any key up to 300
characters, so 300 -- not the shorter value its current key formula happens to
produce -- is the contractual ceiling every consumer must be able to hold.

What the current formula actually emits is much shorter:
``f"{event_type}:{tenant_id}:{shift_id}:{stamp}"``
(``created_idempotency_key`` / ``cancelled_idempotency_key``), i.e.
``len(event_type) + 1 + 36 + 1 + 36 + 1 + len(iso8601_stamp)``. With a
32-character ``2026-09-20T14:23:34.809586+00:00`` stamp that is 130 characters
for ``workforce.shift.created`` (23) and 132 for
``workforce.shift.cancelled`` (25).

Sizing this constant to 130 or 132 would be exactly the mistake that produced
the CAD outage: a column sized to a sample instead of to the contract. One
extra subsecond digit, a longer ``event_type``, or an offset-bearing stamp
would break it again, silently, in whichever service was narrowest.

Core's own producer path (``EventBus.publish``) defaults ``correlation_id`` to
``str(uuid.uuid4())`` -- 36 characters -- so Core-originated traffic sits far
below the ceiling. The ceiling is set by the widest producer, not by the
average one.

RAISING THIS VALUE is safe and cheap. On PostgreSQL, enlarging a
``varchar(n)`` length is a catalog-only change: no table rewrite and no index
rebuild, because no stored value can violate a looser bound.

LOWERING THIS VALUE IS A DATA-LOSS CHANGE, and every consuming migration is
expected to refuse it rather than truncate. A correlation id is the only
thread that ties a consumer's audit row back to the originating write in the
producing service; a truncated one is worse than a null, because it looks
joinable and is not.

To change it: widen the producer's declared column first, raise this constant
second, then let each consumer's repin carry the new width. Never the other
way round.
"""

from __future__ import annotations

BUS_CORRELATION_ID_MAX_LENGTH: int = 300
"""Widest ``correlation_id`` a Core event-bus producer may emit (Labor: 300)."""


__all__ = ["BUS_CORRELATION_ID_MAX_LENGTH"]
