# Copilot instructions for adaptix-contracts

This repository is governed. Read `AGENTS.md` and `CLAUDE.md` first; they bind every agent,
Copilot coding agent included, and the global policies they cite in
`Adaptix-Governance/` outrank anything written here.

## What this repository is

`adaptix-contracts`, the AdaptixCore Contracts repository. It is part of one interconnected production platform:
routes, schema, events, auth, tenancy and downstream consumers are never
isolated work. The canonical branch is `main`, which is PR-required; a
merge is not deployment, and deployment is not runtime proof.

Repository-specific rules in `AGENTS.md` that bind you here:

- Shared contract and merge-bar alignment

## Hard rules

- Never merge, approve, or enable auto-merge on any pull request. Open a
  draft pull request and stop; a person decides.
- Never claim success without evidence. No evidence means UNKNOWN. Do not
  write "fixed", "validated" or "green" for anything you did not run and see.
- Never weaken a gate to make validation pass: no `continue-on-error`, no
  `|| true`, no skipped, deleted or quarantined test, no loosened lint, type
  or security configuration, no suppression added to make a finding go away.
- Never change the `@<sha>` pin of a reusable workflow in
  `.github/workflows/`: those carriers are thin on purpose and call the fleet
  engine in `adaptix-ops` at an immutable commit with its own promotion path.
- Never bypass auth, RBAC, tenant isolation, audit, billing safeguards or a
  security control, and never trust a client-supplied tenant identifier.
- Never add a third-party integration, SDK, service or secret the fleet does
  not already use; never fabricate a provider response, migration, deployment
  or runtime state.
- Keep each change on a short-lived task branch with one clear purpose;
  reuse an applicable open pull request instead of opening a duplicate.

## Validate before you push

```bash
uv sync --frozen --extra dev
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest -q
```

The required check on pull requests to `main` is the GitHub Actions job
`validate` (`.github/workflows/validate.yml`), alongside the fleet security
gates (gitleaks, qodana, semgrep, trivy). Push, then read the jobs on the pull
request and fix what they report in the same pull request.

## Reporting

Describe a pull request in plain language: what a reader would see before,
what they see after, and how. List exactly which commands were run and their
result. If something could not be verified, say so by name rather than
leaving it out.
