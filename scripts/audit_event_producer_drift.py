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
workspace, finds each production of a SHARED-CONTRACT event, resolves the
``event_type`` and the ``source_service`` the producer stamps, and reports:

* UNREGISTERED — an ``event_type`` a producer publishes that ``ALL_EVENTS`` does
  not contain.
* SOURCE_SERVICE_MISMATCH — the producer stamps a ``source_service`` that
  resolves to a different service than the one the registry declares for that
  ``event_type``.
* UNRESOLVED_SOURCE_SERVICE — the producer stamps a ``source_service`` that
  names no service in ``schemas.service_registry`` and has no declared alias.

Resolution rules
----------------
An emission is counted when ``event_type`` can be resolved to a string literal
through any of these, which are the shapes Adaptix producers actually use:

1. **Direct construction** — ``EventSchema(event_type="x", ...)``.
2. **Module-level constant** — ``CHART_SIGNED_EVENT_TYPE = "epcr.chart.signed"``
   passed as ``event_type=CHART_SIGNED_EVENT_TYPE``.
3. **Conditional expression** — ``event_type=(A if cond else B)`` contributes
   BOTH branches; a consumer can receive either.
4. **Function-local variable** — ``event_type = A`` / reassigned under a branch,
   then ``event_type=event_type``. Every value the name can hold inside that
   function is contributed; over-collecting here is safe because each candidate
   is a real string the producer can emit.
5. **Envelope-forwarding function** — a function whose body constructs a shared
   envelope with ``event_type=<its own parameter>`` is a thin publish wrapper, so
   every call to it (by bare name, ``Class.helper(...)`` or ``self.helper(...)``)
   with a resolvable ``event_type=`` is an emission. The wrapper's own literal
   ``source_service`` is attributed to those call sites.
6. **Declared outbox relay** — a persisted outbox row whose worker republishes
   the row's own ``event_type`` through a shared envelope. Those relays are
   listed in :data:`RELAY_ROW_CONSTRUCTORS`, each with the exact relay
   ``file:line`` that proves it, because the relay site itself passes a variable
   and is therefore invisible to rules 1-5.

Scope and honest limits
-----------------------
* Static AST only, within a single file. A producer that reaches an envelope
  through a cross-FILE helper that is not a declared relay is still invisible;
  so is a fully dynamic re-publisher such as
  ``Adaptix-Audit-Service/backend/audit_app/events/publisher.py``, where the
  event type is chosen by that publisher's caller.
* It proves REGISTRATION and PRODUCER IDENTITY, not payload shape. Both shared
  envelopes carry ``payload: dict[str, Any]``, so no payload contract is checked
  here.
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
from collections.abc import Iterator, Sequence
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from adaptix_contracts.events.registry import (  # noqa: E402
    ALL_EVENTS,
    PRODUCER_SOURCE_SERVICE_ALIASES,
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

#: Outbox row constructors whose worker republishes the row's OWN ``event_type``
#: through a shared envelope, keyed by the repository directory name so a
#: same-named class in another repo is not swept up by accident.
#:
#: ``{repo: {row_constructor: (stamped_source_service, relay_file_line)}}``
#:
#: Each relay citation is a real ``file:line`` at that repo's ``origin/main``
#: (verified 2026-08-09) where the worker builds the shared envelope from the
#: row. Do not add an entry without one — the whole point is that the relay is
#: proven, not assumed.
RELAY_ROW_CONSTRUCTORS: dict[str, dict[str, tuple[str, str]]] = {
    "Adaptix-EPCR-Service": {
        "ChartEventOutbox": (
            "epcr",
            "Adaptix-EPCR-Service/backend/epcr_app/outbox_worker.py:99",
        ),
    },
    "Adaptix-Patient-Identity-Service": {
        "OutboxEvent": (
            "patient_identity",
            "Adaptix-Patient-Identity-Service/backend/patient_identity_app/"
            "outbox_worker.py:88",
        ),
    },
}

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


# ---------------------------------------------------------------------------
# Name resolution
# ---------------------------------------------------------------------------


def _callee_names(func: ast.expr) -> frozenset[str]:
    """Return every plausible callee name for a call expression.

    ``helper(...)`` -> ``{"helper"}``;
    ``Class.helper(...)`` -> ``{"Class", "helper"}`` (either half may be the
    name we know: ``AdaptixEventEnvelope.create`` matches on the class,
    ``CareGraphService._outbox`` matches on the method);
    ``self.emit(...)`` -> ``{"self", "emit"}``.
    """
    if isinstance(func, ast.Name):
        return frozenset({func.id})
    if isinstance(func, ast.Attribute):
        names = {func.attr}
        if isinstance(func.value, ast.Name):
            names.add(func.value.id)
        return frozenset(names)
    return frozenset()


def _module_string_constants(tree: ast.Module) -> dict[str, str]:
    """Return module-level ``NAME = "literal"`` / ``NAME: T = "literal"`` pairs."""
    constants: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, str):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        constants[target.id] = node.value.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, str) and isinstance(node.target, ast.Name):
                constants[node.target.id] = node.value.value
    return constants


