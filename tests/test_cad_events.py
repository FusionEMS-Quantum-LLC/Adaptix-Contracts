"""CAD catalog event names.

Locks CAD_INTAKE_CANCELLED to the live CAD outbox emit
``cad.intake.cancelled``. Does not register a listener.
"""

from __future__ import annotations

from adaptix_contracts.cad.events import ALL_CAD_EVENTS, CAD_INTAKE_CANCELLED

_STALE_INTAKE_CANCELLED = "cad.medical_transport.intake.cancelled"
_LIVE_INTAKE_CANCELLED = "cad.intake.cancelled"


def test_cad_intake_cancelled_matches_live_cad_emit() -> None:
    assert CAD_INTAKE_CANCELLED == _LIVE_INTAKE_CANCELLED
    assert CAD_INTAKE_CANCELLED in ALL_CAD_EVENTS
    assert _STALE_INTAKE_CANCELLED not in ALL_CAD_EVENTS
    assert CAD_INTAKE_CANCELLED != _STALE_INTAKE_CANCELLED
