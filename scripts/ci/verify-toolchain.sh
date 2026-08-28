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
  uv run pytest
fi

if find . -name '*.tf' -not -path '*/.terraform/*' -print -quit | grep -q .; then
  terraform fmt -check -recursive
fi

if [[ -x ./gradlew ]]; then
  ./gradlew --no-daemon check
fi
