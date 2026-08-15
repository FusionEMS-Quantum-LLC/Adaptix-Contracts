# Adaptix-Contracts Production Readiness

Date: 2026-08-14
Classification: NO-GO FOR PLATFORM ROLLOUT / LOCAL CONTRACT GATES PASS

## Service Purpose

Shared Python package for cross-service schemas and contract publication truth.

## Exposed Routes

No runtime HTTP routes. This repo publishes package-level schemas/contracts
consumed by services.

## Dependencies

Python packaging, downstream service imports, semantic versioning, and CI
publication process.

## Secrets Required

Package publication credentials if publishing to a private index. No runtime
secrets expected.

## Database/Migration State

No database ownership.

## Integration Dependencies

All service repos that import shared schemas.

## Health/Readiness Endpoint Status

No HTTP endpoint applies because this repo is a library. Readiness is defined by:

- `python validate_contracts.py --json`
- `python -m pytest tests -q`
- `python -m build --sdist --wheel`
- `python -m twine check dist/*`
- `python scripts/audit_workspace_contracts.py --workspace-root <workspace>`
- consumer repository import/build/runtime verification against the exact published
  or pinned contract version

## Test Status

Local contract validation passes in this checkout:

- `python validate_contracts.py --json` — PASS on 2026-08-14
  (`export_count=881`, `model_count=677`, `enum_count=191`,
  `actual_domain_count=73`, `missing_domains=[]`).

This evidence is limited to the Contracts repository. It does not prove that
downstream producer and consumer repositories have rebuilt, imported, deployed,
or run against this contract version.

## Deployment Status

The package is locally buildable, CodeBuild is the authoritative automation path
for publishable-artifact verification, and the workspace audit proves
canonical-package adoption across the audited consumer repos. GitHub Actions in
this repo are analysis-only and do not hold deployment or publication
authority.

## Production Blockers

- Consumer runtime verification is missing for the current contract version.
  Exact coordination owners: all service repositories that import
  `adaptix-contracts`, with priority on known event producers/consumers
  `Adaptix-Billing-Service`, `Adaptix-EPCR-Service`, `Adaptix-Fire-Service`,
  `Adaptix-Patient-Identity-Service`, `Adaptix-Audit-Service`, and
  `Adaptix-Core-Service`.
- Cross-repo event payload compatibility is not fully contract-enforced for
  shared event envelopes whose `payload` remains `dict[str, Any]`. Registry and
  `source_service` drift are guarded here, but payload-shape compatibility must
  be covered by exact producer/consumer schema contracts before platform rollout
  can be declared production-complete.
- A workspace-wide shadow-package audit must be rerun immediately before release:
  `python scripts/audit_workspace_contracts.py --workspace-root <workspace>`.

## Remediation Completed

- Existing shared contract package identified as authority path.
- Added machine-readable validation output via `validate_contracts.py --json`.
- Added workspace shadow-package audit script.
- Added CodeBuild artifact build and `twine check` verification.
- Added `.env.example` for workspace audit configuration.
- Added event producer registry/source-service drift guards and documented the
  remaining payload-shape limitation instead of treating it as covered.

## Final Verdict

NO-GO FOR PLATFORM ROLLOUT — local contract gates pass, but production-complete
user-ready status requires downstream producer/consumer rebuild, import, runtime,
and payload-compatibility evidence against this exact contract version.
