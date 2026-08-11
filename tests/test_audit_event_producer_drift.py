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

# --- Resolution-rule fixtures ----------------------------------------------
# Each mirrors a shape a real Adaptix producer uses. The unregistered event type
# is the assertion handle: if the rule does not fire, nothing is reported and the
# test fails, so a silent scanner cannot pass these.

_MODULE_CONSTANT_PRODUCER = """
from adaptix_contracts.event_contracts import EventSchema, EventMetadata

FIRE_EVENT_TYPE = "fire.incident.definitely_not_registered"


def publish():
    return EventSchema(
        event_type=FIRE_EVENT_TYPE,
        metadata=EventMetadata(
            tenant_id="t",
            timestamp="2026-08-09T00:00:00Z",
            source_service="fire",
        ),
        payload={},
    )
"""

_CONDITIONAL_PRODUCER = """
from adaptix_contracts.event_contracts import EventSchema, EventMetadata

A = "fire.incident.branch_a_not_registered"
B = "fire.incident.branch_b_not_registered"


def publish(flag: bool):
    return EventSchema(
        event_type=(A if flag else B),
        metadata=EventMetadata(
            tenant_id="t",
            timestamp="2026-08-09T00:00:00Z",
            source_service="fire",
        ),
        payload={},
    )
"""

_LOCAL_VARIABLE_PRODUCER = """
from adaptix_contracts.event_contracts import EventSchema, EventMetadata

REVIEWED = "fire.incident.reviewed_not_registered"
RULED_OUT = "fire.incident.ruled_out_not_registered"


def publish(review_changed: bool, rejected: bool):
    event_type = REVIEWED
    if rejected:
        event_type = RULED_OUT
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

_WRAPPER_PRODUCER = """
from adaptix_contracts.event_contracts import EventSchema, EventMetadata


async def _publish_event(*, event_type: str, tenant_id: str, payload: dict):
    event = EventSchema(
        event_type=event_type,
        metadata=EventMetadata(
            tenant_id=tenant_id,
            timestamp="2026-08-09T00:00:00Z",
            source_service="fire",
        ),
        payload=payload,
    )
    return event


async def capture():
    await _publish_event(
        event_type="fire.incident.wrapped_not_registered",
        tenant_id="t",
        payload={},
    )
"""

_STATICMETHOD_WRAPPER_PRODUCER = """
from adaptix_contracts.event_contracts import EventSchema, EventMetadata


class Publisher:
    @staticmethod
    def _emit(*, event_type: str, tenant_id: str):
        return EventSchema(
            event_type=event_type,
            metadata=EventMetadata(
                tenant_id=tenant_id,
                timestamp="2026-08-09T00:00:00Z",
                source_service="fire",
            ),
            payload={},
        )

    @staticmethod
    def create():
        Publisher._emit(
            event_type="fire.incident.qualified_not_registered", tenant_id="t"
        )
"""

_RELAY_PRODUCER = """
from epcr_app.models import ChartEventOutbox


def enqueue(session, tenant_id, chart_id):
    session.add(
        ChartEventOutbox(
            id="1",
            tenant_id=tenant_id,
            chart_id=chart_id,
            event_type="epcr.chart.relayed_not_registered",
            payload_json="{}",
            status="pending",
        )
    )
"""

_SHADOWED_LOCAL_PRODUCER = """
from adaptix_contracts.event_contracts import EventSchema, EventMetadata


def outer():
    event_type = "fire.incident.outer_not_registered"

    def inner():
        event_type = "fire.incident.created"
        return EventSchema(
            event_type=event_type,
            metadata=EventMetadata(
                tenant_id="t",
                timestamp="2026-08-09T00:00:00Z",
                source_service="fire",
            ),
            payload={},
        )

    return inner
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
# Resolution rules: each producer shape Adaptix actually uses is resolved
# ---------------------------------------------------------------------------


def _unregistered_types(tmp_path: Path) -> set[str]:
    return {str(item["event_type"]) for item in _classify(tmp_path)["UNREGISTERED"]}


def test_resolves_a_module_level_constant(tmp_path: Path) -> None:
    _write_repo(tmp_path, "Fake-Service", "app/publisher.py", _MODULE_CONSTANT_PRODUCER)
    assert _unregistered_types(tmp_path) == {"fire.incident.definitely_not_registered"}


