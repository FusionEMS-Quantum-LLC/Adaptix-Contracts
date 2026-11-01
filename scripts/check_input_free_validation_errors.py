#!/usr/bin/env python3
"""Refuse a FastAPI app that answers a refused request with the caller's input.

Why this exists (Contracts #375, step 4)
----------------------------------------
FastAPI's default ``RequestValidationError`` answer repeats each error's
``input``: the rejected value, or the whole body when a field is missing.
Adaptix request bodies carry patient names, dates of birth, MRNs and
credentials. ``adaptix_contracts.validation_errors.install_input_free_validation_errors``
replaces that answer, but the 2026-10-28 census found 0 services calling it
and 69 on the framework default. Adopting it one service at a time leaves the
next new app free to ship the default again, so this check fails on arrival
instead.

What it reports
---------------
Python files only, parsed with ``ast``, so names inside strings, comments and
docstrings are never counted.

* ``missing-installer``: a file that constructs a FastAPI app (``FastAPI(...)``,
  through an import alias, or ``fastapi.FastAPI(...)``) and calls
  ``install_input_free_validation_errors`` fewer times than it constructs
  apps. Every construction in such a file is reported, because the check
  cannot tell which app the call covers. Exception handlers are per app: a
  sub-app built with ``FastAPI()`` and mounted under another does not use its
  parent's handlers, so it needs its own call.

The rule is file-level because the installer's documented place is the app
factory, right after ``FastAPI(...)``. An app whose handlers are installed in
another module, or that registers its own ``RequestValidationError`` handler
that is known to drop ``input`` (Gateway #379, Integrations #335, Transport
#350), is recorded in the allowlist with that reason. When the file itself
registers a ``RequestValidationError`` handler the finding's detail says so,
so the reason can be checked before it is written down. Not detected: an app
built from a subclass of ``FastAPI``.

Allowlist format
----------------
One entry per line: ``<path relative to the scanned root>:<kind>  # <reason>``.
The reason is required. Entries bind to a file and kind, not a line number,
because line numbers move with unrelated edits. An entry that no longer
matches anything is reported as stale so the list shrinks as services adopt
the installer.

Exit status: 0 when every finding is allowlisted, 1 when any is not, 2 on a
malformed allowlist.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

MISSING_INSTALLER = "missing-installer"
KINDS = (MISSING_INSTALLER,)

_FASTAPI = "FastAPI"
_FASTAPI_MODULE = "fastapi"
_INSTALLER = "install_input_free_validation_errors"
_VALIDATION_ERROR = "RequestValidationError"
_HANDLER_REGISTRARS = frozenset({"exception_handler", "add_exception_handler"})

#: Directory and file patterns skipped by default. Tests build bare apps on
#: purpose; vendored and virtual environments are not the repository's code.
DEFAULT_EXCLUDES = (
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "site-packages",
    "build",
    "dist",
    "tests",
    "test_*.py",
    "*_test.py",
    "conftest.py",
)


@dataclass(frozen=True, order=True)
class Finding:
    path: str
    line: int
    kind: str
    detail: str


class AllowlistError(ValueError):
    """The allowlist file is malformed."""


def parse_allowlist(text: str) -> dict[tuple[str, str], str]:
    """Return ``{(path, kind): reason}``; raise on a line without a reason."""
    entries: dict[tuple[str, str], str] = {}
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        target, sep, reason = line.partition("#")
        target = target.strip()
        reason = reason.strip()
        if not sep or not reason:
            raise AllowlistError(f"line {number}: an entry needs '# <reason>'")
        path, colon, kind = target.rpartition(":")
        if not colon or not path or kind not in KINDS:
            raise AllowlistError(
                f"line {number}: expected '<path>:<kind>' with kind in {KINDS}"
            )
        entries[(path, kind)] = reason
    return entries


def _is_excluded(relative: Path, excludes: Iterable[str]) -> bool:
    parts = relative.parts
    for pattern in excludes:
        if any(fnmatch.fnmatch(part, pattern) for part in parts):
            return True
    return False


def iter_python_files(root: Path, excludes: Iterable[str]) -> Iterator[Path]:
    patterns = tuple(excludes)
    for path in sorted(root.rglob("*.py")):
        if not _is_excluded(path.relative_to(root), patterns):
            yield path


def _call_name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


class _Visitor(ast.NodeVisitor):
    def __init__(self) -> None:
        # Local names bound to the FastAPI class and to the fastapi module,
        # e.g. ``from fastapi import FastAPI as App`` or ``import fastapi as fa``.
        self._app_classes: set[str] = {_FASTAPI}
        self._fastapi_modules: set[str] = {_FASTAPI_MODULE}
        # Local names bound to the installer, e.g. ``from
        # adaptix_contracts.validation_errors import
        # install_input_free_validation_errors as install``.
        self._installers: set[str] = {_INSTALLER}
        self.app_lines: list[int] = []
        self.installer_calls = 0
        self.own_handler = False

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in node.names:
            if alias.name == _FASTAPI and module.split(".")[0] == _FASTAPI_MODULE:
                self._app_classes.add(alias.asname or alias.name)
            elif alias.name == _INSTALLER:
                self._installers.add(alias.asname or alias.name)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == _FASTAPI_MODULE:
                self._fastapi_modules.add(alias.asname or alias.name)
        self.generic_visit(node)

    def _is_app_construction(self, func: ast.expr) -> bool:
        if isinstance(func, ast.Name):
            return func.id in self._app_classes
        return (
            isinstance(func, ast.Attribute)
            and func.attr == _FASTAPI
            and isinstance(func.value, ast.Name)
            and func.value.id in self._fastapi_modules
        )

    def _is_installer_call(self, func: ast.expr) -> bool:
        if isinstance(func, ast.Name):
            return func.id in self._installers
        return isinstance(func, ast.Attribute) and func.attr == _INSTALLER

    def _registers_own_handler(self, node: ast.Call) -> bool:
        if _call_name(node.func) in _HANDLER_REGISTRARS:
            return bool(node.args) and _call_name(node.args[0]) == _VALIDATION_ERROR
        return any(
            kw.arg == "exception_handlers"
            and any(_call_name(key) == _VALIDATION_ERROR for key in _dict_keys(kw))
            for kw in node.keywords
        )

    def visit_Call(self, node: ast.Call) -> None:
        if self._is_app_construction(node.func):
            self.app_lines.append(node.lineno)
            if self._registers_own_handler(node):
                self.own_handler = True
        elif self._is_installer_call(node.func):
            self.installer_calls += 1
        elif self._registers_own_handler(node):
            self.own_handler = True
        self.generic_visit(node)


def _dict_keys(keyword: ast.keyword) -> list[ast.expr]:
    if isinstance(keyword.value, ast.Dict):
        return [key for key in keyword.value.keys if key is not None]
    return []


def scan_source(source: str, path: str) -> list[Finding]:
    tree = ast.parse(source, filename=path)
    visitor = _Visitor()
    visitor.visit(tree)
    apps = len(visitor.app_lines)
    if visitor.installer_calls >= apps:
        return []
    detail = f"{apps} app(s), {visitor.installer_calls} installer call(s) in this file"
    if visitor.own_handler:
        detail += "; registers its own RequestValidationError handler"
    return sorted(
        Finding(path, line, MISSING_INSTALLER, detail) for line in visitor.app_lines
    )


def scan(root: Path, excludes: Iterable[str] = DEFAULT_EXCLUDES) -> list[Finding]:
    findings: list[Finding] = []
    for file in iter_python_files(root, excludes):
        relative = file.relative_to(root).as_posix()
        try:
            source = file.read_text(encoding="utf-8")
            findings.extend(scan_source(source, relative))
        except (SyntaxError, UnicodeDecodeError) as exc:
            print(f"warning: {relative}: not parsed ({exc})", file=sys.stderr)
    return sorted(findings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", nargs="?", default=".", type=Path)
    parser.add_argument("--allowlist", type=Path, default=None)
    parser.add_argument(
        "--exclude",
        action="append",
        default=None,
        help="extra glob to skip (repeatable); added to the defaults",
    )
    args = parser.parse_args(argv)

    root: Path = args.root.resolve()
    excludes = DEFAULT_EXCLUDES + tuple(args.exclude or ())
    allowed: dict[tuple[str, str], str] = {}
    if args.allowlist is not None:
        try:
            allowed = parse_allowlist(args.allowlist.read_text(encoding="utf-8"))
        except AllowlistError as exc:
            print(f"error: {args.allowlist}: {exc}", file=sys.stderr)
            return 2

    findings = scan(root, excludes)
    unlisted = [f for f in findings if (f.path, f.kind) not in allowed]
    matched = {(f.path, f.kind) for f in findings}
    stale = sorted(key for key in allowed if key not in matched)

    for finding in unlisted:
        print(f"{finding.path}:{finding.line}: {finding.kind} ({finding.detail})")
    for path, kind in stale:
        print(f"stale allowlist entry: {path}:{kind}")
    print(
        f"input-free validation errors check: {len(findings)} finding(s), "
        f"{len(findings) - len(unlisted)} allowlisted across {len(allowed)} "
        f"entr{'y' if len(allowed) == 1 else 'ies'}, {len(unlisted)} refused, "
        f"{len(stale)} stale"
    )
    return 1 if unlisted else 0


if __name__ == "__main__":
    sys.exit(main())
