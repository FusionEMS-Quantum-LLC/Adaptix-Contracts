# Changelog

All notable changes to `adaptix-contracts` are recorded in this file.

The format follows Keep a Changelog principles and uses semantic versioning.

Entries for 1.1.0 through 1.3.0 were reconstructed from merged pull requests
after the changelog fell behind the `__version__` / `pyproject.toml` version.
Each item below is attributed to the PR that introduced it. The current
package version is `2.36.0` (see `pyproject.toml`; `__version__` resolves it
from the installed package metadata).

## [Unreleased]

### Changed - BREAKING on read

- **79 money and controlled-substance quantity fields moved from `float` to
  `Decimal`.** `payment_contracts.py` has stated the package convention since
  it was written - "Monetary amounts are represented as `Decimal` in major
  currency units" - and `payment_contracts.py` / `finance_contracts.py`
  followed it. Eight other modules did not.

  Modules: `schemas/narcotic.py`, `schemas/inventory_contracts.py`,
  `schemas/founder_contracts.py`, `schemas/crm_contracts.py`,
  `inventory_events.py`, `medications_events.py`, `narcotics_events.py`,
  `supply_integrations.py`.

  **The JSON wire type changes on output.** Pydantic serialises `Decimal` to a
  JSON string, so a field that emitted `2.675` now emits `"2.675"`.
  Deserialisation is unaffected - a JSON number is still accepted - so an
  unmigrated *producer* keeps working against a migrated consumer, but a
  consumer that does arithmetic on the parsed value, or validates
  `type: number`, breaks. Every consumer that reads these fields must move.

  All of `narcotic.py` moved together, not only the waste fields. `Decimal`
  minus `float` raises `TypeError` in Python, so a half-converted
  controlled-substance ledger turns a wrong reconciliation into a crashing
  one.

  Rates, percentages, scores and durations were deliberately left as `float`:
  `churn_rate`, `net_retention_rate`, `denial_rate`, `appeal_success_rate`,
  `average_days_to_payment`, `variance_pct`, `funding_percentage`,
  `likelihood_percentage`, `readiness_score`, `risk_score`, and the trend
  lists. They are neither money nor a counted quantity.

  **No version is cut for this yet.** Releasing it before consumers are ready
  would strand 63 repositories one major behind on a package whose gateway
  audience pin is fail-closed in production.

## [2.36.0]

### Fixed

- **A signed gateway context was accepted no matter how long its own issued
  lifetime was.** `_verify_replay_window` bounded only *expired* (`now > exp`)
  and *issued-in-the-future* (`iat > now`) against the current clock. It never
  bounded `exp - iat`, so a context minted with `exp = iat + 10 years` passed
  every check and verified successfully for a decade.

  The gateway-v1 shared HMAC secret is held by every service that verifies
  gateway-v1 contexts, so any one of them could mint itself a forever-valid
  identity — including `is_founder` and arbitrary roles/entitlements — that
  every consumer running `TRUST_MODE_HMAC` or `TRUST_MODE_DUAL` accepted.
  Revocation could not reach it: the freshness window was the only bound on a
  signed context and that window was unbounded by construction.

  `_verify_replay_window` now rejects, before consulting the clock at all:

  - `exp < iat` — a malformed or hostile window; and
  - `exp - iat > _MAX_CONTEXT_LIFETIME_SECONDS` (300s) — an over-long lifetime.

  Both checks are clock-independent, so an over-long context is refused
  regardless of when it is presented. 300s matches Core's own verifier constant
  (`core_app.auth.gateway_context._MAX_CONTEXT_LIFETIME_SECONDS`).

  Landed in #208, which did not carry a version bump — the fixed and unfixed
  trees therefore both reported `2.35.0` and a consumer could not tell from the
  version which one it had resolved. **2.36.0 exists to make that distinguishable
  and is the first version string that guarantees the cap is present.** Pin
  `>= 2.36.0` (or the 2.36.0 commit) to depend on it.

  **Compatibility:** every Adaptix producer already mints well inside the cap —
  `Adaptix-Gateway` `app/services/auth_context.py` `CONTEXT_TTL_SECONDS = 60`
  with no call site overriding it. A consumer moving to 2.36.0 rejects only
  contexts whose issued lifetime exceeds 300s, which no legitimate producer
  emits.

## [2.35.0]

### Fixed

