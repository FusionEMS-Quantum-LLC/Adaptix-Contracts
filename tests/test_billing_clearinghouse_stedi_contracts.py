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
    OperatorFallbackRefusedReasonCode,
    StediWebhookAcceptedResponse,
    StediWebhookDuplicateResponse,
    StediWebhookEventType,
    StediWebhookRejectedResponse,
    StediWebhookRequest,
)

NEW_SYMBOLS = [
    "StediWebhookEventType",
    "StediWebhookRequest",
    "StediWebhookAcceptedResponse",
    "StediWebhookDuplicateResponse",
    "StediWebhookRejectedResponse",
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


# --- operator-fallback -------------------------------------------------------


def test_operator_fallback_request_enforces_source_constraints() -> None:
    # clearinghouse_router_routes.py:151-157
    ok = ClaimOperatorFallbackRequest(
        target_clearinghouse_slug="waystar",
        reason="payer confirmed original never received",
        evidence="277CA shows no acknowledgement; vendor portal empty",
    )
    assert ok.acknowledge_duplicate_risk is False

    with pytest.raises(ValidationError):  # slug pattern ^[a-z][a-z0-9_]+$
        ClaimOperatorFallbackRequest(
            target_clearinghouse_slug="Waystar",
            reason="valid reason",
            evidence="valid evidence",
        )
    with pytest.raises(ValidationError):  # reason min_length=4
        ClaimOperatorFallbackRequest(
            target_clearinghouse_slug="waystar",
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
        target_slug="availity", transmission_state="unknown"
    )
    assert failed.error == "target_clearinghouse_submit_failed"
    assert set(failed.model_dump()) == {"error", "target_slug", "transmission_state"}
