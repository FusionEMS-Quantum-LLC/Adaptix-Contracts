"""Automation authority guards for repo-local workflows/buildspecs."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"

FORBIDDEN_WORKFLOW_SNIPPETS = (
    "aws-actions/configure-aws-credentials@",
    "docker/build-push-action@",
    "pypa/gh-action-pypi-publish@",
    "softprops/action-gh-release@",
    "amazon-ecr-login",
    "aws ecs ",
    "aws ecr ",
    "twine upload",
    "gh release ",
    "kubectl ",
    "helm ",
)


def workflow_files() -> list[Path]:
    return sorted(p for p in WORKFLOW_DIR.iterdir() if p.suffix in (".yml", ".yaml"))


def test_github_actions_do_not_regain_deploy_or_release_authority() -> None:
    offenders: list[str] = []
    for path in workflow_files():
        text = path.read_text(encoding="utf-8").lower()
        for snippet in FORBIDDEN_WORKFLOW_SNIPPETS:
            if snippet in text:
                offenders.append(f"{path.name}: {snippet}")
    assert not offenders, (
        "GitHub Actions in this repo must stay analysis-only; remove deploy/release "
        f"authority patterns: {offenders}"
    )


def test_codacy_workflow_does_not_mask_failures() -> None:
    text = (WORKFLOW_DIR / "codacy-coverage.yml").read_text(encoding="utf-8")
    assert "continue-on-error: true" not in text
    assert "|| true" not in text
