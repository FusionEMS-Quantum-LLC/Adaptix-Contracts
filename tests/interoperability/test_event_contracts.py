from adaptix_contracts.interoperability.events import INTEROPERABILITY_EVENTS


def test_interoperability_event_fragment_is_core_owned() -> None:
    assert len(INTEROPERABILITY_EVENTS) == 17
    assert "interoperability.exchange.acknowledged" in INTEROPERABILITY_EVENTS
    assert "interoperability.exchange.replayed" in INTEROPERABILITY_EVENTS
    assert all(meta["version"] == "1.0" for meta in INTEROPERABILITY_EVENTS.values())
    assert all(meta["source_service"] == "core" for meta in INTEROPERABILITY_EVENTS.values())
