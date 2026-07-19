"""Signature compliance evaluation contracts for Adaptix domains.

Implements payer-class-aware, jurisdiction-aware signature workflow compliance
evaluation for ambulance/EMS transport signatures.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SignatureCaptureMethod(str, Enum):
    ELECTRONIC = "electronic"
    HANDWRITTEN = "handwritten"
    VERBAL = "verbal"
    ON_FILE = "on_file"


class ComplianceDecision(str, Enum):
    APPROVED = "approved"
    APPROVED_WITH_EXCEPTION = "approved_with_exception"
    CONDITIONAL = "conditional"
    BLOCKED_MISSING_SIGNER = "blocked_missing_signer"
    BLOCKED_PATIENT_INCAPABLE = "blocked_patient_incapable"
    BLOCKED_TRANSFER_NOT_DOCUMENTED = "blocked_transfer_not_documented"
    BLOCKED_POLICY_VIOLATION = "blocked_policy_violation"
    BLOCKED_UNSUPPORTED_METHOD = "blocked_unsupported_method"


class BillingReadinessEffect(str, Enum):
    BILLABLE = "billable"
    CONDITIONALLY_BILLABLE = "conditionally_billable"
    BLOCKED = "blocked"
    DOCUMENTATION_REQUIRED = "documentation_required"


class ChartCompletionEffect(str, Enum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    EXCEPTION_DOCUMENTED = "exception_documented"


class SignatureComplianceEvaluationRequest(BaseModel):
    signature_class: str
    signature_method: str
    workflow_policy: str = "electronic_allowed"
    policy_pack_version: str = "us.wi.forwardhealth.signatures.v1"
    payer_class: str = "medicare_ambulance"
    jurisdiction_country: str = "US"
    jurisdiction_state: str = "WI"
    receiving_facility: str | None = None
    receiving_clinician_name: str | None = None
    receiving_role_title: str | None = None
    transfer_of_care_time: str | datetime | None = None
    transfer_exception_reason_code: str | None = None
    transfer_exception_reason_detail: str | None = None
    signer_identity: str | None = None
    signer_relationship: str | None = None
    signer_authority_basis: str | None = None
    patient_capable_to_sign: bool | None = None
    incapacity_reason: str | None = None
    signature_on_file_reference: str | None = None
    signature_on_file_valid_until: str | datetime | None = None
    ambulance_employee_exception: bool = False
    ambulance_exception_documentation_present: bool = False
    receiving_facility_verification_status: str = "not_required"
    signature_artifact_data_url: str | None = None
    local_capture_device_id: str | None = None

    model_config = {"extra": "allow"}


class SignatureComplianceEvaluationResult(BaseModel):
    decision: ComplianceDecision
    why: str
    allowed_capture_methods: list[SignatureCaptureMethod] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    required_supporting_documents: list[str] = Field(default_factory=list)
    retention_requirements: list[str] = Field(default_factory=list)
    billing_readiness_effect: str = BillingReadinessEffect.BILLABLE.value
    chart_completion_effect: str = ChartCompletionEffect.COMPLETE.value
    narrative_summary: str = ""
    ai_structured_explanation: dict[str, Any] = Field(default_factory=dict)


def evaluate_signature_compliance(
    request: SignatureComplianceEvaluationRequest,
) -> SignatureComplianceEvaluationResult:
    """Evaluate whether a signature capture meets payer, jurisdiction, and policy requirements."""
    missing: list[str] = []
    required_docs: list[str] = []
    allowed_methods: list[SignatureCaptureMethod] = []

    policy = request.workflow_policy.lower()
    if "electronic_allowed" in policy or "electronic" in policy:
        allowed_methods.append(SignatureCaptureMethod.ELECTRONIC)
    if "handwritten" in policy or "handwritten_required" in policy:
        allowed_methods.append(SignatureCaptureMethod.HANDWRITTEN)
    if "verbal" in policy:
        allowed_methods.append(SignatureCaptureMethod.VERBAL)
    if "on_file" in policy:
        allowed_methods.append(SignatureCaptureMethod.ON_FILE)
    if not allowed_methods:
        allowed_methods = [
            SignatureCaptureMethod.ELECTRONIC,
            SignatureCaptureMethod.HANDWRITTEN,
        ]

    is_transfer = request.signature_class in {
        "transfer_of_care",
        "hospital_transfer",
        "facility_transfer",
    }

    if is_transfer:
        if not request.receiving_facility:
            missing.append("receiving_facility")
        if not request.receiving_clinician_name:
            missing.append("receiving_clinician_name")
        if (
            not request.transfer_of_care_time
            and not request.transfer_exception_reason_code
        ):
            missing.append("transfer_of_care_time or transfer_exception_reason_code")
        if (
            request.transfer_exception_reason_code
            and not request.ambulance_exception_documentation_present
        ):
            required_docs.append("transfer_exception_supporting_documentation")

    patient_incapable = request.patient_capable_to_sign is False
    if patient_incapable:
        if not request.incapacity_reason:
            missing.append("incapacity_reason")
        if not request.signer_identity:
            missing.append("signer_identity (authorized representative)")
        if not request.signer_authority_basis:
            missing.append("signer_authority_basis")

    payer_class = request.payer_class.lower()
    if "medicare" in payer_class:
        retention_requirements = [
            "signature_artifact_retain_7_years",
            "signed_abn_if_non_covered",
            "signature_on_file_form_cms_10114",
        ]
    elif "medicaid" in payer_class:
        retention_requirements = [
            "signature_artifact_retain_5_years",
            "state_medicaid_authorization_form",
        ]
    else:
        retention_requirements = ["signature_artifact_retain_3_years"]

    submitted_method = request.signature_method.strip().lower()
    method_supported = submitted_method in {m.value for m in allowed_methods}

    if missing:
        decision = ComplianceDecision.BLOCKED_MISSING_SIGNER
        why = f"Signature compliance blocked: missing required fields: {', '.join(missing)}."
        billing_effect = BillingReadinessEffect.BLOCKED.value
        chart_effect = ChartCompletionEffect.INCOMPLETE.value
    elif not method_supported:
        decision = ComplianceDecision.BLOCKED_UNSUPPORTED_METHOD
        why = (
            f"Signature capture method '{request.signature_method}' is not permitted "
            f"under policy '{request.workflow_policy}'. Allowed methods: "
            f"{', '.join(m.value for m in allowed_methods)}."
        )
        billing_effect = BillingReadinessEffect.BLOCKED.value
        chart_effect = ChartCompletionEffect.INCOMPLETE.value
    elif (
        request.ambulance_employee_exception
        and not request.ambulance_exception_documentation_present
    ):
        decision = ComplianceDecision.APPROVED_WITH_EXCEPTION
        why = "Ambulance employee exception claimed but exception documentation not confirmed present."
        billing_effect = BillingReadinessEffect.CONDITIONALLY_BILLABLE.value
        chart_effect = ChartCompletionEffect.EXCEPTION_DOCUMENTED.value
    else:
        decision = ComplianceDecision.APPROVED
        why = "All required signature compliance conditions are satisfied."
        billing_effect = BillingReadinessEffect.BILLABLE.value
        chart_effect = ChartCompletionEffect.COMPLETE.value

    narrative = (
        f"Signature class '{request.signature_class}' evaluated under policy "
        f"'{request.workflow_policy}' for payer class '{request.payer_class}' "
        f"({request.jurisdiction_state}, {request.jurisdiction_country}). "
        f"Decision: {decision.value}. {why}"
    )

    ai_explanation: dict[str, Any] = {
        "policy": request.workflow_policy,
        "payer_class": request.payer_class,
        "missing_fields": missing,
        "required_documents": required_docs,
        "allowed_methods": [m.value for m in allowed_methods],
        "submitted_method": submitted_method,
        "decision": decision.value,
    }

    return SignatureComplianceEvaluationResult(
        decision=decision,
        why=why,
        allowed_capture_methods=allowed_methods,
        missing_requirements=missing,
        required_supporting_documents=required_docs,
        retention_requirements=retention_requirements,
        billing_readiness_effect=billing_effect,
        chart_completion_effect=chart_effect,
        narrative_summary=narrative,
        ai_structured_explanation=ai_explanation,
    )
