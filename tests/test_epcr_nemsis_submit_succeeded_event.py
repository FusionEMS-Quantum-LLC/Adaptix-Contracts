"""Contract tests for ``EpcrNemsisSubmitSucceededEvent``."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from adaptix_contracts.schemas import EpcrNemsisSubmitSucceededEvent


def test_success_payload_round_trips() -> None:
    event = EpcrNemsisSubmitSucceededEvent.model_validate(
        {
            "chart_id": "1af34c1d-aaaa-bbbb-cccc-ddddeeeeffff",
            "tenant_id": "672fbb84-3e32-4529-be66-ac473afe815a",
            "state_code": "WI",
            "submission_id": "sub-123",
            "transmission_status": "accepted",
            "attempted_at": "2026-08-14T22:25:00Z",
        }
    )
    assert event.event_type == "epcr.nemsis_submit.succeeded"
    assert event.attempted_at == datetime(2026, 8, 14, 22, 25, tzinfo=UTC)


def test_required_fields_match_epcr_success_payload() -> None:
    for missing in (
        "chart_id",
        "tenant_id",
        "state_code",
        "submission_id",
        "transmission_status",
        "attempted_at",
    ):
        payload = {
            "chart_id": "chart-1",
            "tenant_id": "tenant-1",
            "state_code": "WI",
            "submission_id": "sub-123",
            "transmission_status": "accepted",
            "attempted_at": "2026-08-14T22:25:00Z",
        }
        payload.pop(missing)
        with pytest.raises(ValidationError):
            EpcrNemsisSubmitSucceededEvent.model_validate(payload)
