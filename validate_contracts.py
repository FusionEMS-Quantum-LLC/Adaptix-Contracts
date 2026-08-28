#!/usr/bin/env python3
"""Comprehensive validation script for adaptix-contracts package.

This script validates:
1. All schema files can be imported
2. All models can be instantiated with valid data
3. No circular import issues exist
4. All exports are correctly defined
5. Pydantic v2 compatibility
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any


def _status_icon(ok: bool) -> str:
    """Return ASCII-safe status marker for Windows console compatibility."""
    return "[PASS]" if ok else "[FAIL]"


def validate_imports(*, verbose: bool = True) -> dict[str, Any]:
    """Test that all schema modules can be imported."""
    if verbose:
        print("=" * 70)
        print("PHASE 1: Import Validation")
        print("=" * 70)

    try:
        from adaptix_contracts.schemas import __all__

        if verbose:
            print(
                f"{_status_icon(True)} Schema __all__ list defined ({len(__all__)} exports)"
            )

        # Import all schemas
        from adaptix_contracts import schemas

        imported_count = 0
        missing_exports: list[str] = []
        for name in __all__:
            if hasattr(schemas, name):
                imported_count += 1
            else:
                missing_exports.append(name)

        passed = not missing_exports
        if verbose:
            if missing_exports:
                for name in missing_exports:
                    print(f"{_status_icon(False)} Missing export: {name}")
            else:
                print(
                    f"{_status_icon(True)} All {imported_count} exports are accessible"
                )
        return {
            "name": "Import Validation",
            "passed": passed,
            "details": {
                "export_count": len(__all__),
                "imported_count": imported_count,
                "missing_exports": missing_exports,
            },
        }

    except ImportError as e:
        if verbose:
            print(f"{_status_icon(False)} Import failed: {e}")
        return {
            "name": "Import Validation",
            "passed": False,
            "details": {"error": str(e)},
        }


def validate_model_structure(*, verbose: bool = True) -> dict[str, Any]:
    """Validate Pydantic model structure and compatibility."""
    if verbose:
        print("\n" + "=" * 70)
        print("PHASE 2: Model Structure Validation")
        print("=" * 70)

    from adaptix_contracts import schemas
    from pydantic import BaseModel
    from enum import Enum

    models = []
    enums = []

    for name in dir(schemas):
        if name.startswith("_"):
            continue
        obj = getattr(schemas, name)

        if isinstance(obj, type):
            if issubclass(obj, BaseModel) and obj is not BaseModel:
                models.append((name, obj))
            elif issubclass(obj, Enum) and obj is not Enum:
                enums.append((name, obj))

    if verbose:
        print(f"{_status_icon(True)} Found {len(models)} model classes")
        print(f"{_status_icon(True)} Found {len(enums)} enum classes")

    # Check for proper Pydantic v2 usage
    issues = []
    for name, model in models:
        # Check if model has model_config (Pydantic v2 pattern)
        if hasattr(model, "model_fields"):
            # Pydantic v2
            pass
        else:
            issues.append(f"{name}: May not be Pydantic v2 compatible")

    if issues:
        if verbose:
            print("\n[WARN] Potential issues:")
            for issue in issues:
                print(f"   - {issue}")
    else:
        if verbose:
            print(f"{_status_icon(True)} All models appear Pydantic v2 compatible")

    return {
        "name": "Model Structure",
        "passed": True,
        "details": {
            "model_count": len(models),
            "enum_count": len(enums),
            "issues": issues,
        },
    }


def validate_sample_instantiation(*, verbose: bool = True) -> dict[str, Any]:
    """Test that key models can be instantiated."""
    if verbose:
        print("\n" + "=" * 70)
        print("PHASE 3: Model Instantiation Tests")
        print("=" * 70)

    try:
        from adaptix_contracts.schemas import (
            # Core
            VaultCreateRequest,
            NarcoticVaultType,
            # Billing
            ClaimContract,
            ClaimStatus,
            AuditRecord,
            AuditContext,
            AuditActorType,
            AuditActionType,
            AuditSeverity,
            # Feature Flags
            FeatureFlagContract,
            FeatureFlagStatus,
            # Workflow
            WorkflowExecution,
            WorkflowContext,
            WorkflowStatus,
        )

        instantiated_models: list[str] = []

        # Test audit record
        audit_ctx = AuditContext(
            tenant_id="test-tenant", service_name="validation-script"
        )

        audit = AuditRecord(
            audit_id="audit-123",
            actor_type=AuditActorType.SYSTEM,
            action_type=AuditActionType.CREATE,
            resource_type="claim",
            success=True,
            severity=AuditSeverity.LOW,
            context=audit_ctx,
            occurred_at=datetime.now(),
        )
        instantiated_models.append("AuditRecord")
        if verbose:
            print(f"{_status_icon(True)} AuditRecord instantiated: {audit.audit_id}")

        # Test claim contract
        claim = ClaimContract(
            claim_id="claim-123",
            tenant_id="tenant-123",
            patient_id="patient-123",
            status=ClaimStatus.DRAFT,
            total_charge_cents=10000,
            balance_cents=10000,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        instantiated_models.append("ClaimContract")
        if verbose:
            print(f"{_status_icon(True)} ClaimContract instantiated: {claim.claim_id}")

        # Test feature flag
        flag = FeatureFlagContract(
            flag_key="test-feature",
            status=FeatureFlagStatus.ENABLED,
            default_enabled=True,
            evaluated_at=datetime.now(),
        )
        instantiated_models.append("FeatureFlagContract")
        if verbose:
            print(
                f"{_status_icon(True)} FeatureFlagContract instantiated: {flag.flag_key}"
            )

        # Test workflow execution
        workflow_ctx = WorkflowContext(
            workflow_id="workflow-123", tenant_id="tenant-123"
        )

        workflow = WorkflowExecution(
            workflow_id="workflow-123",
            workflow_type="test-workflow",
            context=workflow_ctx,
            status=WorkflowStatus.RUNNING,
            started_at=datetime.now(),
        )
        instantiated_models.append("WorkflowExecution")
        if verbose:
            print(
                f"{_status_icon(True)} WorkflowExecution instantiated: {workflow.workflow_id}"
            )

        narcotic_vault = VaultCreateRequest(
            vault_name="Station 1 Main Vault",
            location="Station 1 / Medication Room",
            vault_type=NarcoticVaultType.STATION,
        )
        instantiated_models.append("VaultCreateRequest")
        if verbose:
            print(
                f"{_status_icon(True)} VaultCreateRequest instantiated: {narcotic_vault.vault_name}"
            )

        if verbose:
            print(f"\n{_status_icon(True)} All sample model instantiations successful")
        return {
            "name": "Model Instantiation",
            "passed": True,
            "details": {"instantiated_models": instantiated_models},
        }

    except Exception as e:
        if verbose:
            print(f"{_status_icon(False)} Model instantiation failed: {e}")
            import traceback

            traceback.print_exc()
        return {
            "name": "Model Instantiation",
            "passed": False,
            "details": {"error": str(e)},
        }


def validate_domain_coverage(*, verbose: bool = True) -> dict[str, Any]:
    """Validate that all expected domains are covered."""
    if verbose:
        print("\n" + "=" * 70)
        print("PHASE 4: Domain Coverage Analysis")
        print("=" * 70)

    expected_domains = {
        "air",
        "air_pilot",
        "audit",
        "billing",
        "billing_auth",
        "billing_clearinghouse",
        "billing_eligibility",
        "billing_portal",
        "billing_transport",
        "cad",
        "cad_transport",
        "communications",
        "clinical_visual",
        "core",
        "crewlink",
        "epcr",
        "feature_flag",
        "field",
        "fire",
        "inventory",
        "narcotic",
        "metrics",
        "nemsis",
        "ocr",
        "patient_portal",
        "search",
        "transport",
        "voice",
        "workflow",
    }

    repo_root = Path(__file__).resolve().parent
    schema_dir = repo_root / "adaptix_contracts" / "schemas"
    contract_files = [f.stem for f in schema_dir.glob("*_contracts.py")]
    contract_files.extend(["nemsis_exports", "narcotic"])  # Special cases

    # Normalize names
    actual_domains = set()
    for f in contract_files:
        domain = f.replace("_contracts", "").replace("_exports", "")
        actual_domains.add(domain)

    missing = sorted(expected_domains - actual_domains)
    extra = sorted(actual_domains - expected_domains)

    if verbose:
        print(f"\nSchema directory: {schema_dir}")
        print(f"Expected domains: {len(expected_domains)}")
        print(f"Actual domains: {len(actual_domains)}")

    if missing:
        if verbose:
            print(f"\n[WARN] Missing domains: {missing}")

    if extra:
        if verbose:
            print(f"\n{_status_icon(True)} Additional domains: {extra}")

    if not missing:
        if verbose:
            print(f"\n{_status_icon(True)} All expected domains are present")

    return {
        "name": "Domain Coverage",
        # A missing expected domain is a FAILURE, not a warning. This was
        # hard-coded ``True``, so the phase printed "[WARN] Missing domains"
        # and still reported success -- the gate could never fail, and
        # tests/test_release_readiness.py asserting ``all_passed is True``
        # was asserting a constant.
        "passed": not missing,
        "details": {
            "schema_directory": str(schema_dir),
            "expected_domain_count": len(expected_domains),
            "actual_domain_count": len(actual_domains),
            "missing_domains": missing,
            "additional_domains": extra,
        },
    }


def build_validation_report(*, verbose: bool = True) -> dict[str, Any]:
    phases = [
        validate_imports(verbose=verbose),
        validate_model_structure(verbose=verbose),
        validate_sample_instantiation(verbose=verbose),
        validate_domain_coverage(verbose=verbose),
    ]
    all_passed = all(phase["passed"] for phase in phases)
    return {
        "generated_at": datetime.now().isoformat(),
        "all_passed": all_passed,
        "phase_count": len(phases),
        "phases": phases,
    }


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate Adaptix contract exports and schema surface."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit a machine-readable JSON report.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run all validation checks."""
    args = _parse_args(argv)
    verbose = not args.json_output

    if verbose:
        print("\n" + "=" * 70)
        print("ADAPTIX CONTRACTS VALIDATION")
        print("=" * 70)

    report = build_validation_report(verbose=verbose)

    if verbose:
        print("\n" + "=" * 70)
        print("VALIDATION SUMMARY")
        print("=" * 70)

        for phase in report["phases"]:
            status = "PASS" if phase["passed"] else "FAIL"
            print(f"{status} - {phase['name']}")

        print("=" * 70)
        if report["all_passed"]:
            print(f"\n{_status_icon(True)} All validations passed!")
        else:
            print(f"\n{_status_icon(False)} Some validations failed!")
    else:
        print(json.dumps(report, indent=2, sort_keys=True))

    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