- **A signed context carrying `Infinity`, `-Infinity` or `NaN` escaped the
  verifier's error contract as an unauthenticated 500.** Python's JSON decoder
  accepts these three constants; RFC 8259 does not define them and no Adaptix
  producer emits them. A context with `{"exp": Infinity}` therefore decoded to
  a float, and the replay-window check casts that claim:

  ```python
  int(float("inf"))  # -> OverflowError
  ```

  `OverflowError` is not a `ValueError`, so the guard around that cast did not
  catch it. It escaped `verify_gateway_signature`, passed every caller's
  `except GatewaySignatureError`, and surfaced as a **500 instead of a 401** —
  the same failure class as 2.34.0, reached by a different route.

  `NaN` was NOT part of that crash: `int(float("nan"))` raises `ValueError`,
  which the existing guard already caught correctly. It is rejected here anyway
  because `NaN` in any claim OTHER than `exp`/`iat` decodes cleanly and then
  makes every comparison against it silently return `False` — including
  equality with itself. That is the general reason the fix belongs at the
  decode boundary rather than at one cast.

  Rejected at the decode boundary via `json.loads(parse_constant=...)`, so
  these values cannot reach *any* claim rather than being defended against one
  cast at a time — the next consumer to cast a claim should not have to
  rediscover this. `OverflowError` is also added to the caught tuple at the
  cast itself, which is now unreachable but is the load-bearing conversion.

  **Found by migrating Core-Service onto this verifier**, specifically by
  writing a regression test to answer a static-analysis claim that delegation
  had dropped Core's `user_id`/`tenant_id` checks. It had not —
  `_verify_identity_claims` enforces both unconditionally on the gateway-v1 and
  gateway-v2 paths alike — but proving it empirically surfaced this. Covered by
  `tests/test_gateway_verifier_malformed_input.py` (PR #206).

  No behaviour change for legitimate traffic: every rejection added here was
  previously a crash or a silently-false comparison.

## [2.34.0]

### Fixed

- **One non-ASCII byte in a header turned a 401 into an unauthenticated 500.**
  Starlette decodes header bytes as latin-1, so a caller controls whether a
  header carries a byte above `0x7F`. Two places in the verifier crashed on
  that rather than rejecting it:

  - `hmac.compare_digest` raises `TypeError` — not a verification failure —
    when either argument is a `str` containing a non-ASCII character;
  - both schemes encode the context as ASCII, raising `UnicodeEncodeError`.

  Neither is a `GatewaySignatureError`, so both escaped the contract every
  caller relies on. A caller that catches `GatewaySignatureError` and answers
  401 instead saw a bare exception propagate, which FastAPI turns into a **500
  — on every gateway-authenticated route, from an unauthenticated request**.

  The context is now validated as ASCII once, before scheme dispatch (covering
  gateway-v1 and gateway-v2 alike), and the HMAC path validates that the
  signature is a hex digest before `compare_digest` is reached. Both produce
  the ordinary `GatewaySignatureError` → 401.

  **Found by migrating Core-Service onto this verifier.** Core had already hit
  this defect in its own verifier copy and fixed it there; the canonical
  verifier never had, so adopting it fleet-wide would have reintroduced the
  crash everywhere Core had closed it — including in services that had already
  adopted it. Covered by `tests/test_gateway_verifier_malformed_input.py`.

  No legitimate traffic is affected: a valid hex digest still verifies in
  either case, and surrounding whitespace is still tolerated.

## [2.33.0]

### Fixed

- **The module-entitlement gate was a second, unrepaired gateway verifier.**
  `auth_contracts.get_auth_context` is the well-known verifier and got the
  D-053/D-034 repair in 2.31.0.
  `auth.module_entitlement_gate._gateway_context_claims` verifies the same
  `X-Adaptix-Auth-*` headers for the 402 entitlement decision and was missed,
  so it still carried both original defects:

  - it never forwarded `X-Adaptix-Auth-Key-Id` to `verify_gateway_signature`,
    so a **gateway-v2 context could not select a public key** and was pinned to
    the legacy HMAC path;
  - it gated verification on `ADAPTIX_GATEWAY_SHARED_SECRET` alone, so a
    service holding only the public keyset — the state rollout step 3 creates
    by withdrawing the shared secret — answered **503 on every gated route**.

  Together these made the gate the component that would have broken the fleet
  by following the migration's own instructions. It now forwards the key id and
  gates on verification MATERIAL (`secret or has_verification_keys()`), matching
  `get_auth_context` exactly.

  Fail-closed posture is unchanged: a signed request that cannot be verified
  still 503s in production and still falls back to the bearer path with a
  CRITICAL log elsewhere. Covered by `tests/test_module_gate_v2_seam.py`, which
  exercises the real FastAPI dependency through a gated route; 5 of its 9 cases
  fail against the pre-fix gate.

### Documentation

- **`GatewayClaims` no longer claims to be the only context producer.** Its
  docstring said it "is the only way to mint a context under either scheme".
  The gateway has always built its own payload and always emits the full claim
  set — including `is_founder: false`, `session_jti` and `module_entitlements`,
  which `GatewayClaims` either omits when falsy or does not model at all. The
  two payload shapes are **not** interchangeable and a context minted by one is
  not byte-compatible with the other; only the signing SCHEME is shared.
  Migrating the gateway onto `GatewayClaims` would silently change the payload
  on every request and break any verifier that strict-keys the gateway shape.

## [2.32.0]

### Fixed

- **Domain error envelopes were a Liskov violation the type checker rejected.**
  `EdgeErrorEnvelope` and `QaErrorEnvelope` subclassed `AdaptixErrorEnvelope`
  and re-declared `error_code` as a wider union, so a function handed an
  `AdaptixErrorEnvelope` could receive a domain code it cannot handle. `mypy`
  reported this on `main` for both files.

  Fixed by extracting `AdaptixErrorEnvelopeBase` — every field except
  `error_code`, plus the factory helpers and `to_http_response`. Each concrete
  envelope now declares its own `error_code`, making the domain envelopes
  SIBLINGS of `AdaptixErrorEnvelope` rather than subclasses. `mypy` is clean
  across all 280 source files, down from 2 errors.

  The two obvious alternatives were rejected deliberately. Widening
  `AdaptixErrorEnvelope.error_code` would silence the checker but make **every**
  service's envelope accept Edge and QA codes at runtime — Pydantic validates
  from the annotation — which weakens validation platform-wide and inverts the
  import direction. Converting Edge and QA to the separate-field pattern the
  other seven subclasses use (`hydrant_error_code`, `mih_error_code`, …) would
  change the serialized `error_code` value on a published wire contract.

  **Behavior preserved, and verified rather than asserted.** The observable
  shape of all three classes was dumped before and after and diffed. Field set,
  required/optional state, annotations, values, factory helpers, and — the one
  that matters — which code families each class ACCEPTS and REJECTS are all
  identical. The platform envelope still refuses Edge and QA codes, which is the
  assertion that distinguishes this fix from the widening alternative.

  **One known delta:** `error_code` now serializes last rather than second,
  because it moved from the shared parent to each concrete class. JSON object
  key order is not contract for any consumer that parses the payload. Nothing
  else differs.

  These envelopes had no test coverage at all. `tests/test_error_envelope_sibling_bases.py`
  adds it, pinning validation strength in both directions.

## [2.31.0]

### Security

- **Issuer-bound asymmetric gateway trust (D-053).** The gateway's symmetric
  HMAC signing key was distributed to every verifying service, so a signature
  proved only possession of a fleet-wide secret — never gateway identity.
  Compromise of any single service yielded the ability to mint arbitrary
  contexts, including `is_founder=true`, accepted by every other service.
  Trust now rests on Ed25519: the gateway alone holds the private key
  (`ADAPTIX_GATEWAY_SIGNING_PRIVATE_KEY` + `_SIGNING_KEY_ID`); services hold
  only a public JWKS (`ADAPTIX_GATEWAY_PUBLIC_KEYS`) selected by `kid`, with
  active+previous rotation. `ADAPTIX_GATEWAY_TRUST_MODE` (`hmac` → `dual` →
  `asymmetric`) gates scheme selection; a v2 context is never verified by HMAC
  and no request header can downgrade a verifier.
- **Mandatory production audience pin (D-034).** Exact audience enforcement was
  conditional on `ADAPTIX_GATEWAY_EXPECTED_AUDIENCE` being configured, so a
  forgotten task-definition variable silently disabled cross-service replay
  protection. The pin is now required in production and fails closed at request
  time, and `assert_gateway_verifier_ready()` fails startup/readiness on missing
  keys or a missing production pin.

### Fixed

- **The gateway producer could not carry every claim the verifier consumes.**
  `GatewayClaims` is the only way to mint a signed context under either scheme,
  but its payload allowlist omitted `is_founder`, `mfa_verified` and the four
  Cortex Live demo claims added in 2.30.0. Because gateway-v2 is the only
  producer path in asymmetric mode, those claims became unmintable at
  migration: `is_founder`/`mfa_verified` degrade closed, but `is_demo` degrades
  **open** — a Cortex Live demo session would silently become an ordinary
  session, losing the demo side-effect policy that keeps it inside its leased
  tenant. Each claim is emitted only when set, so a context that does not use
  them is byte-identical to one minted before this change. `validated()` now
  mirrors the verifier's demo rules exactly (founder — by flag *or* by a
  `founder` role — rejected alongside demo; session/lease must be UUIDs;
  persona non-empty; demo detail without `is_demo` rejected) so a producer
  mistake fails at signing instead of becoming an opaque 401 storm downstream.
- **`get_auth_context` could not verify a gateway-v2 context at all.** The
  dependency every Adaptix service depends on neither accepted nor forwarded
  `X-Adaptix-Auth-Key-Id`, which `verify_gateway_signature` requires on
  gateway-v2 to select the public key by `kid`.
- **Removing the shared secret would have 503'd every migrated service.**
  Verification was gated on a shared secret existing, but a service in the
  asymmetric end-state holds only public keys. The gate now asks whether any
  verification material is present; scheme selection and trust-mode gating stay
  inside `verify_gateway_signature`. Production with a signature and no
  verification material still fails closed with 503.

### Changed — one deliberate behavior change, stated plainly

`get_auth_context` now reads and forwards `X-Adaptix-Auth-Key-Id`. This is
required — without it no gateway-v2 context can be verified at all — but it has
one observable consequence that is NOT a no-op, so it is recorded here rather
than left to be discovered:

`_is_v2_request()` treats **any** non-empty `key_id` as a claim of gateway-v2.
Previously `get_auth_context` always passed `key_id=None`, so routing depended
on `X-Adaptix-Auth-Path` alone. A legacy v1 HMAC request that carries a stray
key-id header is therefore now **rejected** (401) on an `hmac`-mode service,
where before it verified and passed.

This is deliberate and in the safe direction. Claiming v2 can only ever force
*stricter* verification, never weaker — that is the property that guarantees no
header downgrades a verifier. Verified against a real request: a v1 context with
`auth_path=gateway-v1` or `None` and no key-id still passes unchanged; only the
stray-header case changes. Nothing emits that header today — no service holds
public keys and the gateway does not sign v2 yet — so no live traffic is
affected at the time of release.

### Rollout

Ordered, and the order matters — step 3 is safe only from 2.31.0 onward:

1. Generate the keypair; private key into Secrets Manager, referenced by the
   **gateway task definition only**; publish the public JWKS fleet-wide.
2. Services move `hmac` → `dual` automatically on receiving the keyset (unset
   `ADAPTIX_GATEWAY_TRUST_MODE` resolves to `dual` when public keys are
   present, `hmac` when they are not). The gateway begins signing v2.
3. Flip services to `asymmetric`, then remove `ADAPTIX_GATEWAY_SHARED_SECRET`
   from domain-service task definitions.

**Adoption prerequisite:** every service must carry
`ADAPTIX_GATEWAY_EXPECTED_AUDIENCE` naming its own audience *before* it
upgrades to 2.31.0. The pin is mandatory in production and fails closed, and it
resolves from that environment variable only — there is no fallback source.

## [2.30.0]

### Added

- **Cortex Live demo auth context:** `AuthContext` gains backward-compatible
  `is_demo`, `demo_session_id`, `demo_lease_id`, `demo_persona` fields.
  Populated ONLY from a VERIFIED signed gateway context; the unsigned/legacy
  header path always yields non-demo defaults, so no raw header can grant
  demo status. A signed context with `is_demo=true` but malformed
  session/lease UUIDs, an empty persona, or founder privilege is rejected
  with 401 — never silently downgraded to an ordinary token.
