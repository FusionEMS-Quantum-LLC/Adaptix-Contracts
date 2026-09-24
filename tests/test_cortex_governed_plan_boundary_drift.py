"""Drift guard: Cortex governed-plan execution boundary types (FND-001).

``ActionTarget``, ``DomainPreconditionContract``, ``DomainResultType``,
``DomainRecordState`` and ``DomainActionResult`` in
``adaptix_contracts.schemas.cortex_contracts`` must stay field for field the
types Adaptix-Cortex-Service declares in ``app/models/governed_plan.py``.

There is no cross-repository Python dependency to import the Cortex copy
from, so, as ``tests/test_trustsign_client_mirror_drift.py`` does for the
TrustSign client, the Cortex declaration is written down below as a frozen
manifest, transcribed from Cortex origin/main
``eb4b09fa23c2230c66c20e9739d5c69148726781`` (verified 2026-09-24).

If this test fails, one side changed. Change the other side in the same
release: update this module and the manifest, bump the contracts version,
and repin Cortex (or change Cortex back). Once Cortex imports these types
from adaptix-contracts instead of declaring its own, this manifest is the
only remaining copy and the Cortex-side declaration disappears.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

from adaptix_contracts.schemas.cortex_contracts import (
    ActionTarget,
    DomainActionResult,
    DomainPreconditionContract,
    DomainRecordState,
    DomainResultType,
)

CORTEX_SOURCE = (
    "Adaptix-Cortex-Service app/models/governed_plan.py @ "
    "eb4b09fa23c2230c66c20e9739d5c69148726781"
)

REQUIRED = "REQUIRED"
FACTORY_LIST = "default_factory=list"

#: model -> (extra policy, {field: (annotation, default, constraints)}), in
#: declaration order, transcribed from CORTEX_SOURCE.
CORTEX_MANIFEST: dict[
    type[BaseModel], tuple[str | None, dict[str, tuple[Any, Any, dict[str, int]]]]
] = {
    ActionTarget: (
        "forbid",
        {
            "resource_type": (str, REQUIRED, {"min_length": 1, "max_length": 120}),
            "resource_id": (str, REQUIRED, {"min_length": 1, "max_length": 200}),
        },
    ),
    DomainPreconditionContract: (
        "forbid",
        {
            "plan_id": (str, REQUIRED, {}),
            "plan_revision": (str, REQUIRED, {}),
            "tenant_id": (str, REQUIRED, {}),
            "action_index": (int, REQUIRED, {}),
            "action_key": (str, REQUIRED, {}),
            "required_permission": (str, REQUIRED, {}),
            "target": (ActionTarget, REQUIRED, {}),
            "arguments": (dict[str, Any], REQUIRED, {}),
            "idempotency_key": (str | None, REQUIRED, {}),
            "expected_version": (str | None, REQUIRED, {}),
            "requires_approval": (bool, REQUIRED, {}),
            "timeout_seconds": (int, REQUIRED, {}),
        },
    ),
    DomainRecordState: (
        "forbid",
        {
            "tenant_id": (str, REQUIRED, {}),
            "current_version": (str | None, REQUIRED, {}),
            "executor_permissions": (list[str], FACTORY_LIST, {}),
            "approved_revision": (str | None, None, {}),
        },
    ),
    DomainActionResult: (
        None,
        {
            "result_type": (DomainResultType, REQUIRED, {}),
            "message": (str, REQUIRED, {}),
            "expected_version": (str | None, None, {}),
            "current_version": (str | None, None, {}),
        },
    ),
}

#: DomainResultType members, in declaration order, from CORTEX_SOURCE.
CORTEX_RESULT_TYPES = [
    ("SUCCEEDED", "SUCCEEDED"),
    ("STALE_PLAN", "STALE_PLAN"),
    ("REJECTED_TENANT", "REJECTED_TENANT"),
    ("REJECTED_PERMISSION", "REJECTED_PERMISSION"),
    ("REJECTED_NOT_APPROVED", "REJECTED_NOT_APPROVED"),
    ("FAILED", "FAILED"),
]


def _default_of(info: FieldInfo) -> Any:
    if info.default_factory is list:
        return FACTORY_LIST
    if info.default is PydanticUndefined and info.default_factory is None:
        return REQUIRED
    return info.default


def _constraints_of(info: FieldInfo) -> dict[str, int]:
    found: dict[str, int] = {}
    for item in info.metadata:
        for name in ("min_length", "max_length"):
            value = getattr(item, name, None)
            if value is not None:
                found[name] = value
    return found


@pytest.mark.parametrize("model", list(CORTEX_MANIFEST), ids=lambda m: m.__name__)
def test_boundary_model_matches_cortex_field_for_field(model: type[BaseModel]) -> None:
    extra, expected_fields = CORTEX_MANIFEST[model]
    assert model.model_config.get("extra") == extra, (
        f"{model.__name__} extra policy drifted"
    )
    actual = {
        name: (info.annotation, _default_of(info), _constraints_of(info))
        for name, info in model.model_fields.items()
    }
    assert list(actual) == list(expected_fields), (
        f"{model.__name__} field names or order drifted from {CORTEX_SOURCE}"
    )
    for name, expected in expected_fields.items():
        assert actual[name] == expected, (
            f"{model.__name__}.{name} is {actual[name]}, {CORTEX_SOURCE} declares {expected}"
        )


def test_result_types_match_cortex_member_for_member() -> None:
    assert issubclass(DomainResultType, str)
    assert [
        (member.name, member.value) for member in DomainResultType
    ] == CORTEX_RESULT_TYPES


def test_stale_plan_is_a_distinct_result_nothing_executes_on() -> None:
    result = DomainActionResult(
        result_type=DomainResultType.STALE_PLAN,
        message="record version changed since the plan was built",
        expected_version="7",
        current_version="8",
    )
    assert result.result_type is DomainResultType.STALE_PLAN
    assert result.result_type is not DomainResultType.FAILED


def test_precondition_contract_refuses_unknown_fields_and_keeps_nullable_required() -> (
    None
):
    body = {
        "plan_id": "plan-1",
        "plan_revision": "a" * 64,
        "tenant_id": "tenant-cert-a",
        "action_index": 0,
        "action_key": "inventory.blood_unit.quarantine",
        "required_permission": "inventory:write",
        "target": {"resource_type": "blood_unit", "resource_id": "bu-cert-1"},
        "arguments": {},
        "idempotency_key": None,
        "expected_version": None,
        "requires_approval": True,
        "timeout_seconds": 30,
    }
    assert DomainPreconditionContract.model_validate(body).expected_version is None
    with pytest.raises(ValueError):
        DomainPreconditionContract.model_validate({**body, "approved": True})
    missing = dict(body)
    del missing["expected_version"]
    with pytest.raises(ValueError):
        DomainPreconditionContract.model_validate(missing)
