# Adaptix-Contracts Test Evidence

Date: 2026-07-03 (supersedes the 2026-05-08 snapshot below)

## Evidence — 2026-07-03 @ v1.4.0 (main 224673b)
- `ruff check .` — PASS (exit 0)
- `ruff format --check .` — PASS (174 files already formatted)
- `mypy --ignore-missing-imports adaptix_contracts` — PASS ("no issues found in 153 source files")
- `python -m pytest tests -q` — PASS (174 passed, 1 warning, 1.60s, Python 3.14.5)
- `python validate_contracts.py --json` — PASS (exit 0; 29/29 domains, `missing_domains: []`)
- `python -m pytest tests -q --cov=adaptix_contracts --cov-report=term` — PASS; **TOTAL coverage 67%** (12,505 stmts / 4,141 missed)
  - Zero-coverage modules (tracked gap, not a pass claim):
    `transportlink/document_intelligence.py` (54 stmts),
    `transportlink/signatures.py` (81 stmts),
    `workforce/models.py` (73 stmts)
- Known warning: `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead` — tracked; will break on a future starlette major if unaddressed.

## Historical snapshot — 2026-05-08 (1.0.x era)
- `python validate_contracts.py` — PASS
- `python -m pytest tests/test_narcotic_enum_compat.py -q` — PASS
- `python -m pytest tests/test_auth_contracts.py tests/test_release_readiness.py -q` — PASS (11 tests)
- `python -m pytest --cov=adaptix_contracts --cov-report=term-missing` — PASS (79 tests)
- `python -m build --sdist --wheel` — PASS
- `python -m twine check dist/*` — PASS
- Consumer import-source guards (Core, Inventory, Narcotics, Integrations) — PASS
- `python scripts/audit_workspace_contracts.py --workspace-root <workspace> --json` — PASS (`shadow_package_count = 0`)

## Evidence Missing
- Runtime verification of any consumer service running against v1.4.0 (no consumer has rebuilt on 1.4.0 yet — rollout tracked in the 1.4.0 release notes and Infra env wiring).

## Verdict
Local gates PASS at v1.4.0. Coverage 67% with three zero-coverage modules listed above.
