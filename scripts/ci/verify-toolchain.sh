#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${repo_root}"

python3 scripts/generate_tool_inventory.py
python3 scripts/verify_toolchain.py

if [[ -f package-lock.json ]]; then
  npm ci
  npm run typecheck --if-present
  npm run lint --if-present
  npm test --if-present
  npm run build --if-present
fi

if [[ -f pyproject.toml && -f uv.lock ]]; then
  # Fail closed when uv.lock no longer matches pyproject.toml. `uv sync
  # --frozen` does NOT catch this: with pyproject.toml at 4.3.0 and uv.lock
  # still recording 4.2.0 (the state #254 left on main), it exits 0 and
  # leaves the stale lock in place, so this gate reported green while the
  # two files disagreed. `uv lock --check` is the explicit assertion that
  # the lock is current for the manifest, and it is what the fleet
  # dependency law requires: a lock file moves in the same commit as the
  # manifest it derives from, never later.
  uv lock --check
  uv sync --frozen --all-extras
  uv run ruff format --check .
  uv run ruff check .
  uv run mypy .

  # CONSUMER VIEW - the check the run above is structurally unable to perform.
  #
  # `uv run mypy .` loads `plugins = ["pydantic.mypy"]` from pyproject.toml.
  # That plugin models Pydantic field specifiers correctly, including a
  # POSITIONAL default such as `Field(1, ge=1)`, so it can never report the
  # breakage such a default causes in the consumer repositories that do not
  # enable the plugin - they fall back to PEP 681 dataclass_transform, which
  # reads only `default=` / `default_factory=`, keeps the parameter REQUIRED,
  # and fails on ordinary construction with `Missing named argument`.
  #
  # 503 such defaults across 42 files shipped fleet-wide (PR #273) with this
  # gate green throughout. This second run type-checks the SHIPPED package the
  # way a plugin-less consumer sees it. See mypy-consumer-view.ini for the
  # full rationale and the one named exclusion it carries. Declaration sites
  # are additionally covered by tests/test_field_defaults_are_keyword_only.py,
  # which `uv run pytest` below executes.
  uv run mypy --config-file mypy-consumer-view.ini adaptix_contracts
  uv run pytest

  # DEPRECATION_POLICY.md lists `python validate_contracts.py` under "Required
  # release evidence", and CONTRIBUTING.md, README.md and RUNBOOK.md all tell
  # contributors to run it - but nothing executed it automatically, so the
  # repository's own required release check depended on someone remembering.
  # A gate that is only ever run by hand is a gate that silently stops running.
  # Guarded on the file so this script stays usable in repos without it.
  if [[ -f validate_contracts.py ]]; then
    uv run python validate_contracts.py
  fi
fi

if find . -name '*.tf' -not -path '*/.terraform/*' -print -quit | grep -q .; then
  terraform fmt -check -recursive
fi

if [[ -x ./gradlew ]]; then
  ./gradlew --no-daemon check
fi
