# Contract Deprecation and Compatibility Policy

## Purpose

This document governs how `adaptix-contracts` evolves without introducing silent
breakage across the Adaptix polyrepo.

## Compatibility rules

1. **Patch releases** may fix defects, improve documentation, and add
   validation/tests without changing required fields or enum semantics.
2. **Minor releases** may add optional fields, new models, or new enum members
   when downstream consumers can safely ignore them.
3. **Major releases** are required for removing fields, renaming fields,
   changing field meaning, narrowing accepted values, or deleting enum members.

## Deprecation process

1. Mark the field, model, or enum member as deprecated in code comments and
   release notes.
2. Document the replacement path in `CHANGELOG.md`.
3. Preserve backward-compatible parsing for at least one minor release unless a
   security issue requires faster removal.
4. Add or update regression tests proving both legacy and replacement shapes
   validate during the overlap period.
5. Remove the deprecated surface only in the next major version.

## Required release evidence

Before publishing any contract change:

- `python validate_contracts.py` passes
- `python -m pytest` passes
- `CHANGELOG.md` contains the exact public-surface change
- downstream impact is described for any deprecated or newly optional field

## Forbidden changes

- Silent required-field additions in patch or minor releases
- Reusing an existing enum value with different meaning
- Breaking import paths without a major version increment
- Divergent contract copies in sibling repositories
