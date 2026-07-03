"""Deprecation contract for the legacy auth modules.

Per DEPRECATION_POLICY.md the import paths are preserved until 2.0.0 but must
emit DeprecationWarning so any accidental adoption is loud. These tests pin
both the warning and the preserved import surface.
"""

from __future__ import annotations

import importlib
import sys

import pytest


def _fresh_import(module_name: str):
    """Import the module in a way that re-triggers module-level warnings."""
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def test_security_auth_context_emits_deprecation_warning() -> None:
    with pytest.warns(DeprecationWarning, match="security.auth_context is deprecated"):
        mod = _fresh_import("adaptix_contracts.security.auth_context")
    # Import surface preserved until 2.0.0.
    assert hasattr(mod, "TenantAuthContext")
    assert hasattr(mod, "RolePermissionDecision")


def test_rbac_dependencies_emits_deprecation_warning() -> None:
    with pytest.warns(DeprecationWarning, match="rbac_dependencies is deprecated"):
        mod = _fresh_import("adaptix_contracts.auth.rbac_dependencies")
    # Import surface preserved until 2.0.0.
    assert hasattr(mod, "require_permission")
    assert hasattr(mod, "require_billing_access")


def test_canonical_surfaces_do_not_warn() -> None:
    # The canonical auth surfaces must import clean — no deprecation noise.
    import warnings as _w

    for name in (
        "adaptix_contracts.auth_contracts",
        "adaptix_contracts.gateway_signature",
        "adaptix_contracts.auth.module_entitlement_gate",
        "adaptix_contracts.auth.context",
    ):
        sys.modules.pop(name, None)
        with _w.catch_warnings():
            _w.simplefilter("error", DeprecationWarning)
            importlib.import_module(name)
