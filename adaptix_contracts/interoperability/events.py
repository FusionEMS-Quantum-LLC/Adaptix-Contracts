"""Canonical event names emitted by the interoperability control plane."""
from __future__ import annotations

from typing import Final

INTEROPERABILITY_PEER_CREATED: Final[str] = "interoperability.peer.created"
INTEROPERABILITY_PEER_VERIFIED: Final[str] = "interoperability.peer.verified"
INTEROPERABILITY_PEER_REVOKED: Final[str] = "interoperability.peer.revoked"
INTEROPERABILITY_TRUST_ACTIVATED: Final[str] = "interoperability.trust.activated"
INTEROPERABILITY_TRUST_REVOKED: Final[str] = "interoperability.trust.revoked"
INTEROPERABILITY_INCIDENT_LINK_SUGGESTED: Final[str] = "interoperability.incident.link.suggested"
INTEROPERABILITY_INCIDENT_LINK_CONFIRMED: Final[str] = "interoperability.incident.link.confirmed"
INTEROPERABILITY_INCIDENT_LINK_REJECTED: Final[str] = "interoperability.incident.link.rejected"
INTEROPERABILITY_EXCHANGE_QUEUED: Final[str] = "interoperability.exchange.queued"
INTEROPERABILITY_EXCHANGE_SENT: Final[str] = "interoperability.exchange.sent"
INTEROPERABILITY_EXCHANGE_DELIVERED: Final[str] = "interoperability.exchange.delivered"
INTEROPERABILITY_EXCHANGE_ACKNOWLEDGED: Final[str] = "interoperability.exchange.acknowledged"
INTEROPERABILITY_EXCHANGE_FAILED: Final[str] = "interoperability.exchange.failed"
INTEROPERABILITY_EXCHANGE_DEAD_LETTERED: Final[str] = "interoperability.exchange.dead_lettered"
INTEROPERABILITY_EXCHANGE_REPLAYED: Final[str] = "interoperability.exchange.replayed"
INTEROPERABILITY_MAPPING_COMPLETED: Final[str] = "interoperability.mapping.completed"
INTEROPERABILITY_MAPPING_FAILED: Final[str] = "interoperability.mapping.failed"

INTEROPERABILITY_EVENTS: Final[dict[str, dict[str, object]]] = {
    event_type: {"version": "1.0", "source_service": "core"}
    for event_type in (
        INTEROPERABILITY_PEER_CREATED,
        INTEROPERABILITY_PEER_VERIFIED,
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
}

__all__ = [name for name in globals() if name.startswith("INTEROPERABILITY_")]
