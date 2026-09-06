"""Canonical event names for the AdaptixCore interoperability fabric.

These 23 constants are DELIBERATELY NOT registered in
``adaptix_contracts.events.registry.ALL_EVENTS``.

Why: the event-producer drift test (``tests/test_event_producer_registry_drift.py``)
requires every registered event to cite a REAL producer file:line, the way
``events/registry.py``'s CAD/Fleet/Billing blocks do. Adaptix-Core-Service does
implement a substantial interoperability fabric
(``core_app/interoperability/{peer_auth,peer_verification,peer_ingress,
exchange_routes,delivery_worker,tenant_signing_routes}.py``), but a 2026-09-05
audit did not locate, within its search budget, the exact file:line where any
of these 23 dotted strings is constructed as an ``event_type`` literal — so a
citation here would either be fabricated or would have to point at inferred
call sites rather than a verified construction line. Neither is acceptable
per the drift test's own stated purpose (catching the 64-entry
source_service-mismatch class of drift the registry's docstring records).

Register each constant, with its real producer's file:line, in the same pull
request that adds the citation — see ``adaptix_contracts.cad_connect.events``
/ ``adaptix_contracts.qa.events`` for the same staged-contract pattern this
module now follows.
"""

from __future__ import annotations

from typing import Final

INTEROPERABILITY_PEER_CREATED: Final[str] = "interoperability.peer.created"
INTEROPERABILITY_PEER_VERIFIED: Final[str] = "interoperability.peer.verified"
INTEROPERABILITY_PEER_PAUSED: Final[str] = "interoperability.peer.paused"
INTEROPERABILITY_PEER_RESUMED: Final[str] = "interoperability.peer.resumed"
INTEROPERABILITY_PEER_REVOKED: Final[str] = "interoperability.peer.revoked"
INTEROPERABILITY_TRUST_ACTIVATED: Final[str] = "interoperability.trust.activated"
INTEROPERABILITY_TRUST_REVOKED: Final[str] = "interoperability.trust.revoked"
INTEROPERABILITY_INCIDENT_LINK_SUGGESTED: Final[str] = (
    "interoperability.incident.link.suggested"
)
INTEROPERABILITY_INCIDENT_LINK_CONFIRMED: Final[str] = (
    "interoperability.incident.link.confirmed"
)
INTEROPERABILITY_INCIDENT_LINK_REJECTED: Final[str] = (
    "interoperability.incident.link.rejected"
)
INTEROPERABILITY_EXCHANGE_QUEUED: Final[str] = "interoperability.exchange.queued"
INTEROPERABILITY_EXCHANGE_SENT: Final[str] = "interoperability.exchange.sent"
INTEROPERABILITY_EXCHANGE_DELIVERED: Final[str] = "interoperability.exchange.delivered"
INTEROPERABILITY_EXCHANGE_ACKNOWLEDGED: Final[str] = (
    "interoperability.exchange.acknowledged"
)
INTEROPERABILITY_EXCHANGE_FAILED: Final[str] = "interoperability.exchange.failed"
INTEROPERABILITY_EXCHANGE_DEAD_LETTERED: Final[str] = (
    "interoperability.exchange.dead_lettered"
)
INTEROPERABILITY_EXCHANGE_REPLAYED: Final[str] = "interoperability.exchange.replayed"
INTEROPERABILITY_MAPPING_COMPLETED: Final[str] = "interoperability.mapping.completed"
INTEROPERABILITY_MAPPING_FAILED: Final[str] = "interoperability.mapping.failed"

# Patient-Identity owns durable linkage between a local EMPI identity and an
# opaque external/federated patient reference. Discovery is intentionally a
# candidate state: it never asserts that two patients are the same person.
PATIENT_IDENTITY_FEDERATED_REFERENCE_DISCOVERED: Final[str] = (
    "patient.identity.federated_reference.discovered"
)
PATIENT_IDENTITY_FEDERATED_REFERENCE_CONFIRMED: Final[str] = (
    "patient.identity.federated_reference.confirmed"
)
PATIENT_IDENTITY_FEDERATED_REFERENCE_REJECTED: Final[str] = (
    "patient.identity.federated_reference.rejected"
)
PATIENT_IDENTITY_FEDERATED_REFERENCE_UNLINKED: Final[str] = (
    "patient.identity.federated_reference.unlinked"
)

_CORE_INTEROPERABILITY_EVENTS: Final[tuple[str, ...]] = (
    INTEROPERABILITY_PEER_CREATED,
    INTEROPERABILITY_PEER_VERIFIED,
    INTEROPERABILITY_PEER_PAUSED,
    INTEROPERABILITY_PEER_RESUMED,
    INTEROPERABILITY_PEER_REVOKED,
    INTEROPERABILITY_TRUST_ACTIVATED,
    INTEROPERABILITY_TRUST_REVOKED,
    INTEROPERABILITY_INCIDENT_LINK_SUGGESTED,
    INTEROPERABILITY_INCIDENT_LINK_CONFIRMED,
    INTEROPERABILITY_INCIDENT_LINK_REJECTED,
    INTEROPERABILITY_EXCHANGE_QUEUED,
    INTEROPERABILITY_EXCHANGE_SENT,
    INTEROPERABILITY_EXCHANGE_DELIVERED,
    INTEROPERABILITY_EXCHANGE_ACKNOWLEDGED,
    INTEROPERABILITY_EXCHANGE_FAILED,
    INTEROPERABILITY_EXCHANGE_DEAD_LETTERED,
    INTEROPERABILITY_EXCHANGE_REPLAYED,
    INTEROPERABILITY_MAPPING_COMPLETED,
    INTEROPERABILITY_MAPPING_FAILED,
)

INTEROPERABILITY_EVENTS: Final[dict[str, dict[str, object]]] = {
    event_type: {"version": "1.0", "source_service": "core"}
    for event_type in _CORE_INTEROPERABILITY_EVENTS
}
INTEROPERABILITY_EVENTS.update(
    {
        PATIENT_IDENTITY_FEDERATED_REFERENCE_DISCOVERED: {
            "version": "1.0",
            "source_service": "patient-identity",
        },
        PATIENT_IDENTITY_FEDERATED_REFERENCE_CONFIRMED: {
            "version": "1.0",
            "source_service": "patient-identity",
        },
        PATIENT_IDENTITY_FEDERATED_REFERENCE_REJECTED: {
            "version": "1.0",
            "source_service": "patient-identity",
        },
        PATIENT_IDENTITY_FEDERATED_REFERENCE_UNLINKED: {
            "version": "1.0",
            "source_service": "patient-identity",
        },
    }
)

__all__ = [
    name
    for name in globals()
    if name.startswith("INTEROPERABILITY_")
    or name.startswith("PATIENT_IDENTITY_FEDERATED_")
]