- **`demo_contracts.DemoSideEffectClass`** (`read` / `local_demo_write` /
  `sandbox_external` / `production_external`) plus
  `demo_side_effect_allowed(...)` implementing the platform-default demo
  side-effect policy: demo sessions may read and write synthetic records in
  their leased tenant, reach provider sandboxes only when explicitly
  configured, and never trigger production-external side effects.

(Entries for 2.17.0–2.29.1 were not recorded when those versions shipped;
see git history for those releases.)

## [2.16.0]

### Fixed

- **Version monotonicity:** `pyproject.toml` had been rolled back from
  `2.15.0` to `2.12.0` by the concurrent `feat(edge)` commit
  (`cdd94b7`), which regressed the release version below already-shipped
  values (`2.13.0` MIH-CP bump, `2.14.0` Citizen bump, `2.15.0` from the
  original necessity subpackage commit `de6bdcc`). Bumped forward to
  `2.16.0` so the release version is once again monotonically ahead of
  every previously-published tag, and re-aligned this changelog header
  and the "current package version" note.

### Added — carried forward from the original 2.15.0 (necessity) entry

### Added

- **necessity subpackage (`adaptix_contracts.necessity`)** — canonical
  contracts for the **Play P02 pre-submit medical-necessity linter** that
  runs at the ePCR chart-lock boundary before a claim is dropped to the
  clearinghouse.
  - Models: `NecessityAssessment`, `NecessityFinding`, `DenialPrediction`,
    `LcdRule`, `PayerDenialPattern` — with model-level invariants
    (`verdict` must match findings; `denial_count`/`sample_size` must equal
    `historical_denial_rate`; observation-window `end` must be on or after
    `start`; monetary amounts are USD **cents** as `int`, never floats).
  - Enums: `NecessityVerdict` (`clear` / `warn` / `block`) and `MacRegion`
    (`Novitas` / `Palmetto` / `NGS` / `FirstCoast` / `WPS` / `Noridian`,
    CMS-cased so contractor directory imports drop in without a
    normalisation shim).
  - Events: `necessity.assessed`, `chart.lock.blocked`, `denial.predicted`
    registered in `adaptix_contracts.events.registry.ALL_EVENTS` with
    `source_service="epcr"` (the linter runs inside Adaptix-EPCR-Service;
    Billing subscribes to `denial.predicted` as a consumer even though the
    payload is billing-shaped). Payload models `NecessityAssessedEvent`,
    `ChartLockBlockedEvent`, `DenialPredictedEvent` pin `event_type` with a
    `Literal[...]` so a wrong-typed emission fails validation at the
    producer, not at the consumer.
  - Tests: `tests/test_necessity_contracts.py` covers enum values, the
    verdict/findings invariant, the denial-arithmetic invariants, the
    registry wiring for all three event types, and the subpackage export
    surface.

## [2.10.0]

### Deprecated (import path preserved, fully functional; emits `DeprecationWarning` on instantiation)

