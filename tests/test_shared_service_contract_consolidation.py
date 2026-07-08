"""Regression tests for the shared-service contract consolidation (1.5.0).

Covers the additive DTOs, enums, and events added to the six shared-service
contract modules (audit, notification, reference_data, geo, forms, facility),
the PayerType field-identity divergence that is versioned rather than unified,
the backward-compatible deprecation of the direct-write audit client, and the
GeoClient consumer helper.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from pydantic import BaseModel

from adaptix_contracts import schemas
from adaptix_contracts.schemas import (
    AddressSuggestion,
    AuditActorType,
    AuditExportFormat,
    AuditExportResponse,
    AuditExportStatus,
    AuditIngestRequest,
    AuditIngestResponse,
    AuditSearchResponse,
    AutocompleteRequest,
    AutocompleteResult,
    CmsNpiSyncRequest,
    CmsNpiSyncResult,
    DistanceRequest,
    FacilityAliasCreateRequest,
    FacilityCapability,
    FacilityCreateRequest,
    FacilityMappingUpsertRequest,
    FacilityMergedEvent,
    FacilityRegisteredEvent,
    FacilitySearchRequest,
    FacilitySearchResponse,
    FacilityType,
    FacilityUpdatedEvent,
    FacilityUpdateRequest,
    FormPublishedEvent,
    FormSchema,
    FormSubmission,
    FormSubmissionCreateRequest,
    FormSubmissionListResponse,
    FormSubmittedEvent,
    FormTemplateCreateRequest,
    FormTemplateListResponse,
    FormTemplateUpdateRequest,
    FormValidationError,
    FormVersionCreateRequest,
    GeoClient,
    GeoCoordinate,
    GeocodeRequest,
    GeocodeResult,
    NotificationChannel,
    NotificationPreferenceSet,
    NotificationQueuedEvent,
    NotificationReadEvent,
    NotificationSendRequest,
    NotificationSentEvent,
    ReferenceDataItem,
    ReferenceDataListCreateRequest,
    ReferenceDataListPublishedEvent,
    ReferenceDataListResponse,
    ReferenceDataListUpdatedEvent,
    ReferenceDataListUpdateRequest,
    ReferenceDataPayerType,
    ReferenceDataPublishResponse,
    ReferenceDataQuery,
    ReverseGeocodeRequest,
    RouteRequest,
    ServiceLevel,
    StateCode,
)


def _ts() -> datetime:
    return datetime(2026, 7, 8, 12, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Round-trip factories for the new surface
# ---------------------------------------------------------------------------


def _audit_ingest_request() -> AuditIngestRequest:
    return AuditIngestRequest(
        tenant_id=uuid4(),
        actor_user_id=uuid4(),
        actor_type=AuditActorType.SERVICE,
        action="chart_signed",
        resource_type="chart",
        resource_id="chart-001",
        idempotency_key="idem-001",
        metadata={"ip": "10.0.0.1"},
        occurred_at=_ts(),
    )


def _audit_ingest_response() -> AuditIngestResponse:
    return AuditIngestResponse(event_id=uuid4(), duplicate=False, occurred_at=_ts())


def _audit_search_response() -> AuditSearchResponse:
    return AuditSearchResponse(events=[], total=0, limit=50, offset=0)


def _audit_export_response() -> AuditExportResponse:
    return AuditExportResponse(
        export_id=uuid4(),
        tenant_id=uuid4(),
        export_format=AuditExportFormat.NDJSON,
        status=AuditExportStatus.COMPLETED,
        record_count=1200,
        location="s3://adaptix-audit-exports/tenant/abc.ndjson",
        requested_at=_ts(),
        completed_at=_ts(),
    )


def _notification_send_request() -> NotificationSendRequest:
    return NotificationSendRequest(
        tenant_id=uuid4(),
        recipient_id=uuid4(),
        channel=NotificationChannel.EMAIL,
        category="billing",
        subject="Claim denied",
        body="Your claim was denied.",
        idempotency_key="idem-002",
    )


def _notification_preference_set() -> NotificationPreferenceSet:
    return NotificationPreferenceSet(
        tenant_id=uuid4(),
        user_id=uuid4(),
        category="billing",
        email_enabled=True,
        sms_enabled=False,
        quiet_hours_start="22:00",
        quiet_hours_end="06:00",
        timezone="America/Chicago",
        updated_at=_ts(),
    )


def _notification_queued_event() -> NotificationQueuedEvent:
    return NotificationQueuedEvent(
        notification_id=uuid4(),
        tenant_id=uuid4(),
        recipient_id=uuid4(),
        channel=NotificationChannel.IN_APP,
        category="dispatch",
        queued_at=_ts(),
    )


def _notification_sent_event() -> NotificationSentEvent:
    return NotificationSentEvent(
        notification_id=uuid4(),
        tenant_id=uuid4(),
        recipient_id=uuid4(),
        channel=NotificationChannel.SMS,
        provider_message_id="tlnx-123",
        sent_at=_ts(),
    )


def _notification_read_event() -> NotificationReadEvent:
    return NotificationReadEvent(
        notification_id=uuid4(),
        tenant_id=uuid4(),
        recipient_id=uuid4(),
        read_at=_ts(),
    )


def _reference_data_list_create_request() -> ReferenceDataListCreateRequest:
    return ReferenceDataListCreateRequest(
        list_key="service_levels",
        name="Service Levels",
        items=[
            ReferenceDataItem(code="bls", label="Basic Life Support"),
            ReferenceDataItem(code="als", label="Advanced Life Support"),
        ],
    )


def _reference_data_list_update_request() -> ReferenceDataListUpdateRequest:
    return ReferenceDataListUpdateRequest(name="Service Levels (2026)")


def _reference_data_query() -> ReferenceDataQuery:
    return ReferenceDataQuery(list_key="payer_types", limit=25)


def _reference_data_list_response() -> ReferenceDataListResponse:
    return ReferenceDataListResponse(lists=[], total=0, limit=50, offset=0)


def _reference_data_publish_response() -> ReferenceDataPublishResponse:
    return ReferenceDataPublishResponse(
        list_key="payer_types", version=3, published_at=_ts()
    )


def _reference_data_published_event() -> ReferenceDataListPublishedEvent:
    return ReferenceDataListPublishedEvent(
        list_key="payer_types", version=3, published_at=_ts()
    )


def _reference_data_updated_event() -> ReferenceDataListUpdatedEvent:
    return ReferenceDataListUpdatedEvent(
        list_key="payer_types", version=3, updated_at=_ts()
    )


def _reverse_geocode_request() -> ReverseGeocodeRequest:
    return ReverseGeocodeRequest(
        tenant_id=uuid4(),
        coordinate=GeoCoordinate(latitude=43.0731, longitude=-89.4012),
    )


def _autocomplete_request() -> AutocompleteRequest:
    return AutocompleteRequest(tenant_id=uuid4(), query="100 Main", limit=5)


def _autocomplete_result() -> AutocompleteResult:
    return AutocompleteResult(
        suggestions=[
            AddressSuggestion(
                formatted_address="100 Main St, Madison, WI 53703",
                coordinate=GeoCoordinate(latitude=43.0731, longitude=-89.4012),
                provider="stadia",
            )
        ],
        provider="stadia",
    )


def _route_request() -> RouteRequest:
    return RouteRequest(
        tenant_id=uuid4(),
        origin=GeoCoordinate(latitude=43.0, longitude=-89.5),
        destination=GeoCoordinate(latitude=43.1, longitude=-89.3),
    )


def _distance_request() -> DistanceRequest:
    return DistanceRequest(
        tenant_id=uuid4(),
        origin=GeoCoordinate(latitude=43.0, longitude=-89.5),
        destination=GeoCoordinate(latitude=43.1, longitude=-89.3),
    )


def _form_submission() -> FormSubmission:
    return FormSubmission(
        id=uuid4(),
        tenant_id=uuid4(),
        template_id=uuid4(),
        version_id=uuid4(),
        version=1,
        submitted_by=uuid4(),
        values={"patient_name": "Jane Doe"},
        is_valid=False,
        validation_errors=[
            FormValidationError(
                field_key="dob", message="required", rule_type="required"
            )
        ],
        created_at=_ts(),
    )


def _form_template_create_request() -> FormTemplateCreateRequest:
    return FormTemplateCreateRequest(
        key="pcs",
        name="Physician Certification Statement",
        form_schema=FormSchema(title="PCS", fields=[]),
    )


def _form_template_update_request() -> FormTemplateUpdateRequest:
    return FormTemplateUpdateRequest(name="PCS v2")


def _form_version_create_request() -> FormVersionCreateRequest:
    return FormVersionCreateRequest(form_schema=FormSchema(title="PCS", fields=[]))


def _form_submission_create_request() -> FormSubmissionCreateRequest:
    return FormSubmissionCreateRequest(
        values={"patient_name": "Jane Doe"}, idempotency_key="idem-003"
    )


def _form_template_list_response() -> FormTemplateListResponse:
    return FormTemplateListResponse(templates=[], total=0, limit=50, offset=0)


def _form_submission_list_response() -> FormSubmissionListResponse:
    return FormSubmissionListResponse(submissions=[], total=0, limit=50, offset=0)


def _form_published_event() -> FormPublishedEvent:
    return FormPublishedEvent(
        template_id=uuid4(), tenant_id=uuid4(), key="pcs", version=2, published_at=_ts()
    )


def _form_submitted_event() -> FormSubmittedEvent:
    return FormSubmittedEvent(
        submission_id=uuid4(),
        template_id=uuid4(),
        tenant_id=uuid4(),
        version=2,
        is_valid=True,
        submitted_at=_ts(),
    )


def _facility_capability() -> FacilityCapability:
    return FacilityCapability(
        code="trauma_level_1", name="Trauma Level I", category="trauma"
    )


def _facility_search_request() -> FacilitySearchRequest:
    return FacilitySearchRequest(
        query="Mercy",
        facility_type=FacilityType.HOSPITAL,
        state="WI",
        near_latitude=43.0731,
        near_longitude=-89.4012,
        radius_miles=25.0,
    )


def _facility_search_response() -> FacilitySearchResponse:
    return FacilitySearchResponse(facilities=[], total=0, limit=50, offset=0)


def _facility_create_request() -> FacilityCreateRequest:
    return FacilityCreateRequest(
        name="Mercy General Hospital",
        facility_type=FacilityType.HOSPITAL,
        state="WI",
        capabilities=[_facility_capability()],
    )


def _facility_update_request() -> FacilityUpdateRequest:
    return FacilityUpdateRequest(name="Mercy General")


def _facility_alias_create_request() -> FacilityAliasCreateRequest:
    return FacilityAliasCreateRequest(alias="Mercy Hosp", source="nemsis")


def _facility_mapping_upsert_request() -> FacilityMappingUpsertRequest:
    return FacilityMappingUpsertRequest(npi="1234567890", state="WI")


def _cms_npi_sync_request() -> CmsNpiSyncRequest:
    return CmsNpiSyncRequest(npi="1234567890", state="WI")


def _cms_npi_sync_result() -> CmsNpiSyncResult:
    return CmsNpiSyncResult(
        matched=True, facility_id=uuid4(), npi="1234567890", name="Mercy General"
    )


def _facility_registered_event() -> FacilityRegisteredEvent:
    return FacilityRegisteredEvent(
        facility_id=uuid4(), facility_type=FacilityType.HOSPITAL, registered_at=_ts()
    )


def _facility_updated_event() -> FacilityUpdatedEvent:
    return FacilityUpdatedEvent(facility_id=uuid4(), updated_at=_ts())


def _facility_merged_event() -> FacilityMergedEvent:
    return FacilityMergedEvent(
        source_facility_id=uuid4(), target_facility_id=uuid4(), merged_at=_ts()
    )


NEW_SURFACE_FACTORIES = [
    (_audit_ingest_request, AuditIngestRequest),
    (_audit_ingest_response, AuditIngestResponse),
    (_audit_search_response, AuditSearchResponse),
    (_audit_export_response, AuditExportResponse),
    (_notification_send_request, NotificationSendRequest),
    (_notification_preference_set, NotificationPreferenceSet),
    (_notification_queued_event, NotificationQueuedEvent),
    (_notification_sent_event, NotificationSentEvent),
    (_notification_read_event, NotificationReadEvent),
    (_reference_data_list_create_request, ReferenceDataListCreateRequest),
    (_reference_data_list_update_request, ReferenceDataListUpdateRequest),
    (_reference_data_query, ReferenceDataQuery),
    (_reference_data_list_response, ReferenceDataListResponse),
    (_reference_data_publish_response, ReferenceDataPublishResponse),
    (_reference_data_published_event, ReferenceDataListPublishedEvent),
    (_reference_data_updated_event, ReferenceDataListUpdatedEvent),
    (_reverse_geocode_request, ReverseGeocodeRequest),
    (_autocomplete_request, AutocompleteRequest),
    (_autocomplete_result, AutocompleteResult),
    (_route_request, RouteRequest),
    (_distance_request, DistanceRequest),
    (_form_submission, FormSubmission),
    (_form_template_create_request, FormTemplateCreateRequest),
    (_form_template_update_request, FormTemplateUpdateRequest),
    (_form_version_create_request, FormVersionCreateRequest),
    (_form_submission_create_request, FormSubmissionCreateRequest),
    (_form_template_list_response, FormTemplateListResponse),
    (_form_submission_list_response, FormSubmissionListResponse),
    (_form_published_event, FormPublishedEvent),
    (_form_submitted_event, FormSubmittedEvent),
    (_facility_capability, FacilityCapability),
    (_facility_search_request, FacilitySearchRequest),
    (_facility_search_response, FacilitySearchResponse),
    (_facility_create_request, FacilityCreateRequest),
    (_facility_update_request, FacilityUpdateRequest),
    (_facility_alias_create_request, FacilityAliasCreateRequest),
    (_facility_mapping_upsert_request, FacilityMappingUpsertRequest),
    (_cms_npi_sync_request, CmsNpiSyncRequest),
    (_cms_npi_sync_result, CmsNpiSyncResult),
    (_facility_registered_event, FacilityRegisteredEvent),
    (_facility_updated_event, FacilityUpdatedEvent),
    (_facility_merged_event, FacilityMergedEvent),
]


@pytest.mark.parametrize(("factory", "expected_type"), NEW_SURFACE_FACTORIES)
def test_new_surface_round_trip(factory, expected_type) -> None:
    """Every new shared-service DTO/event survives a JSON round trip."""

    contract = factory()
    restored = expected_type.model_validate_json(contract.model_dump_json())
    assert restored == contract
    assert isinstance(contract, BaseModel)


# ---------------------------------------------------------------------------
# Canonical enums
# ---------------------------------------------------------------------------


def test_service_level_and_state_code_values() -> None:
    assert {level.value for level in ServiceLevel} == {
        "bls",
        "als",
        "specialty",
        "cct",
        "air_medical",
    }
    # 50 states + DC + 5 territories = 56 codes.
    assert len(list(StateCode)) == 56
    assert StateCode.WI.value == "WI"


def test_payer_type_divergence_is_versioned_not_unified() -> None:
    """Canonical PayerType is the union superset; domain enums stay divergent."""

    from adaptix_contracts.schemas.billing_contracts import (
        PayerType as BillingPayerType,
    )
    from adaptix_contracts.schemas.intake_contracts import PayerType as IntakePayerType

    canonical = {member.value for member in ReferenceDataPayerType}
    billing = {member.value for member in BillingPayerType}
    intake = {member.value for member in IntakePayerType}

    # Canonical is the superset of both domain enums.
    assert billing.issubset(canonical)
    assert intake.issubset(canonical)
    assert canonical == billing | intake

    # The divergence is real and preserved (not silently unified).
    assert "other" in billing and "other" not in intake
    assert {"tricare", "workers_comp"}.issubset(intake)
    assert {"tricare", "workers_comp"}.isdisjoint(billing)


# ---------------------------------------------------------------------------
# Deprecated direct-write audit client — backward compatible
# ---------------------------------------------------------------------------


def test_deprecated_audit_client_still_importable() -> None:
    """The direct-write client stays importable for CAD/Fire until 2.0.0.

    The legacy module depends on SQLAlchemy (supplied by its consumer services,
    not by the contracts package itself), so this assertion only runs where that
    optional dependency is present.
    """

    pytest.importorskip("sqlalchemy")
    import adaptix_contracts.audit_contracts as legacy

    assert legacy.__deprecated__ is True
    assert hasattr(legacy, "AuditServiceClient")
    assert hasattr(legacy, "AuditLogEntry")
    # CAD migration 019 creates this table from the model — name must not drift.
    assert legacy.AuditLogEntry.__tablename__ == "audit_log_entries"


def test_new_surface_exported_at_package_root() -> None:
    """New shared-service symbols are re-exported from the package root."""

    import adaptix_contracts

    for _factory, model in NEW_SURFACE_FACTORIES:
        assert model.__name__ in adaptix_contracts.__all__
        assert getattr(adaptix_contracts, model.__name__) is model
    for name in ("ReferenceDataPayerType", "ServiceLevel", "StateCode", "GeoClient"):
        assert name in schemas.__all__


# ---------------------------------------------------------------------------
# GeoClient consumer helper
# ---------------------------------------------------------------------------


async def test_geo_client_geocode_parses_result() -> None:
    """GeoClient POSTs the request and parses a GeocodeResult response."""

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            json={
                "coordinate": {"latitude": 43.0731, "longitude": -89.4012},
                "formatted_address": "100 Main St, Madison, WI 53703",
                "matched": True,
                "confidence": 0.98,
                "provider": "stadia",
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = GeoClient("http://adaptix-geo:8000", client=http_client)
        result = await client.geocode(
            GeocodeRequest(tenant_id=uuid4(), address="100 Main St")
        )

    assert isinstance(result, GeocodeResult)
    assert result.matched is True
    assert result.coordinate.latitude == 43.0731
    assert captured["url"] == "http://adaptix-geo:8000/api/v1/geo/geocode"
