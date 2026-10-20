"""The billing snapshot carries NEMSIS eDispatch.05, and its codes have one home.

Adaptix-Billing-Service #1620 (owner decision T1, 2026-10-05): the claim coder
decides the emergency indicator from the structured dispatch priority, because
Medicare decides emergency response by "the nature of the call at the time of
dispatch" (Benefit Policy Manual, Chapter 10, 30.1.1).
``EpcrBillingTransportBlock`` had no field for it, so pydantic's default
``extra="ignore"`` would drop the key EPCR sends and Billing could never read it.

These tests pin two things:

* the block types and round-trips ``dispatch_priority_code``, and a legacy
  event without it still validates;
* ``adaptix_contracts.epcr.dispatch_priority`` holds exactly the four codes of
  the NEMSIS 3.5.1 ``DispatchPriority`` list, with the schema's labels, and
  answers emergency only for Critical and Emergent.
"""

from __future__ import annotations

import pytest

from adaptix_contracts.epcr import dispatch_priority as dp
from adaptix_contracts.schemas import EpcrBillingTransportBlock, EpcrChartFinalizedEvent


def _event_with_transport(transport: dict[str, str | None]) -> dict[str, object]:
    return {
        "chart_id": "18ab537c",
        "tenant_id": "0149677b",
        "call_number": "E2E-EPCR-DISPATCH-001",
        "finalized_at": "2026-10-20T00:00:00+00:00",
        "billing_snapshot": {"transport": transport},
    }


def test_the_transport_block_carries_the_dispatch_priority() -> None:
    block = EpcrBillingTransportBlock.model_validate(
        {"dispatch_priority_code": "2305003"}
    )
    assert block.dispatch_priority_code == "2305003"
    assert block.model_dump()["dispatch_priority_code"] == "2305003"


def test_the_finalized_event_keeps_the_dispatch_priority() -> None:
    event = EpcrChartFinalizedEvent.model_validate(
        _event_with_transport(
            {"service_type_code": "2205001", "dispatch_priority_code": "2305005"}
        )
    )
    assert event.billing_snapshot is not None
    assert event.billing_snapshot.transport is not None
    assert event.billing_snapshot.transport.dispatch_priority_code == "2305005"


def test_an_event_without_the_dispatch_priority_still_validates() -> None:
    event = EpcrChartFinalizedEvent.model_validate(
        _event_with_transport({"service_type_code": "2205001"})
    )
    assert event.billing_snapshot is not None
    assert event.billing_snapshot.transport is not None
    assert event.billing_snapshot.transport.dispatch_priority_code is None


def test_the_code_list_is_exactly_the_nemsis_dispatch_priority_list() -> None:
    assert dp.DISPATCH_PRIORITY_ELEMENT == "eDispatch.05"
    assert dp.DISPATCH_PRIORITY_LABELS == {
        "2305001": "Critical",
        "2305003": "Emergent",
        "2305005": "Lower Acuity",
        "2305007": "Non-Acute [e.g., Scheduled Transfer or Standby]",
    }
    assert (
        dp.EMERGENCY_DISPATCH_PRIORITY_CODES | dp.NON_EMERGENCY_DISPATCH_PRIORITY_CODES
        == set(dp.DISPATCH_PRIORITY_LABELS)
    )
    assert (
        not dp.EMERGENCY_DISPATCH_PRIORITY_CODES
        & dp.NON_EMERGENCY_DISPATCH_PRIORITY_CODES
    )


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("2305001", True),
        ("2305003", True),
        (" 2305003 ", True),
        ("2305005", False),
        ("2305007", False),
        ("2305009", None),
        ("", None),
        (None, None),
    ],
)
def test_only_critical_and_emergent_are_an_emergency_dispatch(
    code: str | None, expected: bool | None
) -> None:
    assert dp.is_emergency_dispatch(code) is expected
