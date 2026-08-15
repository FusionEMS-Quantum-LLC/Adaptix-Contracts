"""Automation authority guards for repo-local workflows/buildspecs."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
CODEBUILD_DIR = REPO_ROOT / ".codebuild"

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


def test_main_validation_buildspec_exists() -> None:
    assert (CODEBUILD_DIR / "main-validation.yml").is_file(), (
        "main-validation.yml is required so CodeBuild, not GitHub Actions, owns "
        "the authoritative main/release validation path"
    )


def test_main_validation_covers_release_readiness_commands() -> None:
    text = (CODEBUILD_DIR / "main-validation.yml").read_text(encoding="utf-8")
    for command in (
        "bash scripts/local-ci.sh python full",
        "python validate_contracts.py --json",
        "python -m build --sdist --wheel",
        "python -m twine check dist/*",
    ):
        assert command in text, f"main-validation.yml is missing `{command}`"


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
