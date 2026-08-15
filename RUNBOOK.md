# Adaptix-Contracts Runbook

## Validate

Run the package validator, regression suite, and publishability checks.

```bash
python validate_contracts.py
python validate_contracts.py --json
python -m pytest
python -m build --sdist --wheel
python -m twine check dist/*
```

GitHub Actions in this repo are analysis/reporting only. CodeBuild is the
authoritative automation path for main-branch release validation and any
publication/deploy workflow.

Audit the wider workspace before release to detect shadow `adaptix_contracts`
packages that can override the canonical package in service builds.

```bash
python scripts/audit_workspace_contracts.py --workspace-root C:\Users\fusio\Desktop\workspace
```

## Release

Publish or pin a specific Git/package version. Do not rely on floating or local
mock contract modules for production. Do not treat GitHub Actions as release or
deployment authority for this repo; CodeBuild owns that path.

## Rollback

Revert consumers to the previous known-good contract version, republish if needed,
and rerun `validate_contracts.py`, `pytest`, artifact verification, and
workspace audit.
