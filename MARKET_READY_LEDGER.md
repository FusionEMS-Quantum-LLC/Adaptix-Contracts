# Adaptix-Contracts Market Ready Ledger

> **HISTORICAL (2026-05 / 1.0.x era)** — superseded by CHANGELOG.md and TEST_EVIDENCE.md.
> The auth trust model changed materially in 1.3.0–1.4.0 (gateway HMAC verification,
> production fail-closed defaults); statements below predate that and are not
> current claims.

Date: 2026-05-08
Repo: Adaptix-Contracts
Feature or workflow: Market-readiness hardening, release-proof surface, and
consumer drift remediation
Status: PASS

## Files Changed

- `pyproject.toml`
- `.github/workflows/contracts-validation.yml`
- `validate_contracts.py`
- `scripts/audit_workspace_contracts.py`
- `.env.example`
- `tests/test_auth_contracts.py`
- `tests/test_narcotic_enum_compat.py`
- `tests/test_release_readiness.py`
- `adaptix_contracts/types/__init__.py`
- `adaptix_contracts/types/enums.py`
- `adaptix_contracts/schemas/narcotic.py`
- `adaptix_contracts/schemas/__init__.py`
- `README.md`
- `RUNBOOK.md`
- `DEPLOYMENT_CHECKLIST.md`
- `PRODUCTION_READINESS.md`
- `TEST_EVIDENCE.md`
- `FINALIZATION_SUMMARY.md`
- `SERVICE_CONTRACT.md`
- `CHANGELOG.md`
- `adaptix_contracts/__init__.py`

## Migrations Added

- None

## Environment Variables Added

- `ADAPTIX_CONTRACTS_WORKSPACE_ROOT`

## Tests Added

- `tests/test_release_readiness.py`

## Commands Run

- `python validate_contracts.py`
- `python -m pytest --cov=adaptix_contracts --cov-report=term-missing`
- `python -m pytest tests/test_narcotic_enum_compat.py -q`
- `python -m pytest tests/test_auth_contracts.py tests/test_release_readiness.py -q`
- `c:/Users/fusio/Desktop/workspace/Adaptix-Core-Service/.venv/Scripts/python.exe -m pytest test_import_source_guard.py -q`
- `py -3.11 -m venv Adaptix-Inventory-Service/.venv311-contracts`
- `Adaptix-Inventory-Service/.venv311-contracts/Scripts/python.exe -m pytest tests/test_import_source_guard.py tests/test_inventory_complete.py -q`
- `Adaptix-Narcotics-Service/.venv/Scripts/python.exe -m pytest -o addopts= tests/test_import_source_guard.py tests/test_narcotic_service.py -q`
- `py -3.11 -m venv Adaptix-Integrations-Service/.venv311-contracts`
- `Adaptix-Integrations-Service/.venv311-contracts/Scripts/python.exe -m pytest tests/test_import_source_guard.py -q`
- `python scripts/audit_workspace_contracts.py --workspace-root C:\Users\fusio\Desktop\workspace --json`

## Results Observed

- `validate_contracts.py` passed all 4 phases.
- Full pytest suite passed with 79 tests.
- Canonical narcotics compatibility test passed.
- Focused auth/readiness suite passed with 11 tests.
- Core import-source guard passed after local path injection removal.
- Inventory anti-shadow guard and representative service suite passed in a
  Python 3.11 validation environment.
- Narcotics anti-shadow guard and representative service suite passed against
  the canonical package compatibility surface.
- Integrations anti-shadow guard passed in a Python 3.11 validation environment.
- `python -m build --sdist --wheel` passed.
- `python -m twine check dist/*` passed cleanly after declaring the README
  metadata in `pyproject.toml`.
- Workspace audit passed with `shadow_package_count = 0`.

## Known Limitations

- Consumer dependency files now point at the canonical package, but local
  focused validation for Inventory and Integrations used Python 3.11 temporary
  virtual environments because the workstation-default Python 3.14 runtime does
  not have compatible wheels for every pinned dependency in those repos.

## Rollback Instructions

- Revert this change set.
- Restore the deleted consumer shadow package trees only if intentionally
  reverting to local copies.
- Remove `adaptix_contracts/types/` and the narcotics compatibility enum exports
  if rolling back the canonical compatibility path.

## Final Status

- PASS — consumer repos no longer shadow `adaptix_contracts`, and the
  authoritative workspace audit confirms canonical package ownership.

---

Date: 2026-05-09
Repo: Adaptix-Contracts
Feature or workflow: Reduced-scope calendar kernel contracts for TransportLink
and Workforce wrapper adoption
Status: PASS

## Files Changed

- `adaptix_contracts/calendar/__init__.py`
- `adaptix_contracts/calendar/event.py`
- `adaptix_contracts/calendar/resource.py`
- `adaptix_contracts/calendar/conflict.py`
- `adaptix_contracts/calendar/audit.py`
- `adaptix_contracts/schemas/calendar_contracts.py`
- `adaptix_contracts/schemas/__init__.py`
- `tests/test_calendar_kernel_contracts.py`

## Migrations Added

- None

## Environment Variables Added

- None

## Tests Added

- `tests/test_calendar_kernel_contracts.py`

## Commands Run

- `C:\Python314\python.exe -m pytest tests/test_calendar_kernel_contracts.py tests/test_contract_surface.py -q`

## Results Observed

- Calendar kernel contracts import cleanly through the public
  `adaptix_contracts.schemas` surface.
- Focused contract validation passed with 12 tests after reconciling the new
  reduced-scope exports with the existing calendar authority models in
  `calendar_contracts.py`.

## Known Limitations

- This slice only provides the shared contract kernel used by the web wrapper
  for TransportLink and Workforce. It does not add new backend calendar APIs in
  service repos.

## Rollback Instructions

- Revert the calendar kernel contract files and schema export changes listed above.
- Remove `tests/test_calendar_kernel_contracts.py` if rolling back the
  reduced-scope wrapper contract surface.

## Final Status

- PASS — the reduced-scope calendar kernel contract surface is implemented and
  validated in the package repo.
