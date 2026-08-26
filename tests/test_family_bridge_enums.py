"""Wire-stability pins for Family-Bridge enums — Play P24.

Every Family-Bridge enum value is stable on the wire (see
``adaptix_contracts/family_bridge/enums.py``). These tests pin the exact
strings so an accidental rename or removal fails loudly, and prove the
``SUPPRESSED`` policy outcome (ACX-CORR-0013) round-trips through the
``bridge.sms.sent`` payload contract exactly like every provider outcome.
"""

from __future__ import annotations

from uuid import uuid4

from adaptix_contracts.family_bridge.enums import SmsDeliveryStatus, ThreadStage
from adaptix_contracts.family_bridge.events import BridgeSmsSentPayload


def test_sms_delivery_status_wire_values_are_pinned() -> None:
    assert {m.value for m in SmsDeliveryStatus} == {
        "queued",
        "sent",
        "delivered",
        "failed",
        "undelivered",
        "suppressed",
    }
    # StrEnum: the member IS its wire string, and the wire string resolves
    # back to the member.
    assert SmsDeliveryStatus.SUPPRESSED == "suppressed"
    assert SmsDeliveryStatus("suppressed") is SmsDeliveryStatus.SUPPRESSED


def test_bridge_sms_sent_payload_round_trips_suppressed() -> None:
    payload = BridgeSmsSentPayload(
        tenant_id=str(uuid4()),
        thread_id=uuid4(),
        stage_at_send=ThreadStage.EN_ROUTE,
        provider_message_id=None,
        delivery_status=SmsDeliveryStatus.SUPPRESSED,
        to_phone_last4="4567",
        template_key="cardiac:en_route",
    )
    wire = payload.model_dump(mode="json")
    assert wire["delivery_status"] == "suppressed"
    assert wire["provider_message_id"] is None
    parsed = BridgeSmsSentPayload.model_validate(wire)
    assert parsed.delivery_status is SmsDeliveryStatus.SUPPRESSED
    assert parsed.stage_at_send is ThreadStage.EN_ROUTE
