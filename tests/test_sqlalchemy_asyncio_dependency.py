"""Regression: the async database stack must declare what it needs to run.

The service runs on SQLAlchemy's asyncio layer, which runs on ``greenlet``.
SQLAlchemy 2.1 stopped installing ``greenlet`` by default; it now arrives only
through the ``sqlalchemy[asyncio]`` extra. With a bare ``sqlalchemy``
requirement the SQLAlchemy 2.1 bump builds an image without greenlet, and the
first database call (or the migrate step) raises ``ImportError: The
SQLAlchemy asyncio module requires that the Python 'greenlet' library is
installed``. That stopped the 2026-09-28 Adaptix-CAD-Service release.

These tests fail if the extra is dropped from pyproject.toml, or if the lock or
any committed export the image installs stops pinning ``greenlet``.
"""

from __future__ import annotations

import importlib.util
import re
import tomllib
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
EXPORTS = tuple(
    path.name
    for pattern in ("requirements*.lock", "requirements*.txt")
    for path in sorted(PROJECT.glob(pattern))
    if "uv export" in "".join(path.read_text(encoding="utf-8").splitlines(True)[:5])
)
# A PEP 508 distribution name; an optional "[extra, extra]" list follows it.
_NAME = re.compile(r"[A-Za-z0-9_.-]+")


def _sqlalchemy_extras() -> set[str]:
    data = tomllib.loads((PROJECT / "pyproject.toml").read_text(encoding="utf-8"))
    found: list[set[str]] = []
    for raw in data["project"]["dependencies"]:
        spec = raw.strip()
        match = _NAME.match(spec)
        if match is None or match.group(0).lower() != "sqlalchemy":
            continue
        rest = spec[match.end() :].lstrip()
        extras = rest[1:].partition("]")[0] if rest.startswith("[") else ""
        found.append({e.strip().lower() for e in extras.split(",") if e.strip()})
    assert len(found) == 1, f"expected one sqlalchemy requirement, found {len(found)}"
    return found[0]


def test_sqlalchemy_is_declared_with_the_asyncio_extra() -> None:
    assert "asyncio" in _sqlalchemy_extras(), (
        "pyproject.toml declares sqlalchemy without the asyncio extra, which does "
        "not install greenlet on SQLAlchemy 2.1; declare sqlalchemy[asyncio]."
    )


@pytest.mark.skipif(not (PROJECT / "uv.lock").exists(), reason="no uv.lock here")
def test_uv_lock_pins_greenlet() -> None:
    text = (PROJECT / "uv.lock").read_text(encoding="utf-8")
    assert 'name = "greenlet"' in text, "uv.lock does not pin greenlet"


def test_every_export_pins_greenlet() -> None:
    # This repository may commit no export at all; every export that installs
    # sqlalchemy must also pin greenlet. An export that does not install
    # sqlalchemy (a GPU-only supplement layered on the service export, say) has
    # nothing to pair greenlet with and is not the one that opens sessions.
    missing = []
    for export in EXPORTS:
        pins = {
            line.partition("==")[0]
            for line in (PROJECT / export).read_text(encoding="utf-8").splitlines()
            if "==" in line and not line.startswith((" ", "#"))
        }
        if "sqlalchemy" in pins and "greenlet" not in pins:
            missing.append(export)
    assert not missing, (
        f"{', '.join(missing)} does not pin greenlet, so an image installed from it "
        "cannot open an AsyncSession."
    )


def test_greenlet_is_importable_in_this_environment() -> None:
    assert importlib.util.find_spec("greenlet") is not None
