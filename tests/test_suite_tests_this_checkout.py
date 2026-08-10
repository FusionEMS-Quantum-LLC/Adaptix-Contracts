"""Guard: the suite must exercise THIS checkout, not an installed copy.

``adaptix-contracts`` is installed into other Adaptix service virtualenvs and,
on developer machines, into the user site-packages. If ``pytest`` resolves
``adaptix_contracts`` from one of those instead of from the repository, every
other test in this suite measures the wrong code: the run can be green while the
source in the working tree is broken, and red while it is correct. That failure
mode is silent — the only symptom is a confusing import error much later.

``pythonpath = ["."]`` in ``pyproject.toml`` prevents it. This test proves the
setting is in force, so removing it fails here rather than months later.
"""

from __future__ import annotations

from pathlib import Path

import adaptix_contracts
from adaptix_contracts.events import registry

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _resolved(module: object) -> Path:
    file_attr = getattr(module, "__file__", None)
    assert file_attr is not None, f"{module!r} has no __file__"
    return Path(file_attr).resolve()


def test_adaptix_contracts_package_is_imported_from_this_repository() -> None:
    imported = _resolved(adaptix_contracts)
    assert imported.is_relative_to(_REPO_ROOT), (
        f"tests imported adaptix_contracts from {imported}, which is outside "
        f"{_REPO_ROOT}. The suite would validate an installed copy instead of "
        'this checkout. Restore `pythonpath = ["."]` under '
        "[tool.pytest.ini_options] in pyproject.toml."
    )


def test_event_registry_module_is_imported_from_this_repository() -> None:
    imported = _resolved(registry)
    assert imported == _REPO_ROOT / "adaptix_contracts" / "events" / "registry.py"
