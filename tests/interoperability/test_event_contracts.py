from adaptix_contracts.interoperability.events import INTEROPERABILITY_EVENTS


def test_interoperability_event_fragment_has_explicit_producer_ownership() -> None:
    assert len(INTEROPERABILITY_EVENTS) == 23
    assert "interoperability.peer.paused" in INTEROPERABILITY_EVENTS
    assert "interoperability.peer.resumed" in INTEROPERABILITY_EVENTS
    assert "interoperability.exchange.acknowledged" in INTEROPERABILITY_EVENTS
    assert "interoperability.exchange.replayed" in INTEROPERABILITY_EVENTS
    assert "patient.identity.federated_reference.discovered" in INTEROPERABILITY_EVENTS
    assert "patient.identity.federated_reference.confirmed" in INTEROPERABILITY_EVENTS
    assert "patient.identity.federated_reference.rejected" in INTEROPERABILITY_EVENTS
    assert "patient.identity.federated_reference.unlinked" in INTEROPERABILITY_EVENTS
    assert all(meta["version"] == "1.0" for meta in INTEROPERABILITY_EVENTS.values())
    assert all(
        meta["source_service"] == "core"
        for event_type, meta in INTEROPERABILITY_EVENTS.items()
        if event_type.startswith("interoperability.")
    )
    assert all(
        meta["source_service"] == "patient-identity"
        for event_type, meta in INTEROPERABILITY_EVENTS.items()
        if event_type.startswith("patient.identity.federated_reference.")
    )
