#!/usr/bin/env python3
"""Detect producer/registry drift for Adaptix cross-service events.

Why this exists
---------------
``adaptix_contracts.events.registry.ALL_EVENTS`` is the allow-list a consumer
uses to decide whether an inbound event is a known contract
(``is_registered``), and ``events/operational_envelope.assert_event_type_registered``
rejects anything absent from it. If a domain service starts publishing a new
``event_type`` through the shared envelope without registering it, nothing fails
at build time in that service's repo — the drift only surfaces as a rejected or
silently-ignored event at runtime, in another repo.

This audit closes that hole. It parses every ``.py`` file in the polyrepo
workspace, finds each construction of a SHARED-CONTRACT event envelope
(``EventSchema``, ``AdaptixEventEnvelope``, ``OperationalEventEnvelope``), reads
the literal ``event_type=`` and the literal ``source_service=`` (on the call
itself or on a nested ``EventMetadata(...)`` argument) and reports:

* UNREGISTERED — an ``event_type`` a producer publishes that ``ALL_EVENTS`` does
  not contain.
* SOURCE_SERVICE_MISMATCH — the producer stamps a ``source_service`` that
  differs from the one the registry declares for that ``event_type``.
* UNRESOLVED_SOURCE_SERVICE — the producer stamps a ``source_service`` that
  names no service in ``schemas.service_registry``.

Scope and honest limits
-----------------------
* Static AST only. It sees literal ``event_type="..."`` arguments. A producer
  that passes a variable (a generic re-publisher such as
  ``Adaptix-Audit-Service/backend/audit_app/events/publisher.py``) is invisible
  to it, by design — the event type there is chosen by that publisher's caller.
* It proves REGISTRATION, not payload shape. Both envelopes carry
  ``payload: dict[str, Any]``, so no payload contract is checked here.
* Test files are reported separately and never fail the audit; a fixture may
  legitimately use an unregistered string.

Usage::

    python scripts/audit_event_producer_drift.py --workspace-root /path/to/workspace
    python scripts/audit_event_producer_drift.py --json

Exit code 0 = no drift, 1 = drift found, 2 = misuse.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from adaptix_contracts.events.registry import (  # noqa: E402
    ALL_EVENTS,
    resolve_source_service,
)

#: Constructors that produce a SHARED cross-service event contract. A service's
#: own private event class is intentionally out of scope.
ENVELOPE_CONSTRUCTORS = frozenset(
    {
        "EventSchema",
        "AdaptixEventEnvelope",
        "OperationalEventEnvelope",
    }
)

#: Nested constructor that carries ``source_service`` for ``EventSchema``.
_METADATA_CONSTRUCTOR = "EventMetadata"

IGNORED_DIR_NAMES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".quarantine-2026-05-21",
        ".ruff_cache",
        ".snapshots",
        ".tox",
        ".venv",
        "_venv",
        "build",
        "dist",
        "htmlcov",
        "node_modules",
        "site-packages",
        "venv",
        "__pycache__",
    }
)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Detect Adaptix event types published through a shared contract "
            "envelope that the events registry does not declare."
        )
    )
    parser.add_argument(
        "--workspace-root",
        default=os.environ.get("ADAPTIX_CONTRACTS_WORKSPACE_ROOT"),
        help=(
            "Polyrepo workspace root containing the Adaptix repos. Defaults to "
            "ADAPTIX_CONTRACTS_WORKSPACE_ROOT or this repo's parent directory."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit a machine-readable JSON report.",
    )
    return parser.parse_args(argv)


def _callee_name(func: ast.expr) -> str | None:
    """Return the constructor name for ``Name(...)`` and ``Name.attr(...)``."""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        if isinstance(func.value, ast.Name):
            # AdaptixEventEnvelope.create(...) -> AdaptixEventEnvelope
            return func.value.id
        return func.attr
    return None


def _literal_kwarg(call: ast.Call, name: str) -> str | None:
    for keyword in call.keywords:
        if keyword.arg == name and isinstance(keyword.value, ast.Constant):
            value = keyword.value.value
            if isinstance(value, str):
                return value
    return None


def _nested_source_service(call: ast.Call) -> str | None:
    """Read ``source_service`` from a nested ``EventMetadata(...)`` argument."""
    for keyword in call.keywords:
        value = keyword.value
        if (
            isinstance(value, ast.Call)
            and _callee_name(value.func) == _METADATA_CONSTRUCTOR
        ):
            nested = _literal_kwarg(value, "source_service")
            if nested is not None:
                return nested
    return None


def _iter_python_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIR_NAMES]
        for filename in filenames:
            if filename.endswith(".py"):
                yield Path(dirpath) / filename


def _is_test_path(relative_posix: str) -> bool:
    return "/tests/" in relative_posix or "/test_" in relative_posix


def collect_emissions(root: Path, workspace_root: Path) -> list[dict[str, object]]:
    """Return one record per shared-envelope construction with a literal type."""
    emissions: list[dict[str, object]] = []
    for path in _iter_python_files(root):
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not any(name in source for name in ENVELOPE_CONSTRUCTORS):
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _callee_name(node.func) not in ENVELOPE_CONSTRUCTORS:
                continue
            event_type = _literal_kwarg(node, "event_type")
            if event_type is None:
                # Dynamic re-publisher: the caller chooses the type.
                continue
            source_service = _literal_kwarg(
                node, "source_service"
            ) or _nested_source_service(node)
            try:
                relative = path.resolve().relative_to(workspace_root).as_posix()
            except ValueError:
                relative = path.resolve().as_posix()
            emissions.append(
                {
                    "event_type": event_type,
                    "source_service": source_service,
                    "site": f"{relative}:{node.lineno}",
                    "is_test": _is_test_path(f"/{relative}"),
                }
            )
    return emissions


def classify(emissions: Sequence[dict[str, object]]) -> dict[str, list[dict]]:
    """Split production emissions into drift buckets."""
    unregistered: list[dict] = []
    mismatched: list[dict] = []
    unresolved: list[dict] = []
    clean: list[dict] = []
    for emission in emissions:
        if emission["is_test"]:
            continue
        event_type = str(emission["event_type"])
        source_service = emission["source_service"]
        if event_type not in ALL_EVENTS:
            unregistered.append(emission)
            continue
        declared = str(ALL_EVENTS[event_type]["source_service"])
        if source_service is None:
            clean.append(emission)
            continue
        if resolve_source_service(str(source_service)) is None:
            unresolved.append({**emission, "registry_source_service": declared})
            continue
        if str(source_service) != declared:
            mismatched.append({**emission, "registry_source_service": declared})
            continue
        clean.append(emission)
    return {
        "UNREGISTERED": unregistered,
        "SOURCE_SERVICE_MISMATCH": mismatched,
        "UNRESOLVED_SOURCE_SERVICE": unresolved,
        "CLEAN": clean,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    workspace_root = (
        Path(args.workspace_root).resolve()
        if args.workspace_root
        else _REPO_ROOT.parent
    )
    if not workspace_root.is_dir():
        print(f"workspace root is not a directory: {workspace_root}", file=sys.stderr)
        return 2

    emissions: list[dict[str, object]] = []
    for repo_dir in sorted(workspace_root.iterdir()):
        if not repo_dir.is_dir() or repo_dir.name in IGNORED_DIR_NAMES:
            continue
        if repo_dir.resolve() == _REPO_ROOT:
            continue
        emissions.extend(collect_emissions(repo_dir, workspace_root))

    buckets = classify(emissions)
    drift_count = (
        len(buckets["UNREGISTERED"])
        + len(buckets["SOURCE_SERVICE_MISMATCH"])
        + len(buckets["UNRESOLVED_SOURCE_SERVICE"])
    )
    passed = drift_count == 0
    report = {
        "workspace_root": str(workspace_root),
        "registry_size": len(ALL_EVENTS),
        "production_emission_sites": sum(1 for e in emissions if not e["is_test"]),
        "drift_count": drift_count,
        "status": "PASS" if passed else "FAIL",
        **buckets,
    }

    if args.json_output:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("ADAPTIX EVENT PRODUCER DRIFT AUDIT")
        print(f"Workspace root: {workspace_root}")
        print(f"Registry size: {len(ALL_EVENTS)} event types")
        print(f"Production emission sites: {report['production_emission_sites']}")
        if passed:
            print("PASS - every literally-typed production emission is registered")
            print("       with a matching, resolvable source_service.")
        else:
            print(f"FAIL - {drift_count} drifted emission(s):")
            for bucket in (
                "UNREGISTERED",
                "SOURCE_SERVICE_MISMATCH",
                "UNRESOLVED_SOURCE_SERVICE",
            ):
                for item in buckets[bucket]:
                    print(
                        f" - [{bucket}] {item['event_type']} "
                        f"(source_service={item['source_service']!r}) "
                        f"at {item['site']}"
                    )

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
