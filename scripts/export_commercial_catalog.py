#!/usr/bin/env python3
"""Write (or check) ``adaptix_contracts/commercial_catalog.json``.

The JSON is the machine-readable form of every carried commercial offer
catalog version (``adaptix_contracts.commercial.offer_catalogs``) for
non-Python consumers such as Adaptix-Web-App, which must show list prices
without hand-copying them. It is committed so a consumer can pin a Contracts
commit and diff, and
``tests/test_commercial_offer_catalog.py::test_committed_commercial_catalog_json_is_current``
fails when a catalog changes without this file being regenerated.

Usage::

    uv run python scripts/export_commercial_catalog.py          # write
    uv run python scripts/export_commercial_catalog.py --check  # exit 1 on drift
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / "adaptix_contracts" / "commercial_catalog.json"

sys.path.insert(0, str(REPO_ROOT))

from adaptix_contracts import __version__  # noqa: E402
from adaptix_contracts.commercial.offer_catalogs import (  # noqa: E402
    export_offer_catalogs,
)


def render_catalog() -> str:
    """Deterministic JSON text for every carried catalog version.

    Like ``export_application_catalog.py`` it embeds no commit, so the drift
    check is satisfiable from a clean tree; consumers record the commit they
    fetched the file at.
    """

    catalog = export_offer_catalogs(contracts_version=__version__)
    catalog["source_repository"] = "FusionEMS-Quantum-LLC/Adaptix-Contracts"
    return json.dumps(catalog, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str]) -> int:
    check = "--check" in argv
    rendered = render_catalog()
    relative = OUTPUT.relative_to(REPO_ROOT)
    if check:
        # Byte-exact, so a CRLF file cannot pass on a platform that would
        # otherwise normalize it away.
        current = OUTPUT.read_bytes().decode("utf-8") if OUTPUT.exists() else ""
        if current != rendered:
            sys.stderr.write(
                f"{relative} is out of date with adaptix_contracts.commercial; run "
                "`uv run python scripts/export_commercial_catalog.py`\n"
            )
            return 1
        print(f"{relative} is current")
        return 0
    # newline="\n" so a Windows generator writes the same bytes as Linux CI.
    OUTPUT.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"wrote {relative}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
