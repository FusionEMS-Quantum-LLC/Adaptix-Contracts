from adaptix_contracts.interoperability import (
    IncidentIdentity,
    PublicSafetyIncident,
    SourceRecordReference,
)


def test_incident_graph_preserves_independent_source_records() -> None:
    incident = PublicSafetyIncident(
        identity=IncidentIdentity(
            global_incident_id="GI-123",
            originating_agency_id="AGENCY-A",
            primary_incident_number="12345",
            incident_type="MVC",
            incident_status="ACTIVE",
        ),
        source_records=[
            SourceRecordReference(
                source_agency_id="AGENCY-A",
                source_service="cad",
                source_record_id="12345",
            ),
            SourceRecordReference(
                source_agency_id="AGENCY-B",
                source_service="fire",
                source_record_id="F-0093",
            ),
            SourceRecordReference(
                source_agency_id="AGENCY-C",
                source_service="epcr",
                source_record_id="PCR-887",
                source_standard="NEMSIS",
                source_standard_version="3.5.1",
            ),
        ],
    )

    assert incident.identity.global_incident_id == "GI-123"
    assert [record.source_record_id for record in incident.source_records] == [
        "12345",
        "F-0093",
        "PCR-887",
    ]
