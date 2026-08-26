"""``SmsDeliveryStatus.SUPPRESSED`` — Family-Bridge consent-suppression outcome.

Family-Bridge's ``_send_for_stage`` (Adaptix-Communications-Service) gained a
platform-wide consent-ledger check before contacting the Telnyx gateway. This
locks the new wire value on the Contracts side: it exists, it round-trips
through the event payload exactly like every other ``SmsDeliveryStatus``
member, and it does not disturb the four pre-existing members.
"""

from __future__ import annotations

from uuid import uuid4

from adaptix_contracts.family_bridge.enums import SmsDeliveryStatus, ThreadStage
from adaptix_contracts.family_bridge.events import (
    BRIDGE_SMS_SENT,
    BridgeSmsSentPayload,
    build_bridge_sms_sent_event,
)


def test_suppressed_member_exists_with_stable_wire_value() -> None:
    assert SmsDeliveryStatus.SUPPRESSED == "suppressed"
    assert SmsDeliveryStatus("suppressed") is SmsDeliveryStatus.SUPPRESSED


def test_pre_existing_members_unchanged() -> None:
    """Adding SUPPRESSED must not renumber or disturb any prior member."""
    assert SmsDeliveryStatus.QUEUED == "queued"
    assert SmsDeliveryStatus.SENT == "sent"
    assert SmsDeliveryStatus.DELIVERED == "delivered"
    assert SmsDeliveryStatus.FAILED == "failed"
    assert SmsDeliveryStatus.UNDELIVERED == "undelivered"
    assert {m.value for m in SmsDeliveryStatus} == {
        "queued",
        "sent",
        "delivered",
        "failed",
        "undelivered",
        "suppressed",
    }


def _payload(**over: object) -> BridgeSmsSentPayload:
    base: dict[str, object] = {
        "tenant_id": str(uuid4()),
        "thread_id": uuid4(),
        "stage_at_send": ThreadStage.EN_ROUTE,
        "delivery_status": SmsDeliveryStatus.SUPPRESSED,
        "provider_message_id": None,
        "to_phone_last4": "1234",
    }
    base.update(over)
    return BridgeSmsSentPayload(**base)  # type: ignore[arg-type]


def test_suppressed_payload_serializes_and_round_trips() -> None:
    payload = _payload()
    dumped = payload.model_dump(mode="json")
    assert dumped["delivery_status"] == "suppressed"
    assert dumped["provider_message_id"] is None

    rebuilt = BridgeSmsSentPayload.model_validate(dumped)
    assert rebuilt.delivery_status is SmsDeliveryStatus.SUPPRESSED
    assert rebuilt == payload


def test_suppressed_payload_builds_a_valid_signal_bus_envelope() -> None:
    """A suppressed send still produces a real, publishable envelope — the
    thread's event log and the Signal Bus outbox always get an entry,
    suppressed or not."""
    payload = _payload()
    envelope = build_bridge_sms_sent_event(payload)
    assert envelope.event_type == BRIDGE_SMS_SENT
    assert envelope.payload["delivery_status"] == "suppressed"
    # No provider message id to key on when suppressed -> falls back to the
    # thread_id + stage idempotency key, matching the existing FAILED path.
    assert envelope.idempotency_key == (
        f"bridge.sms.sent:{payload.thread_id}:{payload.stage_at_send.value}"
    )


def test_suppressed_payload_never_carries_a_phone_number() -> None:
    """PHI rule: only the last 4 digits may ever appear."""
    payload = _payload(to_phone_last4="6789")
    blob = payload.model_dump_json()
    assert "+1" not in blob  # no E.164 phone anywhere in the payload
    assert "6789" in blob  # the last-4 reconciliation field is still present
