"""Behaviour of the Version Tag Drift workflow's comparison step.

The step's shell script is extracted from the workflow file and run under bash
the way GitHub Actions runs it (``-eo pipefail``), against a stub ``gh`` on
PATH. The repository's own validation entrypoint (scripts/ci/verify-toolchain.sh)
is a bash script, so bash is a precondition of this repository, not of the
test alone.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "version-tag-drift.yml"
STEP_NAME = "Compare the declared version against the newest release tag"

_GH_STUB = """#!/usr/bin/env bash
case "$GH_STUB" in
  fail) echo "gh: HTTP 502 Bad Gateway" >&2; exit 1 ;;
  *) printf '%s\\n' "$GH_STUB_TAGS" ;;
esac
"""


def _declared_version() -> str:
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    assert match is not None
    return match.group(1)


def _step_script() -> str:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["drift"]["steps"]
    (step,) = [s for s in steps if s.get("name") == STEP_NAME]
    script: str = step["run"]
    return script


def _run(
    tmp_path: Path, *, stub: str, tags: str = ""
) -> subprocess.CompletedProcess[str]:
    bash = shutil.which("bash")
    assert bash is not None, "bash is required to run this repository's CI scripts"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "gh").write_text(_GH_STUB, encoding="utf-8", newline="\n")
    python = sys.executable.replace("\\", "/")
    (bin_dir / "python3").write_text(
        f'#!/usr/bin/env bash\nexec "{python}" "$@"\n', encoding="utf-8", newline="\n"
    )
    for tool in bin_dir.iterdir():
        tool.chmod(0o755)
    script = tmp_path / "step.sh"
    script.write_text(_step_script(), encoding="utf-8", newline="\n")
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "GITHUB_REPOSITORY": "FusionEMS-Quantum-LLC/Adaptix-Contracts",
        "GH_STUB": stub,
        "GH_STUB_TAGS": tags,
    }
    return subprocess.run(
        [bash, "--noprofile", "--norc", "-eo", "pipefail", str(script)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_tagged_declared_version_passes(tmp_path: Path) -> None:
    declared = _declared_version()
    result = _run(
        tmp_path, stub="tags", tags=f"v0.1.0\nnightly\nv{declared}-rc1\nv{declared}"
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert f"OK -- v{declared} is tagged" in result.stdout


def test_untagged_version_bump_fails(tmp_path: Path) -> None:
    result = _run(tmp_path, stub="tags", tags="v0.1.0")

    assert result.returncode == 1
    assert "Untagged version bump" in result.stdout


def test_repository_without_semver_tags_reports_no_release_tag(tmp_path: Path) -> None:
    result = _run(tmp_path, stub="tags", tags="nightly\nrelease-candidate")

    assert result.returncode == 1
    assert "No release tag" in result.stdout


def test_failed_tag_read_stops_the_job_instead_of_reporting_no_tag(
    tmp_path: Path,
) -> None:
    # Regression: `... | tail -1 || true` swallowed a failed API read, so an
    # outage was reported as "this repository has no vX.Y.Z tag at all".
    result = _run(tmp_path, stub="fail")

    assert result.returncode != 0
    assert "HTTP 502" in result.stderr
    assert "No release tag" not in result.stdout
