"""Regression tests for the Adaptix contracts package surface."""

from __future__ import annotations

from enum import Enum
import importlib
from importlib import import_module
from pathlib import Path
import tomllib

import adaptix_contracts
from adaptix_contracts import schemas
from pydantic import BaseModel
import pytest


def _load_project_version() -> str:
    """Return the package version declared in ``pyproject.toml``."""

    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    project_config = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    return project_config["project"]["version"]


def _load_lockfile_self_version() -> str:
    """Return the version ``uv.lock`` records for this package's own entry.

    ``uv.lock`` carries an editable self-entry for ``adaptix-contracts``. A
    release that bumps ``pyproject.toml`` without re-locking leaves that entry
    naming the previous version, so a consumer resolving from the lock is told
    it has an older package than the tree actually contains.
    """

    lock_path = Path(__file__).resolve().parents[1] / "uv.lock"
    lock = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    for package in lock["package"]:
        if package["name"] == "adaptix-contracts":
            return package["version"]
    raise AssertionError("uv.lock has no self-entry for adaptix-contracts")


def test_package_version_matches_pyproject_metadata() -> None:
    """Keep runtime and packaging versions aligned for reproducible releases."""

    assert adaptix_contracts.__version__ == _load_project_version()


def test_lockfile_self_version_matches_pyproject_metadata() -> None:
    """The lock's own entry must move with every version bump.

    This exists because it did not. ``2.37.0`` (PR #213) bumped
    ``pyproject.toml`` and left ``uv.lock`` declaring ``2.36.0``, so the two
    files named different versions of the same tree. The bump before it
    (``2.36.0``, PR #211) did move the lock, so this is the convention being
    restored rather than a new rule.

    ``test_package_version_matches_pyproject_metadata`` could not catch it: it
    compares the runtime ``__version__`` against ``pyproject.toml`` and never
    reads the lock.
    """

    assert _load_lockfile_self_version() == _load_project_version()


def test_schema_public_exports_are_unique_and_resolvable() -> None:
    """Ensure every declared public export exists exactly once."""

    assert len(schemas.__all__) == len(set(schemas.__all__))
    for symbol_name in schemas.__all__:
        assert hasattr(schemas, symbol_name), f"Missing schema export: {symbol_name}"


def test_package_root_reexports_schema_symbols() -> None:
    """Expose the same contract surface at the package root and schema module."""

    assert adaptix_contracts.__all__ == schemas.__all__
    for symbol_name in schemas.__all__:
        assert getattr(adaptix_contracts, symbol_name) is getattr(schemas, symbol_name)


def test_package_root_import_fails_loudly_for_missing_schema_exports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Protect import surface from stale or drifting ``schemas.__all__`` entries."""

    broken_export = "__missing_schema_export_for_test__"
    original_exports = list(schemas.__all__)
    monkeypatch.setattr(schemas, "__all__", [*original_exports, broken_export])

    with pytest.raises(ImportError, match=broken_export):
        importlib.reload(adaptix_contracts)

    monkeypatch.setattr(schemas, "__all__", original_exports)
    importlib.reload(adaptix_contracts)


def test_every_schema_module_imports_cleanly() -> None:
    """Prevent orphaned schema modules that import only in selective environments."""

    schema_dir = Path(__file__).resolve().parents[1] / "adaptix_contracts" / "schemas"
    for schema_path in schema_dir.glob("*.py"):
        if schema_path.name == "__init__.py":
            continue
        import_module(f"adaptix_contracts.schemas.{schema_path.stem}")


def test_all_exported_models_can_emit_json_schema() -> None:
    """Guarantee the contract surface remains introspectable for downstream tooling."""

    for symbol_name in schemas.__all__:
        symbol = getattr(schemas, symbol_name)
        if isinstance(symbol, type) and issubclass(symbol, BaseModel):
            emitted_schema = symbol.model_json_schema()
            assert isinstance(emitted_schema, dict)
            assert emitted_schema
            assert (
                "title" in emitted_schema
                or "properties" in emitted_schema
                or "$defs" in emitted_schema
                or "type" in emitted_schema
            ), f"Unexpected JSON schema shape for {symbol_name}"


def test_all_exported_enums_have_unique_values() -> None:
    """Protect enum consumers from ambiguous serialized values."""

    for symbol_name in schemas.__all__:
        symbol = getattr(schemas, symbol_name)
        if isinstance(symbol, type) and issubclass(symbol, Enum):
            values = [member.value for member in symbol]
            assert len(values) == len(set(values)), (
                f"Duplicate enum values in {symbol_name}"
            )


def test_contract_onboarding_surface_is_exported() -> None:
    """Adaptix Contracts must expose contract onboarding lifecycle schemas."""
    required = {
        "ContractLifecycleStatus",
        "ContractIntakeRequest",
        "ContractRecord",
        "TrustSignExecutionRequest",
        "TrustSignExecutionResponse",
        "TrustSignCallbackEvent",
        "DropboxSignExecutionRequest",
        "DropboxSignExecutionResponse",
        "DropboxSignCallbackEvent",
        "ContractActivationRequest",
        "ContractActivationResponse",
        "ContractStatusChangedEvent",
    }
    for name in required:
        assert name in schemas.__all__
        assert hasattr(schemas, name)


def test_legal_execution_surface_is_exported() -> None:
    """Legal execution enums must be available from adaptix_contracts.schemas."""
    required = {
        "ContractType",
        "ContractStatus",
        "TenantContractStatusMap",
        "ContractSignatureEvent",
        "ContractAccessCheckRequest",
        "ContractAccessCheckResponse",
    }
    for name in required:
        assert name in schemas.__all__
        assert hasattr(schemas, name)
        assert getattr(adaptix_contracts, name) is getattr(schemas, name)


def test_legal_execution_statuses_cover_execution_lifecycle() -> None:
    required_statuses = {
        "draft",
        "ready_for_review",
        "ready_for_signature",
        "signed_by_counterparty",
        "countersigned",
        "executed",
        "superseded",
        "archived",
    }
    actual = {status.value for status in schemas.ContractStatus}
    assert required_statuses.issubset(actual)


def test_contract_onboarding_statuses_cover_signature_lifecycle() -> None:
    required_statuses = {
        "draft",
        "sent_for_signature",
        "viewed",
        "signed_by_counterparty",
        "countersigned",
        "executed",
        "voided",
        "superseded",
        "archived",
    }
    actual = {status.value for status in schemas.ContractLifecycleStatus}
    assert required_statuses.issubset(actual)
