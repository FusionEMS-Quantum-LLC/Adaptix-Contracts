"""Blood Ops lifecycle and cold-chain excursion state machines (FND-001).

Both expected tables are written out independently of the module's own
tables so a changed transition is caught, not re-read.
"""

from __future__ import annotations

from itertools import product

import pytest

from adaptix_contracts.blood_ops.lifecycle import (
    BLOOD_UNIT_TERMINAL_STATES,
    COLD_CHAIN_USABLE_STATES,
    BloodOpsTransitionError,
    BloodUnitLifecycleState,
    ColdChainExcursionState,
    ColdChainReadingClassification,
    validate_blood_unit_transition,
    validate_cold_chain_excursion_transition,
)

U = BloodUnitLifecycleState
C = ColdChainExcursionState

EXPECTED_UNIT_TRANSITIONS: dict[
    BloodUnitLifecycleState, set[BloodUnitLifecycleState]
] = {
    U.RECEIVED: {U.QUARANTINED, U.AVAILABLE, U.EXPIRED, U.RETURNED, U.DESTROYED},
    U.QUARANTINED: {U.AVAILABLE, U.EXPIRED, U.RETURNED, U.DESTROYED},
    U.AVAILABLE: {U.ASSIGNED, U.QUARANTINED, U.EXPIRED, U.RETURNED, U.DESTROYED},
    U.ASSIGNED: {
        U.AVAILABLE,
        U.QUARANTINED,
        U.TRANSFUSED,
        U.EXPIRED,
        U.RETURNED,
        U.DESTROYED,
    },
    U.EXPIRED: {U.RETURNED, U.DESTROYED},
    U.TRANSFUSED: set(),
    U.RETURNED: set(),
    U.DESTROYED: set(),
}

EXPECTED_EXCURSION_TRANSITIONS: dict[
    ColdChainExcursionState, set[ColdChainExcursionState]
] = {
    C.NORMAL: {C.EXCURSION_DETECTED, C.SENSOR_FAILURE},
    C.EXCURSION_DETECTED: {C.QUARANTINED, C.DISCARDED},
    C.SENSOR_FAILURE: {C.EXCURSION_DETECTED, C.QUARANTINED, C.DISCARDED},
    C.QUARANTINED: {C.RELEASED, C.DISCARDED},
    C.RELEASED: {C.EXCURSION_DETECTED, C.SENSOR_FAILURE},
    C.DISCARDED: set(),
}


def test_unit_lifecycle_runs_from_received_to_destroyed() -> None:
    states = [state.value for state in BloodUnitLifecycleState]
    assert states[0] == "RECEIVED"
    assert states[-1] == "DESTROYED"
    assert set(states) == {
        "RECEIVED",
        "QUARANTINED",
        "AVAILABLE",
        "ASSIGNED",
        "EXPIRED",
        "TRANSFUSED",
        "RETURNED",
        "DESTROYED",
    }


@pytest.mark.parametrize(
    ("current", "target"),
    list(product(BloodUnitLifecycleState, BloodUnitLifecycleState)),
    ids=lambda state: state.value,
)
def test_every_unit_transition_pair_matches_the_expected_table(
    current: BloodUnitLifecycleState, target: BloodUnitLifecycleState
) -> None:
    if target in EXPECTED_UNIT_TRANSITIONS[current]:
        validate_blood_unit_transition(current, target)
    else:
        with pytest.raises(BloodOpsTransitionError):
            validate_blood_unit_transition(current, target)


def test_unit_terminal_states() -> None:
    assert BLOOD_UNIT_TERMINAL_STATES == {U.TRANSFUSED, U.RETURNED, U.DESTROYED}


@pytest.mark.parametrize("target", list(BloodUnitLifecycleState), ids=lambda s: s.value)
def test_a_unit_enters_custody_only_as_received(
    target: BloodUnitLifecycleState,
) -> None:
    if target is U.RECEIVED:
        validate_blood_unit_transition(None, target)
    else:
        with pytest.raises(
            BloodOpsTransitionError, match="enters agency custody as RECEIVED"
        ):
            validate_blood_unit_transition(None, target)


def test_only_an_assigned_unit_can_be_transfused() -> None:
    for state in BloodUnitLifecycleState:
        if state is U.ASSIGNED:
            validate_blood_unit_transition(state, U.TRANSFUSED)
        else:
            with pytest.raises(BloodOpsTransitionError):
                validate_blood_unit_transition(state, U.TRANSFUSED)


def test_excursion_lifecycle_runs_from_normal_to_discarded() -> None:
    states = [state.value for state in ColdChainExcursionState]
    assert states[0] == "NORMAL"
    assert states[-1] == "DISCARDED"


def test_sensor_failure_is_distinct_from_an_excursion() -> None:
    assert C.SENSOR_FAILURE is not C.EXCURSION_DETECTED
    assert C.SENSOR_FAILURE.value != C.EXCURSION_DETECTED.value
    assert (
        ColdChainReadingClassification.SENSOR_FAILURE
        is not ColdChainReadingClassification.OUT_OF_RANGE
    )
    assert C.SENSOR_FAILURE not in COLD_CHAIN_USABLE_STATES


@pytest.mark.parametrize(
    ("current", "target"),
    list(product(ColdChainExcursionState, ColdChainExcursionState)),
    ids=lambda state: state.value,
)
def test_every_excursion_transition_pair_matches_the_expected_table(
    current: ColdChainExcursionState, target: ColdChainExcursionState
) -> None:
    if target in EXPECTED_EXCURSION_TRANSITIONS[current]:
        validate_cold_chain_excursion_transition(current, target)
    else:
        with pytest.raises(BloodOpsTransitionError):
            validate_cold_chain_excursion_transition(current, target)


@pytest.mark.parametrize("detection", [C.EXCURSION_DETECTED, C.SENSOR_FAILURE])
def test_a_detection_never_closes_itself(detection: ColdChainExcursionState) -> None:
    for target in (C.NORMAL, C.RELEASED):
        with pytest.raises(BloodOpsTransitionError):
            validate_cold_chain_excursion_transition(detection, target)


def test_usable_cold_chain_states() -> None:
    assert COLD_CHAIN_USABLE_STATES == {C.NORMAL, C.RELEASED}