def _candidate_strings(expr: ast.expr, names: dict[str, set[str]]) -> set[str]:
    """Return every string value ``expr`` can evaluate to, as far as AST shows.

    Handles a literal, a known name, and a conditional expression (both
    branches). Anything else yields the empty set — unresolved, never guessed.
    """
    if isinstance(expr, ast.Constant):
        return {expr.value} if isinstance(expr.value, str) else set()
    if isinstance(expr, ast.Name):
        return set(names.get(expr.id, ()))
    if isinstance(expr, ast.IfExp):
        return _candidate_strings(expr.body, names) | _candidate_strings(
            expr.orelse, names
        )
    return set()


def _scope_nodes(scope: ast.AST) -> Iterator[ast.AST]:
    """Yield every node inside ``scope`` without entering a nested function."""
    stack = list(ast.iter_child_nodes(scope))
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        stack.extend(ast.iter_child_nodes(node))


def _scope_names(
    scope: ast.AST, module_constants: dict[str, str]
) -> dict[str, set[str]]:
    """Return every string a local name can hold inside ``scope``.

    Starts from the module constants and folds in every ``name = <resolvable>``
    assignment in the scope. Values accumulate rather than overwrite: a name
    reassigned under a branch can hold either value at the emission site, and
    each is a string the producer can really emit.
    """
    names: dict[str, set[str]] = {
        key: {value} for key, value in module_constants.items()
    }
    for node in _scope_nodes(scope):
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets, value = list(node.targets), node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        if value is None:
            continue
        resolved = _candidate_strings(value, names)
        if not resolved:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                names.setdefault(target.id, set()).update(resolved)
    return names


def _calls_by_scope(
    tree: ast.Module,
) -> list[tuple[ast.AST, list[ast.Call]]]:
    """Group every ``Call`` node under its innermost enclosing function scope.

    A call is analysed exactly once, with the name bindings of the scope it is
    written in — so an outer function's local cannot be mistaken for an inner
    function's shadowed name.
    """
    scopes: list[tuple[ast.AST, list[ast.Call]]] = []

    def visit(scope: ast.AST) -> None:
        calls: list[ast.Call] = []
        stack = list(ast.iter_child_nodes(scope))
        while stack:
            node = stack.pop()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(node)
                continue
            if isinstance(node, ast.Call):
                calls.append(node)
            stack.extend(ast.iter_child_nodes(node))
        scopes.append((scope, calls))

    visit(tree)
    return scopes


def _forwarding_functions(
    tree: ast.Module,
    constructors: frozenset[str],
    relays: dict[str, tuple[str, str]],
    module_constants: dict[str, str],
) -> dict[str, tuple[str | None, str | None]]:
    """Return ``{function_name: (source_service, relay_site)}`` for wrappers.

    A wrapper is a function that constructs one of ``constructors`` with
    ``event_type=<one of its own parameters>``: the caller chooses the event
    type, so the caller is the real producer. The wrapper's own literal
    ``source_service`` — or, when it forwards into a declared outbox relay, the
    ``source_service`` that relay's worker stamps — is attributed to the caller.
    """
    wrappers: dict[str, tuple[str | None, str | None]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        parameters = {argument.arg for argument in node.args.args} | {
            argument.arg for argument in node.args.kwonlyargs
        }
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Call):
                continue
            hits = _callee_names(inner.func) & constructors
            if not hits:
                continue
            forwards = any(
                keyword.arg == "event_type"
                and isinstance(keyword.value, ast.Name)
                and keyword.value.id in parameters
                for keyword in inner.keywords
            )
            if not forwards:
                continue
            names = _scope_names(node, module_constants)
            source_service = _stamped_source_service(inner, names)
            relay_site: str | None = None
            for hit in sorted(hits):
                if hit in relays:
                    stamped, relay_site = relays[hit]
                    source_service = source_service or stamped
            wrappers[node.name] = (source_service, relay_site)
    return wrappers


