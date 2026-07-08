"""Round-trip and surface tests for the shared-service contracts.

Covers the AdaptixCore shared services (notification, facility, geo,
signalcore, forms, audit, reference-data, payment, mailroom, rtc, office ally,
device, app access). Each representative model is constructed with real values
and verified to survive a JSON serialize/deserialize round trip without drift.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import BaseModel, ValidationError

from adaptix_contracts import schemas
from adaptix_contracts.schemas import (
    AppAccessDecision,
    AppAccessEffect,
    AppAccessPolicy,
    AuditEvent,
    AuditExportFormat,
    AuditExportRequest,
    AuditSearchQuery,
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    DevicePlatform,
    DeviceRegistration,
    DeviceStatus,
    DistanceResult,
    FacilityContact,
    FacilityMapping,
    FacilityRecord,
    FacilityType,
    FormFieldDefinition,
    FormFieldType,
    FormSchema,
    FormTemplate,
    FormVersion,
    GeoCoordinate,
    GeocodeRequest,
    GeocodeResult,
    InvoiceRef,
    InvoiceStatus,
    MailClass,
    MailPacket,
    MailRecipient,
    MailReturnReason,
    MailReturnStatus,
    MailSender,
    MailStatus,
    NotificationChannel,
    NotificationDeliveryStatus,
    NotificationPreference,
    NotificationRequest,
    NotificationStatus,
    NotificationTemplate,
    OfficeAllyResponse,
    OfficeAllySubmission,
    PaymentEvent,
    PaymentEventType,
    PortalSessionRequest,
    ReferenceDataItem,
    ReferenceDataList,
    RouteEstimate,
    RTCParticipantToken,
    RTCRoomStatus,
    RTCSession,
    ServiceArea,
    SignalCoreEvent,
    SignalCoreTrigger,
    StripeCustomerRef,
    SubscriptionRef,
    SubscriptionStatus,
)


def _ts() -> datetime:
    """Return a deterministic UTC timestamp for regression tests."""

    return datetime(2026, 7, 8, 12, 0, tzinfo=UTC)


def _notification_delivery_status() -> NotificationDeliveryStatus:
    return NotificationDeliveryStatus(
        notification_id=uuid4(),
        tenant_id=uuid4(),
        recipient_id=uuid4(),
        channel=NotificationChannel.PUSH,
        status=NotificationStatus.DELIVERED,
        correlation_id="corr-001",
        attempts=1,
        delivered_at=_ts(),
        updated_at=_ts(),
    )


def _notification_template() -> NotificationTemplate:
    return NotificationTemplate(
        id=uuid4(),
        tenant_id=uuid4(),
        key="claim.denied",
        channel=NotificationChannel.EMAIL,
        subject_template="Claim {{claim_id}} denied",
        body_template="Your claim was denied.",
        created_at=_ts(),
        updated_at=_ts(),
    )


def _notification_preference() -> NotificationPreference:
    return NotificationPreference(
        id=uuid4(),
        tenant_id=uuid4(),
        user_id=uuid4(),
        channel=NotificationChannel.SMS,
        category="billing",
        enabled=False,
        updated_at=_ts(),
    )


def _facility_record() -> FacilityRecord:
    return FacilityRecord(
        id=uuid4(),
        tenant_id=uuid4(),
        name="Mercy General Hospital",
        facility_type=FacilityType.HOSPITAL,
        address_line1="100 Main St",
        city="Madison",
        state="WI",
        postal_code="53703",
        latitude=43.0731,
        longitude=-89.4012,
        contacts=[FacilityContact(name="ED Charge", phone="608-555-0100")],
        mapping=FacilityMapping(
            facility_id=uuid4(),
            cms_certification_number="520001",
            npi="1234567890",
            state="WI",
        ),
        created_at=_ts(),
        updated_at=_ts(),
    )


def _geocode_request() -> GeocodeRequest:
    return GeocodeRequest(
        tenant_id=uuid4(),
        correlation_id="corr-002",
        address="100 Main St",
        city="Madison",
        state="WI",
        postal_code="53703",
    )


def _geocode_result() -> GeocodeResult:
    return GeocodeResult(
        coordinate=GeoCoordinate(latitude=43.0731, longitude=-89.4012),
        formatted_address="100 Main St, Madison, WI 53703",
        matched=True,
        confidence=0.98,
        provider="stadia",
    )


def _distance_result() -> DistanceResult:
    return DistanceResult(
        origin=GeoCoordinate(latitude=43.0731, longitude=-89.4012),
        destination=GeoCoordinate(latitude=43.0747, longitude=-89.3841),
        distance_meters=1500.0,
        distance_miles=0.93,
        provider="valhalla",
    )


def _route_estimate() -> RouteEstimate:
    return RouteEstimate(
        origin=GeoCoordinate(latitude=43.0731, longitude=-89.4012),
        destination=GeoCoordinate(latitude=43.0747, longitude=-89.3841),
        distance_meters=1500.0,
        distance_miles=0.93,
        duration_seconds=240.0,
        duration_minutes=4.0,
        provider="valhalla",
        estimated_at=_ts(),
    )


def _service_area() -> ServiceArea:
    return ServiceArea(
        id=uuid4(),
        tenant_id=uuid4(),
        name="Dane County",
        polygon=[
            GeoCoordinate(latitude=43.0, longitude=-89.5),
            GeoCoordinate(latitude=43.1, longitude=-89.5),
            GeoCoordinate(latitude=43.1, longitude=-89.3),
        ],
        radius_miles=25.0,
        created_at=_ts(),
        updated_at=_ts(),
    )


def _signalcore_event() -> SignalCoreEvent:
    return SignalCoreEvent(
        event_id=uuid4(),
        tenant_id=uuid4(),
        source_service="billing",
        source_entity_type="claim",
        source_entity_id="claim-001",
        event_type="claim.denied",
        payload={"denial_code": "CO-97"},
        correlation_id="corr-003",
        idempotency_key="idem-003",
        occurred_at=_ts(),
    )


def _signalcore_trigger() -> SignalCoreTrigger:
    return SignalCoreTrigger(
        id=uuid4(),
        tenant_id=uuid4(),
        name="Route denials to workqueue",
        event_type_pattern="claim.denied",
        target_service="workforce",
        target_action="create_task",
        created_at=_ts(),
        updated_at=_ts(),
    )


def _form_template() -> FormTemplate:
    return FormTemplate(
        id=uuid4(),
        tenant_id=uuid4(),
        key="pcs",
        name="Physician Certification Statement",
        latest_version=FormVersion(
            id=uuid4(),
            template_id=uuid4(),
            version=1,
            form_schema=FormSchema(
                title="PCS",
                fields=[
                    FormFieldDefinition(
                        key="patient_name",
                        label="Patient Name",
                        field_type=FormFieldType.TEXT,
                        required=True,
                    )
                ],
            ),
            is_published=True,
            created_at=_ts(),
            published_at=_ts(),
        ),
        created_at=_ts(),
        updated_at=_ts(),
    )


def _audit_event() -> AuditEvent:
    return AuditEvent(
        event_id=uuid4(),
        tenant_id=uuid4(),
        actor_user_id=uuid4(),
        action="chart_signed",
        resource_type="chart",
        resource_id="chart-001",
        correlation_id="corr-004",
        metadata={"ip": "10.0.0.1"},
        occurred_at=_ts(),
    )


def _audit_export_request() -> AuditExportRequest:
    return AuditExportRequest(
        tenant_id=uuid4(),
        query=AuditSearchQuery(tenant_id=uuid4(), resource_type="chart", limit=100),
        export_format=AuditExportFormat.NDJSON,
        requested_by=uuid4(),
        requested_at=_ts(),
    )


def _reference_data_list() -> ReferenceDataList:
    return ReferenceDataList(
        list_key="denial_reason_codes",
        name="Denial Reason Codes",
        version=2,
        items=[
            ReferenceDataItem(code="CO-97", label="Bundled service"),
            ReferenceDataItem(code="CO-16", label="Missing information"),
        ],
        updated_at=_ts(),
    )


def _invoice_ref() -> InvoiceRef:
    return InvoiceRef(
        tenant_id=uuid4(),
        stripe_invoice_id="in_123",
        stripe_customer_id="cus_123",
        stripe_subscription_id="sub_123",
        status=InvoiceStatus.PAID,
        amount_due=Decimal("199.00"),
        amount_paid=Decimal("199.00"),
        created_at=_ts(),
    )


def _subscription_ref() -> SubscriptionRef:
    return SubscriptionRef(
        tenant_id=uuid4(),
        stripe_subscription_id="sub_123",
        stripe_customer_id="cus_123",
        status=SubscriptionStatus.ACTIVE,
        price_id="price_123",
        current_period_end=_ts(),
    )


def _checkout_session_request() -> CheckoutSessionRequest:
    return CheckoutSessionRequest(
        tenant_id=uuid4(),
        correlation_id="corr-005",
        price_id="price_123",
        success_url="https://app.adaptixcore.com/billing/success",
        cancel_url="https://app.adaptixcore.com/billing/cancel",
    )


def _payment_event() -> PaymentEvent:
    return PaymentEvent(
        event_id=uuid4(),
        tenant_id=uuid4(),
        event_type=PaymentEventType.INVOICE_PAID,
        stripe_event_id="evt_123",
        stripe_customer_id="cus_123",
        stripe_invoice_id="in_123",
        amount=Decimal("199.00"),
        occurred_at=_ts(),
    )


def _mail_packet() -> MailPacket:
    return MailPacket(
        id=uuid4(),
        tenant_id=uuid4(),
        correlation_id="corr-006",
        sender=MailSender(
            name="Adaptix Billing",
            address_line1="1 Ops Way",
            city="Madison",
            state="WI",
            postal_code="53703",
        ),
        recipient=MailRecipient(
            name="Jane Patient",
            address_line1="200 Elm St",
            city="Madison",
            state="WI",
            postal_code="53704",
        ),
        mail_class=MailClass.FIRST_CLASS,
        status=MailStatus.QUEUED,
        page_count=2,
        created_at=_ts(),
        updated_at=_ts(),
    )


def _mail_return_status() -> MailReturnStatus:
    return MailReturnStatus(
        packet_id=uuid4(),
        tenant_id=uuid4(),
        reason=MailReturnReason.MOVED_NO_FORWARDING,
        postgrid_id="pg_123",
        returned_at=_ts(),
    )


def _rtc_session() -> RTCSession:
    return RTCSession(
        id=uuid4(),
        tenant_id=uuid4(),
        room_name="dispatch-42",
        status=RTCRoomStatus.ACTIVE,
        created_by=uuid4(),
        max_participants=8,
        created_at=_ts(),
        started_at=_ts(),
    )


def _rtc_participant_token() -> RTCParticipantToken:
    return RTCParticipantToken(
        tenant_id=uuid4(),
        session_id=uuid4(),
        room_name="dispatch-42",
        participant_identity="user-001",
        token="jwt.token.value",
        url="wss://rtc.adaptixcore.com",
        expires_at=_ts(),
    )


def _officeally_submission() -> OfficeAllySubmission:
    return OfficeAllySubmission(
        id=uuid4(),
        tenant_id=uuid4(),
        claim_id="claim-001",
        submission_type="837P",
        file_name="batch_001.x12",
        submitted_at=_ts(),
        created_at=_ts(),
    )


def _officeally_response() -> OfficeAllyResponse:
    return OfficeAllyResponse(
        submission_id=uuid4(),
        tenant_id=uuid4(),
        accepted=True,
        ack_type="999",
        status_code="A",
        received_at=_ts(),
    )


def _device_registration() -> DeviceRegistration:
    return DeviceRegistration(
        id=uuid4(),
        tenant_id=uuid4(),
        user_id=uuid4(),
        device_identifier="ABC-123-DEVICE",
        platform=DevicePlatform.IOS,
        status=DeviceStatus.ACTIVE,
        os_version="18.2",
        app_version="1.4.0",
        mdm_managed=True,
        registered_at=_ts(),
        updated_at=_ts(),
    )


def _app_access_decision() -> AppAccessDecision:
    return AppAccessDecision(
        tenant_id=uuid4(),
        user_id=uuid4(),
        app_key="field-app",
        effect=AppAccessEffect.ALLOW,
        allowed=True,
        matched_policy_id=uuid4(),
        device_id=uuid4(),
        reasons=["role:medic", "entitlement:epcr"],
        evaluated_at=_ts(),
    )


def _app_access_policy() -> AppAccessPolicy:
    return AppAccessPolicy(
        id=uuid4(),
        tenant_id=uuid4(),
        app_key="field-app",
        name="Field App Access",
        required_roles=["medic", "supervisor"],
        required_module_entitlements=["epcr"],
        allowed_platforms=["ios", "android"],
        mfa_required=True,
        created_at=_ts(),
        updated_at=_ts(),
    )


def _stripe_customer_ref() -> StripeCustomerRef:
    return StripeCustomerRef(
        tenant_id=uuid4(),
        stripe_customer_id="cus_123",
        email="ops@adaptix.test",
        created_at=_ts(),
    )


def _geocode_portal_request() -> PortalSessionRequest:
    return PortalSessionRequest(
        tenant_id=uuid4(),
        stripe_customer_id="cus_123",
        return_url="https://app.adaptixcore.com/billing",
    )


def _checkout_session_response() -> CheckoutSessionResponse:
    return CheckoutSessionResponse(
        tenant_id=uuid4(),
        session_id="cs_123",
        checkout_url="https://checkout.stripe.com/c/pay/cs_123",
        expires_at=_ts(),
    )


@pytest.mark.parametrize(
    ("factory", "expected_type"),
    [
        (_notification_delivery_status, NotificationDeliveryStatus),
        (_notification_template, NotificationTemplate),
        (_notification_preference, NotificationPreference),
        (_facility_record, FacilityRecord),
        (_geocode_request, GeocodeRequest),
        (_geocode_result, GeocodeResult),
        (_distance_result, DistanceResult),
        (_route_estimate, RouteEstimate),
        (_service_area, ServiceArea),
        (_signalcore_event, SignalCoreEvent),
        (_signalcore_trigger, SignalCoreTrigger),
        (_form_template, FormTemplate),
        (_audit_event, AuditEvent),
        (_audit_export_request, AuditExportRequest),
        (_reference_data_list, ReferenceDataList),
        (_invoice_ref, InvoiceRef),
        (_subscription_ref, SubscriptionRef),
        (_stripe_customer_ref, StripeCustomerRef),
        (_checkout_session_request, CheckoutSessionRequest),
        (_checkout_session_response, CheckoutSessionResponse),
        (_geocode_portal_request, PortalSessionRequest),
        (_payment_event, PaymentEvent),
        (_mail_packet, MailPacket),
        (_mail_return_status, MailReturnStatus),
        (_rtc_session, RTCSession),
        (_rtc_participant_token, RTCParticipantToken),
        (_officeally_submission, OfficeAllySubmission),
        (_officeally_response, OfficeAllyResponse),
        (_device_registration, DeviceRegistration),
        (_app_access_decision, AppAccessDecision),
        (_app_access_policy, AppAccessPolicy),
    ],
)
def test_shared_service_contracts_round_trip(factory, expected_type) -> None:
    """Ensure each shared-service contract survives a JSON round trip."""

    contract = factory()
    restored = expected_type.model_validate_json(contract.model_dump_json())
    assert restored == contract


def test_audit_event_is_immutable() -> None:
    """AuditEvent must be frozen so audit records cannot be mutated in place."""

    event = _audit_event()
    with pytest.raises(ValidationError):
        event.action = "tampered"


def test_notification_request_reused_from_communications() -> None:
    """The canonical NotificationRequest is reused, not duplicated."""

    request = NotificationRequest(
        tenant_id="tenant-001",
        recipient_id="user-001",
        channel="email",
        body="hello",
    )
    assert request.channel == "email"
    # Same object exported once on the package surface.
    assert schemas.__all__.count("NotificationRequest") == 1


def test_decimal_money_fields_reject_negative_amounts() -> None:
    """Monetary Decimal fields reject financially impossible negatives."""

    with pytest.raises(ValidationError):
        InvoiceRef(
            tenant_id=uuid4(),
            stripe_invoice_id="in_123",
            stripe_customer_id="cus_123",
            status=InvoiceStatus.OPEN,
            amount_due=Decimal("-1.00"),
        )


def test_geo_coordinate_rejects_out_of_range_latitude() -> None:
    """Coordinates outside valid WGS84 bounds are rejected."""

    with pytest.raises(ValidationError):
        GeoCoordinate(latitude=91.0, longitude=0.0)


def test_expected_delivery_date_is_a_date() -> None:
    """MailDeliveryStatus.expected_delivery_date accepts a plain date."""

    from adaptix_contracts.schemas import MailDeliveryStatus

    status = MailDeliveryStatus(
        packet_id=uuid4(),
        tenant_id=uuid4(),
        status=MailStatus.MAILED,
        expected_delivery_date=date(2026, 7, 15),
        updated_at=_ts(),
    )
    restored = MailDeliveryStatus.model_validate_json(status.model_dump_json())
    assert restored == status


def test_shared_service_models_are_pydantic_models() -> None:
    """Guard against accidental non-model exports in this surface."""

    for factory in (_facility_record, _signalcore_event, _mail_packet):
        assert isinstance(factory(), BaseModel)
