"""Contract tests for the chart facts the billing snapshot gained in 5.31.0.

Signatures (42 CFR 424.36), secondary impressions, the primary method of
payment, guarantor and employer blocks, attachment references and the
medical-necessity elements beside the PCS. All additive: a payload from an
older producer must still validate, and "the producer did not collect this"
(``None``) must stay distinguishable from "the chart holds none" (``[]``).
Every value below is synthetic.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from adaptix_contracts.schemas import (
    EpcrBillingAttachmentRef,
    EpcrBillingCertificationBlock,
    EpcrBillingEmployerBlock,
    EpcrBillingGuarantorBlock,
    EpcrBillingSignatureFact,
    EpcrBillingSnapshot,
    EpcrChartFinalizedEvent,
)

NEW_SNAPSHOT_FIELDS = (
    "secondary_impression_icd10_codes",
    "primary_method_of_payment_code",
    "patient_resides_in_service_area_code",
    "guarantor",
    "employer",
    "signatures",
    "attachments",
)


def _event(snapshot: dict) -> EpcrChartFinalizedEvent:
    return EpcrChartFinalizedEvent.model_validate(
        {
            "chart_id": "c7a1d2e3-0000-4000-8000-00000000c4a7",
            "tenant_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
            "call_number": "SYN-0001",
            "finalized_at": "2026-04-02T18:00:00+00:00",
            "billing_snapshot": snapshot,
        }
    )


def _patient_signature(**overrides: object) -> dict:
    fact: dict = {
        "signature_id": "5f0a1c9e-1111-4222-8333-444455556666",
        "signature_class": "patient",
        "signature_method": "electronic",
        "signer_type_code": "4512015",
        "signature_reason_codes": ["4513005"],
        "signature_status_code": "4515031",
        "signed_at": "2026-04-02T17:40:00+00:00",
        "signer_identity_documented": True,
        "patient_capable_to_sign": True,
        "signature_graphic_captured": True,
        "compliance_decision": "captured_compliant",
        "billing_readiness_effect": "ready",
    }
    fact.update(overrides)
    return fact


def test_a_pre_5_31_snapshot_still_validates_and_reports_nothing_collected() -> None:
    snapshot = _event(
        {"primary_impression_icd10": "R07.9", "origin_type": "RESIDENCE"}
    ).billing_snapshot

    assert snapshot is not None
    for name in NEW_SNAPSHOT_FIELDS:
        assert getattr(snapshot, name) is None, name


def test_an_empty_list_is_kept_apart_from_not_collected() -> None:
    snapshot = _event(
        {"signatures": [], "attachments": [], "secondary_impression_icd10_codes": []}
    ).billing_snapshot

    assert snapshot is not None
    assert snapshot.signatures == []
    assert snapshot.attachments == []
    assert snapshot.secondary_impression_icd10_codes == []
    dumped = snapshot.model_dump()
    assert dumped["signatures"] == [] and dumped["guarantor"] is None


def test_the_full_fact_set_round_trips_through_the_typed_event() -> None:
    payload = {
        "primary_impression_icd10": "I63.9",
        "secondary_impression_icd10_codes": ["E11.9", "I10"],
        "primary_method_of_payment_code": "2601013",
        "patient_resides_in_service_area_code": "2608001",
        "guarantor": {
            "last_name": "Guardian",
            "first_name": "Synthetic",
            "street_address": "1 Test Way",
            "zip": "53703",
            "phone": "555-0100",
            "relationship_code": "2632019",
        },
        "employer": {"name": "Synthetic Works", "zip": "53704", "phone": "555-0101"},
        "signatures": [
            _patient_signature(),
            {
                "signature_id": "6a1b2d0f-1111-4222-8333-444455557777",
                "signature_class": "receiving_clinician",
                "signer_type_code": "4512005",
                "signature_reason_codes": ["4513007"],
                "signature_status_code": "4515033",
                "signature_graphic_captured": True,
                "receiving_facility_name": "Synthetic General Hospital",
                "receiving_clinician_documented": True,
                "receiving_role_title": "RN",
                "transfer_of_care_time": "2026-04-02T17:55:00+00:00",
                "receiving_facility_verification_status": "verified",
            },
        ],
        "attachments": [
            {
                "attachment_id": "7b2c3e10-1111-4222-8333-444455558888",
                "content_type": "application/pdf",
                "size_bytes": 48211,
                "sha256": "a" * 64,
                "uploaded_at": "2026-04-02T18:10:00+00:00",
            }
        ],
    }

    snapshot = _event(payload).billing_snapshot

    assert snapshot is not None
    assert snapshot.secondary_impression_icd10_codes == ["E11.9", "I10"]
    assert snapshot.primary_method_of_payment_code == "2601013"
    assert isinstance(snapshot.guarantor, EpcrBillingGuarantorBlock)
    assert snapshot.guarantor.relationship_code == "2632019"
    assert isinstance(snapshot.employer, EpcrBillingEmployerBlock)
    assert snapshot.employer.name == "Synthetic Works"
    assert snapshot.signatures is not None and len(snapshot.signatures) == 2
    patient, facility = snapshot.signatures
    assert isinstance(patient, EpcrBillingSignatureFact)
    assert patient.signer_type_code == "4512015"
    assert patient.signed_at is not None and patient.signed_at.utcoffset() is not None
    assert facility.receiving_facility_name == "Synthetic General Hospital"
    assert facility.transfer_of_care_time is not None
    assert snapshot.attachments is not None
    assert isinstance(snapshot.attachments[0], EpcrBillingAttachmentRef)
    assert snapshot.attachments[0].size_bytes == 48211
    # The typed snapshot serializes back to the same facts (JSON mode, as the bus carries it).
    again = EpcrBillingSnapshot.model_validate(snapshot.model_dump(mode="json"))
    assert again == snapshot


def test_a_signature_fact_defaults_every_flag_to_not_documented() -> None:
    fact = EpcrBillingSignatureFact.model_validate({"signature_id": "s-1"})

    assert fact.patient_capable_to_sign is None
    for flag in (
        "signer_identity_documented",
        "incapacity_reason_documented",
        "signature_graphic_captured",
        "signature_on_file_documented",
        "ambulance_employee_exception",
        "receiving_clinician_documented",
        "content_invalidated",
    ):
        assert getattr(fact, flag) is False, flag
    assert fact.signature_reason_codes == []
    assert fact.missing_requirements == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("signer_type_code", "patient"),  # a class name is not an eOther.12 code
        ("signer_type_code", "4515031"),  # a status code in the signer slot
        ("representative_type_code", "4512017"),
        ("signature_status_code", "signed"),
        ("signature_reason_codes", ["billing"]),
        ("signed_at", "2026-04-02T17:40:00"),  # no UTC offset
        ("transfer_of_care_time", "2026-04-02 17:55"),
        ("signature_id", ""),
    ],
)
def test_a_malformed_signature_fact_is_refused(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        EpcrBillingSignatureFact.model_validate(_patient_signature(**{field: value}))


@pytest.mark.parametrize(
    "attachment",
    [
        {"attachment_id": ""},
        {"attachment_id": "a-1", "size_bytes": -1},
        {"attachment_id": "a-1", "sha256": "A" * 64},  # digests are lowercase hex
        {"attachment_id": "a-1", "sha256": "abc"},
        {"attachment_id": "a-1", "uploaded_at": "2026-04-02T18:10:00"},
        {},
    ],
)
def test_a_malformed_attachment_reference_is_refused(attachment: dict) -> None:
    with pytest.raises(ValidationError):
        EpcrBillingAttachmentRef.model_validate(attachment)


def test_an_attachment_reference_cannot_carry_a_file_name_or_location() -> None:
    assert set(EpcrBillingAttachmentRef.model_fields) == {
        "attachment_id",
        "content_type",
        "size_bytes",
        "sha256",
        "uploaded_at",
    }


def test_a_signature_fact_has_no_field_for_a_name_a_narrative_or_a_graphic() -> None:
    forbidden = {
        "signer_identity",
        "incapacity_reason",
        "signature_artifact_data_url",
        "signature_on_file_reference",
        "receiving_clinician_name",
        "transfer_exception_reason_detail",
    }
    assert forbidden.isdisjoint(EpcrBillingSignatureFact.model_fields)


def test_the_certification_block_carries_the_medical_necessity_elements() -> None:
    block = EpcrBillingCertificationBlock.model_validate(
        {
            "physician_certification_statement_code": "9922005",
            "pcs_signed_date": "2026-03-20",
            "response_urgency_code": "2640003",
            "patient_transport_assessment_code": "2641005",
            "specialty_care_transport_provider_code": "2642001",
            "round_trip_purpose_description": "Dialysis, returns to residence",
            "stretcher_purpose_description": "Bed confined",
            "als_assessment_performed_warranted_code": "9923003",
        }
    )

    assert block.response_urgency_code == "2640003"
    assert block.patient_transport_assessment_code == "2641005"
    assert block.stretcher_purpose_description == "Bed confined"
    older = EpcrBillingCertificationBlock.model_validate(
        {"pcs_signed_date": "2026-03-20"}
    )
    assert older.response_urgency_code is None
    assert older.als_assessment_performed_warranted_code is None
