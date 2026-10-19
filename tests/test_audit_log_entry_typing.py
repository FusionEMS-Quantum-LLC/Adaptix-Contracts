"""The audit JSON snapshots are declared as what the column stores (Contracts #407).

``AuditLogEntry.changes_before`` / ``changes_after`` were ``Mapped[dict | None]``.
A bare ``dict`` is ``dict[Unknown, Unknown]`` to Pyright strict and
``dict[Any, Any]`` to mypy, so every strict consumer that read the columns got
unknown types at the read (CAD #732 had to go through
``sqlalchemy.inspect(entry).attrs.<column>.value`` to reach zero). The writer,
``AuditServiceClient.log_action``, took ``dict[str, Any]``: the two sides did
not agree.

Both now declare ``dict[str, JsonValue] | None`` with pydantic's ``JsonValue``,
the alias this package already uses for JSON values. This is the declared type
only; nothing about what is stored or returned changed.
"""

from __future__ import annotations

import inspect
from typing import get_type_hints

from pydantic import JsonValue
from sqlalchemy.orm import Mapped

from adaptix_contracts.audit_contracts import AuditLogEntry, AuditServiceClient

SNAPSHOT_TYPE = dict[str, JsonValue] | None


def test_changes_columns_declare_a_json_object_or_none() -> None:
    hints = get_type_hints(AuditLogEntry)
    assert hints["changes_before"] == Mapped[SNAPSHOT_TYPE]
    assert hints["changes_after"] == Mapped[SNAPSHOT_TYPE]


def test_writer_parameters_agree_with_the_columns() -> None:
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