- **docuseal_contracts:** `DocuSealPackageCreateRequest`, `DocuSealPackageResponse`
  are non-canonical and deprecated. **TrustSign is the only active AdaptixCore
  electronic-signature authority** — this is platform law, independently
  enforced in Adaptix-Governance (`registries/providers.yml` `trustsign`
  entry), Adaptix-Gateway (`README.md` "Does NOT own": *"TrustSign is the
  only AdaptixCore e-signature system. Do not treat Dropbox Sign or DocuSeal
  as the live signer"*), and Adaptix-Billing-Service
  (`TRUSTSIGN_BUILD_DIRECTIVE.md`, AST-enforced by
  `test_signature_provider_authority.py`). Codified in this repo for the
  first time as the README "Canonical signature provider" section (this
  law previously lived only in Adaptix-Gateway's README).
  - These two models were added in 1.5.0 (#94) alongside the other
    service-separation contracts (`cortex_contracts`, `trustsign_contracts`,
    `sagemaker_contracts`, `gateway_contracts`) and were never adopted.
  - **Non-breaking. Zero consumer action required.** Re-verified 2026-08-16
    (not merely re-trusting the prior 3-day-old discovery): repo-wide grep
    of this package, an org-wide GitHub code search across every
    FusionEMS-Quantum-LLC repo, and a direct clone-and-grep spot check of 8
    repos (`Adaptix-DocuSeal-Service`, `Adaptix-TrustSign-Service`,
    `Adaptix-Gateway`, `Adaptix-Billing-Service`, `Adaptix-CAD-Service`,
    `Adaptix-Core-Service`, `Adaptix-Partner-Service`,
    `Adaptix-EPCR-Service`) all found **zero** imports of
    `docuseal_contracts`, `DocuSealPackageCreateRequest`, or
    `DocuSealPackageResponse`. Notably, the standalone
    `Adaptix-DocuSeal-Service` does not consume these contracts either — it
    defines and uses its own local `backend/app/schemas/docuseal_package.py`.
  - Per `DEPRECATION_POLICY.md`: the import path is preserved, both models
    remain fully functional and exported through `schemas.__all__` and the
    package root (no API-surface removal — this is an announcement, not a
    breaking change), and a `DeprecationWarning` now fires on
    **instantiation** of either model (not on import — `docuseal_contracts`
    is eagerly imported by `adaptix_contracts.schemas`, so a module-level
    warning would have fired for all 26 pinned consumer repos on every
    `import adaptix_contracts` regardless of whether they use DocuSeal;
    instantiation-time warning via `model_post_init` only fires for the
    (currently zero) real callers). Replacement:
    `trustsign_contracts.SignaturePackageCreateRequest` /
    `SignaturePackageResponse`. Removal is deferred to the next major
    version (3.0.0), per policy, coordinated through the consumer bump
    matrix at removal time.
  - Regression coverage added: `tests/test_deprecated_docuseal_contracts.py`
    pins the warning, proves the legacy shape still validates during the
    overlap period, and proves the canonical TrustSign surface (and the
    normal package import path) stay warning-free.

## [2.9.0]

### Added — canonical billing-vendor migration contracts

New module `adaptix_contracts/schemas/migration_contracts.py` (+36 public
exports: 23 models, 6 enums, 3 constants, 3 field-type aliases, 1 pure
function). Purely additive; no existing symbol changed, renamed, or removed.

The migration subsystem in `Adaptix-Billing-Service` is real and running, but at
`origin/main` (read 2026-08-16) it defines **zero `Enum` classes** and carries
five mutually disjoint bare-string status vocabularies —
`BillingMigrationJob.status`
(`backend/billing_app/services/migration/migration_service.py:31`, dict keys
only), `MigrationIntake.status` and `ImportBatch.status`
(`backend/billing_app/models/migration_imports.py:30, :48`),
`CommercialInquiry` "migration" status (declared nowhere, hardcoded in
`backend/billing_app/api/migration.py:150`), and `CortexWhispererRun.status`
(`backend/billing_app/models/migration_whisperer.py:29`) — plus three
orthogonal axes (`mapping_state`, `commit_status`, `cortex_status`). None of
those legacy vocabularies is removed or renamed here; they remain their own
tables' persisted values. This module adds the canonical cross-service
vocabulary they map onto.

Added surface:

- `MigrationState` (26 states), `MigrationEraState` (16), plus
  `MIGRATION_STATE_TRANSITIONS` (a `frozenset` of legal successors per state),
  `MIGRATION_TERMINAL_STATES`, and the pure guard
  `is_legal_migration_transition(current, target) -> bool`. Guarded transitions
  are a contract requirement: at
  `backend/billing_app/api/migration_intelligence_routes.py:715` the live commit
  endpoint assigns `job.status = "completed"` on a job created at `"pending"`
  (`:192`) — an illegal jump under that service's own `_VALID_TRANSITIONS`,
  whose guard `update_migration_status`
  (`services/migration/migration_service.py:65`) has **zero callers**. A UI
  button must never be able to advance state. The guard fails CLOSED on any
  unrecognized value and rejects self-transitions. The 26-state edge set is
  canonically defined in this module; no prior machine-readable definition
  existed in the workspace.
- `MappingDecisionLevel`, `MigrationExceptionCategory`,
  `MigrationReconciliationStatus` (prefixed because `ReconciliationStatus` is
  already the finance domain's), and `MigrationErrorCode` (23 codes incl.
  `stedi_*`, `sagemaker_unavailable`, `model_guardrail`, `temporal_delayed`,
  `database_transient`/`_permanent`, `object_store`, `queue_dlq`,
  `internal_invariant`) with the `MigrationError` model carrying `code`,
  `retryable` (defaults `False` so an unclassified failure is never retried),
  `user_safe_message`, `operator_diagnostic`, and `correlation_id`. This is the
  replacement for free-text `row.commit_error = f"{type(exc).__name__}: {exc}"`
  (`api/migration_intelligence_routes.py:621, 664, 709`), which cannot be
  counted, alerted on, or retried by class. It is deliberately NOT merged into
  `error_contracts.ErrorCode`, which is the HTTP-envelope vocabulary.
- Records: `MigrationSourceFile`, `SourceSchemaFingerprint`, `VendorProfileRef`,
  `FieldMappingProposal`, `ReconciliationControl`, `ReconciliationRunResult`,
  `MigrationExceptionGroup`, `CutoverWatermark`, `MigrationSignoff`. Each is
  tenant-scoped (`tenant_id` required), stamped with `schema_version`, and
  carries `correlation_id` plus a `record_version` for the optimistic-concurrency
  conflict `MigrationErrorCode.OPTIMISTIC_CONFLICT` reports.
- Events: `MigrationCreated`, `SourceRegistered`, `SourceFileLanded`,
  `SourceProfiled`, `MappingProposed`, `MappingApproved`, `DryRunCompleted`,
  `MigrationExceptionRaised`, `ReconciliationCompleted`, `CutoverApproved`,
  `OpenARActivated`, `MigrationCompleted`, `MigrationRolledBack`. `tenant_id` is
  REQUIRED on every one (the Core relay refuses tenant-less events); every other
  field is optional so a producer that has not yet collected a fact emits a
  valid event instead of raising inside a consumer's `except` — the exact defect
  recorded for `epcr.chart.finalized` in 2.5.0 above.

Money is **signed integer cents declared `strict`**, so a float is rejected
rather than coerced — `100.0` is refused as firmly as `100.5`, because a lax
`int` field accepts a zero-fraction float and that is how a rounding defect
enters a financial migration unnoticed. This matches the persisted reality:
every money column on the migration path is `BigInteger` cents
(`models/migration_staging.py:80-82, 132-133, 189`;
`models/migration_imports.py:134`) with no `Numeric` and no `Float`.
`difference_cents` is deliberately unconstrained in sign — production below
source is the direction that loses an agency money and must be representable.
`VendorProfileRef.vendor` reuses the existing `MigrationSourceVendor` enum
rather than duplicating it; Stedi remains the only live clearinghouse.

No field, default, docstring, or example carries PHI. Operator-facing sample
fields are named `*_masked_*` and are contractually required to be redacted by
the producer before publication.

**Not yet on the event bus.** At `origin/main` the migration subsystem publishes
nothing to the Adaptix bus: its `event_type` strings are written to
`billing_migration_audit_events` rows via the local `_audit_migration_event`
helper (`api/migration_intelligence_routes.py:128`), and no migration module
imports `EventSchema`/`EventMetadata`. These event types are therefore **not**
registered in `adaptix_contracts.events.registry.ALL_EVENTS`, and publishing one
through the operational envelope will fail `assert_event_type_registered` until
registration lands with a real producer file citation. Registration is
deliberately deferred: the registry requires evidence of a live publisher.
`MigrationCreated.event_type` reuses the live audit value `"migration.created"`
(`api/migration_intelligence_routes.py:201`) because it marks the same act.

Producers: `Adaptix-Billing-Service` migration subsystem and
`Adaptix-Imports-Service` (source ingest/profiling). Consumers: the Billing
migration cockpit in `Adaptix-Web-App`, `Adaptix-Audit-Service` for the evidence
trail, and `Adaptix-Finance-Service` for AR continuity. Tests:
`tests/test_migration_contracts.py` (202 cases) pins enum round-trips, transition
legality in both directions, graph integrity (every state keyed, every target
real, terminals empty, no self-edges, every state reachable from `DRAFT`,
rollback unreachable before cutover), float rejection on all 14 money fields, and
`tenant_id` on all 13 events.

### Changed — the legacy shared-queue hard break moved to `3.0.0`

`EventBusPublisherClient.LEGACY_SHARED_QUEUE_REMOVAL_VERSION` said `"2.9.0"`,
and `README.md` plus `event_consumers.py` promised the omitted-consumer hard
break would land in that release. It did **not** land in 2.9.0, and it should
not have been targeted there: rejecting a previously accepted call narrows
accepted values, which `DEPRECATION_POLICY.md` reserves for a **major** release.
The constant and both prose sites now name `3.0.0`. No behavior changed —
omitting `consumer` still works and still emits `FutureWarning`.

## [2.8.0]

### Added — `EpcrBillingSnapshot` transport, insurance, and certification blocks

`EpcrBillingSnapshot` gains three OPTIONAL sub-models (additive, minor-safe;
legacy payloads without them still validate):

- `EpcrBillingTransportBlock` (`snapshot.transport`) — origin/destination/
  mileage/service-type facts the EPCR producer has ALWAYS emitted under the
  snapshot's `"transport"` key (`ChartBillingReadinessExport`,
  `chart_finalization_service.py` `_collect_billing_snapshot`). The field was
  missing from the typed model, so `model_validate` silently discarded it and
  Billing never received origin, destination, or transport distance — the
  facts required to price and modifier-code a ground transport claim. Raw
  NEMSIS strings; `transport_distance_miles` is deliberately NOT coerced.
- `EpcrBillingInsuranceBlock` (`snapshot.insurance`) — NEMSIS ePayment.09–.22
  / .57–.60 payer + subscriber facts persisted in `epcr_chart_payment`.
  Absence means undocumented, never "uninsured", and never verified coverage.
- `EpcrBillingCertificationBlock` (`snapshot.certification`) — ePayment PCS /
  medical-necessity / prior-authorization facts (ePayment.02–.07, .44–.54)
  that gate non-emergency submission under 42 CFR 410.40(e).

Producers: Adaptix-EPCR-Service (emits `transport` today; `insurance` and
`certification` from its 2.8.0-aligned export). Consumer:
Adaptix-Billing-Service `EpcrEventConsumer`. Tests:
`tests/test_epcr_finalized_billing_snapshot.py` pins legacy-shape
compatibility and the exact producer shapes.

## [2.5.0]

### Fixed — `epcr.chart.finalized` rejected every payload its producer sends

`EpcrChartFinalizedEvent` declared `is_nemsis_compliant: bool` with no default.
The authoritative producer,
`Adaptix-EPCR-Service/backend/epcr_app/chart_finalization_service.py:260`
(origin/main, read 2026-08-09), writes a payload of exactly
`chart_id, tenant_id, call_number, finalized_at, billing_case_id, record_mode` —
and the string `is_nemsis_compliant` occurs nowhere in that service.

The sole consumer,
`Adaptix-Billing-Service/backend/billing_app/event_consumers.py:69`, calls
`EpcrChartFinalizedEvent.model_validate(payload)` inside a `try` whose `except`
logs and returns `False`. Every real chart finalization therefore raised
`ValidationError` and produced **no claim-intake row, no patient financial
account and no draft claim**, while the chart still showed finalized to the
crew. The identical `ValidationError` is recorded verbatim in the archived
`Adaptix-Core-Service/PHASE_11_VALIDATION_RESULTS.json`.

Every fixture for this event supplied the field, which is why the suites stayed
green. `tests/test_epcr_chart_finalized_producer_payload.py` now validates the
producer's key set verbatim; 4 of its 12 tests fail against the old contract.

The field is now `Optional[bool] = None`, deliberately tri-state rather than
defaulted to a bool: an absent value is not evidence of compliance and not
evidence of non-compliance. A consumer that gates on compliance must treat
`None` as unknown and read `EpcrNemsissComplianceContract` instead. No code in
the workspace reads `is_nemsis_compliant` today (verified by fleet-wide grep),
so widening it breaks no reader.

Taking this into the running Billing service requires that repo to bump its
pinned `adaptix-contracts` commit (currently `8465ddf`, which carries the
required-field version) and redeploy.

## [2.4.0]

### Fixed — 30 more live event types were invisible to the producer audit

The 2.3.0 audit only resolved a **literal** `event_type=` written directly on a
shared-envelope construction. Adaptix producers routinely do neither: they write
an outbox row that a worker later republishes with the row's own `event_type`,
or they call a thin publish wrapper. Both shapes put a variable at the envelope
construction site, so the scanner walked straight past them and reported PASS.

`scripts/audit_event_producer_drift.py` now also resolves module-level string
constants, both branches of a conditional, every value a function-local can
hold, calls through an envelope-forwarding wrapper (bare, `Class.helper(...)`
and `self.helper(...)`), and rows written to a **declared outbox relay** — each
relay listed with the exact `file:line` of the worker that proves it. Resolved
production emission sites went from 38 to 74, exposing **30 unregistered event
types** that reach cross-service consumers today:

- via `ChartEventOutbox` → `Adaptix-EPCR-Service/backend/epcr_app/outbox_worker.py:99`
  (`source_service="epcr"`): `epcr.chart.amended`, `epcr.chart.billing_handoff`,
  `epcr.nemsis_submit.failed`, `epcr.nemsis_submit.succeeded`, the six
  `caregraph.*`, the six `cpae.*` and the seven `vas.*` events
- via the vision-capture publish wrapper
  (`chart_vision_capture_service.py:728`, `source_service="epcr"`): the five
  `epcr.vision.*` events and `hospital.cath_lab.activate_recommended`
- via `OutboxEvent` →
  `Adaptix-Patient-Identity-Service/.../outbox_worker.py:88`:
  `patient.identity.merged`

All 30 are registered with the `source_service` their producer actually stamps
and an in-source producing `file:line` citation, enforced by
`INDIRECT_ENVELOPE_PRODUCERS` in `tests/test_event_producer_registry_drift.py`.
Registry size: 85 → 115 event types.

### Fixed — a live producer's `source_service` resolved to no service

`Adaptix-Patient-Identity-Service/.../outbox_worker.py:88` stamps
`source_service="patient_identity"` (underscore), but the service-registry slug
is `patient-identity` (hyphen), so `resolve_source_service()` returned `None`
and `producer_of()` would have raised for every event that service publishes.
New `PRODUCER_SOURCE_SERVICE_ALIASES` maps the live spelling to the canonical
slug. It is deliberately separate from `LEGACY_SOURCE_SERVICE_ALIASES`: a legacy
alias still reports as drift (a producer emitting a superseded string is worth
surfacing), a live-producer alias does not.

### Fixed — the test suite could validate an installed copy, not this checkout

`tests/` has no `__init__.py` and `pyproject.toml` set no `pythonpath`, so
running the repo's own gate (`scripts/local-ci.sh python pr`, which invokes the
`pytest` console script) under an interpreter with an older `adaptix-contracts`
in site-packages imported THAT package. The suite then measured code that is not
in the working tree — green while the source is broken, red while it is correct.
`pythonpath = ["."]` now pins resolution to the checkout, and
`tests/test_suite_tests_this_checkout.py` fails if the setting is removed.

### Known limits (unchanged)

Neither the audit nor these tests validate event PAYLOAD shape. Both shared
envelopes carry `payload: dict[str, Any]`, so producer/consumer payload
compatibility remains unguarded by contract. A fully dynamic re-publisher such
as `Adaptix-Audit-Service/backend/audit_app/events/publisher.py:67` also stays
out of scope by design — its caller chooses the event type.

## [2.3.0]

### Fixed — event registry was out of sync with its live producers

`events/registry.ALL_EVENTS` is the allow-list behind `is_registered()` and
`events/operational_envelope.assert_event_type_registered()`. A workspace audit
(`scripts/audit_event_producer_drift.py`, run 2026-08-09 across 92 sibling
repos) found 38 production sites constructing a shared contract envelope with a
literal `event_type`, of which **18 event types were unregistered** — so the
allow-list returned `False` for real production traffic:

- `billing.claim.created`, `billing.claim.status_changed`,
  `billing.payment.received`, `billing.invoice.created`, `billing.invoice.paid`,
  `billing.call_context.assembled`, `trustsign.document.signed`
  (producer: Adaptix-Billing-Service, slug `billing`)
- `epcr.chart.created`, `.finalized`, `.signed`, `.locked`, `.unlocked`,
  `.nemsis_validation_completed`, `.nemsis_export_completed`
  (producer: Adaptix-EPCR-Service, slug `epcr`)
- `fire.incident.completed`, `fire.incident.closed`, `fire.unit.dispatched`,
  `fire.incident.status_changed` (producer: Adaptix-Fire-Service, slug `fire`)

All 18 are now registered with the `source_service` their producer actually
stamps. Each carries its producing `file:line` at origin/main as an in-source
citation, enforced by `tests/test_event_producer_registry_drift.py`.

`fire.incident.status_changed` is registered ALONGSIDE the pre-existing
`fire.incident.status.updated`; they are distinct strings and only the former
has a producer. Collapsing them is a Fire-domain decision, so both remain and
the divergence is documented in `events/registry.py`.

### Changed — `source_service` is one vocabulary: the service-registry slug

64 of the 67 previously registered events stamped `source_service` values
(`adaptix-fire`, `adaptix-neris`, `adaptix-scheduling`) that are **not**
`schemas.service_registry.SERVICE_BY_SLUG` keys, while the live producers stamp
the slug (`Adaptix-Fire-Service/backend/fire_app/services/event_publisher.py:41`
emits `source_service="fire"`). The only reconciliation lived in a private
helper inside `tests/test_scheduling_service_registration.py`, so no consumer
could perform it. All entries now use the slug, matching both the producers and
the `source_service` semantics `events/operational_envelope.py` already
documented. `adaptix-fire` / `adaptix-neris` remain valid JWT audiences in
`service_audiences` and ECS service names in `platform/ownership_manifest.json`
— those are separate namespaces and are unchanged.

### Added — shipped producer resolution and drift detection

- `events.registry.resolve_source_service(source_service)` and
  `events.registry.producer_of(event_type)` return the `ServiceDefinition` for
  an event's producer. `producer_of` raises `KeyError` on an unregistered type
  rather than guessing.
- `events.registry.LEGACY_SOURCE_SERVICE_ALIASES` keeps the previously published
  `adaptix-`-prefixed strings resolvable for persisted event rows, EventBridge
  archive replays, and consumers pinned to an older `adaptix-contracts`.
- `scripts/audit_event_producer_drift.py` — reusable polyrepo audit that AST-parses
  every shared-envelope construction and reports `UNREGISTERED`,
  `SOURCE_SERVICE_MISMATCH` and `UNRESOLVED_SOURCE_SERVICE`. Exit 0 clean, 1 on
  drift, 2 on misuse; `--json` for machine consumption.
- `tests/test_audit_event_producer_drift.py` validates the detector against a
  known-good control plus one fixture per defect class, and asserts its
  documented blind spots (dynamic `event_type`, test files) so they cannot be
  mistaken for coverage.

Limitation, stated explicitly: none of this validates event PAYLOAD shape. Both
envelopes carry `payload: dict[str, Any]`, so payload compatibility between a
producer and a consumer remains unguarded by contract.

## [Unreleased]

### Changed

- Clarified current automation authority: GitHub Actions in this repo remain
  analysis-only (`CodeQL`, `Codacy`) while CodeBuild owns authoritative
  main/release validation and any publication/deploy path.
- Release note for downstream consumers of
  `adaptix_contracts.gateway_signature.verify_gateway_signature`: signed
  payloads now require an `aud` claim naming the target Adaptix service, and
  test fixtures that build synthetic signed payloads must include the same
  claim (for example, CAD discovered this while updating to the new
  `EventBusPublisherClient` consumer API in PR #285).
- `EventBusPublisherClient.get_pending_events_unfiltered`,
  `.mark_delivered`, and `.mark_failed` now emit a `FutureWarning` when
  called with `consumer=None`, so the remaining legacy shared-queue path fails
  loudly during the 2.8.0 rollout instead of silently preserving the unsafe
  behavior.
- Blank consumer names now raise `ValueError` instead of being treated like the
  legacy omitted-consumer path.

### Added — canonical event-bus consumer registry

- Added `adaptix_contracts.event_consumers` as the single import surface for the
  current audited Core fan-out consumer names:
  `BILLING_SERVICE_CONSUMER`, `CAD_SERVICE_CONSUMER`,
  `EPCR_SERVICE_CONSUMER`, and `HOSPITAL_SERVICE_CONSUMER`.
- Re-exported those constants from `adaptix_contracts.event_contracts` and the
  package root for downstream callers already anchored on the event client
  module.
- Documented the hard-break follow-up now: once the Hospital migration lands,
  `adaptix-contracts` 2.9.0 will reject omitted consumer names instead of
  warning.

### Added — EPCR submission event typing

- Added `EpcrNemsisSubmitSucceededEvent` for the producer-owned
  `epcr.nemsis_submit.succeeded` outbox payload emitted by
  `Adaptix-EPCR-Service/backend/epcr_app/chart_finalization_service.py`.
- Exported the new typed schema from `adaptix_contracts.schemas` and added
  regression coverage that pins the exact required producer fields.

### Added — canonical signup application-creation contract

- Added SignupApplicationCreateRequest and SignupApplicationCreateResponse for
  POST /api/v1/signup/applications.
- Made application_id the canonical response identifier while retaining id as
  a required, equality-checked compatibility alias for rolling Web/Core
  deployment.
- Added the constrained SignupIdempotencyKey type and canonical
  Idempotency-Key header constant. Exact retries reuse the same opaque key;
  conflicting payload reuse is rejected by the producer.
- Added regression coverage for schema generation, additive response fields,
  identifier equality, and idempotency-key validation.

### Added — Canonical product/module identifier registry (`adaptix_contracts.module_registry`)

Single source of truth for Adaptix module ids. Five vocabularies for the same
products had drifted while the runtime entitlement gate does exact normalized
string matching, so a tenant could pay for a module and still be denied it
(e.g. Core `signup_pricing.py` sells `billing_automation`, but
`Adaptix-Billing-Service/backend/billing_app/main.py:968` gates on `billing`).

- `ModuleDefinition` — canonical id, display name, `aliases` (exact synonyms of
  the same product), `implies` (a purchase that additionally grants a different
  module), `purchasable`, `audience`, and a `source` citation per entry.
- `MODULE_REGISTRY` / `ALIAS_INDEX` / `RUNTIME_GATE_SLUGS` — validated at import
  time (no duplicate canonical ids, no alias shadowing a canonical id, no
  dangling or self-referential `implies`, every live gate slug canonical).
- `resolve_module_id`, `require_module_id`, `expand_entitlements`,
  `is_module_entitled`, `is_any_module_entitled`, `normalize_module_id`,
  `canonical_module_ids`, `purchasable_module_ids`.

Canonical ids are the slugs the runtime already enforces — nothing
customer-visible is renamed. Resolution is strictly additive: `expand_entitlements`
returns the caller's own normalized ids plus canonical plus implied, and passes
unregistered ids through untouched, so anything entitled today stays entitled.

Covered by `tests/test_module_registry.py` (140 tests), which proves
purchased => allowed and unpurchased => denied for every purchasable module id
and every one of its sold spellings.

### Added — Billing clearinghouse: Stedi webhook + retry-eligibility + operator-fallback (additive only)

Closes cross-repo contract drift from the merged billing/Stedi work by adding
the request/response/enum contracts for three real endpoints in
`Adaptix-Billing-Service`. Every model mirrors the service source exactly;
paths, status codes, and value sets are cited in-line in
`adaptix_contracts/schemas/billing_clearinghouse_contracts.py`.

- **`POST /api/v1/billing/webhooks/stedi`** (service source
  `backend/billing_app/api/webhooks_stedi.py`, commit `9ba5c6e2`, PR #541):
  - `StediWebhookEventType` — KNOWN `detail-type` set
    (`transaction.processed.v2`, `file.delivered.v2`, `file.failed.v2`).
  - `StediWebhookRequest` — EventBridge-shaped inbound envelope (`id` required,
    `detail-type` read, extra fields persisted verbatim). Bearer auth is
    out-of-band, not a body field.
  - `StediWebhookAcceptedResponse` (202 new), `StediWebhookDuplicateResponse`
    (202 idempotent duplicate), `StediWebhookRejectedResponse`
    (400/401/413/503, `status`+`reason`).
- **`GET /api/v1/billing/clearinghouse/claims/{claim_id}/retry-eligibility`** and
  **`POST /api/v1/billing/clearinghouse/claims/{claim_id}/operator-fallback`**
  (service source `backend/billing_app/api/clearinghouse_router_routes.py`,
  commit `9dc57abf`, PR #539; value sets from `clearinghouse/base.py` and
  `clearinghouse/router.py`). Both require `founder`/`billing_admin` role +
  `billing` entitlement and are tenant-scoped.
  - `ClaimTransmissionState` (`not_transmitted`/`unknown`/`transmitted`),
    `ClaimRetryReasonCode`
    (`no_prior_attempt`/`proven_not_transmitted`/`already_accepted`/`unknown_transmission`),
    `ClaimRetryEligibilityResponse`.
  - `ClaimOperatorFallbackRequest` (with source field constraints),
    `ClaimOperatorFallbackResponse`, `OperatorFallbackRefusedReasonCode`
    (six 409 codes), `ClaimOperatorFallbackRefusedError` (409 detail),
    `ClaimOperatorFallbackTargetFailedError` (503 detail).
- **Note (observed, not changed):** these service routes return status+reason
  bodies and FastAPI `{"detail": ...}` payloads rather than the repo's
  `common/error_envelope.py::ErrorEnvelope`. Recorded here as a known
  cross-repo error-envelope divergence for follow-up; no service behavior was
  altered by this contracts change.

### Added — `SCHEDULING_SERVICE` registration (additive only)

Phase 1 of the Workforce Scheduling directive, driven by
`SCHEDULING_ARCHITECTURE_LOCK.md` section 3.3 (Adaptix-Governance).

- **`adaptix_contracts.schemas.service_registry.SCHEDULING_SERVICE`** — new
  `ServiceDefinition` (name `Adaptix-Scheduling-Service`, slug `scheduling`,
  route_prefix `/api/v1/scheduling`, port `8046`), appended to `ALL_SERVICES` and
  therefore present in `SERVICE_BY_SLUG`. Closes the gap where 27 `schedule.*`
  events in `events/registry.py:128-131` declared
  `source_service="adaptix-scheduling"` with no service to resolve to.
  **Runtime reality:** `/api/v1/scheduling` is currently proxied to Labor-Service
  (`Adaptix-Gateway/backend/app/config/routes.py:1830-1842`, audience
  `adaptix-labor`). No `Adaptix-Scheduling-Service` repository or ECS service
  exists. This entry declares contract-level ownership only.
- **`adaptix_contracts/platform/ownership_manifest.json`** — new `scheduling`
  entry with `api_prefixes: ["/api/v1/scheduling"]` and all 27 `schedule.*`
  events in `owned_events`; `status: "declared_not_deployed"` with the runtime
  caveat recorded in `notes`.
- **`adaptix_contracts.scheduling.ai.FatigueRiskScore`** — gains optional
  `risk_factors: list[str] = []`, `ai_generated: bool = False` and
  `supervisor_review_flag: bool = False`, carried over from
  `workforce.models.FatigueAssessment:49-54`. All optional with safe defaults, so
  existing producers and payloads are unaffected.
- **Canonical re-exports.** `adaptix_contracts.scheduling.models` symbols are now
  importable from the three duplicate modules so callers can adopt the
  single-truth names before the shapes move:
  `schemas/workforce_contracts.py` re-exports `ShiftInstance`, `ShiftAssignment`,
  `AvailabilityWindow`, `TimeOffRequest`, `RiskLevel` (plus
  `Canonical{Shift,Assignment,TimeOff}Status`); `schemas/labor_contracts.py`
  re-exports `ShiftInstance`, `ShiftAssignment`, `ShiftSwapRequest`,
  `TimeOffRequest`, `RiskLevel` (plus `Canonical{Shift,Assignment,TimeOff,Swap}Status`);
  `workforce/models.py` re-exports `RiskLevel`.
- **Machine-readable deprecation maps.** `DEPRECATED_MODEL_REPLACEMENTS` /
  `DEPRECATED_ENUM_REPLACEMENTS` (workforce_contracts, labor_contracts),
  `DEPRECATED_REPLACEMENTS` (workforce/models), and `PAYROLL_ONLY_SURFACE`
  (labor_contracts, naming the payroll surface that deliberately stays put).
- **Tests** — `tests/test_scheduling_service_registration.py` (19 tests):
  every `source_service` in `ALL_EVENTS` resolves to a registered
  `ServiceDefinition`; `service_registry` route prefixes match
  `ownership_manifest` `api_prefixes` per slug; deprecated names and their
  canonical replacements both resolve; legacy enum value sets are frozen.

### Fixed — stale `narcotics` api_prefix in the ownership manifest

`ownership_manifest.json` listed only the singular `/api/v1/narcotic`. The
gateway boundary-matches the **plural** `/api/v1/narcotics`
(`Adaptix-Gateway/backend/app/config/routes.py:1849`), which is precisely why
`Adaptix-Narcotics-Service/backend/core_app/main.py:40-62` aliases every singular
router onto the plural namespace. `api_prefixes` is now
`["/api/v1/narcotics", "/api/v1/narcotic"]` — plural first as the canonical
externally routable prefix, singular retained because the service still serves
it natively. No code change; manifest data only.

### Known drift — recorded, not papered over

- **`crew`** — `CREW_SERVICE` (slug `crew`, `/api/v1/crew`) has **no**
  `ownership_manifest.json` entry. The nearest entry, `crewlink`, declares
  `/api/v1/crewlink` and `canonical_repo: Adaptix-Crew-Service`, but the gateway
  routes `/api/v1/crewlink` to **CAD-Service** and comments that the
  `adaptix-crewlink` upstream "has no ECS service backing it"
  (`routes.py:1438-1460`), while `/api/v1/crew` is a separate live route to
  `crew_service_url` (`routes.py:1788-1793`). Correct repo / ECS service /
  schema for a `crew` entry, and the crewlink ownership contradiction, are not
  derivable from this repository. Tracked by an `xfail(strict=True)` test that
  will fail the moment it is fixed, forcing the marker's removal.
- **33 registered slugs have no manifest entry** (`crew`, `transport`,
  `telephony`, `labor`, and 29 newer domain services). Frozen in
  `_SLUGS_WITHOUT_MANIFEST_ENTRY` so the gap cannot grow silently.

### BLOCKED — the model/enum consolidation itself is a major-version change

`SCHEDULING_ARCHITECTURE_LOCK.md` section 3.3 calls for deleting the duplicate
models/enums in `schemas/workforce_contracts.py`, `schemas/labor_contracts.py`
and `workforce/models.py` and re-exporting `scheduling.models` in their place.
**Not shipped.** Re-exporting preserves the *import path* but not the *shape*, and
these shapes are not interchangeable. Under this repository's own
`DEPRECATION_POLICY.md` ("Major releases are required for removing fields,
renaming fields, changing field meaning, narrowing accepted values, or deleting
enum members") every substitution below requires a major release plus a
downstream data migration:

| Legacy | Canonical | Incompatibility |
| --- | --- | --- |
| `workforce_contracts.FatigueLevel` | `RiskLevel` | deletes `none`, `moderate`; adds `medium` |
| `workforce.models.FatigueRiskLevel` | `RiskLevel` | deletes `moderate`; adds `medium` |
| `workforce_contracts.ShiftStatus` | `ShiftStatus` | deletes `draft`, `published`, `in_progress` |
| `labor_contracts.ShiftStatus` | `ShiftStatus` | deletes `draft`, `published`, `locked`, `in_progress` |
| `labor_contracts.AssignmentStatus` | `AssignmentStatus` | deletes `overridden` |
| `labor_contracts.TradeStatus` | `SwapStatus` | deletes `proposed`, `accepted`, `completed` |
| `WorkforceShiftContract` | `ShiftInstance` | drops `name`, `location`; adds 4 required fields |
| `WorkforceShiftAssignmentContract` | `ShiftAssignment` | `user_id`→`person_id`; drops `role`; adds 4 required fields |
| `WorkforceAvailabilityContract` | `AvailabilityWindow` | recurring `day_of_week`+`time` cannot be expressed as an absolute `datetime` window |
| `WorkforceTimeOffContract` | `TimeOffRequest` | `user_id`→`person_id`; `date`→`datetime`; adds 2 required fields |
| `LaborShiftContract` | `ShiftInstance` | `str`→`UUID` ids; `"HH:MM"` str→`datetime` |
| `LaborAssignmentContract` | `ShiftAssignment` | `str`→`UUID` ids; drops `slot_id`, `override_reason` |

`WorkforceReadinessContract` and `LaborEmployeeReadinessContract` have **no**
canonical counterpart in `scheduling/models.py` and cannot be re-pointed at all.

Every legacy name is therefore retained and marked deprecated in code, with the
canonical target recorded in the machine-readable maps above. Unblocking
requires a founder decision on a `3.0.0` major release plus a coordinated
downstream migration.

## [2.1.0] - 2026-07-14

### Added — Telephony platform contracts (additive only)

New shared module `adaptix_contracts.schemas.telephony_contracts` so
`Adaptix-Telephony-Service`, `Adaptix-Web-App`, and `Adaptix-Founder-Service`
agree on the provider-agnostic telephony wire shapes and realtime event types.

- **Enums:** `DestinationType` (user/team/queue/department/workspace/
  cortex_agent/voicemail_box/external_number/on_call_policy), `CallStatus`
  (new/ringing/ai_active/queued/offered/answered/on_hold/transferring/voicemail/
  completed/abandoned/failed), `VoicemailStatus` (new/unread/listened/in_review/
  assigned/callback_required/callback_completed/archived/deleted/
  failed_processing), `QueueStatus` (open/closed/paused/degraded).
- **Realtime event-type constants:** `TelephonyEventType` covering
  `telephony.call.{ringing,offered,answered,held,resumed,transferred,completed,
  failed}`, `telephony.voicemail.{created,transcribed,processing_failed}`,
  `telephony.queue.updated`, and `telephony.presence.updated`.
- **Entity contracts:** `Call`, `Voicemail`, `Queue`, `UserPresence` (each
  `from_attributes=True`), matching the directive field lists.
- **Why minor:** Purely additive new module + exports; no existing contract
  changed. Existing provider-specific `telnyx_contracts` are untouched and map
  INTO these platform shapes. Consumers opt in by re-pinning `>=2.1.0`.
- **Surface:** All nine symbols re-exported from `adaptix_contracts.schemas`
  and the package root; `__version__` and `pyproject.toml` bumped to `2.1.0`.

## [2.0.0] - 2026-07-12

### Removed — BREAKING: `TransactionSource.PLAID` enum member

Founder decision: Plaid is removed from the platform and replaced by SimpleFIN
as the bank-feed ingestion provider. The `PLAID = "plaid"` member of
`adaptix_contracts.schemas.finance_contracts.TransactionSource` is deleted.

- **Enum:** `TransactionSource` now accepts only `CSV`, `MANUAL`, `STRIPE`.
- **Why major:** Per `DEPRECATION_POLICY.md`, deleting an enum member requires a
  major release, even though a workspace-wide consumer scan found **zero** code
  consumers of this Contracts member. (`Adaptix-Finance-Service` defines its own
  separate local `TransactionSource` enum in
  `finance_app/ledger_v2/schemas.py` and does not import this one; the Web-App
  `TransactionSource` is an independent hand-maintained TypeScript literal type.
  None of these are affected by this removal.)
- **Replacement path:** A SimpleFIN-backed transaction source is the founder-
  designated replacement. It is intentionally **not** added in this release —
  introducing a new `SIMPLEFIN` member is a separate additive (minor) change to
  be coordinated with the Finance/SimpleFIN ingestion work.
- **Downstream:** Consumers pinning `adaptix-contracts` must re-pin to `>=2.0.0`
  to pick up this change. No consumer code changes are required, because the
  removed member had no importers of this contract.

## [1.6.0] - 2026-07-09

### Added — ACIN (AdaptixCore Clinical Intelligence Narrative) shared contracts (additive only)

New standalone subpackage `adaptix_contracts.acin` defining the canonical,
versioned ACIN record surface consumed by EPCR, NEMSIS, Billing,
Medical-Necessity, QA/QI, Legal, CMS-audit, AI-review, and Clinical-Decision-
Support. Additive only — no existing field, model, or enum member was removed or
repointed, and the `schemas` surface is unchanged.

- **acin.enums:** `ACINSection` (A-C-I-N-E-L-S, each with a `.letter`),
  `ACINRecordStatus`, `ACINClaimReviewState`, `ACINReviewType`,
  `ACINReviewStatus`, `ACINReviewSeverity`.
- **acin.provenance:** `ACINSourceRef` (grounding primitive mirroring
  `ai.capabilities.AISourceField`), `ACINProvenanceMixin`, and `ACINClaimDTO`.
  `ACINClaimDTO` fails closed — an `ai_generated` claim with zero
  `source_field_refs` is invalid (no fabrication).
- **acin.sections:** the seven section DTOs `ACINActivationDTO`,
  `ACINClinicalPictureDTO`, `ACINIntelligenceDTO`, `ACINNarrativeDTO`,
  `ACINEvidenceDTO`, `ACINLogicDTO`, `ACINSummaryDTO`, plus sub-DTOs
  `ACINTimelineEntryDTO`, `ACINWitnessStatementDTO`, `ACINContradictionFlagDTO`
  (flagged, never resolved), `ACINConditionFlagsDTO`, `ACINDifferentialDTO`.
- **acin.scores:** `ACINScoreSetDTO` — the 10 model-attributed scores
  (8 bounded 0-100 + contradictions/missing-elements counts).
- **acin.reviews:** `ACINReviewDTO` and `ACINReviewFindingDTO` for the four
  Cortex review lenses (clinical/billing/qa/legal); reviews record
  `failed_unavailable` truthfully rather than stubbing completion.
- **acin.record:** `ACINRecordDTO` — the full aggregation (7 sections + scores +
  reviews) with `overall_ai_generated`/`requires_human_review` advisory guards.

Contract-enforced non-negotiables: generated claims are grounded; AI content
always requires human review; contradictions are flagged not resolved;
narrative/summary are never authoritative truth.

## [1.5.0] - 2026-07-08

### Added — shared-service contract consolidation (additive only)

Makes the six shared-service contract modules the canonical, versioned surface
the shared services import (so service builds don't re-duplicate or drift).
Every change is additive; no existing field, model, or enum member was removed
or repointed.

- **audit_contracts (schemas):** completed the standalone Audit service surface
  with `AuditIngestRequest`, `AuditIngestResponse`, `AuditSearchResponse`,
  `AuditExportStatus`, `AuditExportResponse` (ingest/search/export
  request-response DTOs to sit alongside `AuditEvent`, `AuditSearchQuery`,
  `AuditExportRequest` and the four `audit.*` events).
- **audit_contracts (top-level direct-write client):** deprecated
  `adaptix_contracts.audit_contracts` (`AuditServiceClient`, `AuditLogEntry`)
  in favour of the Audit service surface above. Import path and behaviour are
  **preserved** (live consumers: Adaptix-CAD-Service `cad_app/audit_service.py`
  - migration `019_add_audit_log_entries`; Adaptix-Fire-Service
  `fire_app/audit_service.py`). Removal is deferred to 2.0.0.
- **notification_contracts:** `NotificationSendRequest` (typed canonical send
  request), `NotificationPreferenceSet` (Core per-category/per-channel + quiet
  hours shape), and `notification.*` events `NotificationQueuedEvent`,
  `NotificationSentEvent`, `NotificationReadEvent`. The str-typed
  `communications_contracts.NotificationRequest` and its
  `communications.notification.*` delivered/failed events are left unchanged and
  documented as the dispatcher shape — the two are versioned side by side, not
  merged.
- **reference_data_contracts:** canonical `PayerType` (union superset),
  `ServiceLevel`, and `StateCode` enums; CRUD/query/publish DTOs
  (`ReferenceDataListCreateRequest`, `ReferenceDataListUpdateRequest`,
  `ReferenceDataItemUpsertRequest`, `ReferenceDataQuery`,
  `ReferenceDataListResponse`, `ReferenceDataPublishRequest`,
  `ReferenceDataPublishResponse`); and `reference_data.*` events
  (`ReferenceDataListPublishedEvent`, `ReferenceDataListUpdatedEvent`).
  Exported at the package root as `ReferenceDataPayerType` to avoid shadowing
  the existing `billing_contracts.PayerType` export.
- **geo_contracts:** `ReverseGeocodeRequest`, `AutocompleteRequest`,
  `AddressSuggestion`, `AutocompleteResult`, `RouteRequest`, `DistanceRequest`,
  and an async `GeoClient` httpx helper wrapping `/api/v1/geo`.
- **forms_contracts:** `FormSubmission`, `FormValidationError`, create/update
  requests (`FormTemplateCreateRequest`, `FormTemplateUpdateRequest`,
  `FormVersionCreateRequest`, `FormSubmissionCreateRequest`), paged response
  wrappers (`FormTemplateListResponse`, `FormSubmissionListResponse`), and
  `form.*` events (`FormPublishedEvent`, `FormSubmittedEvent`).
- **facility_contracts:** `FacilityCapability` (+ optional `capabilities` on
  `FacilityRecord`), directory search (`FacilitySearchRequest`,
  `FacilitySearchResponse`), create/update (`FacilityCreateRequest`,
  `FacilityUpdateRequest`), alias/mapping upsert (`FacilityAliasCreateRequest`,
  `FacilityMappingUpsertRequest`), CMS/NPI sync (`CmsNpiSyncRequest`,
  `CmsNpiSyncResult`), and `facility.*` events (`FacilityRegisteredEvent`,
  `FacilityUpdatedEvent`, `FacilityMergedEvent`).

### Field-identity divergence — versioned, not unified (requires founder call)

- **PayerType** has real member divergence across domains:
  `billing_contracts.PayerType` = {MEDICARE, MEDICAID, COMMERCIAL, SELF_PAY,
  OTHER}; `intake_contracts.PayerType` = {MEDICARE, MEDICAID, TRICARE,
  COMMERCIAL, SELF_PAY, WORKERS_COMP}. The new canonical
  `reference_data_contracts.PayerType` is the union superset. The two domain
  enums are intentionally **not** repointed to it — selecting one authoritative
  set for billing/intake to import is a founder/billing decision.

### Added — service-separation contracts (additive only, from #94)

- **cortex_contracts:** `RecommendationRequest`, `RecommendationResponse` for the
  separated Cortex recommendation service.
- **trustsign_contracts:** `SignaturePackageCreateRequest`,
  `SignaturePackageResponse` for the separated TrustSign signing service.
- **docuseal_contracts:** `DocuSealPackageCreateRequest`,
  `DocuSealPackageResponse` for the separated DocuSeal signing integration.
- **sagemaker_contracts:** `PredictionRequest`, `PredictionResponse` for the
  separated SageMaker prediction service.
- **gateway_contracts:** `GatewayRouteRegistryEntry`, `ForwardedRequestContext`
  for the separated Adaptix Core gateway.
- All ten models are re-exported through `adaptix_contracts.schemas.__all__` and
  the package root. No existing contract was modified or removed.

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
- Canonical event registry entries `billing.claim.updated` and
  `epcr.chart.updated` (#76).

### Changed

- **Auth trust model:** replaced the custom HMAC/RS256 gateway-context proof with
  the AWS API Gateway injected-header contract (`X-User-Id` / `X-Tenant-Id` /
  `X-User-Roles` / `X-Is-Founder`), with `build_gateway_context_jwt` retained as
  a
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

- Added machine-readable `--json` output to `validate_contracts.py` so release
  automation can consume structured validation proof.
- Added `scripts/audit_workspace_contracts.py` to detect shadow
  `adaptix_contracts` trees across a polyrepo workspace.
- Added `tests/test_release_readiness.py` to cover JSON validation output and
  workspace shadow-package auditing.
- Added `.env.example` documenting `ADAPTIX_CONTRACTS_WORKSPACE_ROOT` for
  release audits.
- Added `MARKET_READY_LEDGER.md` as the authoritative proof ledger for
  market-readiness status.

### Changed

- Removed the repo's dependency on `pytest-asyncio` by converting async auth
  contract tests to synchronous `asyncio.run(...)` calls.
- Extended CI to build wheel/sdist artifacts and run `twine check` on the
  generated distributions.
- Updated readiness/runbook documentation to treat shadow-package detection as a
  hard release gate.

## [1.0.1] - 2026-04-21

### Added

- Added a pytest regression suite for schema exports, enum integrity, JSON
  schema generation, serialization round-trips, and representative validation
  failures.
- Added GitHub Actions validation for import checks, contract regression tests,
  and coverage reporting.
- Added documented deprecation and backward-compatibility policy for downstream
  services.

### Changed

- Fixed package-level symbol re-exports so `adaptix_contracts.<Symbol>` resolves
  consistently with `adaptix_contracts.schemas.<Symbol>`.
- Hardened `validate_contracts.py` to resolve schema paths from the repository
  location instead of the process working directory.
- Updated documented domain coverage from 26 to 28 to reflect `clinical_visual`
  and `inventory` contracts already present in the package.

## [1.0.0] - 2026-04-21

### Added

- Initial published shared Adaptix contracts package with cross-domain schema coverage.
