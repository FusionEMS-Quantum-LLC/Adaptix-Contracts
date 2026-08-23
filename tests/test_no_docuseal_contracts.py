"""3.0.0: DocuSeal contracts are gone. TrustSign is the only signer."""

from __future__ import annotations

import importlib
import pkgutil

import pytest


def test_docuseal_module_is_absent() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("adaptix_contracts.schemas.docuseal_contracts")


def test_schemas_package_does_not_export_docuseal() -> None:
    schemas = importlib.import_module("adaptix_contracts.schemas")
    assert not hasattr(schemas, "DocuSealPackageCreateRequest")
    assert not hasattr(schemas, "DocuSealPackageResponse")
    names = set(getattr(schemas, "__all__", ()))
    assert "DocuSealPackageCreateRequest" not in names
    assert "DocuSealPackageResponse" not in names


def test_no_docuseal_module_on_disk() -> None:
    schemas = importlib.import_module("adaptix_contracts.schemas")
    found = [
        m.name
        for m in pkgutil.iter_modules(schemas.__path__)
        if "docuseal" in m.name.lower()
    ]
    assert found == []
