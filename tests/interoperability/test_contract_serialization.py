from datetime import datetime, timezone

from adaptix_contracts.interoperability import DataProvenance, TransformationType


def test_provenance_round_trip_preserves_source_and_mapping_evidence() -> None:
    provenance = DataProvenance(
        source_agency_id="AGENCY-A",
        source_tenant_id="TENANT-A",
        source_service="epcr",
        source_record_id="PCR-1",
        source_field="eTimes.06",
        source_standard="NEMSIS",
        source_standard_version="3.5.1",
        mapping_set_id="PRODUCTION",
        mapping_rule_id="MAP-1",
        mapping_version="1.0",
        transformation_type=TransformationType.DIRECT,
        confidence=1.0,
        observed_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
    )

    restored = DataProvenance.model_validate_json(provenance.model_dump_json())
    assert restored == provenance
    assert restored.source_field == "eTimes.06"
    assert restored.mapping_rule_id == "MAP-1"
