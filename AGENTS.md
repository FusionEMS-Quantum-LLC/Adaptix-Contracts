# LOCAL ADAPTIX REPO GOVERNANCE

This repository inherits global governance from:

Adaptix-Governance/AGENTS.md

## Local repo scope

Repo name: Adaptix-Contracts
Domain: Contracts
Owner service: adaptix-contracts

## Local execution rule

This repo must comply with:

- GLOBAL_EXECUTION_POLICY.md
- GLOBAL_CHANGE_CLASSIFICATION.md
- GLOBAL_CHANGE_LIFECYCLE_POLICY.md
- GLOBAL_NO_FAKE_SUCCESS_POLICY.md
- GLOBAL_PRODUCTION_READINESS.md
- GLOBAL_ROUTE_POLICY.md
- GLOBAL_SERVICE_POLICY.md
- GLOBAL_AUTH_POLICY.md
- GLOBAL_TENANT_POLICY.md
- GLOBAL_SCHEMA_POLICY.md
- GLOBAL_OBSERVABILITY_POLICY.md
- GLOBAL_SECURITY_POLICY.md
- GLOBAL_EVIDENCE_POLICY.md
- GLOBAL_CLEARINGHOUSE_BOUNDARY.md

## Change lifecycle rule

Any change in this repository must follow the AdaptixCore lifecycle defined by
`Adaptix-Governance/GLOBAL_CHANGE_LIFECYCLE_POLICY.md`.

Required local behavior:

1. Inspect existing open pull requests before creating new work.
2. Reuse the applicable existing PR instead of duplicating the task.
3. Use a short-lived task branch when a change is required.
4. Run repository-native validation before merge.
5. Resolve repository-resolvable conflicts, review findings, and failing checks
   in the same PR.
6. Merge through the protected branch workflow when repository policy permits.
7. Verify the canonical target branch contains the change.
8. Remove the completed task branch/worktree where supported.
9. Deploy through the approved AWS path where applicable.
10. Runtime-verify the deployed behavior where applicable.
11. Do not advance to unrelated work in this repository while the active task
    remains actionable.

An open PR, green CI result, or merge is not AdaptixCore Tier 5. Tier 5 means
production runtime verified.

## Local override rule

Local rules may be stricter than global rules.

Local rules may never weaken global rules.

## Shared contract and merge-bar alignment

This repository is the shared schema truth owner. Adaptix-Governance owns
written policy. The two must match, and live GitHub must enforce the same bar.

- Required GitHub Actions job name on pull requests to `main`: `validate`
- GitHub must require that exact job name. Do not invent a fleet-wide check name.
- CodeBuild is release authority for this non-deployable library only when a
  release is cut. It is not the pull-request merge gate.
- Shared schemas live in `adaptix_contracts/`. Downstream services import the
  published package. Divergent copies are forbidden.
- Backup, wip, temp, archive, recovery, and similar leftover branches are forbidden.
