"""Contract + drift tests for the merged billing/Stedi endpoints.

These lock the Adaptix-Contracts surface to the real Adaptix-Billing-Service
source so cross-repo drift is caught in CI:

* ``POST /api/v1/billing/webhooks/stedi``
  (backend/billing_app/api/webhooks_stedi.py, PR #541)
* ``GET  /api/v1/billing/clearinghouse/claims/{claim_id}/retry-eligibility``
* ``POST /api/v1/billing/clearinghouse/claims/{claim_id}/operator-fallback``
  (backend/billing_app/api/clearinghouse_router_routes.py, PR #539; value sets
  from clearinghouse/base.py and clearinghouse/router.py)

Every expected value below is copied from the service source, not inferred.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

import adaptix_contracts
from adaptix_contracts import schemas
from adaptix_contracts.schemas import (
    ClaimOperatorFallbackRefusedError,
    ClaimOperatorFallbackRequest,
    ClaimOperatorFallbackResponse,
    ClaimOperatorFallbackTargetFailedError,
    ClaimRetryEligibilityResponse,
    ClaimRetryReasonCode,
    ClaimTransmissionState,
    ClearinghouseProvider,
    MigrationSourceClearinghouseSettingsResponse,
    MigrationSourceClearinghouseSettingsUpdate,
    MigrationSourceVendor,
    OperatorFallbackRefusedReasonCode,
    RemittanceListResponse,
    RemittancePostingStatus,
    RemittanceSummary,
    StediAllowedTransition,
    StediArtifactTransactionKind,
    StediClaimTransition,
    StediCreateEnrollmentRequest,
    StediCreateEnrollmentResponse,
    StediEnrollmentTransactionType,
    StediMigrationMode,
    StediMigrationModeResponse,
    StediMigrationTransitionKind,
    StediMigrationTransitionRequest,
    StediNormalizationResult,
    StediNormalizedArtifact,
    StediPayerEnrollmentStatus,
    StediPayerRow,
    StediReadinessBlockerOwner,
    StediReadinessState,
    StediServiceLineOutcome,
    StediStatusBlocker,
    StediStatusResponse,
    StediWebhookProcessingStatus,
    StediWebhookReconcileOutcome,
    StediWebhookAcceptedResponse,
    StediWebhookDuplicateResponse,
    StediWebhookEventType,
    StediWebhookStatus,
    StediWebhookVerification,
    StediWebhookRejectedResponse,
    StediWebhookRequest,
    SubmissionAttemptStatus,
    SubmissionFrequency,
    SubmissionSummaryResponse,
)

NEW_SYMBOLS = [
    "StediWebhookEventType",
    "StediWebhookRequest",
    "StediWebhookAcceptedResponse",
    "StediWebhookDuplicateResponse",
    "StediWebhookRejectedResponse",
    "StediReadinessState",
    "StediWebhookVerification",
    "StediReadinessBlockerOwner",
    "StediMigrationMode",
    "StediMigrationTransitionKind",
    "StediEnrollmentTransactionType",
    "StediPayerEnrollmentStatus",
    "SubmissionAttemptStatus",
    "RemittancePostingStatus",
    "SubmissionFrequency",
    "StediArtifactTransactionKind",
    "StediClaimTransition",
    "StediWebhookProcessingStatus",
    "StediStatusResponse",
    "StediMigrationModeResponse",
    "StediCreateEnrollmentRequest",
    "MigrationSourceClearinghouseSettingsResponse",
    "SubmissionSummaryResponse",
    "RemittanceListResponse",
    "StediNormalizationResult",
    "StediWebhookReconcileOutcome",
    "ClaimTransmissionState",
    "ClaimRetryReasonCode",
    "ClaimRetryEligibilityResponse",
    "ClaimOperatorFallbackRequest",
    "ClaimOperatorFallbackResponse",
    "OperatorFallbackRefusedReasonCode",
    "ClaimOperatorFallbackRefusedError",
    "ClaimOperatorFallbackTargetFailedError",
]


def test_new_symbols_exported_from_schema_and_package_root() -> None:
    for name in NEW_SYMBOLS:
        assert name in schemas.__all__, f"{name} missing from schemas.__all__"
        assert getattr(adaptix_contracts, name) is getattr(schemas, name)


# --- Stedi webhook -----------------------------------------------------------


def test_stedi_event_type_values_match_known_event_types() -> None:
    # webhooks_stedi.py KNOWN_EVENT_TYPES (lines 77-83)
    assert {e.value for e in StediWebhookEventType} == {
        "transaction.processed.v2",
        "file.delivered.v2",
        "file.failed.v2",
    }


def test_stedi_request_requires_id_and_reads_detail_type_alias() -> None:
    parsed = StediWebhookRequest.model_validate(
        {
            "id": "evt-123",
            "detail-type": "transaction.processed.v2",
            "detail": {"x12": "835"},
            "source": "stedi.eventbridge",  # extra field is accepted verbatim
        }
    )
    assert parsed.id == "evt-123"
    assert parsed.detail_type == "transaction.processed.v2"
    assert parsed.detail == {"x12": "835"}

    with pytest.raises(ValidationError):
        StediWebhookRequest.model_validate({"detail-type": "file.failed.v2"})


def test_stedi_response_field_sets_match_source_bodies() -> None:
    # webhooks_stedi.py:434-440 / 393-397 / rejected paths
    assert set(StediWebhookAcceptedResponse.model_fields) == {
        "status",
        "event_id",
        "event_type",
        "known_event_type",
        "enqueued",
    }
    assert set(StediWebhookDuplicateResponse.model_fields) == {
        "status",
        "event_id",
        "known_event_type",
    }
    assert set(StediWebhookRejectedResponse.model_fields) == {"status", "reason"}
    assert StediWebhookAcceptedResponse.model_fields["status"].default == "accepted"
    assert (
        StediWebhookDuplicateResponse.model_fields["status"].default
        == "duplicate_ignored"
    )


# --- STEDI-only live vendor vocabulary ---------------------------------------


def test_live_billing_clearinghouse_is_stedi_only() -> None:
    assert {p.value for p in ClearinghouseProvider} == {"stedi"}
    with pytest.raises(ValueError):
        ClearinghouseProvider("office_ally")
    assert {v.value for v in MigrationSourceVendor} == {
        "office_ally",
        "waystar",
        "availity",
        "change_healthcare",
        "trizetto",
        "other",
        "none_yet",
    }


def test_migration_source_settings_do_not_use_live_provider_enum() -> None:
    settings = MigrationSourceClearinghouseSettingsResponse(
        tenant_id="tenant-1",
        clearinghouse_vendor="office_ally",
        oa_sftp_username=None,
        oa_tpid=None,
        oa_sftp_verified=False,
        edi_837p_enabled=True,
        edi_835_enabled=True,
        edi_999_enabled=True,
        edi_277_enabled=True,
        submission_frequency="daily",
        updated_at=None,
    )
    assert settings.clearinghouse_vendor is MigrationSourceVendor.OFFICE_ALLY

    update = MigrationSourceClearinghouseSettingsUpdate(
        clearinghouse_vendor="waystar", submission_frequency="weekly"
    )
    assert update.clearinghouse_vendor is MigrationSourceVendor.WAYSTAR
    assert update.submission_frequency is SubmissionFrequency.WEEKLY
    with pytest.raises(ValidationError):
        MigrationSourceClearinghouseSettingsUpdate(clearinghouse_vendor="stedi")


# --- readiness + migration mode ----------------------------------------------


def test_stedi_readiness_state_values_match_service_and_web() -> None:
    assert {s.value for s in StediReadinessState} == {
        "not_configured",
        "credentials_missing",
        "credentials_invalid",
        "credentials_configured",
        "connection_verification_pending",
        "connection_verified",
        "provider_incomplete",
        "enrollment_required",
        "test_ready",
        "testing",
        "test_failed",
        "production_pending",
        "production_ready",
        "degraded",
        "suspended",
    }
    assert {v.value for v in StediWebhookVerification} == {
        "verified",
        "not_verified",
        "unknown",
    }
    assert {o.value for o in StediReadinessBlockerOwner} == {
        "agency",
        "adaptix",
        "payer",
    }


def test_stedi_status_response_shape_matches_service_and_web() -> None:
    body = StediStatusResponse(
        tenant_id="tenant-1",
        state="provider_incomplete",
        checked_at=None,
        providers=[],
        payers=[
            StediPayerRow(
                payer_id="payer-1",
                payer_name="Test Payer",
                state="enrollment_required",
                enrollment_required=True,
            )
        ],
        webhook=StediWebhookStatus(verification="unknown", last_event_at=None),
        blockers=[
            StediStatusBlocker(
                code="payer_enrollment_required",
                label="Payer requires enrollment.",
                section="§8",
                owner="agency",
            )
        ],
    )
    assert set(body.model_dump()) == {
        "tenant_id",
        "state",
        "checked_at",
        "providers",
        "payers",
        "webhook",
        "blockers",
    }
    assert body.payers[0].state is StediReadinessState.ENROLLMENT_REQUIRED


def test_stedi_migration_mode_values_and_transition_shape_match_service() -> None:
    assert {m.value for m in StediMigrationMode} == {
        "office_ally_active",
        "stedi_shadow",
        "stedi_test",
        "stedi_primary",
        "office_ally_read_only",
        "migration_blocked",
    }
    assert {k.value for k in StediMigrationTransitionKind} == {
        "advance",
        "rollback",
        "block",
        "recover",
    }
    response = StediMigrationModeResponse(
        tenant_id="tenant-1",
        mode="office_ally_active",
        description="Legacy Office Ally source mode retained only for migration compatibility.",
        updated_by=None,
        last_reason=None,
        updated_at=None,
        is_default=True,
        allowed_transitions=[
            StediAllowedTransition(
                to_mode="stedi_shadow",
                kind="advance",
                requires_founder=False,
                caller_authorized=True,
                description="Begin migration — start Stedi in shadow.",
            )
        ],
    )
    assert response.allowed_transitions[0].to_mode is StediMigrationMode.STEDI_SHADOW

    request = StediMigrationTransitionRequest(
        to_mode="stedi_test", reason="validated provider identity"
    )
    assert request.reason == "validated provider identity"
    with pytest.raises(ValidationError):
        StediMigrationTransitionRequest(to_mode="stedi_test", reason="   ")


# --- payer enrollment ---------------------------------------------------------


def test_stedi_enrollment_request_and_response_shape_match_service() -> None:
    assert {t.value for t in StediEnrollmentTransactionType} == {
        "claims",
        "era",
        "eligibility",
    }
    assert {s.value for s in StediPayerEnrollmentStatus} == {
        "draft",
        "submitted",
        "pending",
        "live",
        "rejected",
        "canceled",
        "unknown",
    }
    request = StediCreateEnrollmentRequest(
        payer_id="payer-1",
        payer_name="Test Payer",
        transaction_types=["claims", "era"],
    )
    assert request.transaction_types == [
        StediEnrollmentTransactionType.CLAIMS,
        StediEnrollmentTransactionType.ERA,
    ]
    with pytest.raises(ValidationError):
        StediCreateEnrollmentRequest(payer_id="payer-1", transaction_types=["claims", "claims_status"])

    response = StediCreateEnrollmentResponse(
        enrollment_id="enroll-1",
        stedi_enrollment_id="stedi-enroll-1",
        status="pending",
        payer_id="payer-1",
        transaction_types=["claims"],
    )
    assert set(response.model_dump()) == {
        "enrollment_id",
        "stedi_enrollment_id",
        "status",
        "payer_id",
        "transaction_types",
    }


# --- retry-eligibility -------------------------------------------------------


def test_transmission_state_values_match_base_constants() -> None:
    # clearinghouse/base.py:88-96
    assert {s.value for s in ClaimTransmissionState} == {
        "not_transmitted",
        "unknown",
        "transmitted",
    }


def test_retry_reason_codes_match_base_source() -> None:
    # clearinghouse/base.py:135-180
    assert {c.value for c in ClaimRetryReasonCode} == {
        "no_prior_attempt",
        "proven_not_transmitted",
        "already_accepted",
        "unknown_transmission",
    }


def test_retry_eligibility_response_field_set_matches_source() -> None:
    # clearinghouse_router_routes.py:138-148
    assert set(ClaimRetryEligibilityResponse.model_fields) == {
        "claim_id",
        "tenant_id",
        "safe",
        "blocking_state",
        "reason_code",
        "reason",
        "latest_clearinghouse_slug",
        "latest_transmission_state",
    }


# --- submission, 835 posting, reconciliation ---------------------------------


def test_submission_and_remittance_status_vocabularies_match_web_client() -> None:
    assert {s.value for s in SubmissionAttemptStatus} == {
        "pending",
        "preflight_failed",
        "queued",
        "transmitted",
        "accepted",
        "rejected",
        "resubmit_required",
    }
    summary = SubmissionSummaryResponse(
        availability="available",
        by_status={"accepted": 2, "queued": 1},
        total_queued=1,
        total_transmitted=3,
        total_accepted=2,
        total_rejected=0,
        as_of="2026-08-14T00:00:00Z",
    )
    assert summary.by_status[SubmissionAttemptStatus.ACCEPTED] == 2

    assert {s.value for s in RemittancePostingStatus} == {"posted", "unposted"}
    listing = RemittanceListResponse(
        items=[
            RemittanceSummary(
                id="era-1",
                era_check_number="eft-1",
                payer_name="Test Payer",
                payer_id="payer-1",
                total_paid_cents=1000,
                claim_count=1,
                source_filename="835.edi",
                received_at="2026-08-14T00:00:00Z",
                posting_status="unposted",
            )
        ],
        count=1,
        unposted_count=1,
        limit=25,
        offset=0,
    )
    assert listing.items[0].posting_status is RemittancePostingStatus.UNPOSTED


def test_stedi_artifact_reconciliation_vocabularies_preserve_undetermined_states() -> None:
    assert {k.value for k in StediArtifactTransactionKind} == {
        "file_delivered",
        "file_failed",
        "ack_999",
        "ack_277ca",
        "remittance_835",
    }
    assert {t.value for t in StediClaimTransition} == {
        "delivered_to_payer",
        "delivery_failed",
        "ack_accepted",
        "ack_rejected",
        "accepted",
        "rejected",
        "denied",
        "partially_paid",
        "paid",
        "undetermined",
    }
    artifact = StediNormalizedArtifact(
        kind="remittance_835",
        service_lines=[
            StediServiceLineOutcome(
                billed_cents=1000,
                paid_cents=0,
                denied=False,
                patient_responsibility_cents=1000,
            )
        ],
    )
    result = StediNormalizationResult(
        artifact=artifact, tenant_id="tenant-1", claim_ref="claim-1"
    )
    assert result.artifact.kind is StediArtifactTransactionKind.REMITTANCE_835

    assert {s.value for s in StediWebhookProcessingStatus} == {
        "received",
        "queued",
        "processing",
        "processed",
        "failed",
        "pending_reconciliation",
        "received_unknown_type",
    }
    outcome = StediWebhookReconcileOutcome(
        status="pending_reconciliation", detail="claim_not_found"
    )
    assert outcome.status is StediWebhookProcessingStatus.PENDING_RECONCILIATION


# --- operator-fallback -------------------------------------------------------


def test_operator_fallback_request_enforces_stedi_only_live_target() -> None:
    ok = ClaimOperatorFallbackRequest(
        target_clearinghouse_slug="stedi",
        reason="payer confirmed original never received",
        evidence="277CA shows no acknowledgement; vendor portal empty",
    )
    assert ok.target_clearinghouse_slug is ClearinghouseProvider.STEDI
    assert ok.acknowledge_duplicate_risk is False

    with pytest.raises(ValidationError):  # legacy vendors are migration sources only
        ClaimOperatorFallbackRequest(
            target_clearinghouse_slug="waystar",
            reason="valid reason",
            evidence="valid evidence",
        )
    with pytest.raises(ValidationError):  # reason min_length=4
        ClaimOperatorFallbackRequest(
            target_clearinghouse_slug="stedi",
            reason="no",
            evidence="valid evidence",
        )


def test_operator_fallback_response_field_set_matches_source() -> None:
    # clearinghouse_router_routes.py:160-169
    assert set(ClaimOperatorFallbackResponse.model_fields) == {
        "claim_id",
        "fallback_event_id",
        "original_clearinghouse_slug",
        "original_transmission_state",
        "target_clearinghouse_slug",
        "new_submission_reference",
        "cost_cents",
    }


def test_operator_fallback_refused_reason_codes_match_router_source() -> None:
    # clearinghouse/router.py:1088-1138
    assert {c.value for c in OperatorFallbackRefusedReasonCode} == {
        "no_original_submission",
        "same_vendor",
        "original_already_accepted",
        "unknown_transmission_requires_acknowledgement",
        "target_not_configured",
        "target_not_eligible",
    }


def test_operator_fallback_error_detail_shapes_match_source() -> None:
    # 409: clearinghouse_router_routes.py:502-509
    refused = ClaimOperatorFallbackRefusedError(
        reason_code="same_vendor", message="target is the original vendor"
    )
    assert set(refused.model_dump()) == {"reason_code", "message"}
    # 503: clearinghouse_router_routes.py:510-521
    failed = ClaimOperatorFallbackTargetFailedError(
        target_slug="stedi", transmission_state="unknown"
    )
    assert failed.error == "target_clearinghouse_submit_failed"
    assert set(failed.model_dump()) == {"error", "target_slug", "transmission_state"}
