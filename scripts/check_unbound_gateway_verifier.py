#!/usr/bin/env python3
"""Refuse new uses of the gateway verifier that skips the route binding.

Why this exists (Contracts #397)
--------------------------------
``verify_gateway_signature`` checks the signed ``method``/``path`` claims only
when its caller passes ``request_method``/``request_path``. Its short name does
not say so, and 18 repositories referenced it. AssetOps #163 showed what that
costs: a context the gateway signed for ``/work-orders/`` resolved an identity
on ``/vendors/``. Fixing the call sites one at a time leaves the next service
free to pick the short name again, so this check fails on arrival instead.

What it reports
---------------
Python files only, parsed with ``ast``, so names inside strings, comments and
docstrings are never counted.

* ``unbound-verifier``: any import or use of ``verify_gateway_signature``, or of
  its ``gateway_identity.verify`` alias.
* ``get-auth-context-without-request``: a plain call of ``get_auth_context``
  without ``request=``. Resolved as ``Depends(get_auth_context)`` FastAPI
  supplies the request; called by hand without it, the contracts code runs the
  unbound path. Analytics and Graph were found this way.

Neither finding is automatically a vulnerability. A worker that no route can
reach may verify without a binding. Such a site is recorded in the allowlist
with its reason, and the count is printed on every run so the list cannot grow
quietly.

Allowlist format
----------------
One entry per line: ``<path relative to the scanned root>:<kind>  # <reason>``.
The reason is required. Entries bind to a file and kind, not a line number,
because line numbers move with unrelated edits. An entry that no longer
matches anything is reported as stale so the list shrinks as lanes migrate.

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

UNBOUND_VERIFIER = "unbound-verifier"
GET_AUTH_CONTEXT_WITHOUT_REQUEST = "get-auth-context-without-request"
KINDS = (UNBOUND_VERIFIER, GET_AUTH_CONTEXT_WITHOUT_REQUEST)

_UNBOUND_NAME = "verify_gateway_signature"
_ALIAS_MODULE_SUFFIX = "gateway_identity"
_ALIAS_NAME = "verify"

#: Directory and file patterns skipped by default. Tests exercise the
#: deprecated name on purpose during the overlap; vendored and virtual
#: environments are not the repository's code.
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
    def __init__(self, path: str) -> None:
        self.path = path
        self.findings: list[Finding] = []
        # Local names bound to the gateway_identity module, e.g.
        # ``from adaptix_contracts import gateway_identity as gi``.
        self._alias_modules: set[str] = set()

    def _add(self, node: ast.AST, kind: str, detail: str) -> None:
        self.findings.append(
            Finding(self.path, getattr(node, "lineno", 0), kind, detail)
        )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in node.names:
            if alias.name == _UNBOUND_NAME:
                self._add(node, UNBOUND_VERIFIER, f"import from {module}")
            elif alias.name == _ALIAS_NAME and module.endswith(_ALIAS_MODULE_SUFFIX):
                self._add(node, UNBOUND_VERIFIER, f"import of {module}.verify")
            elif alias.name == _ALIAS_MODULE_SUFFIX:
                self._alias_modules.add(alias.asname or alias.name)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name.endswith(_ALIAS_MODULE_SUFFIX):
                self._alias_modules.add(alias.asname or alias.name.split(".")[0])
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id == _UNBOUND_NAME and isinstance(node.ctx, ast.Load):
            self._add(node, UNBOUND_VERIFIER, "use")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr == _UNBOUND_NAME and isinstance(node.ctx, ast.Load):
            self._add(node, UNBOUND_VERIFIER, "attribute use")
        elif (
            node.attr == _ALIAS_NAME
            and isinstance(node.value, (ast.Name, ast.Attribute))
            and _call_name(node.value) in self._alias_modules | {_ALIAS_MODULE_SUFFIX}
        ):
            self._add(node, UNBOUND_VERIFIER, "gateway_identity.verify")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if _call_name(node.func) == "get_auth_context":
            keywords = {kw.arg for kw in node.keywords}
            # ``**kwargs`` (arg None) may carry request=; it is not provable
            # either way from the call site, so it is not reported.
            if "request" not in keywords and None not in keywords:
                self._add(node, GET_AUTH_CONTEXT_WITHOUT_REQUEST, "plain call")
        self.generic_visit(node)


def scan_source(source: str, path: str) -> list[Finding]:
    tree = ast.parse(source, filename=path)
    visitor = _Visitor(path)
    visitor.visit(tree)
    return sorted(visitor.findings)


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
        f"unbound gateway verifier check: {len(findings)} finding(s), "
        f"{len(findings) - len(unlisted)} allowlisted across {len(allowed)} "
        f"entr{'y' if len(allowed) == 1 else 'ies'}, {len(unlisted)} refused, "
        f"{len(stale)} stale"
    )
    return 1 if unlisted else 0


if __name__ == "__main__":
    sys.exit(main())
