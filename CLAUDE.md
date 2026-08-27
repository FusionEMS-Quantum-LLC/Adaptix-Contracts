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

Do not voluntarily stop while repository-resolvable work remains on the active
task. An open actionable implementation PR is work in progress, not completion.

Do not call CI green, an open PR, or a merge `Tier 5`. AdaptixCore Tier 5 means
production runtime verified with the required security, tenancy, persistence,
observability, recovery, and downstream evidence.

## Enforcement

Project lifecycle enforcement is registered in `.claude/settings.json` and
implemented in `.claude/hooks/`. Hooks must remain local-only and fast.
External GitHub, CI, AWS, deployment, and runtime proof belongs in explicit
lifecycle validation, not hot-path hooks. Any governance exception must be
recorded in the authoritative governance source and must retain the hook latency
limits.
