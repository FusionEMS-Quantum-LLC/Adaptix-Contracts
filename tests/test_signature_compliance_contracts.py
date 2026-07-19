"""Contract tests for signature compliance evaluation."""

from __future__ import annotations

import pytest

from adaptix_contracts.schemas.signature_compliance_contracts import (
    BillingReadinessEffect,
    ChartCompletionEffect,
    ComplianceDecision,
    SignatureCaptureMethod,
    SignatureComplianceEvaluationRequest,
    evaluate_signature_compliance,
)


def test_verbal_method_under_electronic_only_policy_is_blocked():
    """Regression: an out-of-policy capture method must not be APPROVED/BILLABLE."""
    result = evaluate_signature_compliance(
        SignatureComplianceEvaluationRequest(
            signature_class="patient",
            signature_method="verbal",
            workflow_policy="electronic_allowed",
        )
    )

    assert result.allowed_capture_methods == [SignatureCaptureMethod.ELECTRONIC]
    assert result.decision is ComplianceDecision.BLOCKED_UNSUPPORTED_METHOD
    assert result.billing_readiness_effect == BillingReadinessEffect.BLOCKED.value
    assert result.chart_completion_effect == ChartCompletionEffect.INCOMPLETE.value
    assert "verbal" in result.why


@pytest.mark.parametrize("method", ["on_file", "wet_ink", ""])
def test_other_unsupported_methods_are_blocked(method):
    result = evaluate_signature_compliance(
        SignatureComplianceEvaluationRequest(
            signature_class="patient",
            signature_method=method,
            workflow_policy="electronic_allowed",
        )
    )
    assert result.decision is ComplianceDecision.BLOCKED_UNSUPPORTED_METHOD
    assert result.billing_readiness_effect == BillingReadinessEffect.BLOCKED.value


def test_allowed_method_still_approves():
    result = evaluate_signature_compliance(
        SignatureComplianceEvaluationRequest(
            signature_class="patient",
            signature_method="electronic",
            workflow_policy="electronic_allowed",
        )
    )
    assert result.decision is ComplianceDecision.APPROVED
    assert result.billing_readiness_effect == BillingReadinessEffect.BILLABLE.value


def test_method_match_is_case_and_whitespace_insensitive():
    result = evaluate_signature_compliance(
        SignatureComplianceEvaluationRequest(
            signature_class="patient",
            signature_method="  Electronic ",
            workflow_policy="electronic_allowed",
        )
    )
    assert result.decision is ComplianceDecision.APPROVED


def test_policy_naming_verbal_permits_verbal():
    """A policy that permits verbal capture must not be blocked by the new gate."""
    result = evaluate_signature_compliance(
        SignatureComplianceEvaluationRequest(
            signature_class="patient",
            signature_method="verbal",
            workflow_policy="verbal_allowed",
        )
    )
    assert SignatureCaptureMethod.VERBAL in result.allowed_capture_methods
    assert result.decision is ComplianceDecision.APPROVED


def test_default_policy_permits_handwritten():
    result = evaluate_signature_compliance(
        SignatureComplianceEvaluationRequest(
            signature_class="patient",
            signature_method="handwritten",
            workflow_policy="unspecified_policy",
        )
    )
    assert result.allowed_capture_methods == [
        SignatureCaptureMethod.ELECTRONIC,
        SignatureCaptureMethod.HANDWRITTEN,
    ]
    assert result.decision is ComplianceDecision.APPROVED


def test_missing_signer_still_takes_precedence_over_method_gate():
    """Existing BLOCKED_MISSING_SIGNER behaviour must be preserved."""
    result = evaluate_signature_compliance(
        SignatureComplianceEvaluationRequest(
            signature_class="transfer_of_care",
            signature_method="verbal",
            workflow_policy="electronic_allowed",
        )
    )
    assert result.decision is ComplianceDecision.BLOCKED_MISSING_SIGNER
    assert "receiving_facility" in result.missing_requirements
