"""Unit tests for TransportLink document-intelligence and signature contracts.

Exercises valid construction, enum integrity, validation-failure paths for
required/constrained fields, and JSON round-trip stability for the Pydantic
contract schemas in:

- adaptix_contracts.transportlink.document_intelligence
- adaptix_contracts.transportlink.signatures
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import BaseModel, ValidationError

from adaptix_contracts.transportlink.document_intelligence import (
    DocumentIntelligenceAssessRequest,
    DocumentIntelligenceAssessmentContract,
    DocumentIntelligenceAuditContract,
    DocumentIntelligenceLatestResponse,
    DocumentReadinessContract,
    DocumentRequirementContract,
    MedicalNecessitySupportContract,
)
from adaptix_contracts.transportlink.signatures import (
    SignatureDocumentType,
    SignatureManualOverrideRequest,
    SignatureManualOverrideResponse,
    SignaturePacketRequest,
    SignaturePacketResponse,
    SignaturePacketStatus,
    SignatureStatusResponse,
    SignatureWebhookEvent,
    SignerStatus,
)

_NOW = datetime(2026, 7, 3, 12, 0, 0, tzinfo=timezone.utc)


def _assert_json_round_trip(model: BaseModel) -> None:
    """A model must survive dump -> validate and JSON dump -> validate."""

    cls = type(model)
    rebuilt_from_dict = cls.model_validate(model.model_dump())
    assert rebuilt_from_dict == model

    rebuilt_from_json = cls.model_validate_json(model.model_dump_json())
    assert rebuilt_from_json == model


# --------------------------------------------------------------------------- #
# document_intelligence.py
# --------------------------------------------------------------------------- #


def test_document_requirement_contract_valid_and_defaults() -> None:
    contract = DocumentRequirementContract(required=True, reason="PCS missing")

    assert contract.required is True
    assert contract.reason == "PCS missing"
    # Defaults must hold, including the human-review safety default.
    assert contract.missing_fields == []
    assert contract.contradictions == []
    assert contract.requires_human_review is True
    _assert_json_round_trip(contract)


def test_document_requirement_contract_missing_required_field_fails() -> None:
    with pytest.raises(ValidationError) as exc_info:
        DocumentRequirementContract(required=True)  # type: ignore[call-arg]

    assert "reason" in str(exc_info.value)


def test_medical_necessity_support_contract_safety_defaults() -> None:
    contract = MedicalNecessitySupportContract()

    # AI-safety invariants must default on: human review required, no invented facts.
    assert contract.human_review_required is True
    assert contract.no_invented_facts is True
    assert contract.draft_pcs_narrative is None
    assert contract.confidence is None
    _assert_json_round_trip(contract)


def test_medical_necessity_support_confidence_type_is_validated() -> None:
    with pytest.raises(ValidationError):
        MedicalNecessitySupportContract(confidence="not-a-float")  # type: ignore[arg-type]


def test_document_readiness_contract_requires_both_readiness_flags() -> None:
    contract = DocumentReadinessContract(
        ready_for_signature_packet=False,
        ready_for_cad=False,
        blocking_reasons=["pcs_unsigned"],
    )

    assert contract.ready_for_signature_packet is False
    assert contract.ready_for_cad is False
    assert contract.blocking_reasons == ["pcs_unsigned"]
    _assert_json_round_trip(contract)

    with pytest.raises(ValidationError):
        DocumentReadinessContract(ready_for_signature_packet=True)  # type: ignore[call-arg]


def test_document_intelligence_audit_contract_logging_defaults_are_false() -> None:
    audit = DocumentIntelligenceAuditContract(
        model_provider="bedrock",
        model_name="claude",
        policy_version="v1",
        created_at=_NOW,
    )

    # No PHI / prompt / completion may be logged by default.
    assert audit.phi_logged is False
    assert audit.prompt_logged is False
    assert audit.completion_logged is False
    _assert_json_round_trip(audit)


def test_document_intelligence_audit_contract_requires_created_at() -> None:
    with pytest.raises(ValidationError):
        DocumentIntelligenceAuditContract(
            model_provider="bedrock",
            model_name="claude",
            policy_version="v1",
        )  # type: ignore[call-arg]


def _valid_assessment() -> DocumentIntelligenceAssessmentContract:
    requirement = DocumentRequirementContract(required=True, reason="required")
    return DocumentIntelligenceAssessmentContract(
        assessment_id="assess-1",
        request_id="req-1",
        tenant_id="tenant-1",
        actor_id="actor-1",
        pcs=requirement,
        aob=requirement,
        abn=requirement,
        medical_necessity_support=MedicalNecessitySupportContract(),
        readiness=DocumentReadinessContract(
            ready_for_signature_packet=True,
            ready_for_cad=False,
        ),
        audit=DocumentIntelligenceAuditContract(
            model_provider="bedrock",
            model_name="claude",
            policy_version="v1",
            created_at=_NOW,
        ),
    )


def test_document_intelligence_assessment_valid_with_nested_contracts() -> None:
    assessment = _valid_assessment()

    assert assessment.request_id == "req-1"
    assert isinstance(assessment.pcs, DocumentRequirementContract)
    assert isinstance(assessment.audit, DocumentIntelligenceAuditContract)
    # AI-authority guardrails must default on.
    assert assessment.human_review_required is True
    assert assessment.ai_may_not_sign is True
    assert assessment.ai_may_not_mark_complete is True
    assert assessment.ai_may_not_override_provider is True
    assert assessment.ai_may_not_submit_to_cad is True
    _assert_json_round_trip(assessment)


def test_document_intelligence_assessment_missing_nested_contract_fails() -> None:
    with pytest.raises(ValidationError) as exc_info:
        DocumentIntelligenceAssessmentContract(
            assessment_id="assess-1",
            request_id="req-1",
            tenant_id="tenant-1",
            actor_id="actor-1",
            medical_necessity_support=MedicalNecessitySupportContract(),
            readiness=DocumentReadinessContract(
                ready_for_signature_packet=True,
                ready_for_cad=False,
            ),
            audit=DocumentIntelligenceAuditContract(
                model_provider="bedrock",
                model_name="claude",
                policy_version="v1",
                created_at=_NOW,
            ),
        )  # type: ignore[call-arg]

    message = str(exc_info.value)
    assert "pcs" in message


def test_document_intelligence_assess_request_valid_and_defaults() -> None:
    request = DocumentIntelligenceAssessRequest(
        request_id="req-1",
        tenant_id="tenant-1",
        actor_id="actor-1",
    )

    assert request.request_data == {}
    assert request.idempotency_key is None
    _assert_json_round_trip(request)


def test_document_intelligence_assess_request_requires_tenant() -> None:
    with pytest.raises(ValidationError):
        DocumentIntelligenceAssessRequest(
            request_id="req-1",
            actor_id="actor-1",
        )  # type: ignore[call-arg]


def test_document_intelligence_latest_response_empty_default() -> None:
    response = DocumentIntelligenceLatestResponse()

    assert response.assessment is None
    assert response.has_assessment is False
    assert response.credential_gated is False
    _assert_json_round_trip(response)


def test_document_intelligence_latest_response_carries_assessment() -> None:
    response = DocumentIntelligenceLatestResponse(
        assessment=_valid_assessment(),
        has_assessment=True,
    )

    assert response.has_assessment is True
    assert response.assessment is not None
    assert response.assessment.request_id == "req-1"
    _assert_json_round_trip(response)


# --------------------------------------------------------------------------- #
# signatures.py — enums
# --------------------------------------------------------------------------- #


def test_signature_packet_status_enum_values() -> None:
    expected = {
        "pending",
        "sent",
        "partially_signed",
        "completed",
        "declined",
        "expired",
        "error",
        "manual_override",
        "credential_gated",
    }
    actual = {status.value for status in SignaturePacketStatus}
    assert actual == expected
    assert len(actual) == len(list(SignaturePacketStatus))


def test_signature_document_type_enum_values() -> None:
    assert {t.value for t in SignatureDocumentType} == {"pcs", "aob", "abn", "combined"}


def test_signer_status_enum_values() -> None:
    assert {s.value for s in SignerStatus} == {
        "pending",
        "sent",
        "viewed",
        "signed",
        "declined",
    }


# --------------------------------------------------------------------------- #
# signatures.py — models
# --------------------------------------------------------------------------- #


def test_signature_packet_request_valid_with_enum_coercion() -> None:
    request = SignaturePacketRequest(
        request_id="req-1",
        tenant_id="tenant-1",
        actor_id="actor-1",
        document_types=["pcs", "aob"],
        patient_name="Jane Doe",
    )

    assert request.document_types == [
        SignatureDocumentType.PCS,
        SignatureDocumentType.AOB,
    ]
    assert request.payer is None
    _assert_json_round_trip(request)


def test_signature_packet_request_rejects_invalid_document_type() -> None:
    with pytest.raises(ValidationError):
        SignaturePacketRequest(
            request_id="req-1",
            tenant_id="tenant-1",
            actor_id="actor-1",
            document_types=["not_a_real_document"],
            patient_name="Jane Doe",
        )


def test_signature_packet_request_missing_patient_name_fails() -> None:
    with pytest.raises(ValidationError) as exc_info:
        SignaturePacketRequest(
            request_id="req-1",
            tenant_id="tenant-1",
            actor_id="actor-1",
            document_types=[SignatureDocumentType.COMBINED],
        )  # type: ignore[call-arg]

    assert "patient_name" in str(exc_info.value)


def test_signature_packet_response_valid_round_trip() -> None:
    response = SignaturePacketResponse(
        packet_id="packet-1",
        request_id="req-1",
        tenant_id="tenant-1",
        status=SignaturePacketStatus.SENT,
        document_types=[SignatureDocumentType.PCS],
        created_at=_NOW,
    )

    assert response.status is SignaturePacketStatus.SENT
    assert response.credential_gated is False
    _assert_json_round_trip(response)


def test_signature_packet_response_rejects_invalid_status() -> None:
    with pytest.raises(ValidationError):
        SignaturePacketResponse(
            packet_id="packet-1",
            request_id="req-1",
            tenant_id="tenant-1",
            status="not_a_status",
            document_types=[SignatureDocumentType.PCS],
            created_at=_NOW,
        )


def test_signature_status_response_defaults() -> None:
    response = SignatureStatusResponse(
        packet_id="packet-1",
        request_id="req-1",
        tenant_id="tenant-1",
        status=SignaturePacketStatus.PARTIALLY_SIGNED,
    )

    assert response.signers == []
    assert response.ready_for_cad is False
    assert response.ready_for_billing is False
    assert response.blocking_reasons == []
    _assert_json_round_trip(response)


def test_signature_manual_override_request_valid() -> None:
    override = SignatureManualOverrideRequest(
        request_id="req-1",
        tenant_id="tenant-1",
        actor_id="actor-1",
        reason="patient unavailable",
        document_type=SignatureDocumentType.ABN,
        override_justification="supervisor approved",
    )

    assert override.document_type is SignatureDocumentType.ABN
    assert override.supervisor_id is None
    _assert_json_round_trip(override)


def test_signature_manual_override_request_requires_justification() -> None:
    with pytest.raises(ValidationError) as exc_info:
        SignatureManualOverrideRequest(
            request_id="req-1",
            tenant_id="tenant-1",
            actor_id="actor-1",
            reason="patient unavailable",
            document_type=SignatureDocumentType.ABN,
        )  # type: ignore[call-arg]

    assert "override_justification" in str(exc_info.value)


def test_signature_manual_override_response_audit_default() -> None:
    response = SignatureManualOverrideResponse(
        override_id="override-1",
        request_id="req-1",
        tenant_id="tenant-1",
        actor_id="actor-1",
        document_type=SignatureDocumentType.PCS,
        reason="patient unavailable",
        occurred_at=_NOW,
    )

    assert response.audit_event_emitted is True
    _assert_json_round_trip(response)


def test_signature_webhook_event_valid_and_provider_default() -> None:
    event = SignatureWebhookEvent(
        event_type="signature_request_signed",
        provider_request_id="prov-1",
        idempotency_key="idem-1",
        received_at=_NOW,
    )

    assert event.provider == "dropbox_sign"
    assert event.tenant_id is None
    assert event.payload == {}
    _assert_json_round_trip(event)


def test_signature_webhook_event_requires_idempotency_key() -> None:
    with pytest.raises(ValidationError) as exc_info:
        SignatureWebhookEvent(
            event_type="signature_request_signed",
            provider_request_id="prov-1",
            received_at=_NOW,
        )  # type: ignore[call-arg]

    assert "idempotency_key" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
