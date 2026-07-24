"""Tests for the ePCR <-> MAR medication reconciliation contracts.

These pin the contract to the real merged shapes in Adaptix-Medications-Service
(PR #173, commit e035f5b): ``backend/medications/api/epcr_reconciliation_routes.py``
(request models + ``_serialize`` response body) and ``backend/medications/models.py``
(``EPCRMedicationReconciliationModel`` status / resolution_action value sets).

The response round-trip tests build payloads shaped exactly as the service's
``_serialize`` returns them, so the contract is proven against real output rather
than an invented shape.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from adaptix_contracts.schemas import (
    EpcrDiscrepancyType,
    EpcrFieldDiff,
    EpcrMedItem,
    EpcrReconciliationCreateRequest,
    EpcrReconciliationDiscrepancy,
    EpcrReconciliationListResponse,
    EpcrReconciliationResolveRequest,
    EpcrReconciliationResponse,
    EpcrReconciliationStatus,
    EpcrResolutionAction,
)


# ---------------------------------------------------------------------------
# Enum value sets (frozen against the DB model / route allow-list)
# ---------------------------------------------------------------------------


def test_reconciliation_status_values() -> None:
    assert {s.value for s in EpcrReconciliationStatus} == {
        "pending",
        "in_progress",
        "complete",
        "discrepancy",
    }


def test_discrepancy_type_values() -> None:
    # Exactly the three kinds the reconciliation route emits (timing_mismatch,
    # named only in the DB column comment, is intentionally excluded).
    assert {d.value for d in EpcrDiscrepancyType} == {
        "missing_from_epcr",
        "missing_from_mar",
        "dose_mismatch",
    }


def test_resolution_action_values() -> None:
    assert {a.value for a in EpcrResolutionAction} == {
        "manual_correction",
        "auto_correction",
        "waived",
    }


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


def test_create_request_minimal_defaults_empty_lists() -> None:
    req = EpcrReconciliationCreateRequest(epcr_chart_id="chart-1", patient_id="pat-1")
    assert req.encounter_id is None
    assert req.medications_from_epcr == []
    assert req.medications_from_mar == []


def test_create_request_requires_chart_and_patient() -> None:
    with pytest.raises(ValidationError):
        EpcrReconciliationCreateRequest(patient_id="pat-1")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        EpcrReconciliationCreateRequest(epcr_chart_id="chart-1")  # type: ignore[call-arg]


def test_create_request_with_medication_items() -> None:
    req = EpcrReconciliationCreateRequest(
        epcr_chart_id="chart-1",
        patient_id="pat-1",
        encounter_id="enc-1",
        medications_from_epcr=[
            {"name": "Aspirin", "rxnorm_code": "1191", "dose": "324 mg", "route": "PO"}
        ],
        medications_from_mar=[{"name": "Aspirin", "dose": "81 mg", "route": "PO"}],
    )
    assert isinstance(req.medications_from_epcr[0], EpcrMedItem)
    assert req.medications_from_epcr[0].rxnorm_code == "1191"


def test_med_item_name_required_and_bounded() -> None:
    with pytest.raises(ValidationError):
        EpcrMedItem(name="")  # min_length=1
    with pytest.raises(ValidationError):
        EpcrMedItem(name="x" * 501)  # max_length=500


def test_resolve_request_enum_enforced() -> None:
    ok = EpcrReconciliationResolveRequest(resolution_action="waived")
    assert ok.resolution_action is EpcrResolutionAction.WAIVED

    with pytest.raises(ValidationError):
        EpcrReconciliationResolveRequest(resolution_action="not_a_real_action")


def test_resolve_notes_max_length() -> None:
    with pytest.raises(ValidationError):
        EpcrReconciliationResolveRequest(
            resolution_action="manual_correction", resolution_notes="z" * 2001
        )


# ---------------------------------------------------------------------------
# Response models (round-tripped against real ``_serialize`` shapes)
# ---------------------------------------------------------------------------


def _clean_serialized_row() -> dict:
    """A ``_serialize`` body for a session with no discrepancies (pre-resolve)."""
    return {
        "reconciliation_id": "3f9a5b2c-1d4e-4a7b-9c8d-0e1f2a3b4c5d",
        "tenant_id": "tenant-1",
        "epcr_chart_id": "chart-1",
        "encounter_id": "enc-1",
        "patient_id": "pat-1",
        "reconciliation_status": "in_progress",
        "medications_from_epcr": [{"name": "Aspirin", "dose": "81 mg", "route": "PO"}],
        "medications_from_mar": [{"name": "Aspirin", "dose": "81 mg", "route": "PO"}],
        "has_discrepancies": False,
        "discrepancies": [],
        "discrepancy_type": None,
        "resolved_by": None,
        "resolved_date": None,
        "resolution_notes": None,
        "resolution_action": None,
        "created_by": "user-1",
        "created_at": "2026-07-24T23:03:21",
        "updated_at": "2026-07-24T23:03:21",
    }


def _discrepancy_serialized_row() -> dict:
    """A ``_serialize`` body carrying a dose_mismatch + a missing_from_mar."""
    row = _clean_serialized_row()
    row.update(
        {
            "reconciliation_status": "discrepancy",
            "medications_from_epcr": [
                {
                    "name": "Aspirin",
                    "rxnorm_code": "1191",
                    "dose": "324 mg",
                    "route": "PO",
                },
                {"name": "Fentanyl", "dose": "50 mcg", "route": "IV"},
            ],
            "medications_from_mar": [
                {
                    "name": "Aspirin",
                    "rxnorm_code": "1191",
                    "dose": "81 mg",
                    "route": "PO",
                }
            ],
            "has_discrepancies": True,
            "discrepancies": [
                {
                    "type": "dose_mismatch",
                    "identity_key": "rxnorm:1191",
                    "epcr": {
                        "name": "Aspirin",
                        "rxnorm_code": "1191",
                        "dose": "324 mg",
                        "route": "PO",
                    },
                    "mar": {
                        "name": "Aspirin",
                        "rxnorm_code": "1191",
                        "dose": "81 mg",
                        "route": "PO",
                    },
                    "field_diffs": {"dose": {"epcr": "324 mg", "mar": "81 mg"}},
                },
                {
                    "type": "missing_from_mar",
                    "identity_key": "name:fentanyl",
                    "epcr": {"name": "Fentanyl", "dose": "50 mcg", "route": "IV"},
                    "mar": None,
                },
            ],
            "discrepancy_type": "dose_mismatch,missing_from_mar",
        }
    )
    return row


def test_response_parses_clean_serialized_row() -> None:
    resp = EpcrReconciliationResponse.model_validate(_clean_serialized_row())
    assert resp.reconciliation_status is EpcrReconciliationStatus.IN_PROGRESS
    assert resp.has_discrepancies is False
    assert resp.discrepancies == []
    assert resp.resolution_action is None
    assert resp.created_at is not None


def test_response_parses_discrepancy_serialized_row() -> None:
    resp = EpcrReconciliationResponse.model_validate(_discrepancy_serialized_row())
    assert resp.reconciliation_status is EpcrReconciliationStatus.DISCREPANCY
    assert resp.has_discrepancies is True
    assert len(resp.discrepancies) == 2

    dose = resp.discrepancies[0]
    assert isinstance(dose, EpcrReconciliationDiscrepancy)
    assert dose.type is EpcrDiscrepancyType.DOSE_MISMATCH
    assert dose.field_diffs is not None
    assert isinstance(dose.field_diffs["dose"], EpcrFieldDiff)
    assert dose.field_diffs["dose"].epcr == "324 mg"
    assert dose.field_diffs["dose"].mar == "81 mg"

    missing = resp.discrepancies[1]
    assert missing.type is EpcrDiscrepancyType.MISSING_FROM_MAR
    assert missing.mar is None
    assert missing.field_diffs is None
    assert resp.discrepancy_type == "dose_mismatch,missing_from_mar"


def test_resolved_response_shape() -> None:
    row = _clean_serialized_row()
    row.update(
        {
            "reconciliation_status": "complete",
            "resolved_by": "clinician-9",
            "resolved_date": "2026-07-24T23:10:00",
            "resolution_action": "waived",
            "resolution_notes": "Reviewed; MAR is authoritative.",
        }
    )
    resp = EpcrReconciliationResponse.model_validate(row)
    assert resp.reconciliation_status is EpcrReconciliationStatus.COMPLETE
    assert resp.resolution_action is EpcrResolutionAction.WAIVED
    assert resp.resolved_by == "clinician-9"


def test_list_response_round_trip() -> None:
    payload = {
        "tenant_id": "tenant-1",
        "reconciliations": [_clean_serialized_row(), _discrepancy_serialized_row()],
        "generated_at": "2026-07-24T23:12:00+00:00",
    }
    listed = EpcrReconciliationListResponse.model_validate(payload)
    assert listed.tenant_id == "tenant-1"
    assert len(listed.reconciliations) == 2
    assert (
        listed.reconciliations[1].reconciliation_status
        is EpcrReconciliationStatus.DISCREPANCY
    )
