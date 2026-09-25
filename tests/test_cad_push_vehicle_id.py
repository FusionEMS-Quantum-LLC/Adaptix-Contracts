"""CadPushRequestedEvent carries the assigned vehicle (5.28.0, finding 40 lineage)."""

from datetime import UTC, datetime

from adaptix_contracts.schemas.transport_contracts import CadPushRequestedEvent

_BASE = {
    "trip_id": "trip-1",
    "request_id": "req-1",
    "tenant_id": "t-1",
    "pushed_at": datetime(2026, 9, 25, tzinfo=UTC),
}


def test_vehicle_id_is_carried() -> None:
    event = CadPushRequestedEvent(
        **_BASE, unit_id="unit-7", vehicle_id="veh-42", crew_ids=["c-1", "c-2"]
    )
    assert event.vehicle_id == "veh-42"
    assert (
        CadPushRequestedEvent.model_validate_json(event.model_dump_json()).vehicle_id
        == "veh-42"
    )


def test_an_older_producer_without_vehicle_id_still_validates() -> None:
    assert CadPushRequestedEvent(**_BASE).vehicle_id is None
