"""Contract tests for provider adapters (shared platform primitive D)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from adaptix_contracts import schemas
from adaptix_contracts.schemas.provider_adapter_contracts import (
    ProviderOperationRecord,
    ProviderOperationState,
    ProviderRetryability,
    ProviderTransportResult,
    is_safe_to_retry_without_idempotency,
    is_terminal,
    requires_reconciliation,
)
import pytest
from pydantic import ValidationError

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)


def _record(**overrides: object) -> ProviderOperationRecord:
    payload: dict[str, object] = {
        "provider_name": "stedi",
        "adaptix_operation_id": "op-1",
        "tenant_id": "tenant-a",
        "requested_at": NOW,
        "request_hash": "sha256:req",
        "correlation_id": "corr-1",
        "idempotency_key": "idem-1",
        "canonical_status": ProviderOperationState.ACCEPTED,
    }
    payload.update(overrides)
    return ProviderOperationRecord(**payload)  # type: ignore[arg-type]


class TestTerminality:
    @pytest.mark.parametrize(
        "state",
        [
            ProviderOperationState.REJECTED,
            ProviderOperationState.COMPLETED,
            ProviderOperationState.FAILED,
        ],
    )
    def test_authoritative_answers_are_terminal(
        self, state: ProviderOperationState
    ) -> None:
        assert is_terminal(state)

    @pytest.mark.parametrize(
        "state",
        [
            ProviderOperationState.REQUESTED,
            ProviderOperationState.ACCEPTED,
            ProviderOperationState.PENDING,
            ProviderOperationState.UNKNOWN,
            ProviderOperationState.RECONCILIATION_REQUIRED,
        ],
    )
    def test_in_flight_states_are_not_terminal(
        self, state: ProviderOperationState
    ) -> None:
        assert not is_terminal(state)

    def test_accepted_is_not_completed(self) -> None:
        """The provider took the request; that is not a business outcome."""

        assert not is_terminal(ProviderOperationState.ACCEPTED)

    def test_unknown_state_is_not_terminal(self) -> None:
        assert not is_terminal("something_the_provider_invented")


class TestReconciliation:
    @pytest.mark.parametrize(
        "state",
        [
            ProviderOperationState.UNKNOWN,
            ProviderOperationState.RECONCILIATION_REQUIRED,
        ],
    )
    def test_ambiguous_states_require_reconciliation(
        self, state: ProviderOperationState
    ) -> None:
        assert requires_reconciliation(state)

    def test_completed_needs_no_reconciliation(self) -> None:
        assert not requires_reconciliation(ProviderOperationState.COMPLETED)

    def test_unrecognised_state_requires_reconciliation(self) -> None:
        """Not knowing what a state means is itself a reason to check."""

        assert requires_reconciliation("provider_specific_limbo")

    def test_record_exposes_the_same_answer(self) -> None:
        record = _record(canonical_status=ProviderOperationState.UNKNOWN)
        assert record.requires_reconciliation()


class TestRetrySafety:
    @pytest.mark.parametrize(
        "state",
        [ProviderOperationState.REQUESTED, ProviderOperationState.REJECTED],
    )
    def test_states_with_no_side_effect_are_safe(
        self, state: ProviderOperationState
    ) -> None:
        assert is_safe_to_retry_without_idempotency(state)

    def test_unknown_is_never_safe_to_blind_retry(self) -> None:
        """This is how a claim gets submitted twice."""

        assert not is_safe_to_retry_without_idempotency(ProviderOperationState.UNKNOWN)

    @pytest.mark.parametrize(
        "state",
        [
            ProviderOperationState.ACCEPTED,
            ProviderOperationState.PENDING,
            ProviderOperationState.COMPLETED,
            ProviderOperationState.FAILED,
            ProviderOperationState.RECONCILIATION_REQUIRED,
        ],
    )
    def test_every_other_state_needs_an_idempotency_key(
        self, state: ProviderOperationState
    ) -> None:
        assert not is_safe_to_retry_without_idempotency(state)

    def test_unrecognised_state_is_not_safe(self) -> None:
        assert not is_safe_to_retry_without_idempotency("mystery")


class TestRecordInvariants:
    def test_idempotency_key_is_required(self) -> None:
        """Optional would let a retry loop duplicate a provider side effect."""

        assert ProviderOperationRecord.model_fields["idempotency_key"].is_required()

    def test_transport_success_may_not_leave_status_at_requested(self) -> None:
        with pytest.raises(ValidationError, match="ACCEPTED at minimum"):
            _record(
                canonical_status=ProviderOperationState.REQUESTED,
                transport=ProviderTransportResult(succeeded=True, status_code=200),
            )

    def test_transport_success_with_accepted_status_is_valid(self) -> None:
        record = _record(
            transport=ProviderTransportResult(
                succeeded=True, status_code=200, latency_ms=120
            )
        )
        assert record.canonical_status is ProviderOperationState.ACCEPTED

    def test_transport_failure_may_map_to_unknown(self) -> None:
        """A timeout is ambiguous, not a failure."""

        record = _record(
            canonical_status=ProviderOperationState.UNKNOWN,
            transport=ProviderTransportResult(succeeded=False, error_class="timeout"),
        )
        assert record.requires_reconciliation()

    def test_response_may_not_predate_the_request(self) -> None:
        with pytest.raises(ValidationError, match="responded_at precedes"):
            _record(responded_at=NOW - timedelta(seconds=1))

    def test_retry_after_must_record_when(self) -> None:
        with pytest.raises(ValidationError, match="RETRY_AFTER requires"):
            _record(retryability=ProviderRetryability.RETRY_AFTER)

    def test_retry_after_with_a_time_is_valid(self) -> None:
        record = _record(
            retryability=ProviderRetryability.RETRY_AFTER,
            next_reconciliation_at=NOW + timedelta(minutes=30),
        )
        assert record.next_reconciliation_at is not None

    def test_retryability_defaults_to_unknown(self) -> None:
        assert _record().retryability is ProviderRetryability.UNKNOWN

    def test_unknown_field_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _record(raw_response_body="never store the payload here")


def test_transport_result_carries_a_class_not_raw_error_text() -> None:
    assert "error_class" in ProviderTransportResult.model_fields
    assert "error_message" not in ProviderTransportResult.model_fields


def test_surface_is_exported_from_the_package_root() -> None:
    for name in (
        "ProviderOperationRecord",
        "ProviderOperationState",
        "ProviderRetryability",
        "ProviderTransportResult",
        "TERMINAL_PROVIDER_STATES",
        "RECONCILIATION_PROVIDER_STATES",
    ):
        assert name in schemas.__all__
        assert hasattr(schemas, name)
