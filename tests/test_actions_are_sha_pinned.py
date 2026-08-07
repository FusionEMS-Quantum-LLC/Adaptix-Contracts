"""Every GitHub Action must be pinned to a 40-hex commit SHA (AX5-PIN).

A `uses: actions/checkout@v4` reference resolves a *mutable* tag at run time:
whoever can move that tag decides what executes inside a workflow that holds
this repository's `GITHUB_TOKEN`. Pinning to an immutable commit SHA is what
makes a reviewed action stay the reviewed action.

The negative case below is the important half -- it feeds known-bad refs back
through the same checker, so this file cannot quietly stop testing anything.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"

# `uses:` values that are not third-party actions and cannot be SHA-pinned.
_LOCAL_PREFIXES = ("./", "../", "docker://")

_USES = re.compile(r"^\s*(?:-\s+)?uses:\s*['\"]?(?P<ref>[^'\"#\s]+)['\"]?")
_SHA40 = re.compile(r"^[0-9a-f]{40}$")


def workflow_files() -> list[Path]:
    if not WORKFLOW_DIR.is_dir():
        return []
    return sorted(p for p in WORKFLOW_DIR.iterdir() if p.suffix in (".yml", ".yaml"))


def unpinned_refs(text: str) -> list[str]:
    """Return every `uses:` ref in `text` that is not pinned to a commit SHA."""
    bad: list[str] = []
    for line in text.splitlines():
        m = _USES.match(line)
        if not m:
            continue
        ref = m.group("ref")
        if ref.startswith(_LOCAL_PREFIXES):
            continue
        if "@" not in ref:
            bad.append(ref)
            continue
        if not _SHA40.match(ref.rsplit("@", 1)[1]):
            bad.append(ref)
    return bad


def test_workflow_directory_is_present() -> None:
    """Guard against 'going green' by deleting the workflows."""
    assert workflow_files(), (
        f"no workflow files found under {WORKFLOW_DIR} -- if they were removed, "
        "this test has stopped protecting anything"
    )


@pytest.mark.parametrize("path", workflow_files(), ids=lambda p: p.name)
def test_every_action_is_pinned_to_a_commit_sha(path: Path) -> None:
    bad = unpinned_refs(path.read_text(encoding="utf-8"))
    assert not bad, (
        f"{path.relative_to(REPO_ROOT)} uses mutable action refs {bad}; pin each to a "
        "reviewed 40-character commit SHA and keep the release tag in a trailing comment"
    )


def test_every_pinned_ref_keeps_its_version_comment() -> None:
    """A bare SHA with no `# vX.Y.Z` is unreviewable and undiffable."""
    missing: list[str] = []
    for path in workflow_files():
        for line in path.read_text(encoding="utf-8").splitlines():
            m = _USES.match(line)
            if not m or m.group("ref").startswith(_LOCAL_PREFIXES):
                continue
            ref = m.group("ref")
            if "@" in ref and _SHA40.match(ref.rsplit("@", 1)[1]) and "#" not in line:
                missing.append(f"{path.name}: {ref}")
    assert not missing, f"SHA-pinned refs with no version comment: {missing}"


# --- negative case -----------------------------------------------------------


@pytest.mark.parametrize(
    "ref",
    [
        "actions/checkout@v4",
        "actions/setup-python@v5",
        "github/codeql-action/init@v3",
        "github/codeql-action/analyze@v4.37.5",
        "codacy/codacy-coverage-reporter-action@v1",
        "actions/checkout@main",
        "actions/checkout",
        "actions/checkout@11d5960a326750d5838078e36cf38b85af6772",  # 39 chars
        "actions/checkout@11D5960A326750D5838078E36CF38B85AF677262",  # uppercase
    ],
)
def test_mutable_refs_are_rejected(ref: str) -> None:
    """The checker must still flag the exact forms this change removed."""
    assert unpinned_refs(f"      - uses: {ref}\n") == [ref], (
        f"unpinned ref {ref!r} was NOT detected -- unpinned_refs() has regressed "
        "and the assertions above are vacuous"
    )


@pytest.mark.parametrize(
    "ref",
    [
        "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
        "github/codeql-action/init@c4dd10e44af883a891fe31ced449bcb4a6728b9b",
        "./.github/actions/local-composite",
    ],
)
def test_properly_pinned_refs_are_accepted(ref: str) -> None:
    """And it must not produce false positives on correctly pinned refs."""
    assert unpinned_refs(f"      - uses: {ref} # v4.4.0\n") == []
