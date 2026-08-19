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

Any change made in this repository must complete the full Adaptix change lifecycle:

1. Commit the change.
2. Push the branch to GitHub.
3. Monitor for merge conflicts.
4. Resolve merge conflicts.
5. Monitor GitHub Actions / CI.
6. Correct validation or CI failures.
7. Merge only after required checks pass.
8. Deploy to AWS where applicable.
9. Monitor AWS deployment health.
10. Monitor ECS tasks, services, logs, target groups, gateway/API behavior, and
    service health.
11. Correct runtime failures.
12. Redeploy if corrections are required.
13. Repeat monitoring until stable.
14. Record completion evidence.

A change is not complete because it was edited locally.

A change is complete only when it is committed, pushed, conflict-checked,
merged, deployed where applicable, monitored, corrected for failures, and
verified stable with evidence.

## First rollout restriction

This local AGENTS.md file is governance inheritance only.

Do not modify production logic as part of this first rollout.

## Local override rule

Local rules may be stricter than global rules.

Local rules may never weaken global rules.

## Bedrock Remote Repair And Deployment Rule

Agent audit, repair, validation, and deployment work must not stay local. Every
change is verified locally against this repository's own declared gates, then
committed directly to `main` - solo operator, trunk-based: no branch, no
worktree, no pull request, no force-push, no history rewrite. GitHub is source
control, not the execution engine; continuous CI-on-push was retired on
2026-08-19, so never wait on, require, or claim a GitHub CI status that no longer
runs. Deployment executes only through this repository's approved AWS release
path (AWS CodeBuild is the only approved deployment executor). Release artifacts
are immutable and traceable to the exact commit they were built from. Record the
evidence that path actually produces: a commit on `main` is not a deployment, and
a completed deployment is not runtime proof. Never leave a fix, audit result,
deployment change, or conflict resolution local-only, and never weaken, skip, or
bypass a gate to make work land. If this repository lacks its release path or the
required AWS configuration, report it as BLOCKED rather than claiming repair,
deployment, or production readiness.