def test_resolves_both_branches_of_a_conditional(tmp_path: Path) -> None:
    """A consumer can receive either branch, so both must be reported."""
    _write_repo(tmp_path, "Fake-Service", "app/publisher.py", _CONDITIONAL_PRODUCER)
    assert _unregistered_types(tmp_path) == {
        "fire.incident.branch_a_not_registered",
        "fire.incident.branch_b_not_registered",
    }


def test_resolves_every_value_a_local_variable_can_hold(tmp_path: Path) -> None:
    _write_repo(tmp_path, "Fake-Service", "app/publisher.py", _LOCAL_VARIABLE_PRODUCER)
    assert _unregistered_types(tmp_path) == {
        "fire.incident.reviewed_not_registered",
        "fire.incident.ruled_out_not_registered",
    }


def test_resolves_a_call_through_an_envelope_forwarding_wrapper(
    tmp_path: Path,
) -> None:
    _write_repo(tmp_path, "Fake-Service", "app/publisher.py", _WRAPPER_PRODUCER)
    buckets = _classify(tmp_path)
    assert len(buckets["UNREGISTERED"]) == 1
    found = buckets["UNREGISTERED"][0]
    assert found["event_type"] == "fire.incident.wrapped_not_registered"
    # The wrapper's own literal source_service is attributed to the caller.
    assert found["source_service"] == "fire"


def test_resolves_a_qualified_static_helper_call(tmp_path: Path) -> None:
    """``Publisher._emit(...)`` must match on the METHOD, not just the class."""
    _write_repo(
        tmp_path, "Fake-Service", "app/publisher.py", _STATICMETHOD_WRAPPER_PRODUCER
    )
    assert _unregistered_types(tmp_path) == {"fire.incident.qualified_not_registered"}


def test_resolves_a_declared_outbox_relay_row(tmp_path: Path) -> None:
    """An outbox row is a producer: its worker republishes the row's own type."""
    _write_repo(
        tmp_path,
        "Adaptix-EPCR-Service",
        "backend/epcr_app/enqueue.py",
        _RELAY_PRODUCER,
    )
    buckets = _classify(tmp_path)
    assert len(buckets["UNREGISTERED"]) == 1
    found = buckets["UNREGISTERED"][0]
    assert found["event_type"] == "epcr.chart.relayed_not_registered"
    assert found["source_service"] == "epcr"
    assert found["relay_site"] == (
        "Adaptix-EPCR-Service/backend/epcr_app/outbox_worker.py:99"
    )


def test_relay_row_constructor_is_scoped_to_its_own_repo(tmp_path: Path) -> None:
    """Control: the same class name in another repo is NOT swept up."""
    _write_repo(tmp_path, "Some-Other-Service", "app/enqueue.py", _RELAY_PRODUCER)
    assert _unregistered_types(tmp_path) == set()


def test_every_declared_relay_cites_a_relay_site() -> None:
    for repo, constructors in audit.RELAY_ROW_CONSTRUCTORS.items():
        assert repo.startswith("Adaptix-")
        for constructor, (source_service, relay_site) in constructors.items():
            assert constructor
            assert source_service
            assert relay_site.startswith(f"{repo}/")
            assert relay_site.rsplit(":", 1)[-1].isdigit()


def test_a_shadowed_inner_binding_does_not_leak_from_the_outer_scope(
    tmp_path: Path,
) -> None:
    """Control against over-collection: only the inner binding is in scope."""
    _write_repo(tmp_path, "Fake-Service", "app/publisher.py", _SHADOWED_LOCAL_PRODUCER)
    buckets = _classify(tmp_path)
    assert buckets["UNREGISTERED"] == []
    assert [item["event_type"] for item in buckets["CLEAN"]] == [
        "fire.incident.created"
    ]


def test_a_live_producer_source_service_alias_is_not_reported_as_drift(
    tmp_path: Path,
) -> None:
    """``patient_identity`` is what the running service stamps; it must pass."""
    body = """
from adaptix_contracts.event_contracts import EventSchema, EventMetadata


def publish():
    return EventSchema(
        event_type="patient.identity.merged",
        metadata=EventMetadata(
            tenant_id="t",
            timestamp="2026-08-09T00:00:00Z",
            source_service="patient_identity",
        ),
        payload={},
    )
"""
    _write_repo(tmp_path, "Fake-Service", "app/publisher.py", body)
    buckets = _classify(tmp_path)
    assert buckets["SOURCE_SERVICE_MISMATCH"] == []
    assert buckets["UNRESOLVED_SOURCE_SERVICE"] == []
    assert len(buckets["CLEAN"]) == 1


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
