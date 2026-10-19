from typing import get_args, get_origin, get_type_hints

from pydantic import JsonValue

from adaptix_contracts.audit_contracts import AuditLogEntry


def test_audit_log_snapshots_are_typed_json_objects() -> None:
    annotations = get_type_hints(AuditLogEntry)

    for column in ("changes_before", "changes_after"):
        snapshot_type = get_args(annotations[column])[0]
        object_type = next(
            item for item in get_args(snapshot_type) if item is not type(None)
        )

        assert get_origin(object_type) is dict
        assert get_args(object_type) == (str, JsonValue)
