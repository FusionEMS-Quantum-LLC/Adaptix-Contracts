"""Pydantic ``Field()`` defaults in the shipped package must be KEYWORD-passed.

A positional default - ``quantity: int = Field(1, ge=1)`` - is honoured by
Pydantic at runtime, so this repository's own tests and its plugin-enabled
mypy run both stay green. Consumers see something else entirely.

Every repository that consumes ``adaptix_contracts`` without enabling the
``pydantic.mypy`` plugin type-checks these models through PEP 681
``dataclass_transform``, which recognises only the ``default=`` and
``default_factory=`` KEYWORD parameters of a field specifier. A positional
default is invisible to it, so the synthesised ``__init__`` parameter stays
REQUIRED and ordinary construction fails with ``Missing named argument``.

That defect reached 503 declarations across 42 files and broke consumers
fleet-wide (corrected in PR #273). Nothing in the repository's gate could see
it, because the gate only ever looked through the plugin.

This test closes that hole at the DECLARATION site, which is where the defect
is actually introduced. It is deliberately independent of mypy: the
complementary plugin-less mypy run (``mypy-consumer-view.ini``) reports the
same defect class only where a model is also CONSTRUCTED inside this package,
which most of these contract modules never do.
"""

from __future__ import annotations

import ast
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "adaptix_contracts"


def _called_name(func: ast.expr) -> str | None:
    """Return the trailing callable name for ``Field(...)`` or ``x.Field(...)``."""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _positional_field_defaults(tree: ast.AST) -> list[tuple[int, str]]:
    """Return ``(lineno, rendered_argument)`` for every offending ``Field()`` call."""
    offenders: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _called_name(node.func) != "Field":
            continue
        for arg in node.args:
            # `Field(...)` - a bare Ellipsis - is Pydantic's explicit "this field
            # is required" marker, not a default. PEP 681 already treats a field
            # specifier carrying no `default=`/`default_factory=` as required,
            # so both views agree and there is nothing to diverge.
            if isinstance(arg, ast.Constant) and arg.value is Ellipsis:
                continue
            offenders.append((node.lineno, ast.unparse(arg)))
    return offenders


def test_no_positional_field_defaults_in_shipped_package() -> None:
    assert PACKAGE_ROOT.is_dir(), f"package root not found: {PACKAGE_ROOT}"

    sources = sorted(PACKAGE_ROOT.rglob("*.py"))
    assert sources, f"no Python sources discovered under {PACKAGE_ROOT}"

    findings: list[str] = []
    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for lineno, rendered in _positional_field_defaults(tree):
            location = path.relative_to(PACKAGE_ROOT.parent).as_posix()
            findings.append(f"  {location}:{lineno}: Field({rendered}, ...)")

    assert not findings, (
        "Pydantic Field() defaults must be passed by KEYWORD "
        "(`default=` / `default_factory=`), never positionally.\n"
        "A positional default is honoured at runtime but is INVISIBLE to PEP 681 "
        "dataclass_transform, which every consumer that does not enable the "
        "pydantic mypy plugin falls back to. Those consumers see the field as "
        "REQUIRED and fail with `Missing named argument` on ordinary "
        "construction. Rewrite each of these as `Field(default=<value>, ...)`:\n"
        + "\n".join(findings)
    )
