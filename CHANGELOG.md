# Changelog

All notable changes to `adaptix-contracts` are recorded in this file.

The format follows Keep a Changelog principles and uses semantic versioning.

Entries for 1.1.0 through 1.3.0 were reconstructed from merged pull requests
after the changelog fell behind the `__version__` / `pyproject.toml` version.
Each item below is attributed to the PR that introduced it. The current
package version is `1.4.0` (see `pyproject.toml` and `adaptix_contracts/__init__.py`).

## [1.4.0] - 2026-07-03

### Security — entitlement gate fail-closed (production)
- **module_entitlement_gate:** a gateway signature that is PRESENT but cannot be
  verified because `ADAPTIX_GATEWAY_SHARED_SECRET` is not configured now returns
  **503 `gateway_secret_not_configured`** in production instead of silently
  falling back to the unverified-bearer legacy path — same posture as
  `get_auth_context` behavior 3. Non-production keeps fail-open + CRITICAL log
  (#86). Absent-signature bearer path, verified path, and tampered→401 are
  unchanged.

### Deprecated (import paths preserved until 2.0.0; emit DeprecationWarning)
- `adaptix_contracts.security.auth_context` (`TenantAuthContext`,
  `RolePermissionDecision`) — parallel auth-context model with zero consumers.
  Replacement: `auth_contracts.AuthContext` (gateway edge) or
  `auth.context.AdaptixAuthContext` (JWT-payload model) (#87).
- `adaptix_contracts.auth.rbac_dependencies` — never adopt: its
  `Depends()`-on-a-pydantic-model pattern sources identity from request data;
  its `require_module_entitlement` conflicts with the real gate; its
  `rbac_decorator` enforces nothing. Replacement: `get_auth_context` +
  `auth.module_entitlement_gate` + service-side RBAC (#87). README gains a
  "Canonical auth surfaces" section (#87).

### Governance / packaging
- CODEOWNERS rewritten to this repo's real layout — the shared auth trust files
  are now founder-review-protected once branch protection is enabled (#82).
- Removed the committed salvaged-branch git bundle (content verified merged) (#83).
- `uv.lock` synced to 1.4.0; `[project.urls]` repointed to the canonical
  `FusionEMS-Quantum-LLC` org repo (#84).
- Fixed `auth_contracts.py` module-docstring drift (no dev bearer-JWT fallback
  exists); refreshed TEST_EVIDENCE (coverage 67%); buildspec/env-example
  de-templating; historical status docs marked HISTORICAL (#85).

### Verified fleet rollout status (live ECS matrix, 2026-07-03)
The fail-closed default keys off `ENVIRONMENT` ∈ {`production`, `prod`}.
Live `aws ecs describe-task-definition` sweep of the `adaptix-production`
cluster on 2026-07-03 showed:

- **Arms on next rebuild (ENVIRONMENT set):** ai, air-pilot, assetops, bedrock,
  billing, communications, core, epcr, field, fire, gateway, hl7, hospital,
  telephony, voice. All of these carry `ADAPTIX_GATEWAY_SHARED_SECRET`
  **except air-pilot** (owner: air lane — wire the secret with the pending
  gateway route/CloudMap work or its first ≥1.4.0 rebuild 503s signed traffic).
- **fire** already runs `ADAPTIX_GATEWAY_HMAC_ENFORCE=true` (enforcement live);
  `fire_taskdef.tf` `ignore_changes` protects it from TF reverts.
- **investor** lacks the shared secret (inert today — ENVIRONMENT unset).
- **~45 other production services do NOT set `ENVIRONMENT`** — this package
  treats them as non-production (previous fail-open behavior) until each sets
  it. Fleet-wide `ENVIRONMENT=production` is a tracked follow-up hardening
  program; flipping it arms enforcement and must be per-service verified.

**Per-service rebuild checklist (run at each service's first deploy on ≥1.4.0):**
1. Real user path through the gateway → 200.
2. Forged `X-Is-Founder`/`X-User-Id`/`X-Tenant-Id` direct to the service (no
   signature) → 401.
3. Logs: no unexpected `Missing gateway auth context signature` 401s from
   legitimate callers, and no `503 … shared secret is not configured`.
4. If a legitimate unsigned intra-VPC caller surfaces: set
   `ADAPTIX_GATEWAY_HMAC_ENFORCE=false` for that service, file the caller for
   gateway-fronting, and re-verify.

### Security (BREAKING default in production — coordinate fleet rollout)
- **APPSEC-CONTRACTS-UNSIGNED-HEADER-TRUST:** `get_auth_context` is now
  **fail-closed by default in production** for UNSIGNED requests. Previously,
  with `ADAPTIX_GATEWAY_HMAC_ENFORCE` unset, forged `X-User-Id` / `X-Tenant-Id`
  / `X-Is-Founder` headers on an unsigned request were trusted — live-exploitable
  on ALB-direct routes that bypass the gateway. Now, when `ENVIRONMENT` is
  `production`/`prod`, an absent gateway signature returns **401** unless
  `ADAPTIX_GATEWAY_HMAC_ENFORCE` is EXPLICITLY set to a false-y value
  (`false`/`0`/`no`) as a migration opt-out. Non-production keeps the previous
  default (absent signature allowed) for dev/test ergonomics. An explicit
  `true`/`1`/`yes` forces enforcement in any environment.
- **Behavior 3 fail-closed in production:** a gateway signature that is PRESENT
  but cannot be verified because the service has no `ADAPTIX_GATEWAY_SHARED_SECRET`
  configured now returns **503** in production instead of allow-with-warning. A
  signed request that cannot be verified must not be trusted. Non-production
  keeps allow-with-warning.
- **Audience pinning** on the verified (B1) path is unchanged and remains
  additive: when `ADAPTIX_GATEWAY_EXPECTED_AUDIENCE` is set, the verified signed
  context's `aud` must match (401 on mismatch); no-op when unset. Enforced by
  `verify_gateway_signature`.
- **Unchanged:** the verified-signature path (present signature + configured
  secret → HMAC verify, replay window, identity-match, signed payload
  authoritative for roles/email/founder) and the tampered/expired/identity-
  mismatch → 401 behaviors are untouched.

**Rollout warning:** this is a fleet-wide behavior change. Before the fleet
re-pins this Contracts version, every domain service that has a legitimate
UNSIGNED intra-VPC caller MUST set `ADAPTIX_GATEWAY_HMAC_ENFORCE=false`
explicitly, or it will begin returning 401 in production. Coordinate via the
platform orchestrator; do not blind-merge and fleet-deploy.

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