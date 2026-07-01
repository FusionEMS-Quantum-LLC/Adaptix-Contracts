# Changelog

All notable changes to `adaptix-contracts` are recorded in this file.

The format follows Keep a Changelog principles and uses semantic versioning.

Entries for 1.1.0 through 1.3.0 were reconstructed from merged pull requests
after the changelog fell behind the `__version__` / `pyproject.toml` version.
Each item below is attributed to the PR that introduced it. The current
package version is `1.3.0` (see `pyproject.toml` and `adaptix_contracts/__init__.py`).

## [1.3.0] - unreleased (accumulated on the 1.3.0 line)

`__version__` was bumped to `1.3.0` in #24. The changes below all landed on the
1.3.0 line without a further version bump; they are grouped here for consumers.

### Added
- Canonical TrustSign HTTP client in the shared package (#24).
- New domain schemas: narcotics, RBAC, supply-integrations, and `asyncio_mode` (#26).
- `require_module_entitlement` shared gate for module-services (#35).
- `require_any_module_entitlement(*slugs)` multi-slug entitlement gate.
- `ClaimStatusUpdatedEvent` enriched for the ePCR back-channel (#33, #39).
- `NarcoticAccessType` expanded with `ADMINISTER` / `WASTE` / `TRANSFER_OUT` / `TRANSFER_IN`.
- Canonical event registry entries `billing.claim.updated` and `epcr.chart.updated` (#76).

### Changed
- **Auth trust model:** replaced the custom HMAC/RS256 gateway-context proof with
  the AWS API Gateway injected-header contract (`X-User-Id` / `X-Tenant-Id` /
  `X-User-Roles` / `X-Is-Founder`), with `build_gateway_context_jwt` retained as a
  loud-failing shim (#45, #46).
- Modernized typing to PEP 604/585 and replaced `datetime.utcnow` with
  timezone-aware `datetime.now(timezone.utc)` (#37).

### Security
- **F-24:** `get_auth_context` now verifies the gateway HMAC signature
  (`X-Adaptix-Auth-Context` + `X-Adaptix-Auth-Signature`) when present. A present
  signature that fails verification returns 401. Behavior is **non-breaking and
  default-off**: an absent signature is allowed unless
  `ADAPTIX_GATEWAY_HMAC_ENFORCE=true` (#74).
- When a gateway signature verifies, the signed payload is **authoritative** for
  `roles` / `email` / `is_founder`; the individually spoofable `X-User-Roles` /
  `X-Is-Founder` / `X-User-Email` headers are ignored so a holder of a valid
  signature for their own identity cannot escalate roles or founder status (#79).
- `module_entitlement_gate` trusts gateway-verified identity (non-breaking) (#75).
- SEC-004: fixed an undefined `Optional` and restored green canonical CI (#58).

## [1.2.0] - 2026-05

### Added
- Dispatch, platform event bus, and audit domain action schemas (#20).

## [1.1.0] - 2026-05

### Added
- Finance and ledger domain contracts, bringing 15 services into compliance (#13).

### Fixed
- Aligned `__version__` with `pyproject.toml` at 1.1.0 (#13).

## [1.0.2] - 2026-05-08

### Added
- Added machine-readable `--json` output to `validate_contracts.py` so release automation can consume structured validation proof.
- Added `scripts/audit_workspace_contracts.py` to detect shadow `adaptix_contracts` trees across a polyrepo workspace.
- Added `tests/test_release_readiness.py` to cover JSON validation output and workspace shadow-package auditing.
- Added `.env.example` documenting `ADAPTIX_CONTRACTS_WORKSPACE_ROOT` for release audits.
- Added `MARKET_READY_LEDGER.md` as the authoritative proof ledger for market-readiness status.

### Changed
- Removed the repo's dependency on `pytest-asyncio` by converting async auth contract tests to synchronous `asyncio.run(...)` calls.
- Extended CI to build wheel/sdist artifacts and run `twine check` on the generated distributions.
- Updated readiness/runbook documentation to treat shadow-package detection as a hard release gate.

## [1.0.1] - 2026-04-21

### Added
- Added a pytest regression suite for schema exports, enum integrity, JSON schema generation, serialization round-trips, and representative validation failures.
- Added GitHub Actions validation for import checks, contract regression tests, and coverage reporting.
- Added documented deprecation and backward-compatibility policy for downstream services.

### Changed
- Fixed package-level symbol re-exports so `adaptix_contracts.<Symbol>` resolves consistently with `adaptix_contracts.schemas.<Symbol>`.
- Hardened `validate_contracts.py` to resolve schema paths from the repository location instead of the process working directory.
- Updated documented domain coverage from 26 to 28 to reflect `clinical_visual` and `inventory` contracts already present in the package.

## [1.0.0] - 2026-04-21

### Added
- Initial published shared Adaptix contracts package with cross-domain schema coverage.