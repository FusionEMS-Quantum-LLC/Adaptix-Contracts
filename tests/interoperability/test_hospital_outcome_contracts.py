"""Hospital outcome received event contract (FND-001).

An outcome attached to the wrong chart is the failure this contract exists
to prevent, so every match status is checked against the chart references it
may and may not carry, and the PHI boundary is checked directly.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from adaptix_contracts.events.registry import ALL_EVENTS, producer_of
from adaptix_contracts.interoperability.delivery import (
    INTEROPERABILITY_EXCHANGE_DELIVERY_STATE_CHANGED,
)
from adaptix_contracts.interoperability.gateway import ExchangeGatewayKind
from adaptix_contracts.interoperability.hospital_outcome import (
    HOSPITAL_OUTCOME_MAX_CANDIDATES,
    HOSPITAL_OUTCOME_RECEIVED,
    HospitalOutcomeMatchStatus,
    HospitalOutcomeReceivedPayload,
)
from adaptix_contracts.interoperability.provenance import (
    DataProvenance,
    TransformationType,
)

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


def _outcome(**overrides: object) -> HospitalOutcomeReceivedPayload:
    data: dict[str, object] = {
        "outcome_id": "out-1",
        "tenant_id": "tenant-cert-a",
        "exchange_id": "ex-in-1",
        "gateway_id": "gw-hosp-1",
        "gateway_kind": ExchangeGatewayKind.HOSPITAL_INTERFACE,
        "facility_id": "fac-cert-regional",
        "match_status": HospitalOutcomeMatchStatus.MATCHED,
        "matched_chart_id": "chart-cert-1",
        "payload_ref": "s3://certification/outcomes/out-1",
        "payload_sha256": "b" * 64,
        "outcome_recorded_at": NOW,
        "received_at": NOW,
        "correlation_id": "corr-1",
        "idempotency_key": "hosp-msg-1",
    }
    data.update(overrides)
    return HospitalOutcomeReceivedPayload.model_validate(data)


def test_match_status_vocabulary_is_exactly_the_card() -> None:
    assert {status.value for status in HospitalOutcomeMatchStatus} == {
        "MATCHED",
        "AMBIGUOUS",
        "NO_MATCH",
    }


def test_matched_names_exactly_one_chart() -> None:
    assert _outcome().matched_chart_id == "chart-cert-1"
    with pytest.raises(ValidationError, match="names matched_chart_id"):
        _outcome(matched_chart_id=None)
    with pytest.raises(ValidationError, match="carries no candidate_chart_ids"):
        _outcome(candidate_chart_ids=("chart-cert-2",))


def test_ambiguous_lists_two_distinct_candidates_and_links_nothing() -> None:
    ambiguous = _outcome(
        match_status=HospitalOutcomeMatchStatus.AMBIGUOUS,
        matched_chart_id=None,
        candidate_chart_ids=("chart-cert-1", "chart-cert-2"),
    )
    assert ambiguous.candidate_chart_ids == ("chart-cert-1", "chart-cert-2")
    with pytest.raises(ValidationError, match="at least two distinct"):
        _outcome(
            match_status=HospitalOutcomeMatchStatus.AMBIGUOUS,
            matched_chart_id=None,
            candidate_chart_ids=("chart-cert-1",),
        )
    with pytest.raises(ValidationError, match="at least two distinct"):
        _outcome(
            match_status=HospitalOutcomeMatchStatus.AMBIGUOUS,
            matched_chart_id=None,
            candidate_chart_ids=("chart-cert-1", "chart-cert-1"),
        )
    with pytest.raises(ValidationError, match="linked to no chart"):
        _outcome(
            match_status=HospitalOutcomeMatchStatus.AMBIGUOUS,
            candidate_chart_ids=("chart-cert-1", "chart-cert-2"),
        )


def test_no_match_links_nothing_and_lists_nothing() -> None:
    no_match = _outcome(
        match_status=HospitalOutcomeMatchStatus.NO_MATCH, matched_chart_id=None
    )
    assert no_match.matched_chart_id is None
    with pytest.raises(ValidationError, match="linked to no chart"):
        _outcome(match_status=HospitalOutcomeMatchStatus.NO_MATCH)
    with pytest.raises(ValidationError, match="linked to no chart"):
        _outcome(
            match_status=HospitalOutcomeMatchStatus.NO_MATCH,
            matched_chart_id=None,
            matched_global_encounter_id="ge-1",
        )
    with pytest.raises(ValidationError, match="NO_MATCH outcome carries no"):
        _outcome(
            match_status=HospitalOutcomeMatchStatus.NO_MATCH,
            matched_chart_id=None,
            candidate_chart_ids=("chart-cert-1", "chart-cert-2"),
        )


def test_candidate_list_is_bounded() -> None:
    too_many = tuple(f"chart-{i}" for i in range(HOSPITAL_OUTCOME_MAX_CANDIDATES + 1))
    with pytest.raises(ValidationError):
        _outcome(
            match_status=HospitalOutcomeMatchStatus.AMBIGUOUS,
            matched_chart_id=None,
            candidate_chart_ids=too_many,
        )


@pytest.mark.parametrize(
    "phi_field",
    ["patient_name", "date_of_birth", "medical_record_number", "diagnosis_codes"],
)
def test_outcome_event_refuses_patient_content(phi_field: str) -> None:
    with pytest.raises(ValidationError, match="extra"):
        _outcome(**{phi_field: "certification-value"})


def test_outcome_event_reuses_data_provenance() -> None:
    provenance = DataProvenance(
        source_agency_id="fac-cert-regional",
        source_tenant_id="tenant-cert-a",
        source_service="hospital_interface",
        source_record_id="hosp-msg-1",
        transformation_type=TransformationType.NORMALIZED,
        confidence=1.0,
        observed_at=NOW,
        received_at=NOW,
    )
    assert _outcome(provenance=(provenance,)).provenance == (provenance,)


def test_outcome_event_requires_aware_times() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        _outcome(received_at=datetime(2026, 9, 24, 12, 0))


def test_events_are_registered_ahead_of_their_producers() -> None:
    expected = {
        HOSPITAL_OUTCOME_RECEIVED: "epcr",
        INTEROPERABILITY_EXCHANGE_DELIVERY_STATE_CHANGED: "core",
    }
    for event_type, slug in expected.items():
        assert ALL_EVENTS[event_type] == {"version": "1.0", "source_service": slug}
        assert producer_of(event_type).slug == slug
    assert HOSPITAL_OUTCOME_RECEIVED == "hospital.outcome.received"
