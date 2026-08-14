"""AdaptixCore Fire CAD Connect — domain event type constants.

These are the canonical wire strings for the CAD Connect import lifecycle. They
are defined here so every producer/consumer uses the same value, but they are
DELIBERATELY NOT YET registered in ``adaptix_contracts.events.registry.ALL_EVENTS``.

Why: the event-producer drift test (``tests/test_event_producer_registry_drift``)
requires every registered event to cite a REAL producer (file:line where it is
emitted). The producers live in the Fire-Service / Imports-Service and do not
exist yet. Each constant below is registered in ``events/registry.py`` in the
SAME pull request that adds its producer, with that producer's file:line
citation — so the drift test stays green and no event is registered ahead of a
real emitter. This is a staged contract, not a dead path.

Producer plan (register with citation when the emitter lands):
    CAD_CONNECT_SOURCE_CONNECTED        -> Fire-Service (connector configured/verified)
    CAD_CONNECT_PAYLOAD_RECEIVED        -> Imports-Service (payload accepted into the gateway)
    CAD_CONNECT_NORMALIZED              -> Imports-Service / Fire-Service (normalized record produced)
    CAD_CONNECT_REVIEW_REQUIRED         -> Fire-Service (import needs human review)
    CAD_CONNECT_APPLIED                 -> Fire-Service (approved import applied to a Fire incident)
    CAD_CONNECT_FAILED                  -> Imports-Service / Fire-Service (import failed/quarantined)
    CAD_CONNECT_MAPPING_PROFILE_ACTIVATED -> Fire-Service (agency mapping profile version activated)
"""

from __future__ import annotations

from typing import Final

CAD_CONNECT_SOURCE_CONNECTED: Final[str] = "cad_connect.source.connected"
CAD_CONNECT_PAYLOAD_RECEIVED: Final[str] = "cad_connect.payload.received"
CAD_CONNECT_NORMALIZED: Final[str] = "cad_connect.normalized"
CAD_CONNECT_REVIEW_REQUIRED: Final[str] = "cad_connect.review_required"
CAD_CONNECT_APPLIED: Final[str] = "cad_connect.applied"
CAD_CONNECT_FAILED: Final[str] = "cad_connect.failed"
CAD_CONNECT_MAPPING_PROFILE_ACTIVATED: Final[str] = (
    "cad_connect.mapping_profile.activated"
)

# The full set, for producer PRs to register against events.registry.ALL_EVENTS.
CAD_CONNECT_EVENT_TYPES: Final[tuple[str, ...]] = (
    CAD_CONNECT_SOURCE_CONNECTED,
    CAD_CONNECT_PAYLOAD_RECEIVED,
    CAD_CONNECT_NORMALIZED,
    CAD_CONNECT_REVIEW_REQUIRED,
    CAD_CONNECT_APPLIED,
    CAD_CONNECT_FAILED,
    CAD_CONNECT_MAPPING_PROFILE_ACTIVATED,
)


__all__ = [
    "CAD_CONNECT_SOURCE_CONNECTED",
    "CAD_CONNECT_PAYLOAD_RECEIVED",
    "CAD_CONNECT_NORMALIZED",
    "CAD_CONNECT_REVIEW_REQUIRED",
    "CAD_CONNECT_APPLIED",
    "CAD_CONNECT_FAILED",
    "CAD_CONNECT_MAPPING_PROFILE_ACTIVATED",
    "CAD_CONNECT_EVENT_TYPES",
]
