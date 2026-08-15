# Fabrication-Surface Scanner Pattern

**Status:** stable — adopted in `Adaptix-Payments-Service` under PR #32 (`e010cd8`, merged 2026-08-15).
**Owner:** any service handling real money, real PHI, real signatures, or real audit rows.
**Origin:** Josh directive 2026-08-14 — "Production Level 5 = user-ready, agency-ready, billing-ready,
end to end. Zero fabrication."

---

## 1. Problem the scanner solves

Every service in the fleet integrates real external systems (Stripe, STEDI, TrustSign, DocuSign, Twilio,
EPCR clinical stores, RDS/Postgres). A single env-flip shortcut — `if os.environ.get("PAYMENTS_STUB")`,
`if settings.demo_mode:`, `if mock_stripe:` — silently converts a misconfigured deployment into a
**fabricated success signal**. Payment fabricates. PHI fabricates. Signature fabricates. Audit
fabricates.

The founder-direction-absolute rule forbids that. Manual pre-merge audits catch it at merge; nothing
catches it on the fifth merge next quarter when a developer legitimately needs a "quick sandbox path"
and nobody notices the env-flip re-emerging.

The scanner is a CI-enforced regression test that fails the build if a shipped module tree references
any known fabrication token outside of a comment or docstring.

## 2. Guarantees

| Property | Guarantee |
| --- | --- |
| Scan target | Shipped runtime package tree only (e.g. `payments_app/`, not `tests/`). |
| Scan granularity | Line-level, with docstring + comment exclusion. |
| Failure mode | CI-breaking test failure with offending file, line number, and token. |
| False-positive posture | Boundary comments (`# there is no fake success`) are permitted; docstrings are permitted; test fakes are unreachable at runtime and out of scope. |
| Token set | Service-tailored (see §4). |

## 3. Adoption cost

- One file, ~110 lines of pure-Python stdlib.
- No new dependency.
- Runs in the existing pytest CI job.

## 4. Service-specific token sets

Each service picks the tokens that could plausibly appear as a real fabrication shortcut for its own
domain. The Payments token set is the reference; other services add their own.

### 4.1 Money-path services (Payments, Billing, Finance)

```
demo_mode
mock_stripe
PAYMENTS_STUB       # or BILLING_STUB / FINANCE_STUB
FAKE_STRIPE
sandbox_mode
dry_run
if os.environ.get   # env-flip shortcut around the money path
```

**Deliberately excluded:** `test_mode`. Stripe's own API surfaces `livemode` / test-mode as a truthful
property of the key/event. Services that report that property honestly are documenting reality, not
fabricating. `livemode`, `test_mode`, and `test_clock` may appear in real boundary-reporting code
without being fabrication.

### 4.2 PHI-path services (EPCR, Communications, Telephony)

```
demo_patient
mock_phi
fake_chart
synthetic_phi
skip_hipaa
PHI_STUB
if os.environ.get   # env-flip shortcut around the PHI persistence path
```

### 4.3 Signature-path services (TrustSign, DocuSign integrators, Compliance)

```
demo_signature
mock_docusign
FAKE_SIGNATURE
skip_signature_check
signature_bypass
if os.environ.get   # env-flip shortcut around signature verification
```

### 4.4 Audit-path services (any service writing regulatory audit rows)

```
skip_audit
audit_disabled
mock_audit
AUDIT_STUB
if os.environ.get   # env-flip shortcut around the audit write
```

Services owning multiple paths (e.g. Billing owns money + audit) union the sets.

## 5. Reference implementation

The canonical implementation lives in `Adaptix-Payments-Service`:

- File: `backend/tests/test_no_fabrication_surface.py`
- PR: [FusionEMS-Quantum-LLC/Adaptix-Payments-Service#32](https://github.com/FusionEMS-Quantum-LLC/Adaptix-Payments-Service/pull/32)
- Commit: `e010cd8`

Structure (paraphrased for portability):

```python
"""Regression: no fabricated / stubbed / demo codepath is reachable in prod."""

from __future__ import annotations

import re
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "<your_shipped_package>"

_FABRICATION_TOKENS = (
    # Fill in from §4 for your service domain.
)

_COMMENT_LINE = re.compile(r"^\s*#")


def _iter_shipped_python_lines():
    for path in sorted(_PACKAGE_ROOT.rglob("*.py")):
        rel = path.relative_to(_PACKAGE_ROOT)
        text = path.read_text(encoding="utf-8")
        in_docstring = False
        docstring_delim: str | None = None
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not in_docstring:
                for delim in ('"""', "'''"):
                    if stripped.startswith(delim):
                        rest = stripped[len(delim) :]
                        if delim in rest:
                            break
                        in_docstring = True
                        docstring_delim = delim
                        break
            else:
                assert docstring_delim is not None
                if docstring_delim in stripped:
                    in_docstring = False
                    docstring_delim = None
                continue
            if in_docstring:
                continue
            if _COMMENT_LINE.match(line):
                continue
            yield rel, lineno, line


def test_shipped_module_tree_has_no_fabrication_flags() -> None:
    hits: list[str] = []
    for rel, lineno, line in _iter_shipped_python_lines():
        for token in _FABRICATION_TOKENS:
            if token.lower() in line.lower():
                hits.append(f"{rel}:{lineno}: {line.strip()}  (token={token})")
    assert not hits, (
        "Fabrication-surface regression: a shipped code line references a "
        "demo / stub / mock / sandbox / dry-run flag outside a comment/docstring. "
        "Every real path must stay real — no env-flip may fabricate success. "
        "Offending lines:\n  " + "\n  ".join(hits)
    )
```

### 5.1 Non-Python services

The same pattern ports to any tree-walk-able source (TypeScript, Go, Rust). Replace `.py` glob and
comment/docstring logic with the language's own equivalent. Contract stays:

1. Walk shipped runtime tree only.
2. Skip comments + docstrings/JSDoc/rustdoc/etc.
3. Fail loudly on hit, with file + line + token.

## 6. Adoption checklist

- [ ] Pick the token set for your service domain from §4 (or union multiple).
- [ ] Copy §5 reference implementation into your `tests/` tree.
- [ ] Point `_PACKAGE_ROOT` at your shipped runtime package.
- [ ] Run manual audit BEFORE first CI run:
      `rg -i "(demo_mode|mock_.*|.*_STUB|FAKE_.*|sandbox_mode|dry_run|skip_.*|.*_disabled)" <your_package>/`
- [ ] Fix or gate every real hit before the regression test lands (otherwise CI breaks immediately).
- [ ] Ensure comment-based boundary documentation (`# there is no fake success`) is preserved — it is
      protective, not fabrication.
- [ ] Wire pytest / equivalent runner into CI (usually already done).
- [ ] Open PR referencing this doc.
- [ ] Report adoption to the operator so the fleet ledger is current.

## 7. What this scanner does NOT do

- Does not validate that fakes are absent from `tests/`. Test fakes at boundaries are legitimate.
- Does not validate that upstream vendors report truthful `livemode` / `test_mode` — that's a boundary
  concern, not a fabrication concern.
- Does not replace runtime fail-closed defenses (503 on missing config, 400 on bad signature). It is
  additive to those.
- Does not replace tenant isolation / RBAC / audit-row checks. Those have their own regression tests.

## 8. Change control

Extending a service's token set is a normal PR. Removing a token requires an explicit justification in
the PR body: which threat model no longer applies, and why.

Removing the scanner test itself requires operator sign-off.
