"""``epcr.chart.finalized`` must validate the payload its producer really sends.

The break this locks down
-------------------------
``EpcrChartFinalizedEvent`` declared ``is_nemsis_compliant: bool`` with no
default. The producer —
``Adaptix-EPCR-Service/backend/epcr_app/chart_finalization_service.py:260``
(origin/main, read 2026-08-09) — writes a ``ChartEventOutbox`` row whose payload
is exactly::

    {"chart_id", "tenant_id", "call_number", "finalized_at",
     "billing_case_id", "record_mode"}

and the string ``is_nemsis_compliant`` does not occur anywhere in that service.
The sole consumer,
``Adaptix-Billing-Service/backend/billing_app/event_consumers.py:69``, runs
``EpcrChartFinalizedEvent.model_validate(payload)`` inside a ``try`` whose
``except`` logs and returns ``False``. So every real chart finalization raised
``ValidationError`` and silently produced **no** claim-intake row, **no** patient
financial account and **no** draft claim — with the chart still showing
finalized to the crew.

Every existing fixture for this event supplied ``is_nemsis_compliant``, which is
precisely why the suite stayed green while production traffic could not
validate. These tests use the producer's key set verbatim instead.

What these tests prove
----------------------
That the shared contract accepts the exact payload the live producer emits, and
that the fields the consumer reads survive validation. What they do NOT prove:
that Billing actually writes the three rows (that needs Billing's database), nor
that the event is delivered on the bus, nor anything about any other event type.
Taking the fix into the running Billing service also requires that repo to bump
its pinned ``adaptix-contracts`` commit and redeploy.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from adaptix_contracts.schemas.epcr_contracts import EpcrChartFinalizedEvent

#: The producer's payload keys, copied from
#: ``chart_finalization_service.py:265-279`` at origin/main (2026-08-09).
PRODUCER_PAYLOAD_KEYS: frozenset[str] = frozenset(
    {
        "chart_id",
        "tenant_id",
        "call_number",
        "finalized_at",
        "billing_case_id",
        "record_mode",
    }
)


def _live_producer_payload(**overrides: object) -> dict[str, object]:
    """Return a payload with exactly the producer's key set."""
    payload: dict[str, object] = {
        "chart_id": "3f2b1c44-0000-4000-8000-000000000001",
        "tenant_id": "9a8b7c66-0000-4000-8000-000000000002",
        "call_number": "2026-000123",
        "finalized_at": datetime(2026, 8, 9, 14, 30, tzinfo=timezone.utc).isoformat(),
        "billing_case_id": "5d4e3f22-0000-4000-8000-000000000003",
        "record_mode": "production",
    }
    payload.update(overrides)
    return payload


def test_fixture_key_set_matches_the_documented_producer_key_set() -> None:
    """Guard the guard: the fixture must not drift from the producer."""
    assert frozenset(_live_producer_payload()) == PRODUCER_PAYLOAD_KEYS


def test_the_exact_live_producer_payload_validates() -> None:
    """The regression. This raised ValidationError before the contract fix."""
    event = EpcrChartFinalizedEvent.model_validate(_live_producer_payload())
    assert event.chart_id == "3f2b1c44-0000-4000-8000-000000000001"
    assert event.tenant_id == "9a8b7c66-0000-4000-8000-000000000002"
    assert event.call_number == "2026-000123"


def test_absent_compliance_is_unknown_not_an_assertion_of_compliance() -> None:
    """``None`` means the producer said nothing — never "compliant"."""
    event = EpcrChartFinalizedEvent.model_validate(_live_producer_payload())
    assert event.is_nemsis_compliant is None
    assert bool(event.is_nemsis_compliant) is False


@pytest.mark.parametrize("stated", [True, False])
def test_a_producer_that_does_state_compliance_is_preserved(stated: bool) -> None:
    """Optional does not mean ignored: an explicit value round-trips."""
    event = EpcrChartFinalizedEvent.model_validate(
        _live_producer_payload(is_nemsis_compliant=stated)
    )
    assert event.is_nemsis_compliant is stated


def test_every_field_the_billing_consumer_reads_survives_validation() -> None:
    """The consumer reads chart_id, tenant_id, call_number and finalized_at.

    Cited: Adaptix-Billing-Service/backend/billing_app/event_consumers.py:71-115
    (origin/main 2026-08-09) — ``validated_event.finalized_at.date().isoformat()``
    is passed as ``encounter_date``, ``call_number`` as ``chief_complaint`` and
    ``patient_name``, ``chart_id`` as ``patient_id``.
    """
    event = EpcrChartFinalizedEvent.model_validate(_live_producer_payload())
    assert event.finalized_at.date().isoformat() == "2026-08-09"
    assert event.chart_id and event.tenant_id and event.call_number


def test_unknown_producer_keys_do_not_break_validation() -> None:
    """``billing_case_id`` / ``record_mode`` are not modelled and must not fail."""
    event = EpcrChartFinalizedEvent.model_validate(_live_producer_payload())
    assert not hasattr(event, "billing_case_id")
    assert not hasattr(event, "record_mode")


# ---------------------------------------------------------------------------
# Controls: validation is still real
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("required", ["chart_id", "tenant_id", "call_number"])
def test_a_field_the_consumer_depends_on_is_still_required(required: str) -> None:
    payload = _live_producer_payload()
    del payload[required]
    with pytest.raises(ValidationError, match=required):
        EpcrChartFinalizedEvent.model_validate(payload)


def test_finalized_at_is_still_required_and_must_be_a_timestamp() -> None:
    payload = _live_producer_payload()
    del payload["finalized_at"]
    with pytest.raises(ValidationError, match="finalized_at"):
        EpcrChartFinalizedEvent.model_validate(payload)
    with pytest.raises(ValidationError, match="finalized_at"):
        EpcrChartFinalizedEvent.model_validate(
            _live_producer_payload(finalized_at="not-a-timestamp")
        )


def test_a_non_boolean_compliance_value_is_still_rejected() -> None:
    """Optional widened the field to tri-state, not to anything at all."""
    with pytest.raises(ValidationError, match="is_nemsis_compliant"):
        EpcrChartFinalizedEvent.model_validate(
            _live_producer_payload(is_nemsis_compliant="maybe")
        )
