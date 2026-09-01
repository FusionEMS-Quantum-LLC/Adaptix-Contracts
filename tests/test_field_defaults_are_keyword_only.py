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
is actually introduced. Its independence from mypy is load-bearing rather than
defensive: the complementary plugin-less mypy run (``mypy-consumer-view.ini``)
reports this defect class as ``call-arg`` at a CONSTRUCTION site, and a
contract library mostly declares models rather than constructing them. On the
demonstration run for PR #274 a positional default reintroduced in
``adaptix_contracts/epcr/caregraph_contracts.py`` was invisible to BOTH mypy
runs and was caught only here.
"""

from __future__ import annotations

import ast
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "adaptix_contracts"

#: Modules that export the Pydantic field specifier this guard tracks.
_PYDANTIC_MODULES = frozenset({"pydantic", "pydantic.fields"})


def _local_field_names(tree: ast.AST) -> set[str]:
    """Return the local names bound to Pydantic's ``Field`` in one module.

    ``from pydantic import Field`` is the convention throughout this package,
    but ``from pydantic import Field as F`` binds the same callable to another
    name, and a guard matching only the literal string ``Field`` would be
    silently bypassed by it. Attribute calls such as ``pydantic.Field(...)``
    are matched separately, on the attribute name.
    """
    names = {"Field"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if (node.module or "") not in _PYDANTIC_MODULES:
            continue
        names.update(
            alias.asname or alias.name for alias in node.names if alias.name == "Field"
        )
    return names


def _is_field_call(node: ast.Call, local_names: set[str]) -> bool:
    if isinstance(node.func, ast.Name):
        return node.func.id in local_names
    if isinstance(node.func, ast.Attribute):
        return node.func.attr == "Field"
    return False


def _positional_field_defaults(tree: ast.AST) -> list[tuple[int, str]]:
    """Return ``(lineno, rendered_argument)`` for every offending ``Field()`` call."""
    local_names = _local_field_names(tree)
    offenders: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_field_call(node, local_names):
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


def _findings(source: str) -> list[tuple[int, str]]:
    return _positional_field_defaults(ast.parse(source))


def test_detector_flags_a_positional_default() -> None:
    """Positive control. A guard that cannot fail proves nothing."""
    source = (
        "from pydantic import BaseModel, Field\n"
        "class M(BaseModel):\n"
        "    quantity: int = Field(1, ge=1)\n"
    )
    assert _findings(source) == [(3, "1")]


def test_detector_accepts_the_keyword_and_required_forms() -> None:
    """Negative control. The forms PEP 681 and Pydantic agree on must pass."""
    source = (
        "from pydantic import BaseModel, Field\n"
        "class M(BaseModel):\n"
        "    quantity: int = Field(default=1, ge=1)\n"
        "    tags: list[str] = Field(default_factory=list)\n"
        "    name: str = Field(..., description='required')\n"
    )
    assert _findings(source) == []


def test_detector_follows_an_aliased_field_import() -> None:
    """An alias binds the same callable and must not slip past the guard."""
    source = (
        "from pydantic import BaseModel\n"
        "from pydantic import Field as F\n"
        "class M(BaseModel):\n"
        "    quantity: int = F(1, ge=1)\n"
    )
    assert _findings(source) == [(4, "1")]


def test_detector_follows_a_qualified_field_call() -> None:
    """``pydantic.Field(...)`` is the same specifier under another spelling."""
    source = (
        "import pydantic\n"
        "class M(pydantic.BaseModel):\n"
        "    quantity: int = pydantic.Field(1, ge=1)\n"
    )
    assert _findings(source) == [(3, "1")]


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
