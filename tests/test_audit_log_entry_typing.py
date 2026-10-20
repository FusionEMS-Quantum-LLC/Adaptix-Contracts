import inspect
import sys
from typing import get_args, get_origin, get_type_hints
from uuid import UUID

import pytest

from pydantic import JsonValue

from adaptix_contracts.audit_contracts import AuditLogEntry, AuditServiceClient


def test_audit_log_snapshots_are_typed_json_objects() -> None:
    annotations = get_type_hints(AuditLogEntry)

    for column in ("changes_before", "changes_after"):
        snapshot_type = get_args(annotations[column])[0]
        object_type = next(
            item for item in get_args(snapshot_type) if item is not type(None)
        )

        assert get_origin(object_type) is dict
        assert get_args(object_type) == (str, JsonValue)


SNAPSHOT_TYPE = dict[str, JsonValue] | None


def test_writer_parameters_agree_with_the_columns() -> None:
    """``log_action`` takes the type the columns store (Contracts #407).

    It took ``dict[str, Any]`` while the columns held ``dict``; the two sides of
    the same value did not agree, and ``Any`` hid that from every checker.
    """
    hints = get_type_hints(AuditServiceClient.log_action)
    assert hints["changes_before"] == SNAPSHOT_TYPE
    assert hints["changes_after"] == SNAPSHOT_TYPE


def test_ignored_keyword_arguments_are_typed_as_object_not_any() -> None:
    """The extra keyword arguments are discarded, so ``object`` is the truthful
    type: no reader narrows them, and ``Any`` would only hide that."""
    hints = get_type_hints(AuditServiceClient.log_action)
    assert hints["_ignored_kwargs"] is object


def test_module_source_carries_no_any() -> None:
    """``Any`` was the module's only escape hatch; none is left."""
    import adaptix_contracts.audit_contracts as module

    source = inspect.getsource(module)
    assert "Any" not in source.replace("JsonValue", "")


def test_audit_log_entry_repr_text_is_unchanged() -> None:
    """The text a log line or debugger shows for an entry (Contracts #407).

    ``__repr__`` is a custom override, not the ``<AuditLogEntry object at ...>``
    default, so consumers can read who did what from it. Marking it ``@override``
    must not change it.
    """
    entry = AuditLogEntry(
        id=UUID("00000000-0000-0000-0000-0000000000a1"),
        tenant_id=UUID("00000000-0000-0000-0000-0000000000b2"),
        actor_user_id=UUID("00000000-0000-0000-0000-0000000000c3"),
        action="cad.case.created",
        resource_type="case",
        resource_id="case-1",
    )
    assert repr(entry) == (
        "<AuditLogEntry 00000000-0000-0000-0000-0000000000a1 "
        "(cad.case.created on case case-1 by "
        "00000000-0000-0000-0000-0000000000c3)>"
    )


@pytest.mark.skipif(
    sys.version_info < (3, 12),
    reason=(
        "typing.override sets __override__ from 3.12; on the 3.11 floor the "
        "marker is an identity decorator (CI runs 3.12)"
    ),
)
def test_repr_override_is_marked_with_the_stdlib_marker() -> None:
    """The override is declared, not implicit (reportImplicitOverride).

    ``typing.override`` records ``__override__ = True`` on the function, so the
    marker is observable at runtime on 3.12+ and the type checkers read it.
    """
    assert getattr(AuditLogEntry.__repr__, "__override__", False) is True
