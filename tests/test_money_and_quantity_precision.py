"""Money and controlled-substance quantities are Decimal, and stay Decimal.

`payment_contracts.py` has stated the package convention since it was written:
"Monetary amounts are represented as ``Decimal`` in major currency units". Most
of the package did not follow it. 79 fields across eight modules were `float` —
including every quantity on the controlled-substance ledger.

Why that is not a style question:

* IEEE-754 binary cannot represent 0.1 or 2.675 exactly. A waste amount a
  clinician enters as 0.1 mg is stored as 0.1000000000000000055511151231257827,
  and a sum of per-administration waste does not reconcile against the recorded
  doses. On a DEA-reportable ledger an unexplained fractional discrepancy reads
  as diversion.
* A partial conversion is worse than none. `Decimal - float` raises TypeError in
  Python, so converting `waste_amount` while leaving `dose`, `quantity`,
  `pre_count`, `post_count`, `expected_count`, `actual_count` and `variance` as
  float turns a wrong reconciliation into a crashing one. That is why the whole
  of `narcotic.py` moved together rather than the five fields the 2026-08-20
  register (LEAD-009) named.

Rates, percentages, scores and durations stay `float` on purpose:
`churn_rate`, `net_retention_rate`, `denial_rate`, `appeal_success_rate`,
`average_days_to_payment`, `variance_pct`, `likelihood_percentage`,
`readiness_score`, `risk_score` and the trend lists are not money and not a
counted quantity.
"""

from __future__ import annotations

import inspect
import json
import re
from decimal import Decimal
from typing import get_args, get_origin

import pytest
from pydantic import BaseModel

from adaptix_contracts import (
    inventory_events,
    medications_events,
    narcotics_events,
    supply_integrations,
)
from adaptix_contracts.schemas import (
    crm_contracts,
    founder_contracts,
    inventory_contracts,
    narcotic,
)

CONVERTED_MODULES = (
    narcotic,
    inventory_contracts,
    founder_contracts,
    crm_contracts,
    inventory_events,
    medications_events,
    narcotics_events,
    supply_integrations,
)

# Names that must never be annotated `float` in a converted module. Money terms
# plus the controlled-substance quantity vocabulary.
MUST_BE_EXACT = re.compile(
    r"(amount|cost|price|total|revenue|balance|paid|pledged|funded|committed"
    r"|quantity|dose|waste|_count|counts|variance)$"
)

# Names that match the pattern above but are deliberately inexact.
INEXACT_BY_DESIGN = frozenset(
    {
        "variance_pct",
        "funding_percentage",
        "likelihood_percentage",
    }
)


_UUID_A = "3f1b8c7e-0000-4000-8000-000000000001"
_UUID_B = "3f1b8c7e-0000-4000-8000-000000000002"


def _waste_request(amount: Decimal) -> narcotic.WasteNarcoticRequest:
    return narcotic.WasteNarcoticRequest(
        medication_id=_UUID_A,
        waste_amount=amount,
        wasted_by=_UUID_A,
        witnessed_by=_UUID_B,
        reason="partial dose",
    )


def _models(module):
    for obj in vars(module).values():
        if (
            inspect.isclass(obj)
            and issubclass(obj, BaseModel)
            and obj is not BaseModel
            and obj.__module__ == module.__name__
        ):
            yield obj


def _annotation_contains_float(annotation) -> bool:
    if annotation is float:
        return True
    origin = get_origin(annotation)
    if origin is None:
        return False
    return any(_annotation_contains_float(arg) for arg in get_args(annotation))


@pytest.mark.parametrize("module", CONVERTED_MODULES, ids=lambda m: m.__name__)
def test_no_money_or_quantity_field_is_float(module):
    offenders = []
    for model in _models(module):
        for name, field in model.model_fields.items():
            if name in INEXACT_BY_DESIGN or not MUST_BE_EXACT.search(name):
                continue
            if _annotation_contains_float(field.annotation):
                offenders.append(f"{model.__name__}.{name}: {field.annotation}")

    assert not offenders, (
        "these fields carry money or a counted quantity and are typed float; "
        "binary floating point cannot represent them exactly:\n  "
        + "\n  ".join(sorted(offenders))
    )


