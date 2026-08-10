"""Self-tests for ``scripts/audit_event_producer_drift.py``.

A drift detector that cannot be shown to DETECT is worthless — a silent scanner
and a clean workspace look identical. These tests validate the detector against
synthetic fixture repos with a known-good control (a registered, correctly
stamped emission that must NOT be reported) alongside each defect class it is
supposed to catch.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "audit_event_producer_drift.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "adaptix_audit_event_producer_drift", _SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit = _load_module()


def _write_repo(root: Path, name: str, relative: str, body: str) -> Path:
    path = root / name / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    (root / name / ".git").mkdir(parents=True, exist_ok=True)
    return path


_CLEAN_PRODUCER = """
from adaptix_contracts.event_contracts import EventSchema, EventMetadata


def publish():
    return EventSchema(
        event_type="fire.incident.created",
        metadata=EventMetadata(
            tenant_id="t",
            timestamp="2026-08-09T00:00:00Z",
            source_service="fire",
        ),
        payload={},
    )
"""

_UNREGISTERED_PRODUCER = """
from adaptix_contracts.event_contracts import EventSchema, EventMetadata


def publish():
    return EventSchema(
        event_type="fire.incident.definitely_not_registered",
        metadata=EventMetadata(
            tenant_id="t",
            timestamp="2026-08-09T00:00:00Z",
            source_service="fire",
        ),
        payload={},
    )
"""

_MISMATCHED_PRODUCER = """
from adaptix_contracts.event_contracts import EventSchema, EventMetadata


def publish():
    return EventSchema(
        event_type="fire.incident.created",
        metadata=EventMetadata(
            tenant_id="t",
            timestamp="2026-08-09T00:00:00Z",
            source_service="billing",
        ),
        payload={},
    )
"""

_UNRESOLVED_PRODUCER = """
from adaptix_contracts.event_contracts import EventSchema, EventMetadata


def publish():
    return EventSchema(
        event_type="fire.incident.created",
        metadata=EventMetadata(
            tenant_id="t",
            timestamp="2026-08-09T00:00:00Z",
            source_service="not-a-service",
        ),
        payload={},
    )
"""

_DYNAMIC_PRODUCER = """
from adaptix_contracts.event_contracts import EventSchema, EventMetadata


def publish(event_type: str):
    return EventSchema(
        event_type=event_type,
        metadata=EventMetadata(
            tenant_id="t",
            timestamp="2026-08-09T00:00:00Z",
            source_service="fire",
        ),
        payload={},
    )
