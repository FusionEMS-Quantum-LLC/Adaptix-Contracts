"""occurred_at on AdaptixEventEnvelope is normalized to UTC.

The field documents "ISO 8601 UTC" but was a free string with no enforcement,
so a tz-naive or non-UTC timestamp could be misread as UTC by a consumer. The
validator normalizes only the incorrect cases and never rejects, so no existing
producer can break.
"""

from __future__ import annotations

from datetime import datetime, timezone

from adaptix_contracts.events.envelope import AdaptixEventEnvelope


def _envelope(occurred_at: str) -> AdaptixEventEnvelope:
    return AdaptixEventEnvelope(
        event_type="test.event",
        tenant_id="t1",
        source_service="tests",
        occurred_at=occurred_at,
    )


def test_naive_timestamp_is_stamped_utc() -> None:
    env = _envelope("2026-01-01T12:00:00")
    assert env.occurred_at == "2026-01-01T12:00:00+00:00"
    # And it now parses as an aware, UTC datetime.
    assert datetime.fromisoformat(
        env.occurred_at
    ).utcoffset() == timezone.utc.utcoffset(None)


def test_already_utc_offset_is_unchanged() -> None:
    env = _envelope("2026-01-01T12:00:00+00:00")
    assert env.occurred_at == "2026-01-01T12:00:00+00:00"


def test_zulu_is_left_unchanged_but_is_utc() -> None:
    # "Z" is already UTC; the representation is preserved (no churn), and it
    # still parses to a zero-offset instant.
    env = _envelope("2026-01-01T12:00:00Z")
    assert env.occurred_at == "2026-01-01T12:00:00Z"
    assert datetime.fromisoformat(env.occurred_at).utcoffset().total_seconds() == 0


def test_non_utc_offset_is_converted_to_utc_same_instant() -> None:
    env = _envelope("2026-01-01T12:00:00+05:00")
    # Same instant, expressed in UTC.
    assert env.occurred_at == "2026-01-01T07:00:00+00:00"
    original = datetime.fromisoformat("2026-01-01T12:00:00+05:00")
    assert datetime.fromisoformat(env.occurred_at) == original


def test_unparseable_value_is_left_unchanged_not_rejected() -> None:
    # A malformed timestamp must never raise a ValidationError (that would break
    # an existing producer); it passes through untouched.
    env = _envelope("not-a-timestamp")
    assert env.occurred_at == "not-a-timestamp"


def test_default_factory_output_is_already_utc_and_unchanged() -> None:
    env = AdaptixEventEnvelope(
        event_type="test.event", tenant_id="t1", source_service="tests"
    )
    parsed = datetime.fromisoformat(env.occurred_at)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset().total_seconds() == 0
