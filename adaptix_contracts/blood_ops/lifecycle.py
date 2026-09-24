"""Blood Ops vocabulary: unit lifecycle, cold-chain status and their transitions.

Two state machines live here, each with the one validator every producer and
consumer must use:

* :class:`BloodUnitLifecycleState` - where an agency-held blood unit is in its
  life, from ``RECEIVED`` into agency custody to a terminal ``TRANSFUSED``,
  ``RETURNED`` or ``DESTROYED``.
* :class:`ColdChainExcursionState` - whether the unit's temperature history is
  trustworthy, from ``NORMAL`` to a terminal ``DISCARDED``.

No temperature threshold appears anywhere in this package. The acceptable
storage band depends on the product, the container and the agency's medical
direction, so it is configuration owned by the producing service (a storage
profile), never a contract constant. A reading carries only the
classification the service made and the storage profile it used.

``SENSOR_FAILURE`` is distinct from an excursion on purpose. A failed sensor
means the temperature is UNKNOWN, which is neither in range nor out of range;
reporting it as either would be a false statement about the product.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final


class BloodUnitLifecycleState(StrEnum):
    """Lifecycle of one blood unit held by an EMS agency.

    * ``RECEIVED`` - accepted into agency custody from the issuing blood bank.
    * ``QUARANTINED`` - held back from use pending review (a cold-chain
      problem, a label or visual-inspection concern).
    * ``AVAILABLE`` - in agency storage and released for use.
    * ``ASSIGNED`` - loaded onto an apparatus for a shift or a mission.
    * ``EXPIRED`` - past its label expiry; can only be returned or destroyed.
    * ``TRANSFUSED`` - administered to a patient (terminal).
    * ``RETURNED`` - handed back to a blood bank or a receiving hospital
      (terminal for this agency).
    * ``DESTROYED`` - discarded and destroyed (terminal).
    """

    RECEIVED = "RECEIVED"
    QUARANTINED = "QUARANTINED"
    AVAILABLE = "AVAILABLE"
    ASSIGNED = "ASSIGNED"
    EXPIRED = "EXPIRED"
    TRANSFUSED = "TRANSFUSED"
    RETURNED = "RETURNED"
    DESTROYED = "DESTROYED"


_U = BloodUnitLifecycleState

#: Every permitted unit transition. A pair that is not listed is refused.
BLOOD_UNIT_TRANSITIONS: Final[
    dict[BloodUnitLifecycleState, frozenset[BloodUnitLifecycleState]]
] = {
    _U.RECEIVED: frozenset(
        {_U.QUARANTINED, _U.AVAILABLE, _U.EXPIRED, _U.RETURNED, _U.DESTROYED}
    ),
    _U.QUARANTINED: frozenset({_U.AVAILABLE, _U.EXPIRED, _U.RETURNED, _U.DESTROYED}),
    _U.AVAILABLE: frozenset(
        {_U.ASSIGNED, _U.QUARANTINED, _U.EXPIRED, _U.RETURNED, _U.DESTROYED}
    ),
    _U.ASSIGNED: frozenset(
        {
            _U.AVAILABLE,
            _U.QUARANTINED,
            _U.TRANSFUSED,
            _U.EXPIRED,
            _U.RETURNED,
            _U.DESTROYED,
        }
    ),
    _U.EXPIRED: frozenset({_U.RETURNED, _U.DESTROYED}),
    _U.TRANSFUSED: frozenset(),
    _U.RETURNED: frozenset(),
    _U.DESTROYED: frozenset(),
}

#: Lifecycle states no transition leaves.
BLOOD_UNIT_TERMINAL_STATES: Final[frozenset[BloodUnitLifecycleState]] = frozenset(
    state for state, targets in BLOOD_UNIT_TRANSITIONS.items() if not targets
)

#: Lifecycle states in which a unit can still reach a patient. A unit in one
#: of these states must have a usable cold chain.
BLOOD_UNIT_USABLE_STATES: Final[frozenset[BloodUnitLifecycleState]] = frozenset(
    {_U.AVAILABLE, _U.ASSIGNED}
)


class ColdChainExcursionState(StrEnum):
    """Cold-chain status of a blood unit (the excursion lifecycle).

    * ``NORMAL`` - every reading so far is in range.
    * ``EXCURSION_DETECTED`` - a reading was out of the storage profile's band.
    * ``SENSOR_FAILURE`` - no trustworthy reading: the temperature is unknown.
    * ``QUARANTINED`` - the unit is held while a person reviews the episode.
    * ``RELEASED`` - a person reviewed the episode and released the unit. The
      unit is usable again, but its history keeps the fact that it had one.
    * ``DISCARDED`` - a person reviewed the episode and the unit must be
      destroyed (terminal).
    """

    NORMAL = "NORMAL"
    EXCURSION_DETECTED = "EXCURSION_DETECTED"
    SENSOR_FAILURE = "SENSOR_FAILURE"
    QUARANTINED = "QUARANTINED"
    RELEASED = "RELEASED"
    DISCARDED = "DISCARDED"


_C = ColdChainExcursionState

#: Every permitted cold-chain transition. An episode never closes itself:
#: from a detection the only ways out are review (``QUARANTINED``) or
#: ``DISCARDED``, never straight back to ``NORMAL``.
COLD_CHAIN_EXCURSION_TRANSITIONS: Final[
    dict[ColdChainExcursionState, frozenset[ColdChainExcursionState]]
] = {
    _C.NORMAL: frozenset({_C.EXCURSION_DETECTED, _C.SENSOR_FAILURE}),
    _C.EXCURSION_DETECTED: frozenset({_C.QUARANTINED, _C.DISCARDED}),
    _C.SENSOR_FAILURE: frozenset({_C.EXCURSION_DETECTED, _C.QUARANTINED, _C.DISCARDED}),
    _C.QUARANTINED: frozenset({_C.RELEASED, _C.DISCARDED}),
    _C.RELEASED: frozenset({_C.EXCURSION_DETECTED, _C.SENSOR_FAILURE}),
    _C.DISCARDED: frozenset(),
}

#: Cold-chain states under which a unit may be used.
COLD_CHAIN_USABLE_STATES: Final[frozenset[ColdChainExcursionState]] = frozenset(
    {_C.NORMAL, _C.RELEASED}
)

#: Cold-chain states that open an episode needing review.
COLD_CHAIN_DETECTION_STATES: Final[frozenset[ColdChainExcursionState]] = frozenset(
    {_C.EXCURSION_DETECTED, _C.SENSOR_FAILURE}
)


class ColdChainReadingClassification(StrEnum):
    """How the producing service classified one temperature reading.

    ``SENSOR_FAILURE`` carries no temperature: the sensor reported a fault,
    went silent past its reporting interval, or returned a value it flagged
    as invalid.
    """

    IN_RANGE = "IN_RANGE"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    SENSOR_FAILURE = "SENSOR_FAILURE"


class BloodOpsTransitionError(ValueError):
    """A unit or cold-chain status was asked to make a transition not permitted."""


def validate_blood_unit_transition(
    current: BloodUnitLifecycleState | None, target: BloodUnitLifecycleState
) -> None:
    """Refuse a unit lifecycle transition the state machine does not permit.

    ``current=None`` means the unit is entering agency custody, which is only
    ever ``RECEIVED``. A transition to the same state is refused: a no-op is
    not a custody event.
    """

    if current is None:
        if target is not BloodUnitLifecycleState.RECEIVED:
            raise BloodOpsTransitionError(
                f"a blood unit enters agency custody as RECEIVED, not {target.value}"
            )
        return
    if target not in BLOOD_UNIT_TRANSITIONS[current]:
        raise BloodOpsTransitionError(
            f"blood unit cannot move from {current.value} to {target.value}"
        )


def validate_cold_chain_excursion_transition(
    current: ColdChainExcursionState, target: ColdChainExcursionState
) -> None:
    """Refuse a cold-chain transition the state machine does not permit."""

    if target not in COLD_CHAIN_EXCURSION_TRANSITIONS[current]:
        raise BloodOpsTransitionError(
            f"cold chain cannot move from {current.value} to {target.value}"
        )


__all__ = [
    "BLOOD_UNIT_TERMINAL_STATES",
    "BLOOD_UNIT_TRANSITIONS",
    "BLOOD_UNIT_USABLE_STATES",
    "COLD_CHAIN_DETECTION_STATES",
    "COLD_CHAIN_EXCURSION_TRANSITIONS",
    "COLD_CHAIN_USABLE_STATES",
    "BloodOpsTransitionError",
    "BloodUnitLifecycleState",
    "ColdChainReadingClassification",
    "ColdChainExcursionState",
    "validate_blood_unit_transition",
    "validate_cold_chain_excursion_transition",
]