def _keyword_strings(call: ast.Call, name: str, names: dict[str, set[str]]) -> set[str]:
    for keyword in call.keywords:
        if keyword.arg == name:
            return _candidate_strings(keyword.value, names)
    return set()


def _stamped_source_service(call: ast.Call, names: dict[str, set[str]]) -> str | None:
    """Read ``source_service`` from the call or a nested ``EventMetadata(...)``."""
    direct = _keyword_strings(call, "source_service", names)
    if len(direct) == 1:
        return next(iter(direct))
    for keyword in call.keywords:
        value = keyword.value
        if isinstance(value, ast.Call) and _METADATA_CONSTRUCTOR in _callee_names(
            value.func
        ):
            nested = _keyword_strings(value, "source_service", names)
            if len(nested) == 1:
                return next(iter(nested))
    return None


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------


def _iter_python_files(root: Path) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIR_NAMES]
        for filename in filenames:
            if filename.endswith(".py"):
                yield Path(dirpath) / filename


def _is_test_path(relative_posix: str) -> bool:
    return "/tests/" in relative_posix or "/test_" in relative_posix


def _relay_constructors(repo_name: str) -> dict[str, tuple[str, str]]:
    return RELAY_ROW_CONSTRUCTORS.get(repo_name, {})


def collect_emissions(root: Path, workspace_root: Path) -> list[dict[str, object]]:
    """Return one record per resolved shared-contract event emission."""
    emissions: list[dict[str, object]] = []
    for path in _iter_python_files(root):
        try:
            relative = path.resolve().relative_to(workspace_root).as_posix()
        except ValueError:
            relative = path.resolve().as_posix()
        repo_name = relative.split("/", 1)[0]
        relays = _relay_constructors(repo_name)
        interesting = ENVELOPE_CONSTRUCTORS | frozenset(relays)
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not any(name in source for name in interesting):
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        module_constants = _module_string_constants(tree)
        wrappers = _forwarding_functions(tree, interesting, relays, module_constants)
        targets = interesting | frozenset(wrappers)

        for scope, calls in _calls_by_scope(tree):
            names = _scope_names(scope, module_constants)
            for node in calls:
                hits = _callee_names(node.func) & targets
                if not hits:
                    continue
                event_types = _keyword_strings(node, "event_type", names)
                if not event_types:
                    # Dynamic re-publisher, or a relay whose type comes from a
                    # persisted row: the caller chooses the type.
                    continue
                source_service = _stamped_source_service(node, names)
                relay_site: str | None = None
                for hit in sorted(hits):
                    if hit in wrappers:
                        forwarded, forwarded_relay = wrappers[hit]
                        source_service = source_service or forwarded
                        relay_site = relay_site or forwarded_relay
                    if hit in relays:
                        stamped, relay_site = relays[hit]
                        source_service = source_service or stamped
                for event_type in sorted(event_types):
                    emissions.append(
                        {
                            "event_type": event_type,
                            "source_service": source_service,
                            "site": f"{relative}:{node.lineno}",
                            "relay_site": relay_site,
                            "is_test": _is_test_path(f"/{relative}"),
                        }
                    )
    return _deduplicate(emissions)


def _deduplicate(emissions: list[dict[str, object]]) -> list[dict[str, object]]:
    """Collapse identical records (one call can match several callee names)."""
    seen: set[tuple] = set()
    unique: list[dict[str, object]] = []
    for emission in emissions:
        key = (
            emission["event_type"],
            emission["source_service"],
            emission["site"],
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(emission)
    return unique


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
        # A LIVE producer alias (PRODUCER_SOURCE_SERVICE_ALIASES) is the
        # canonical slug spelled the way a running service stamps it, so it is
        # not drift. A LEGACY alias still IS drift: it resolves, but it means a
        # producer is emitting a superseded string, and that is worth surfacing.
        canonical = PRODUCER_SOURCE_SERVICE_ALIASES.get(
            str(source_service), str(source_service)
        )
        if canonical != declared:
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
            print("PASS - every resolvable production emission is registered")
            print("       with a matching, resolvable source_service.")
        else:
            print(f"FAIL - {drift_count} drifted emission(s):")
            for bucket in (
                "UNREGISTERED",
                "SOURCE_SERVICE_MISMATCH",
                "UNRESOLVED_SOURCE_SERVICE",
            ):
                for item in buckets[bucket]:
                    via = (
                        f" via relay {item['relay_site']}" if item["relay_site"] else ""
                    )
                    print(
                        f" - [{bucket}] {item['event_type']} "
                        f"(source_service={item['source_service']!r}) "
                        f"at {item['site']}{via}"
                    )

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
