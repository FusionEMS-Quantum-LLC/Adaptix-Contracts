"""Deprecation contract for the legacy ``common`` modules.

Per DEPRECATION_POLICY.md the import path is preserved until the next major
version but must emit ``DeprecationWarning`` so any accidental adoption is
loud. Mirrors the pattern in ``tests/test_deprecated_auth_modules.py``.
"""

from __future__ import annotations

import importlib
import sys

import pytest


def _fresh_import(module_name: str):
    """Import the module in a way that re-triggers module-level warnings."""
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def test_common_error_envelope_emits_deprecation_warning() -> None:
    with pytest.warns(DeprecationWarning, match="common.error_envelope is deprecated"):
        mod = _fresh_import("adaptix_contracts.common.error_envelope")
    # Import surface preserved until the next major version.
    assert hasattr(mod, "ErrorEnvelope")
    assert hasattr(mod, "ErrorCode")
    assert hasattr(mod, "CredentialGatedResponse")


def test_canonical_error_envelopes_do_not_warn() -> None:
    # The two live envelope shapes must import clean — no deprecation noise.
    import warnings as _w

    for name in (
        "adaptix_contracts.error_contracts",
        "adaptix_contracts.errors.envelope",
    ):
        sys.modules.pop(name, None)
        with _w.catch_warnings():
            _w.simplefilter("error", DeprecationWarning)
            importlib.import_module(name)
