"""Exchange delivery lifecycle contract (FND-001).

The expected transition table below is written out independently of
``EXCHANGE_DELIVERY_TRANSITIONS`` so the test can catch a changed table, not
just re-read it.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from itertools import product

import pytest
from pydantic import ValidationError

from adaptix_contracts.interoperability.delivery import (
    EXCHANGE_DELIVERY_TERMINAL_STATES,
    INTEROPERABILITY_EXCHANGE_DELIVERY_STATE_CHANGED,
    ExchangeDelivery,
    ExchangeDeliveryState,
    ExchangeDeliveryStateChangedPayload,
    ExchangeDeliveryTransitionError,
    validate_exchange_delivery_transition,
)
from adaptix_contracts.interoperability.gateway import ExchangeGatewayKind

S = ExchangeDeliveryState
NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)

EXPECTED_TRANSITIONS: dict[ExchangeDeliveryState, set[ExchangeDeliveryState]] = {
    S.DRAFT: {S.QUEUED},
    S.QUEUED: {S.SENDING},
    S.SENDING: {
        S.DELIVERED,
        S.ACKNOWLEDGED,
        S.REJECTED,
        S.RETRYABLE_FAILURE,
        S.PERMANENT_FAILURE,
    },
    S.DELIVERED: {S.ACKNOWLEDGED, S.REJECTED},
    S.ACKNOWLEDGED: set(),
    S.REJECTED: set(),
    S.RETRYABLE_FAILURE: {S.QUEUED, S.DEAD_LETTER},
    S.PERMANENT_FAILURE: {S.DEAD_LETTER},
    S.DEAD_LETTER: {S.QUEUED},
}


def test_delivery_state_vocabulary_is_exactly_the_card() -> None:
    assert [state.value for state in ExchangeDeliveryState] == [
        "DRAFT",
        "QUEUED",
        "SENDING",
        "DELIVERED",
        "ACKNOWLEDGED",
        "REJECTED",
        "RETRYABLE_FAILURE",
        "PERMANENT_FAILURE",
        "DEAD_LETTER",
    ]


@pytest.mark.parametrize(
    ("current", "target"),
    list(product(ExchangeDeliveryState, ExchangeDeliveryState)),
    ids=lambda state: state.value,
)
def test_every_transition_pair_matches_the_expected_table(
    current: ExchangeDeliveryState, target: ExchangeDeliveryState
) -> None:
    if target in EXPECTED_TRANSITIONS[current]:
        validate_exchange_delivery_transition(current, target)
    else:
        with pytest.raises(ExchangeDeliveryTransitionError):
            validate_exchange_delivery_transition(current, target)


def test_terminal_states_are_acknowledged_and_rejected_only() -> None:
    assert EXCHANGE_DELIVERY_TERMINAL_STATES == {S.ACKNOWLEDGED, S.REJECTED}


def test_a_permanent_failure_is_never_retried_automatically() -> None:
    with pytest.raises(ExchangeDeliveryTransitionError):
        validate_exchange_delivery_transition(S.PERMANENT_FAILURE, S.QUEUED)


def test_a_dead_letter_can_be_replayed_by_an_operator() -> None:
    validate_exchange_delivery_transition(S.DEAD_LETTER, S.QUEUED)


@pytest.mark.parametrize("state", list(ExchangeDeliveryState), ids=lambda s: s.value)
def test_a_delivery_is_created_only_as_draft_or_queued(
    state: ExchangeDeliveryState,
) -> None:
    if state in {S.DRAFT, S.QUEUED}:
        validate_exchange_delivery_transition(None, state)
    else:
        with pytest.raises(
            ExchangeDeliveryTransitionError, match="created as DRAFT or QUEUED"
        ):
            validate_exchange_delivery_transition(None, state)


def _delivery(**overrides: object) -> ExchangeDelivery:
    data: dict[str, object] = {
        "delivery_id": "del-1",
        "tenant_id": "tenant-cert-a",
        "exchange_id": "ex-1",
        "gateway_id": "gw-1",
        "gateway_kind": ExchangeGatewayKind.HOSPITAL_INTERFACE,
        "state": S.QUEUED,
        "payload_sha256": "a" * 64,
        "idempotency_key": "ex-1:gw-1",
        "attempt_count": 0,
        "max_attempts": 5,
        "correlation_id": "corr-1",
        "version": 1,
        "created_at": NOW,
        "updated_at": NOW,
    }
    data.update(overrides)
    return ExchangeDelivery.model_validate(data)


@pytest.mark.parametrize(
    "state",
    [S.REJECTED, S.RETRYABLE_FAILURE, S.PERMANENT_FAILURE, S.DEAD_LETTER],
    ids=lambda s: s.value,
)
def test_a_failure_state_carries_its_error_code(state: ExchangeDeliveryState) -> None:
    extra = {"next_attempt_at": NOW} if state is S.RETRYABLE_FAILURE else {}
    with pytest.raises(ValidationError, match="must carry error_code"):
        _delivery(state=state, attempt_count=1, **extra)
    assert _delivery(
        state=state, attempt_count=1, error_code="E_PEER_5XX", **extra
    ).error_code


def test_a_success_state_cannot_carry_an_error_code() -> None:
    with pytest.raises(ValidationError, match="cannot carry error_code"):
        _delivery(state=S.DELIVERED, attempt_count=1, error_code="E_OLD")


def test_acknowledged_names_its_acknowledgement() -> None:
    with pytest.raises(ValidationError, match="acknowledgement_id"):
        _delivery(state=S.ACKNOWLEDGED, attempt_count=1)
    assert (
        _delivery(
            state=S.ACKNOWLEDGED, attempt_count=1, acknowledgement_id="ack-1"
        ).acknowledgement_id
        == "ack-1"
    )


def test_retryable_failure_states_when_it_retries() -> None:
    with pytest.raises(ValidationError, match="next_attempt_at"):
        _delivery(state=S.RETRYABLE_FAILURE, attempt_count=1, error_code="E_TIMEOUT")


def test_attempts_never_exceed_the_budget_and_a_draft_made_none() -> None:
    with pytest.raises(ValidationError, match="cannot exceed max_attempts"):
        _delivery(attempt_count=6)
    with pytest.raises(ValidationError, match="DRAFT delivery has made no attempt"):
        _delivery(state=S.DRAFT, attempt_count=1)
    with pytest.raises(ValidationError):
        _delivery(attempt_count=True)


def test_delivery_binds_the_exact_payload_digest() -> None:
    with pytest.raises(ValidationError):
        _delivery(payload_sha256="A" * 64)
    with pytest.raises(ValidationError):
        _delivery(payload_sha256="a" * 63)


def test_delivery_refuses_payload_content() -> None:
    with pytest.raises(ValidationError, match="extra"):
        _delivery(payload={"patient_name": "Certification Patient"})


def test_updated_at_never_precedes_created_at() -> None:
    with pytest.raises(ValidationError, match="updated_at precedes created_at"):
        _delivery(updated_at=NOW - timedelta(seconds=1))


def _change(**overrides: object) -> ExchangeDeliveryStateChangedPayload:
    data: dict[str, object] = {
        "tenant_id": "tenant-cert-a",
        "delivery_id": "del-1",
        "exchange_id": "ex-1",
        "gateway_id": "gw-1",
        "gateway_kind": ExchangeGatewayKind.FHIR_API,
        "from_state": S.QUEUED,
        "to_state": S.SENDING,
        "attempt_count": 1,
        "delivery_version": 3,
        "occurred_at": NOW,
        "correlation_id": "corr-1",
        "idempotency_key": "del-1:v3",
    }
    data.update(overrides)
    return ExchangeDeliveryStateChangedPayload.model_validate(data)


def test_state_change_event_accepts_a_permitted_transition() -> None:
    assert _change().to_state is S.SENDING
    assert (
        _change(from_state=None, to_state=S.DRAFT, attempt_count=0).from_state is None
    )


def test_state_change_event_refuses_a_forbidden_transition() -> None:
    with pytest.raises(
        ValidationError, match="cannot move from ACKNOWLEDGED to QUEUED"
    ):
        _change(from_state=S.ACKNOWLEDGED, to_state=S.QUEUED)
    with pytest.raises(ValidationError, match="created as DRAFT or QUEUED"):
        _change(from_state=None, to_state=S.SENDING)


def test_state_change_to_a_failure_carries_its_error_code() -> None:
    with pytest.raises(ValidationError, match="must carry error_code"):
        _change(from_state=S.SENDING, to_state=S.PERMANENT_FAILURE)
    assert (
        _change(
            from_state=S.SENDING, to_state=S.PERMANENT_FAILURE, error_code="E_HTTP_400"
        ).error_code
        == "E_HTTP_400"
    )


def test_event_name() -> None:
    assert (
        INTEROPERABILITY_EXCHANGE_DELIVERY_STATE_CHANGED
        == "interoperability.exchange.delivery.state_changed"
    )
