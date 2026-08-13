"""Tests for shared telephony platform contracts."""

from __future__ import annotations

# import uuid # REMOVED IN PYTHON 3.14
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

import adaptix_contracts as ac
from adaptix_contracts.schemas.telephony_contracts import (
    Call,
    CallStatus,
    DestinationType,
    Queue,
    QueueStatus,
    TelephonyEventType,
    UserPresence,
    Voicemail,
    VoicemailStatus,
)


def _now() -> datetime:
    return datetime.now(UTC)


def test_root_reexports_telephony_surface() -> None:
    assert ac.Call is Call
    assert ac.Voicemail is Voicemail
    assert ac.Queue is Queue
    assert ac.UserPresence is UserPresence
    assert ac.TelephonyEventType is TelephonyEventType
    assert ac.DestinationType is DestinationType
    assert ac.CallStatus is CallStatus
    assert ac.VoicemailStatus is VoicemailStatus
    assert ac.QueueStatus is QueueStatus


def test_event_type_constants_match_directive() -> None:
    expected = {
        "telephony.call.ringing",
        "telephony.call.offered",
        "telephony.call.answered",
        "telephony.call.held",
        "telephony.call.resumed",
        "telephony.call.transferred",
        "telephony.call.completed",
        "telephony.call.failed",
        "telephony.voicemail.created",
        "telephony.voicemail.transcribed",
        "telephony.voicemail.processing_failed",
        "telephony.queue.updated",
        "telephony.presence.updated",
    }
    actual = {member.value for member in TelephonyEventType}
    assert actual == expected


def test_enum_member_sets_match_directive() -> None:
    assert {m.value for m in DestinationType} == {
        "user",
        "team",
        "queue",
        "department",
        "workspace",
        "cortex_agent",
        "voicemail_box",
        "external_number",
        "on_call_policy",
    }
    assert {m.value for m in CallStatus} == {
        "new",
        "ringing",
        "ai_active",
        "queued",
        "offered",
        "answered",
        "on_hold",
        "transferring",
        "voicemail",
        "completed",
        "abandoned",
        "failed",
    }
    assert {m.value for m in VoicemailStatus} == {
        "new",
        "unread",
        "listened",
        "in_review",
        "assigned",
        "callback_required",
        "callback_completed",
        "archived",
        "deleted",
        "failed_processing",
    }
    assert {m.value for m in QueueStatus} == {"open", "closed", "paused", "degraded"}


def test_call_construction_and_json_schema() -> None:
    call = Call(
        call_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        provider="telnyx",
        provider_call_id="v3:abc123",
        direction="inbound",
        from_number="+15551230000",
        to_number="+15559990000",
        destination_type=DestinationType.QUEUE,
        destination_id=str(uuid.uuid4()),
        status=CallStatus.RINGING,
        created_at=_now(),
        updated_at=_now(),
    )
    assert call.status is CallStatus.RINGING
    assert call.destination_type is DestinationType.QUEUE
    assert call.metadata == {}
    assert call.answered_at is None
    assert isinstance(Call.model_json_schema(), dict)


def test_call_destination_id_accepts_external_number() -> None:
    call = Call(
        call_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        provider="telnyx",
        provider_call_id="v3:xyz",
        direction="outbound",
        from_number="+15559990000",
        to_number="+15551230000",
        destination_type=DestinationType.EXTERNAL_NUMBER,
        destination_id="+15551230000",
        status=CallStatus.NEW,
        created_at=_now(),
        updated_at=_now(),
    )
    assert call.destination_id == "+15551230000"


def test_call_rejects_negative_duration() -> None:
    with pytest.raises(ValidationError):
        Call(
            call_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            provider="telnyx",
            provider_call_id="v3:abc",
            direction="inbound",
            from_number="+15551230000",
            to_number="+15559990000",
            status=CallStatus.COMPLETED,
            duration_seconds=-1,
            created_at=_now(),
            updated_at=_now(),
        )


def test_call_requires_status() -> None:
    with pytest.raises(ValidationError):
        Call(
            call_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            provider="telnyx",
            provider_call_id="v3:abc",
            direction="inbound",
            from_number="+15551230000",
            to_number="+15559990000",
            created_at=_now(),
            updated_at=_now(),
        )


def test_voicemail_construction_defaults() -> None:
    vm = Voicemail(
        voicemail_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        voicemail_box_id=uuid.uuid4(),
        caller_number="+15551230000",
        status=VoicemailStatus.NEW,
        received_at=_now(),
        created_at=_now(),
        updated_at=_now(),
    )
    assert vm.callback_required is False
    assert vm.call_id is None
    assert vm.audio_object_key is None
    assert vm.status is VoicemailStatus.NEW
    assert isinstance(Voicemail.model_json_schema(), dict)


def test_queue_policies_default_to_empty_objects() -> None:
    q = Queue(
        queue_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        name="Billing Inbound",
        slug="billing-inbound",
        status=QueueStatus.OPEN,
        created_at=_now(),
        updated_at=_now(),
    )
    assert q.routing_policy == {}
    assert q.business_hours_policy == {}
    assert q.overflow_policy == {}
    assert q.voicemail_box_id is None
    assert isinstance(Queue.model_json_schema(), dict)


def test_user_presence_construction() -> None:
    presence = UserPresence(
        user_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        telephony_status="on_call",
        device_status="registered",
        active_call_id=uuid.uuid4(),
    )
    assert presence.do_not_disturb is False
    assert presence.last_seen_at is None
    assert isinstance(UserPresence.model_json_schema(), dict)


def test_entities_support_from_attributes() -> None:
    class _Row:
        def __init__(self, **kw: object) -> None:
            self.__dict__.update(kw)

    row = _Row(
        user_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        telephony_status="available",
        device_status="registered",
        last_seen_at=None,
        active_call_id=None,
        do_not_disturb=True,
    )
    presence = UserPresence.model_validate(row)
    assert presence.do_not_disturb is True
    assert presence.telephony_status == "available"
