from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from adaptix_contracts.interoperability import PublicSafetyExchangeEnvelope


NOW = datetime.now(timezone.utc)


def _envelope(**overrides: object) -> PublicSafetyExchangeEnvelope:
    data: dict[str, object] = {
        "exchange_id": "EX-1",
        "correlation_id": "CORR-1",
        "origin_tenant_id": "TEN-A",
        "origin_agency_id": "AGENCY-A",
        "origin_service": "epcr",
        "origin_record_id": "PCR-1",
        "origin_record_version": "7",
        "recipient_agency_id": "AGENCY-B",
        "recipient_peer_id": "PEER-B",
        "global_incident_id": "GI-1",
        "source_incident_id": "CAD-1",
        "global_encounter_id": "GE-1",
        "source_encounter_id": "PCR-1",
        "patient_identity_ref": "PAT-1",
        "resource_type": "patient_encounter_summary",
        "source_standard": "NEMSIS",
        "source_standard_version": "3.5.1",
        "canonical_resource_version": "1.0",
        "payload_ref": "s3://protected/reference",
        "payload_sha256": "a" * 64,
        "purpose_of_use": "TREATMENT",
        "sharing_policy_id": "POL-1",
        "consent_decision_ref": "CONSENT-1",
        "sensitivity": "PHI",
        "occurred_at": NOW,
        "created_at": NOW,
        "idempotency_key": "idem-1",
    }
    data.update(overrides)
    return PublicSafetyExchangeEnvelope(**data)


def test_exchange_contract_is_reference_only() -> None:
    dumped = _envelope().model_dump(mode="json")
    assert dumped["payload_ref"] == "s3://protected/reference"
    assert "payload" not in dumped
    assert dumped["idempotency_key"] == "idem-1"


def test_exchange_rejects_raw_payload_and_invalid_hash() -> None:
    with pytest.raises(ValidationError):
        _envelope(payload_sha256="not-a-hash")
    with pytest.raises(ValidationError):
        _envelope(raw_phi={"patient": "must-not-live-here"})


def test_exchange_rejects_expiry_before_creation() -> None:
    with pytest.raises(ValidationError):
        _envelope(expires_at=NOW - timedelta(seconds=1))