"""


def _classify(tmp_path: Path) -> dict[str, list[dict]]:
    emissions: list[dict] = []
    for repo in sorted(tmp_path.iterdir()):
        if repo.is_dir():
            emissions.extend(audit.collect_emissions(repo, tmp_path))
    return audit.classify(emissions)


# ---------------------------------------------------------------------------
# Known-good control
# ---------------------------------------------------------------------------


def test_control_a_correct_producer_is_not_reported(tmp_path: Path) -> None:
    _write_repo(tmp_path, "Fake-Service", "app/publisher.py", _CLEAN_PRODUCER)
    buckets = _classify(tmp_path)
    assert buckets["UNREGISTERED"] == []
    assert buckets["SOURCE_SERVICE_MISMATCH"] == []
    assert buckets["UNRESOLVED_SOURCE_SERVICE"] == []
    assert len(buckets["CLEAN"]) == 1
    assert buckets["CLEAN"][0]["event_type"] == "fire.incident.created"


# ---------------------------------------------------------------------------
# Each defect class is actually detected
# ---------------------------------------------------------------------------


def test_detects_an_unregistered_event_type(tmp_path: Path) -> None:
    _write_repo(tmp_path, "Fake-Service", "app/publisher.py", _UNREGISTERED_PRODUCER)
    buckets = _classify(tmp_path)
    assert len(buckets["UNREGISTERED"]) == 1
    found = buckets["UNREGISTERED"][0]
    assert found["event_type"] == "fire.incident.definitely_not_registered"
    assert found["site"].endswith(":6")
    assert found["site"].startswith("Fake-Service/app/publisher.py")


def test_detects_a_source_service_mismatch(tmp_path: Path) -> None:
    _write_repo(tmp_path, "Fake-Service", "app/publisher.py", _MISMATCHED_PRODUCER)
    buckets = _classify(tmp_path)
    assert len(buckets["SOURCE_SERVICE_MISMATCH"]) == 1
    found = buckets["SOURCE_SERVICE_MISMATCH"][0]
    assert found["source_service"] == "billing"
    assert found["registry_source_service"] == "fire"


def test_detects_an_unresolvable_source_service(tmp_path: Path) -> None:
    _write_repo(tmp_path, "Fake-Service", "app/publisher.py", _UNRESOLVED_PRODUCER)
    buckets = _classify(tmp_path)
    assert len(buckets["UNRESOLVED_SOURCE_SERVICE"]) == 1
    assert buckets["UNRESOLVED_SOURCE_SERVICE"][0]["source_service"] == "not-a-service"


def test_accepts_a_legacy_prefixed_source_service_without_flagging_it_unresolved(
    tmp_path: Path,
) -> None:
    """A pinned older producer may still stamp "adaptix-fire"; that resolves."""
    body = _CLEAN_PRODUCER.replace(
        'source_service="fire"', 'source_service="adaptix-fire"'
    )
    _write_repo(tmp_path, "Fake-Service", "app/publisher.py", body)
    buckets = _classify(tmp_path)
    assert buckets["UNRESOLVED_SOURCE_SERVICE"] == []
    # It resolves, but it is no longer the canonical declared value, so it is
    # surfaced as a mismatch rather than silently accepted.
    assert len(buckets["SOURCE_SERVICE_MISMATCH"]) == 1


# ---------------------------------------------------------------------------
# Documented limits, asserted so they cannot be mistaken for coverage
# ---------------------------------------------------------------------------


def test_dynamic_event_type_is_out_of_scope(tmp_path: Path) -> None:
    """A generic re-publisher passes a variable; the AST cannot resolve it."""
    _write_repo(tmp_path, "Fake-Service", "app/publisher.py", _DYNAMIC_PRODUCER)
    buckets = _classify(tmp_path)
    assert all(not items for key, items in buckets.items())


def test_test_files_are_not_treated_as_production_emitters(tmp_path: Path) -> None:
    _write_repo(
        tmp_path, "Fake-Service", "tests/test_publisher.py", _UNREGISTERED_PRODUCER
    )
    buckets = _classify(tmp_path)
    assert buckets["UNREGISTERED"] == []


def test_non_envelope_constructor_is_ignored(tmp_path: Path) -> None:
    body = _UNREGISTERED_PRODUCER.replace("EventSchema(", "SomePrivateEvent(").replace(
        "import EventSchema, EventMetadata", "import EventMetadata"
    )
    _write_repo(tmp_path, "Fake-Service", "app/publisher.py", body)
    buckets = _classify(tmp_path)
    assert buckets["UNREGISTERED"] == []


def test_unparseable_file_does_not_crash_the_audit(tmp_path: Path) -> None:
    _write_repo(tmp_path, "Fake-Service", "app/broken.py", "def (:::\n")
    _write_repo(tmp_path, "Fake-Service", "app/publisher.py", _CLEAN_PRODUCER)
    buckets = _classify(tmp_path)
    assert len(buckets["CLEAN"]) == 1


# ---------------------------------------------------------------------------
# CLI contract
# ---------------------------------------------------------------------------


def test_cli_exits_zero_on_a_clean_workspace(tmp_path: Path, capsys) -> None:
    _write_repo(tmp_path, "Fake-Service", "app/publisher.py", _CLEAN_PRODUCER)
    exit_code = audit.main(["--workspace-root", str(tmp_path)])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_cli_exits_one_and_names_the_site_on_drift(tmp_path: Path, capsys) -> None:
    _write_repo(tmp_path, "Fake-Service", "app/publisher.py", _UNREGISTERED_PRODUCER)
    exit_code = audit.main(["--workspace-root", str(tmp_path)])
    assert exit_code == 1
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "UNREGISTERED" in out
    assert "fire.incident.definitely_not_registered" in out
    assert "Fake-Service/app/publisher.py:6" in out


def test_cli_exits_two_on_a_missing_workspace_root(tmp_path: Path) -> None:
    assert audit.main(["--workspace-root", str(tmp_path / "nope")]) == 2


def test_cli_json_output_is_machine_readable(tmp_path: Path, capsys) -> None:
    import json

    _write_repo(tmp_path, "Fake-Service", "app/publisher.py", _UNREGISTERED_PRODUCER)
    audit.main(["--workspace-root", str(tmp_path), "--json"])
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "FAIL"
    assert report["drift_count"] == 1
    assert report["UNREGISTERED"][0]["event_type"] == (
        "fire.incident.definitely_not_registered"
    )


@pytest.mark.parametrize("ignored", sorted(audit.IGNORED_DIR_NAMES))
def test_ignored_directories_are_skipped(tmp_path: Path, ignored: str) -> None:
    _write_repo(
        tmp_path, "Fake-Service", f"{ignored}/publisher.py", _UNREGISTERED_PRODUCER
    )
    buckets = _classify(tmp_path)
    assert buckets["UNREGISTERED"] == []
