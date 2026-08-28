from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_validate_contracts_json_report() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "validate_contracts.py"), "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    payload = json.loads(result.stdout)

    assert payload["all_passed"] is True
    assert payload["phase_count"] == 4
    assert {phase["name"] for phase in payload["phases"]} == {
        "Import Validation",
        "Model Structure",
        "Model Instantiation",
        "Domain Coverage",
    }


def test_production_readiness_does_not_overclaim_platform_rollout() -> None:
    readiness = (REPO_ROOT / "docs" / "archive" / "PRODUCTION_READINESS.md").read_text(
        encoding="utf-8"
    )

    assert "Classification: NO-GO FOR PLATFORM ROLLOUT" in readiness
    assert "Consumer runtime verification is missing" in readiness
    assert "payload-shape compatibility" in readiness
    assert "PASS — the canonical package" not in readiness


def test_workspace_audit_detects_shadow_contract_package(tmp_path: Path) -> None:
    contracts_repo = tmp_path / "Adaptix-Contracts"
    scripts_dir = contracts_repo / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "audit_workspace_contracts.py").write_text(
        (REPO_ROOT / "scripts" / "audit_workspace_contracts.py").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )

    shadow_repo = tmp_path / "Adaptix-Shadow-Service" / "backend" / "adaptix_contracts"
    shadow_repo.mkdir(parents=True)

    result = subprocess.run(
        [
            sys.executable,
            str(scripts_dir / "audit_workspace_contracts.py"),
            "--workspace-root",
            str(tmp_path),
            "--json",
        ],
        cwd=contracts_repo,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)

    assert result.returncode == 1
    assert payload["status"] == "FAIL"
    assert payload["shadow_package_count"] == 1
    assert payload["shadow_package_paths"] == [str(shadow_repo.resolve())]
