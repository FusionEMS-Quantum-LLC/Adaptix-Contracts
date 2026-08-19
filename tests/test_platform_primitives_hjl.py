"""Contract tests for platform primitives H (AI flight recorder), J (offline
authority) and L (PHI-safe product telemetry), plus the additive causal/
sensitivity fields on the operational event envelope (primitive E)."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone

from adaptix_contracts import schemas
from adaptix_contracts.ai.audit import (
    FORBIDDEN_AI_RECORD_FIELDS,
    AIAuditEvent,
    AIExecutionFailureClass,
    AIModelExecutionRecord,
)
from adaptix_contracts.ai.connection import DataClassification
from adaptix_contracts.events.operational_envelope import (
    REQUIRED_ENVELOPE_FIELDS,
    SCHEMA_VERSION,
    OperationalEventEnvelope,
)
from adaptix_contracts.schemas.continuity_contracts import (
    ContinuityMode,
    OfflineAuthorityGrant,
    OfflineOperationEnvelope,
    OperationEnvelope,
    may_diverge_from_canonical,
)
from adaptix_contracts.schemas.metrics_contracts import (
    ProductTelemetryEvent,
    TelemetryOutcome,
    forbidden_telemetry_dimensions,
)
import pytest
from pydantic import ValidationError

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
LATER = NOW + timedelta(hours=8)


# ---------------------------------------------------------------------------
# H — AI model flight recorder
# ---------------------------------------------------------------------------


class TestAIFlightRecorder:
    def test_a_record_defaults_to_success_with_no_downstream_action(self) -> None:
        record = AIModelExecutionRecord(tenant_id="tenant-a", model_id="claude-opus-5")
        assert record.succeeded()
        assert not record.acted_on_anything()

    def test_a_record_that_changed_state_reports_it(self) -> None:
        record = AIModelExecutionRecord(
            tenant_id="tenant-a",
            downstream_action="epcr.narrative.proposed",
        )
        assert record.acted_on_anything()

    def test_a_failed_execution_reports_its_class(self) -> None:
        record = AIModelExecutionRecord(
            tenant_id="tenant-a",
            failure_class=AIExecutionFailureClass.PROVIDER_TIMEOUT,
        )
        assert not record.succeeded()

    def test_low_confidence_is_distinct_from_a_provider_error(self) -> None:
        """One is a model-quality signal, the other an availability problem."""

        assert (
            AIExecutionFailureClass.LOW_CONFIDENCE
            is not AIExecutionFailureClass.PROVIDER_ERROR
        )

    def test_the_record_carries_no_prompt_completion_or_reasoning(self) -> None:
        names = {f.name for f in dataclasses.fields(AIModelExecutionRecord)}
        assert not names & FORBIDDEN_AI_RECORD_FIELDS

    def test_the_existing_audit_event_also_carries_none_of_them(self) -> None:
        names = {f.name for f in dataclasses.fields(AIAuditEvent)}
        assert not names & FORBIDDEN_AI_RECORD_FIELDS

    def test_hashes_are_recorded_instead_of_content(self) -> None:
        names = {f.name for f in dataclasses.fields(AIModelExecutionRecord)}
        assert {"input_hash", "output_hash"} <= names

    def test_human_disposition_is_representable_and_optional(self) -> None:
        record = AIModelExecutionRecord(
            tenant_id="tenant-a", human_confirmation_receipt_id="rcpt-1"
        )
        assert record.human_confirmation_receipt_id == "rcpt-1"
        assert AIModelExecutionRecord().human_confirmation_receipt_id is None


# ---------------------------------------------------------------------------
# J — offline authority
# ---------------------------------------------------------------------------


def _grant(**overrides: object) -> OfflineAuthorityGrant:
    payload: dict[str, object] = {
        "grant_id": "grant-1",
        "tenant_id": "tenant-a",
        "device_id": "device-1",
        "device_cert_id": "cert-1",
        "user_id": "user-1",
        "allowed_operation_types": ["epcr.chart.update", "unit.status.change"],
        "issued_at": NOW,
        "expires_at": LATER,
    }
    payload.update(overrides)
    return OfflineAuthorityGrant(**payload)  # type: ignore[arg-type]


def _operation(**overrides: object) -> OfflineOperationEnvelope:
    payload: dict[str, object] = {
        "offline_operation_id": "op-1",
        "device_id": "device-1",
        "device_cert_id": "cert-1",
        "tenant_id": "tenant-a",
        "user_id": "user-1",
        "authority_grant_id": "grant-1",
        "issued_at": NOW,
        "expires_at": LATER,
        "operation_type": "epcr.chart.update",
        "resource_type": "epcr_chart",
        "resource_id": "chart-1",
        "base_state_version": 3,
        "local_sequence": 7,
        "payload_hash": "sha256:payload",
        "signature": "sig",
    }
    payload.update(overrides)
    return OfflineOperationEnvelope(**payload)  # type: ignore[arg-type]


class TestContinuityMode:
    def test_normal_mode_does_not_diverge(self) -> None:
        assert not may_diverge_from_canonical(ContinuityMode.NORMAL)

    def test_a_provider_outage_does_not_make_local_state_divergent(self) -> None:
        """A clearinghouse outage is not the platform being down."""

        assert not may_diverge_from_canonical(ContinuityMode.DEGRADED_PROVIDER)

    @pytest.mark.parametrize(
        "mode",
        [
            ContinuityMode.DEGRADED_CLOUD,
            ContinuityMode.EDGE_AUTHORITY,
            ContinuityMode.RECOVERY,
            ContinuityMode.RECONCILIATION,
        ],
    )
    def test_disconnected_modes_diverge(self, mode: ContinuityMode) -> None:
        assert may_diverge_from_canonical(mode)

    def test_unknown_mode_fails_closed(self) -> None:
        assert may_diverge_from_canonical("some_new_mode")

    def test_all_six_modes_exist(self) -> None:
        assert {member.value for member in ContinuityMode} == {
            "normal",
            "degraded_provider",
            "degraded_cloud",
            "edge_authority",
            "recovery",
            "reconciliation",
        }


class TestOfflineAuthorityGrant:
    def test_a_grant_permits_a_listed_operation_inside_its_window(self) -> None:
        assert _grant().permits("epcr.chart.update", when=NOW + timedelta(hours=1))

    def test_a_grant_refuses_an_unlisted_operation(self) -> None:
        """Allow-list, never deny-list: unlisted means not permitted offline."""

        assert not _grant().permits("narcotics.vial.destroy", when=NOW)

    def test_an_expired_grant_permits_nothing(self) -> None:
        assert not _grant().permits(
            "epcr.chart.update", when=LATER + timedelta(seconds=1)
        )

    def test_a_grant_is_not_live_before_it_was_issued(self) -> None:
        assert not _grant().is_valid_at(NOW - timedelta(seconds=1))

    def test_expiry_is_required(self) -> None:
        assert OfflineAuthorityGrant.model_fields["expires_at"].is_required()

    def test_a_reversed_window_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="expires_at must be after"):
            _grant(expires_at=NOW - timedelta(hours=1))

    def test_an_empty_allow_list_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            _grant(allowed_operation_types=[])


class TestOfflineOperationEnvelope:
    def test_an_operation_inside_its_grant_is_authorised(self) -> None:
        assert _operation().is_within_authority(_grant(), when=NOW + timedelta(hours=1))

    def test_a_mismatched_certificate_is_refused(self) -> None:
        """A replay with the right grant id and the wrong cert is not authority."""

        operation = _operation(device_cert_id="cert-2")
        assert not operation.is_within_authority(_grant(), when=NOW)

    def test_a_mismatched_tenant_is_refused(self) -> None:
        operation = _operation(tenant_id="tenant-b")
        assert not operation.is_within_authority(_grant(), when=NOW)

    def test_a_mismatched_device_is_refused(self) -> None:
        operation = _operation(device_id="device-2")
        assert not operation.is_within_authority(_grant(), when=NOW)

    def test_a_mismatched_grant_id_is_refused(self) -> None:
        operation = _operation(authority_grant_id="grant-2")
        assert not operation.is_within_authority(_grant(), when=NOW)

    def test_an_ungranted_operation_type_is_refused(self) -> None:
        operation = _operation(operation_type="narcotics.vial.destroy")
        assert not operation.is_within_authority(_grant(), when=NOW)

    def test_replay_after_expiry_is_refused(self) -> None:
        assert not _operation().is_within_authority(
            _grant(), when=LATER + timedelta(minutes=1)
        )

    def test_it_carries_the_base_state_version_for_reconciliation(self) -> None:
        assert _operation().base_state_version == 3

    def test_local_sequence_is_required_and_not_a_clock(self) -> None:
        assert OfflineOperationEnvelope.model_fields["local_sequence"].is_required()
        assert _operation().local_sequence == 7

    def test_the_online_workspace_envelope_is_still_its_own_contract(self) -> None:
        assert "base_sync_version" in OperationEnvelope.model_fields
        assert "base_state_version" not in OperationEnvelope.model_fields
        assert "signature" not in OperationEnvelope.model_fields


# ---------------------------------------------------------------------------
# L — PHI-safe product telemetry
# ---------------------------------------------------------------------------


def _telemetry(**overrides: object) -> ProductTelemetryEvent:
    payload: dict[str, object] = {
        "tenant_ref": "t_9f2c",
        "feature": "ambient_capture",
        "operation": "structured_proposal",
        "outcome": TelemetryOutcome.SUCCESS,
        "measured_at": NOW,
    }
    payload.update(overrides)
    return ProductTelemetryEvent(**payload)  # type: ignore[arg-type]


class TestProductTelemetry:
    def test_a_safe_event_round_trips(self) -> None:
        event = _telemetry(
            duration_ms=812,
            dimensions={"surface": "field_app", "network": "offline"},
        )
        assert event.outcome is TelemetryOutcome.SUCCESS

    @pytest.mark.parametrize(
        "key",
        [
            "patient_id",
            "PatientName",
            "primary_patient_name_display",
            "dob",
            "member_ssn",
            "narrative",
            "transcript_segment",
            "auth_token",
            "api_secret",
        ],
    )
    def test_protected_dimension_keys_are_refused(self, key: str) -> None:
        with pytest.raises(ValidationError, match="must not carry protected keys"):
            _telemetry(dimensions={key: "value"})

    def test_the_offending_keys_are_named(self) -> None:
        assert forbidden_telemetry_dimensions(
            {"surface": "web", "patient_id": "x", "mrn": "y"}
        ) == ["mrn", "patient_id"]

    def test_safe_keys_pass(self) -> None:
        assert (
            forbidden_telemetry_dimensions({"surface": "web", "network": "wifi"}) == []
        )

    def test_degraded_is_distinct_from_success(self) -> None:
        """A fallback path is not the same product experience as the normal one."""

        assert TelemetryOutcome.DEGRADED is not TelemetryOutcome.SUCCESS

    def test_tenant_ref_is_opaque_not_the_tenant_id(self) -> None:
        assert "tenant_id" not in ProductTelemetryEvent.model_fields
        assert "tenant_ref" in ProductTelemetryEvent.model_fields

    def test_no_free_text_error_message_field_exists(self) -> None:
        assert "error_class" in ProductTelemetryEvent.model_fields
        assert "error_message" not in ProductTelemetryEvent.model_fields

    def test_unknown_field_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _telemetry(patient_age=57)


# ---------------------------------------------------------------------------
# E — additive envelope fields
# ---------------------------------------------------------------------------


class TestOperationalEnvelopeAdditions:
    def _envelope(self, **overrides: object) -> OperationalEventEnvelope:
        payload: dict[str, object] = {
            "event_type": "billing.claim.created",
            "tenant_id": "tenant-a",
            "source_service": "billing",
            "source_record_id": "claim-1",
            "source_version": 1,
            "observed_at": NOW,
            "effective_at": NOW,
        }
        payload.update(overrides)
        return OperationalEventEnvelope(**payload)  # type: ignore[arg-type]

    def test_the_new_fields_are_optional(self) -> None:
        """Additive: an existing producer keeps constructing the envelope as-is."""

        envelope = self._envelope()
        assert envelope.causation_id is None
        assert envelope.sensitivity is None

    def test_causation_id_records_the_direct_antecedent(self) -> None:
        envelope = self._envelope(causation_id="event-0")
        assert envelope.causation_id == "event-0"

    def test_sensitivity_reuses_the_platform_classification(self) -> None:
        envelope = self._envelope(sensitivity=DataClassification.PHI)
        assert envelope.sensitivity is DataClassification.PHI

    def test_the_nine_required_fields_are_unchanged(self) -> None:
        """Adding optional fields must not disturb the directive invariant."""

        assert REQUIRED_ENVELOPE_FIELDS == (
            "tenant_id",
            "source_service",
            "source_record_id",
            "source_version",
            "observed_at",
            "effective_at",
            "correlation_id",
            "event_type",
            "schema_version",
        )

    def test_the_schema_version_is_not_bumped_by_additive_fields(self) -> None:
        assert SCHEMA_VERSION == "1.0"

    def test_the_envelope_still_serialises_for_eventbridge(self) -> None:
        detail = self._envelope(sensitivity=DataClassification.PHI).to_detail_json()
        assert '"sensitivity":"PHI"' in detail


def test_new_surface_is_exported_from_the_package_root() -> None:
    for name in (
        "ContinuityMode",
        "DIVERGENT_CONTINUITY_MODES",
        "OfflineAuthorityGrant",
        "OfflineOperationEnvelope",
        "ProductTelemetryEvent",
        "TelemetryOutcome",
        "FORBIDDEN_TELEMETRY_DIMENSION_KEYS",
    ):
        assert name in schemas.__all__
        assert hasattr(schemas, name)