def test_every_narcotic_quantity_field_moved_together():
    """A half-converted narcotics ledger raises TypeError on Decimal - float."""
    quantity_names = re.compile(r"(quantity|dose|waste_amount|_count|counts|variance)$")

    floats = []
    decimals = []
    for model in _models(narcotic):
        for name, field in model.model_fields.items():
            if not quantity_names.search(name):
                continue
            (
                floats if _annotation_contains_float(field.annotation) else decimals
            ).append(f"{model.__name__}.{name}")

    assert decimals, (
        "no narcotic quantity fields resolved — the scan is not finding the models"
    )
    assert not floats, (
        "these narcotic quantity fields are still float while their siblings are "
        "Decimal; arithmetic between them raises TypeError:\n  "
        + "\n  ".join(sorted(floats))
    )


@pytest.mark.parametrize("value", ["0.1", "2.675", "0.05", "1.005", "0.3"])
def test_a_quantity_survives_the_json_round_trip_unchanged(value: str):
    """These are the values binary float gets wrong. Decimal must not."""
    payload = _waste_request(Decimal(value))

    restored = narcotic.WasteNarcoticRequest.model_validate_json(
        payload.model_dump_json()
    )

    assert restored.waste_amount == Decimal(value)
    # The exact digits, not merely an equal-looking value.
    assert str(restored.waste_amount) == value


def test_the_same_value_as_a_float_does_not_survive():
    """The defect this change removes, stated as an executable fact."""
    total = 0.0
    for _ in range(10):
        total += 0.1
    assert total != 1.0, (
        "if this ever passes, the float claim in this module needs revisiting"
    )

    exact = sum((Decimal("0.1") for _ in range(10)), Decimal("0"))
    assert exact == Decimal("1.0")


def test_the_json_wire_type_is_a_string_and_this_is_the_breaking_change():
    """Pinned deliberately, because consumers have to move for it.

    Pydantic serialises `Decimal` to a JSON *string*. Every one of these 79
    fields previously emitted a JSON number, so a consumer doing arithmetic on
    the parsed value without converting will break. Input stays compatible —
    a JSON number still deserialises — so the break is one-directional, on read.
    """
    emitted = json.loads(_waste_request(Decimal("2.675")).model_dump_json())
    assert isinstance(emitted["waste_amount"], str), (
        "the wire type changed back to a number; that is a second breaking "
        "change for every consumer that already migrated"
    )
    assert emitted["waste_amount"] == "2.675"

    # A JSON number on the way in is still accepted, so producers on the old
    # contract keep working against a migrated consumer.
    from_number = narcotic.WasteNarcoticRequest.model_validate_json(
        json.dumps({**emitted, "waste_amount": 2.675})
    )
    assert from_number.waste_amount == Decimal("2.675")


def test_the_positive_quantity_constraints_survived_the_conversion():
    """`gt=0` and `ge=0` are not interchangeable on a DEA-reportable field."""
    with pytest.raises(ValueError):
        _waste_request(Decimal("0"))

    # ge=0 fields still accept zero — the two constraints must not have been
    # normalised to one during the conversion.
    from datetime import UTC, datetime

    accepted = narcotic.MedicationCreateRequest(
        drug_name="fentanyl",
        dea_schedule=narcotic.ControlledSubstanceSchedule.SCHEDULE_II,
        strength="100 mcg/2 mL",
        form="ampule",
        vault_id=_UUID_B,
        quantity=Decimal("0"),
        lot_number="LOT-1",
        expiration_date=datetime(2027, 1, 1, tzinfo=UTC),
    )
    assert accepted.quantity == Decimal("0")
