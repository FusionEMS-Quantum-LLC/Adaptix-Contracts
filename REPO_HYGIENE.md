# REPO_HYGIENE.md

## Purpose

This document defines mandatory standards for repository cleanliness, structure, and long-term maintainability. All contributors and automated agents must follow these rules without exception.

This file governs **Adaptix-Contracts** only (Contracts / owner service `adaptix-contracts`). It is not permission to modify other Adaptix repositories from this workspace.

## 1. Repository Structure & Organization

Maintain a clear, predictable directory hierarchy.

Follow established naming conventions for folders, files, modules, and assets.

Keep related components grouped logically; avoid ad-hoc or duplicate structures.

This repository's established layout includes `docs/`, `tools/` and repository-native config at the root.

Ensure every file has a clear purpose aligned with the repository's scope.

## 2. File Consistency & Standards

All files must conform to the repo's language, formatting, linting, and documentation standards.

Enforce consistent code style across all modules.

Ensure configuration files and lockfiles remain synchronized with actual dependencies and project structure.

Remove or rewrite any file that deviates from repo conventions - only after proving it is unused or incorrect. Do not delete from a search miss.

Do not run a repository-wide format or lint rewrite while unrelated in-progress work is present.

## 3. Legacy & Obsolete Removal

Identify and delete deprecated, unused, or abandoned:

- source files
- modules
- configs
- assets
- scripts
- branches

No dead code, no outdated artifacts, no unmaintained directories.

If a file is replaced, remove the old version immediately - after proving no remaining import, route registration, dynamic load, test, or manifest reference.

Do not delete in-progress product work.

## 4. Debris-Free Repositories

Repos must remain free of:

- temporary files
- build artifacts
- logs
- caches
- editor leftovers
- partial or failed outputs

Maintain strict `.gitignore` rules to prevent accidental commits of non-source files.

Ignored files must include the build caches, test caches, OS junk, editor folders, and scanner output this stack actually produces. Do not hide source behind an overbroad ignore.

## 5. Standardization Enforcement

Apply uniform formatting and linting across all files using this repo's native tools.

Use automated tools (formatters, linters, type checkers) to enforce consistency - scoped to the change, never as a drive-by rewrite of the whole tree.

Ensure documentation follows a unified structure and tone.

Keep dependency versions consistent with this repo's lockfile. Shared fleet standards live in Adaptix-Governance; do not change other repos from here.

## 6. Cross-Repository Alignment

This repository is a member of the AdaptixCore polyrepo.

Maintain shared standards for naming, structure, dependencies, and documentation as defined by Adaptix-Governance.

Ensure architectural patterns remain consistent with platform contracts.

Avoid divergence in conventions unless explicitly documented.

Do not wander into other repositories to standardize them from this workspace.

## 7. Continuous Cleanup & Maintenance

Regularly audit the repository for structural drift, clutter, or inconsistencies.

Automatically correct issues when detected - debris and ignore gaps first; source deletion only when unused is proven.

Keep the repo in a production-ready state at all times.

Nothing stays local: hygiene changes go on a dedicated branch, get pushed, and open a pull request.

## 8. Enforcement

Any violation of this hygiene policy must be corrected immediately. Automated agents should self-correct; contributors must submit cleanup PRs as needed.

Never use `git stash`, force-push, or history rewrite to make the tree look clean.

Never commit secrets, PHI, or scanner output that embeds extracted credentials.
