"""Contract guards for the Family-Bridge activation path (FB-001).

These cover the contracts the activation DAG needs and the disclosure rules
that make them safe to publish:

* ``ComplaintClass`` is a closed set, so a producer cannot copy the chief
  complaint into the tone bucket.
* The ePCR transport payloads are PHI-bounded by ``extra="forbid"``.
* ``bridge.sms.delivery.updated`` cannot be published without the provider
  message id it is supposed to reconcile against.
* ``patient.nok.consent.changed`` cannot carry a name, an email address, or a
  full phone number.
* Every event the platform actually publishes on this path is registered in
  ``ALL_EVENTS`` with a resolvable producer.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from adaptix_contracts.epcr.transport_events import (
    EPCR_TRANSPORT_ARRIVED_DESTINATION,
    EPCR_TRANSPORT_DESTINATION_UPDATED,
    EpcrTransportArrivedDestinationPayload,
    EpcrTransportDestinationUpdatedPayload,
)
from adaptix_contracts.events.registry import (
    ALL_EVENTS,
    is_registered,
    producer_of,
)
from adaptix_contracts.family_bridge.enums import (
    ComplaintClass,
    ConsentSource,
    ConsentStatus,
    SmsDeliveryStatus,
)
from adaptix_contracts.family_bridge.events import (
    BRIDGE_SMS_DELIVERY_UPDATED,
    BRIDGE_SMS_SENT,
    BRIDGE_STATUS_UPDATED,
    BRIDGE_THREAD_CLOSED,
    BRIDGE_THREAD_OPENED,
    BridgeSmsDeliveryUpdatedPayload,
    BridgeThreadOpenedPayload,
    build_bridge_sms_delivery_updated_event,
)
from adaptix_contracts.patient_identity.events import (
    PATIENT_NOK_CONSENT_CHANGED,
    PatientNokConsentChangedPayload,
)

TENANT = "tenant-abc"


# ---------------------------------------------------------------------------
# complaint_class is a closed set, not free text
# ---------------------------------------------------------------------------


def test_complaint_class_accepts_only_the_six_coarse_tone_buckets() -> None:
    assert {c.value for c in ComplaintClass} == {
        "cardiac",
        "trauma",
        "medical",
        "behavioral",
        "pediatric",
        "obstetric",
    }


@pytest.mark.parametrize(
    "leaked",
    [
        "chest pain radiating to left arm",
        "34yo F, GSW to abdomen",
        "acute exacerbation of CHF",
        "zzz",
    ],
)
def test_thread_opened_rejects_a_complaint_in_the_tone_bucket(leaked: str) -> None:
    """The tone bucket must not become a smuggling route for the complaint.

    Typing this field as ``str`` -- which is what it was -- makes every string
    above valid, storable on the thread row, and publishable on the bus.
    """
    with pytest.raises(ValidationError):
        BridgeThreadOpenedPayload(
            tenant_id=TENANT,
            thread_id=uuid4(),
            patient_id="p-1",
            chart_id="c-1",
            nok_contact_id=uuid4(),
            consent_id=uuid4(),
            consent_source=ConsentSource.PATIENT_SCENE,
            complaint_class=leaked,
        )


def test_thread_opened_still_accepts_a_real_tone_bucket() -> None:
    payload = BridgeThreadOpenedPayload(
        tenant_id=TENANT,
        thread_id=uuid4(),
        patient_id="p-1",
        chart_id="c-1",
        nok_contact_id=uuid4(),
        consent_id=uuid4(),
        consent_source=ConsentSource.PATIENT_SCENE,
        complaint_class="cardiac",
    )
    assert payload.complaint_class is ComplaintClass.CARDIAC


# ---------------------------------------------------------------------------
# ePCR transport payloads are PHI-bounded
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field, value",
    [
        ("patient_name", "Jane Doe"),
        ("date_of_birth", "1984-02-11"),
        ("chief_complaint", "chest pain"),
        ("narrative", "Pt found supine on the floor"),
        ("vitals", {"hr": 118}),
        ("medications", ["aspirin"]),
    ],
)
def test_destination_updated_forbids_clinical_or_identifying_fields(
    field: str, value: object
) -> None:
    with pytest.raises(ValidationError):
        EpcrTransportDestinationUpdatedPayload(
            tenant_id=TENANT,
            chart_id="c-1",
            destination_name="Saint Mary Regional",
            **{field: value},
        )


def test_arrived_destination_forbids_clinical_or_identifying_fields() -> None:
    with pytest.raises(ValidationError):
        EpcrTransportArrivedDestinationPayload(
            tenant_id=TENANT,
            chart_id="c-1",
            arrived_at=datetime.now(UTC),
            chief_complaint="chest pain",
        )


def test_arrived_destination_requires_the_arrival_time() -> None:
    """An arrival event with no arrival time is not the fact it claims to be."""
    with pytest.raises(ValidationError):
        EpcrTransportArrivedDestinationPayload(tenant_id=TENANT, chart_id="c-1")


def test_arrival_and_transfer_of_care_stay_separate_facts() -> None:
    payload = EpcrTransportArrivedDestinationPayload(
        tenant_id=TENANT,
        chart_id="c-1",
        arrived_at=datetime(2026, 9, 7, 14, 30, tzinfo=UTC),
    )
    assert payload.transfer_of_care_at is None


# ---------------------------------------------------------------------------
# Telnyx delivery receipts
# ---------------------------------------------------------------------------


def _delivery(status: SmsDeliveryStatus) -> BridgeSmsDeliveryUpdatedPayload:
    return BridgeSmsDeliveryUpdatedPayload(
        tenant_id=TENANT,
        thread_id=uuid4(),
        provider_message_id="tx-9001",
        delivery_status=status,
        provider_status_at=datetime(2026, 9, 7, 15, 0, tzinfo=UTC),
    )


@pytest.mark.parametrize("bad_id", ["", None])
def test_delivery_update_requires_a_provider_message_id(bad_id: object) -> None:
    """A receipt that cannot be tied to a sent message is not reconcilable."""
    with pytest.raises(ValidationError):
        BridgeSmsDeliveryUpdatedPayload(
            tenant_id=TENANT,
            thread_id=uuid4(),
            provider_message_id=bad_id,
            delivery_status=SmsDeliveryStatus.DELIVERED,
            provider_status_at=datetime.now(UTC),
        )


def test_delivery_update_requires_an_explicit_status() -> None:
    """No default: an unknown provider outcome must never fall through to one."""
    with pytest.raises(ValidationError):
        BridgeSmsDeliveryUpdatedPayload(
            tenant_id=TENANT,
            thread_id=uuid4(),
            provider_message_id="tx-9001",
            provider_status_at=datetime.now(UTC),
        )


def test_repeated_receipt_for_the_same_status_is_idempotent() -> None:
    """Telnyx retries webhooks; the same receipt must not act twice."""
    first = build_bridge_sms_delivery_updated_event(_delivery(SmsDeliveryStatus.SENT))
    repeat = build_bridge_sms_delivery_updated_event(_delivery(SmsDeliveryStatus.SENT))
    assert first.idempotency_key == repeat.idempotency_key


def test_a_later_transition_gets_its_own_idempotency_key() -> None:
    """sent -> delivered is a new fact, not a duplicate of the send."""
    sent = build_bridge_sms_delivery_updated_event(_delivery(SmsDeliveryStatus.SENT))
    delivered = build_bridge_sms_delivery_updated_event(
        _delivery(SmsDeliveryStatus.DELIVERED)
    )
    assert sent.idempotency_key != delivered.idempotency_key


def test_delivery_update_envelope_carries_the_registered_event_type() -> None:
    envelope = build_bridge_sms_delivery_updated_event(
        _delivery(SmsDeliveryStatus.DELIVERED)
    )
    assert envelope.event_type == BRIDGE_SMS_DELIVERY_UPDATED
    assert envelope.source_service == "communications"


# ---------------------------------------------------------------------------
# NoK consent change
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field, value",
    [
        ("name", "Jane Doe"),
        ("nok_name", "Jane Doe"),
        ("email", "jane@example.com"),
        ("phone_e164", "+15555550123"),
        ("phone", "555-555-0123"),
    ],
)
def test_consent_changed_forbids_name_email_and_full_phone(
    field: str, value: str
) -> None:
    with pytest.raises(ValidationError):
        PatientNokConsentChangedPayload(
            tenant_id=TENANT,
            patient_id="p-1",
            nok_contact_id=uuid4(),
            consent_id=uuid4(),
            status=ConsentStatus.REVOKED,
            consent_source=ConsentSource.PATIENT_SCENE,
            **{field: value},
        )


def test_consent_changed_carries_only_the_last_four_digits() -> None:
    payload = PatientNokConsentChangedPayload(
        tenant_id=TENANT,
        patient_id="p-1",
        nok_contact_id=uuid4(),
        consent_id=uuid4(),
        status=ConsentStatus.ACTIVE,
        consent_source=ConsentSource.PATIENT_PRIOR,
        phone_last4="0123",
    )
    assert payload.phone_last4 == "0123"

    with pytest.raises(ValidationError):
        PatientNokConsentChangedPayload(
            tenant_id=TENANT,
            patient_id="p-1",
            nok_contact_id=uuid4(),
            consent_id=uuid4(),
            status=ConsentStatus.ACTIVE,
            consent_source=ConsentSource.PATIENT_PRIOR,
            phone_last4="+15555550123",
        )


def test_consent_changed_requires_an_explicit_status() -> None:
    """A consent change with no resulting standing is not actionable."""
    with pytest.raises(ValidationError):
        PatientNokConsentChangedPayload(
            tenant_id=TENANT,
            patient_id="p-1",
            nok_contact_id=uuid4(),
            consent_id=uuid4(),
            consent_source=ConsentSource.PATIENT_PRIOR,
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


ACTIVATION_PATH_EVENTS = (
    (BRIDGE_THREAD_OPENED, "communications"),
    (BRIDGE_SMS_SENT, "communications"),
    (BRIDGE_STATUS_UPDATED, "communications"),
    (BRIDGE_THREAD_CLOSED, "communications"),
    (BRIDGE_SMS_DELIVERY_UPDATED, "communications"),
    (EPCR_TRANSPORT_DESTINATION_UPDATED, "epcr"),
    (EPCR_TRANSPORT_ARRIVED_DESTINATION, "epcr"),
    (PATIENT_NOK_CONSENT_CHANGED, "patient-identity"),
)


@pytest.mark.parametrize("event_type, slug", ACTIVATION_PATH_EVENTS)
def test_activation_path_event_is_registered_to_its_owning_service(
    event_type: str, slug: str
) -> None:
    assert is_registered(event_type)
    assert ALL_EVENTS[event_type]["source_service"] == slug
    assert producer_of(event_type) is not None


@pytest.mark.parametrize("event_type, _slug", ACTIVATION_PATH_EVENTS)
def test_activation_path_event_declares_a_version(event_type: str, _slug: str) -> None:
    assert ALL_EVENTS[event_type].get("version")


def test_epcr_chart_opened_was_not_invented_as_a_second_canonical_name() -> None:
    """``epcr.chart.created`` already owns the chart-opened fact.

    Adaptix-EPCR-Service publishes ``epcr.chart.created`` from
    ``services/chart_publisher.py`` and it is registered here. A parallel
    ``epcr.chart.opened`` would be a second canonical name for one fact.
    """
    assert is_registered("epcr.chart.created")
    assert not is_registered("epcr.chart.opened")
