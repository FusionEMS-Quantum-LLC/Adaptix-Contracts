"""The Fire reporting event types added in 5.36.0.

Fire publishes these through :class:`AnalyticsPublisher`, which refuses any
event type missing from the catalog and any payload missing the contract's
``value_field``. These tests pin the exact strings and fields both sides read:
Adaptix-Fire-Service (producer) and Adaptix-Analytics-Service (fire reports,
ISO PPC evidence pack).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from adaptix_contracts.analytics_events import (
    ALL_EVENT_TYPES,
    FIRE_HOSE_TEST,
    FIRE_HYDRANT_FLOW_TEST,
    FIRE_INCIDENT_CLOSED,
    FIRE_PREPLAN_REVIEW,
    FIRE_PUMP_TEST,
    payload_contract,
)
from adaptix_contracts.analytics_publisher import AnalyticsEvent, _validate_event

_TENANT = "33333333-3333-3333-3333-333333333333"

_EXPECTED = {
    FIRE_INCIDENT_CLOSED: ("fire.incident_closed", "duration_minutes", "minutes", None),
    FIRE_HOSE_TEST: ("fire.hose_test", "result", "category", "passed"),
    FIRE_HYDRANT_FLOW_TEST: (
        "fire.hydrant_flow_test",
        "observed_flow_gpm",
        "gpm",
        None,
    ),
    FIRE_PREPLAN_REVIEW: ("fire.preplan_review", "status", "category", "active"),
    FIRE_PUMP_TEST: ("fire.pump_test", "result", "category", "passed"),
}


@pytest.mark.parametrize("event_type", sorted(_EXPECTED))
def test_fire_event_type_is_catalogued_with_its_exact_contract(event_type: str) -> None:
    name, value_field, unit, truthy = _EXPECTED[event_type]
    assert event_type == name
    assert event_type in ALL_EVENT_TYPES
    contract = payload_contract(event_type)
    assert (contract.value_field, contract.unit, contract.rate_truthy) == (
        value_field,
        unit,
        truthy,
    )


@pytest.mark.parametrize("event_type", sorted(_EXPECTED))
def test_publisher_accepts_payload_carrying_the_value_field(event_type: str) -> None:
    value_field = _EXPECTED[event_type][1]
    _validate_event(
        AnalyticsEvent(
            event_type=event_type,
            tenant_id=_TENANT,
            payload={value_field: None},
            occurred_at=datetime.now(UTC),
        )
    )


@pytest.mark.parametrize("event_type", sorted(_EXPECTED))
def test_publisher_refuses_payload_without_the_value_field(event_type: str) -> None:
    with pytest.raises(ValueError, match=_EXPECTED[event_type][1]):
        _validate_event(
            AnalyticsEvent(
                event_type=event_type,
                tenant_id=_TENANT,
                payload={"unrelated": 1},
                occurred_at=datetime.now(UTC),
            )
        )


def test_hose_and_pump_results_share_the_fire_pass_vocabulary() -> None:
    """Fire's HoseTest.result vocabulary is passed / failed / condemned."""
    assert payload_contract(FIRE_HOSE_TEST).rate_truthy == "passed"
    assert payload_contract(FIRE_PUMP_TEST).rate_truthy == "passed"
