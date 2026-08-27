# AdaptixCore Claude Code Bootstrap

## Governance

@AGENTS.md

This repository is part of AdaptixCore. `AGENTS.md` and the global governance
policies it references are authoritative.

## Execution role

Work as an implementation agent under the AdaptixCore governance contract.
Reuse established architecture and finish the assigned scope end to end.
Do not invent replacement architecture, fake success, or production evidence.

## Lifecycle

```text
DISCOVER -> IMPLEMENT -> VALIDATE -> REVIEW -> MERGE -> CLEAN BRANCH
-> DEPLOY (when applicable) -> RUNTIME VERIFY (when applicable) -> COMPLETE
```

Before creating work, inspect existing open pull requests and reuse the
applicable PR. Do not create duplicate implementation PRs for the same task.

After a task branch is integrated, switch the checkout back to the canonical
local branch. `Stop` and `TaskCompleted` remain blocked until then.

Do not voluntarily stop while repository-resolvable work remains on the active
task. An open actionable implementation PR is work in progress, not completion.

Do not call CI green, an open PR, or a merge `Tier 5`. AdaptixCore Tier 5 means
production runtime verified with the required security, tenancy, persistence,
observability, recovery, and downstream evidence.

## Enforcement

Project lifecycle enforcement is registered in `.claude/settings.json` and
implemented in `.claude/hooks/`. Hooks must remain local-only and fast.
External GitHub, CI, AWS, deployment, and runtime proof belongs in explicit
lifecycle validation, not hot-path hooks.

The hook finds the canonical branch from local Git references that point to
each remote's default branch. It does not assume a remote named `origin` or a
branch named `main` or `master`.

The local hook does not try to prove PR integration from Git ancestry because
squash and rebase merges intentionally break that equivalence. GitHub merge
status is validated in the explicit lifecycle; the hook requires the checkout
to return to the canonical branch before completion.

Each local Git command has a 0.2-second timeout. A timeout blocks completion.
This limit is intentional. Do not make the hook slower to compensate for a slow
checkout. Fix local repository responsiveness instead.

Governance exceptions require an applicable active record under
`Adaptix-Governance/exceptions/`. Repository-local files cannot create or widen
an exception, including for emergency changes. Approval authority comes from
the active exception record and applicable global exception policy. Hook latency
limits remain binding whenever an exception authorizes production work.

Canonical hook regression tests live in
`Adaptix-Governance/tests/test_adaptix_governance_hook.py`.
