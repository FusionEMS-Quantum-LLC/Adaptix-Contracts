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
