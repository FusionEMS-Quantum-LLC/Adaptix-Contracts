"""Contract tests for ``EpcrChartAmendedEvent``.

Pins the invariant that made the event unpublishable in production: the
relay (``Adaptix-EPCR-Service/backend/epcr_app/outbox_worker.py``) refuses
tenant-less events, so ``tenant_id`` must be REQUIRED at the contract layer
— a producer that omits it fails at validation time, not at relay time.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from adaptix_contracts.schemas import EpcrChartAmendedEvent


def test_minimal_valid_payload_round_trips() -> None:
    event = EpcrChartAmendedEvent.model_validate(
        {
            "amendment_id": "9f0e8a3c-1111-2222-3333-444455556666",
            "chart_id": "1af34c1d-aaaa-bbbb-cccc-ddddeeeeffff",
            "tenant_id": "672fbb84-3e32-4529-be66-ac473afe815a",
            "field": "narrative",
        }
    )
    assert event.event_type == "epcr.chart.amended"
    assert event.actor_id is None
    assert event.amended_at is None


def test_tenant_id_is_required() -> None:
    with pytest.raises(ValidationError):
        EpcrChartAmendedEvent.model_validate(
            {
                "amendment_id": "9f0e8a3c-1111-2222-3333-444455556666",
                "chart_id": "1af34c1d-aaaa-bbbb-cccc-ddddeeeeffff",
                "field": "narrative",
            }
        )


def test_amendment_identity_fields_are_required() -> None:
    for missing in ("amendment_id", "chart_id", "field"):
        payload = {
            "amendment_id": "a",
            "chart_id": "b",
            "tenant_id": "c",
            "field": "narrative",
        }
        payload.pop(missing)
        with pytest.raises(ValidationError):
            EpcrChartAmendedEvent.model_validate(payload)


def _legacy_payload() -> dict[str, str]:
    return {
        "amendment_id": "9f0e8a3c-1111-2222-3333-444455556666",
        "chart_id": "1af34c1d-aaaa-bbbb-cccc-ddddeeeeffff",
        "tenant_id": "672fbb84-3e32-4529-be66-ac473afe815a",
        "field": "narrative",
    }


def test_pre_discriminator_payload_is_read_as_legacy_field_diff() -> None:
    """Payloads emitted before the discriminator existed came only from the
    legacy field-diff producer, so its absence must resolve to that authority
    -- never to the canonical one."""
    event = EpcrChartAmendedEvent.model_validate(_legacy_payload())
    assert event.amendment_authority == "legacy_field_diff"
    assert event.signed_version_id is None
    assert event.signature_id is None


def test_canonical_signed_version_payload_round_trips() -> None:
    payload = {
        **_legacy_payload(),
        "field": "canonical_signed_version",
        "amendment_authority": "canonical_signed_version",
        "signed_version_id": "5b1c0d9e-0000-1111-2222-333344445555",
        "supersedes_signed_version_id": "4a0b9c8d-0000-1111-2222-333344445555",
        "signature_id": "9f0e8a3c-1111-2222-3333-444455556666",
        "document_hash": "a" * 64,
    }
    event = EpcrChartAmendedEvent.model_validate(payload)
    assert event.amendment_authority == "canonical_signed_version"
    assert event.field == "canonical_signed_version"
    assert event.signed_version_id == payload["signed_version_id"]
    assert event.supersedes_signed_version_id == payload["supersedes_signed_version_id"]
    assert event.document_hash == "a" * 64
    dumped = event.model_dump()
    assert dumped["amendment_authority"] == "canonical_signed_version"
    assert EpcrChartAmendedEvent.model_validate(dumped) == event


def test_explicit_legacy_authority_round_trips() -> None:
    event = EpcrChartAmendedEvent.model_validate(
        {**_legacy_payload(), "amendment_authority": "legacy_field_diff"}
    )
    assert event.amendment_authority == "legacy_field_diff"
    assert event.model_dump()["amendment_authority"] == "legacy_field_diff"


@pytest.mark.parametrize(
    "bad", ["", "canonical", "CANONICAL_SIGNED_VERSION", "trustsign", 1, None]
)
def test_unknown_amendment_authority_is_rejected(bad: object) -> None:
    with pytest.raises(ValidationError):
        EpcrChartAmendedEvent.model_validate(
            {**_legacy_payload(), "amendment_authority": bad}
        )
