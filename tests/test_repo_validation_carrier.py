"""GOV-GAP-09: prove this repository carries the canonical fleet validation carrier.

Adaptix-Contracts was the sole repository still on the retired
``.github/workflows/validate.yml`` carrier and produced no
``adaptix/repo-validation`` status check. It now carries the canonical
``.github/workflows/repo-validation.yml`` that every other repository runs
(FusionEMS-Quantum-LLC/adaptix-ops/validation) and the legacy carrier is gone.

These tests fail on the pre-migration tree (no repo-validation.yml, validate.yml
present) and pass on the migrated tree. They assert the invariants the fleet
engine itself documents in validation/carrier-workflow.yml: the required-check
job name is the literal ``adaptix/repo-validation`` contract, the carrier
subscribes to pull_request/merge_group/push, and the engine reference appears
consistently -- two ``uses:`` pins plus two ``engine-sha`` inputs, all one
immutable commit (the "SHA appears four times and all four must match" rule).
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
CARRIER = WORKFLOWS / "repo-validation.yml"
RETIRED = WORKFLOWS / "validate.yml"

ENGINE_REPO = "FusionEMS-Quantum-LLC/adaptix-ops"
REQUIRED_CHECK_NAME = "adaptix/repo-validation"

# `uses:` engine pins (plan sub-action and the validation action) plus the
# `engine-sha:` inputs the planner seals into the capsule.
_USES_RE = re.compile(
    r"uses:\s*" + re.escape(ENGINE_REPO) + r"/validation[^@\s]*@([0-9a-f]{40})"
)
_ENGINE_SHA_RE = re.compile(r"engine-sha:\s*([0-9a-f]{40})")


def _load_carrier() -> dict:
    with CARRIER.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_canonical_carrier_present() -> None:
    assert CARRIER.is_file(), (
        f"{CARRIER} is missing: the repository does not carry the canonical "
        "adaptix/repo-validation carrier."
    )


def test_retired_validate_carrier_removed() -> None:
    assert not RETIRED.exists(), (
        f"{RETIRED} still exists: the retired 'validate' carrier must be removed "
        "so the repository runs only the canonical adaptix/repo-validation check."
    )


def test_required_check_job_name_is_the_contract() -> None:
    data = _load_carrier()
    jobs = data.get("jobs") or {}
    job_names = {job.get("name") for job in jobs.values() if isinstance(job, dict)}
    assert REQUIRED_CHECK_NAME in job_names, (
        "the carrier must contain a job named "
        f"{REQUIRED_CHECK_NAME!r} -- the required status-check context branch "
        f"protection enforces; found job names {sorted(n for n in job_names if n)}"
    )


def test_carrier_subscribes_to_gating_events() -> None:
    data = _load_carrier()
    # PyYAML (YAML 1.1) parses the bare key ``on`` as the boolean True.
    triggers = data.get("on", data.get(True)) or {}
    assert "pull_request" in triggers, "carrier must run on pull_request"
    assert "merge_group" in triggers, (
        "carrier must subscribe to merge_group or the required check never "
        "reports to the merge queue and it stalls"
    )
    push = triggers.get("push") or {}
    assert "main" in (push.get("branches") or []), (
        "carrier must run on push to main so main is validated directly"
    )


def test_engine_reference_is_one_consistent_pinned_commit() -> None:
    text = CARRIER.read_text(encoding="utf-8")
    uses = _USES_RE.findall(text)
    engine_sha = _ENGINE_SHA_RE.findall(text)
    assert len(uses) == 2, (
        f"expected 2 pinned '{ENGINE_REPO}/validation@<sha>' uses references, "
        f"found {len(uses)}: {uses}"
    )
    assert len(engine_sha) == 2, (
        f"expected 2 'engine-sha:' inputs, found {len(engine_sha)}: {engine_sha}"
    )
    all_shas = set(uses) | set(engine_sha)
    assert len(all_shas) == 1, (
        "all four engine references must pin the same immutable commit "
        f"(two uses pins and two engine-sha inputs); found divergence: {all_shas}"
    )
