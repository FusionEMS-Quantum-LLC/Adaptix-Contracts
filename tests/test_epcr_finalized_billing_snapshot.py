"""Contract tests for the optional billing_snapshot on the finalized event.

The finalized event carried only 6 keys, so the Billing consumer built
placeholder claims (patient_name = call_number, insurance_verified = False).
This adds an OPTIONAL, fully back-compatible claim-ready snapshot so Billing
can mint a real claim — while a legacy 6-key event must still validate.
"""

from __future__ import annotations

from adaptix_contracts.schemas import EpcrBillingSnapshot, EpcrChartFinalizedEvent


def _base() -> dict:
    return {
        "chart_id": "18ab537c",
        "tenant_id": "0149677b",
        "call_number": "E2E-EPCR-001",
        "finalized_at": "2026-08-14T00:00:00+00:00",
    }


def test_legacy_six_key_event_still_validates_without_snapshot() -> None:
    event = EpcrChartFinalizedEvent.model_validate(_base())
    assert event.billing_snapshot is None
    assert event.is_test is False


def test_enriched_event_carries_real_billing_facts() -> None:
    payload = _base()
    payload["billing_snapshot"] = {
        "chart_status": "finalized",
        "primary_impression": "chest pain",
        "primary_impression_icd10": "R07.9",
        "primary_impression_snomed": "29857009",
        "transport_reason": "ALS emergency",
        "level_of_service_code": "ALS",
        "level_of_service_label": "Advanced Life Support",
        "patient_demographics": {
            "first_name": "Zed",
            "last_name": "Synthetic",
            "date_of_birth": "1961-03-15",
            "age_years": 65,
            "sex": "male",
            "weight_kg": 82.0,
        },
        "attending_crew": [
            {"crew_member_id": "u1", "level_code": "paramedic", "sequence_index": 0}
        ],
        "missing_fields": [],
        "ready_for_billing": True,
    }
    event = EpcrChartFinalizedEvent.model_validate(payload)
    snap = event.billing_snapshot
    assert isinstance(snap, EpcrBillingSnapshot)
    assert snap.primary_impression_icd10 == "R07.9"
    assert snap.patient_demographics.last_name == "Synthetic"
    assert snap.patient_demographics.age_years == 65
    assert snap.level_of_service_code == "ALS"
    assert snap.attending_crew[0].crew_member_id == "u1"
    assert snap.ready_for_billing is True


def test_partial_snapshot_is_valid() -> None:
    """A partial chart still produces a valid event — no field is required."""
    payload = _base()
    payload["billing_snapshot"] = {"primary_impression": "chest pain"}
    event = EpcrChartFinalizedEvent.model_validate(payload)
    assert event.billing_snapshot.primary_impression == "chest pain"
    assert event.billing_snapshot.ready_for_billing is False
    assert event.billing_snapshot.patient_demographics is None
    assert event.billing_snapshot.transport is None
    assert event.billing_snapshot.insurance is None
    assert event.billing_snapshot.certification is None


def test_transport_block_is_no_longer_dropped() -> None:
    """The producer has always emitted "transport"; 2.8.0 types it.

    Before this field existed, ``model_validate`` silently discarded the
    block — origin, destination and mileage never reached Billing. This
    test pins the exact producer shape (TransportBillingBlock asdict).
    """
    payload = _base()
    payload["billing_snapshot"] = {
        "transport": {
            "origin_name": "Scene - Main St",
            "origin_address": "123 Main St",
            "origin_latitude": "43.0731",
            "origin_longitude": "-89.4012",
            "destination_name": "General Hospital",
            "destination_address": "600 Highland Ave",
            "transport_distance_miles": "12.4",
            "service_type_code": "2205001",
            "unit_role_code": "2207011",
        }
    }
    snap = EpcrChartFinalizedEvent.model_validate(payload).billing_snapshot
    assert snap.transport.destination_name == "General Hospital"
    # Raw NEMSIS string, deliberately NOT coerced to a number.
    assert snap.transport.transport_distance_miles == "12.4"


def test_insurance_and_certification_blocks_validate() -> None:
    payload = _base()
    payload["billing_snapshot"] = {
        "insurance": {
            "insurance_company_id": "87726",
            "insurance_company_name": "Forward Health WI",
            "insurance_billing_priority_code": "2701001",
            "insurance_policy_id_number": "POL-0042",
            "insurance_group_id": "GRP-9",
            "insured_last_name": "Synthetic",
            "insured_first_name": "Zed",
            "relationship_to_insured_code": "2703001",
            "payer_type_code": "2707011",
            "insured_date_of_birth": "1961-03-15",
        },
        "certification": {
            "physician_certification_statement_code": "4502001",
            "pcs_signed_date": "2026-08-01",
            "reason_for_pcs_codes": ["4503001", "4503005"],
            "ambulance_transport_reason_code": "4507001",
            "cms_service_level_code": "4511005",
            "ems_condition_codes": ["Z9911"],
            "transport_authorization_code": "AUTH-77",
            "prior_authorization_code_payer": "PA-123",
            "mileage_to_closest_hospital": 4.2,
        },
    }
    snap = EpcrChartFinalizedEvent.model_validate(payload).billing_snapshot
    assert snap.insurance.insurance_company_name == "Forward Health WI"
    assert snap.insurance.payer_type_code == "2707011"
    assert snap.certification.reason_for_pcs_codes == ["4503001", "4503005"]
    assert snap.certification.mileage_to_closest_hospital == 4.2
    # Absent lists stay None (undocumented), never fabricated empties.
    assert snap.certification.cms_transportation_indicator_codes is None
