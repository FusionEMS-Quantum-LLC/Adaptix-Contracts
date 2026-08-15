# Adaptix-Contracts Deployment Checklist

> This repository is a Python package, not an ECS service. GitHub Actions are
> analysis-only here; CodeBuild owns authoritative release/publish validation.

## Preflight

- [ ] Run `python validate_contracts.py`.
- [ ] Run `python validate_contracts.py --json` and capture the report.
- [ ] Run `python -m pytest`.
- [ ] Verify build artifact with `python -m build --sdist --wheel`.
- [ ] Verify package metadata with `python -m twine check dist/*`.
- [ ] Verify package version.
- [ ] Verify all consumers pin/use the real package by running
  `python scripts/audit_workspace_contracts.py --workspace-root <workspace>`.

## Release

- [ ] Confirm the CodeBuild main/release validation gate is green.
- [ ] Publish package or commit Git dependency target.
- [ ] Update consumers intentionally.
- [ ] Run consumer import tests.
- [ ] Run producer/consumer contract checks in every repo that imports this
  package, prioritized for Billing, ePCR, Fire, Patient Identity, Audit, and Core.
- [ ] Record any required consumer code change as a linked PR or blocker in that
  exact repo; do not claim the Contracts repo alone proves runtime compatibility.

## Runtime Verification

- [ ] Core imports succeed.
- [ ] ePCR imports succeed.
- [ ] Billing imports succeed.
- [ ] All service contract imports succeed in deployed images.
- [ ] Event producers and consumers that exchange shared envelopes verify payload
  shape compatibility, not only `event_type` registration.

## Verdict

PASS only when all checks above pass and
`python scripts/audit_workspace_contracts.py --workspace-root <workspace>`
reports `shadow_package_count = 0`.
