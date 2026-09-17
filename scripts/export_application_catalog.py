#!/usr/bin/env python3
"""Write (or check) ``adaptix_contracts/application_catalog.json``.

The JSON is the machine-readable form of ``adaptix_contracts.application_registry``
that non-Python consumers (Adaptix-Web-App's generated TypeScript catalog)
mirror. It is committed so a consumer can pin a Contracts commit and diff, and
``tests/test_application_registry.py::test_committed_catalog_json_is_current``
fails when the registry changes without this file being regenerated.

Usage::

    uv run python scripts/export_application_catalog.py          # write
    uv run python scripts/export_application_catalog.py --check  # exit 1 on drift
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / "adaptix_contracts" / "application_catalog.json"

sys.path.insert(0, str(REPO_ROOT))

from adaptix_contracts import __version__  # noqa: E402
from adaptix_contracts.application_registry import (  # noqa: E402
    export_application_catalog,
)
from adaptix_contracts.commercial.wisconsin_launch_catalog import (  # noqa: E402
    WI_LAUNCH_CATALOG,
)


def _source_commit() -> str | None:
    """The commit the catalog was generated from, or ``None`` outside git."""

    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    sha = completed.stdout.strip()
    return sha or None


def render_catalog() -> str:
    """Deterministic JSON text for the current registry (no commit stamp).

    The commit is deliberately NOT embedded: it would change on every commit
    and make the drift check impossible to satisfy from a clean tree. Consumers
    record the commit they fetched the file at.
    """

    catalog = export_application_catalog(
        contracts_version=__version__, pricing_catalog=WI_LAUNCH_CATALOG
    )
    catalog["source_repository"] = "FusionEMS-Quantum-LLC/Adaptix-Contracts"
    return json.dumps(catalog, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str]) -> int:
    check = "--check" in argv
    rendered = render_catalog()
    if check:
        # Byte-exact: universal-newline decoding would hide a CRLF file that
        # this script would never itself produce on Linux CI.
        current = OUTPUT.read_bytes().decode("utf-8") if OUTPUT.exists() else ""
        if current != rendered:
            sys.stderr.write(
                f"{OUTPUT.relative_to(REPO_ROOT)} is out of date with "
                "adaptix_contracts.application_registry; run "
                "`uv run python scripts/export_application_catalog.py`\n"
            )
            return 1
        print(f"{OUTPUT.relative_to(REPO_ROOT)} is current")
        return 0
    # newline="\n" so a Windows generator writes the same bytes as Linux CI —
    # the file exists to be diffed across a Contracts commit pin.
    OUTPUT.write_text(rendered, encoding="utf-8", newline="\n")
    commit = _source_commit()
    print(
        f"wrote {OUTPUT.relative_to(REPO_ROOT)} (registry at {commit or 'unknown commit'})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
