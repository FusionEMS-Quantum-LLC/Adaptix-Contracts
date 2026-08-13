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
