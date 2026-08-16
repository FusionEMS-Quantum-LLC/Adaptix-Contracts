"""Deprecation contract for the legacy DocuSeal package contracts.

TrustSign is the only active AdaptixCore electronic-signature authority
(see README.md "Canonical signature provider" and DEPRECATION_POLICY.md).
``docuseal_contracts`` is non-canonical and has zero consumers (re-verified
2026-08-16), so it is deprecated but not removed: the import path is
preserved and both models remain fully functional.

Because this module is eagerly imported by ``adaptix_contracts.schemas``
(and therefore by every one of the ~26 pinned consumers of
``adaptix_contracts``, whether or not they touch DocuSeal), the
DeprecationWarning fires on **instantiation**, not on import — unlike the
``security.auth_context`` / ``auth.rbac_dependencies`` precedent in
``test_deprecated_auth_modules.py``, which are opt-in modules nobody
imports by default. These tests pin that distinction, the warning itself,
the preserved legacy shape, and the warning-free canonical replacement.
"""

from __future__ import annotations

import importlib
import sys
import warnings

import pytest

from adaptix_contracts.schemas.docuseal_contracts import (
    DocuSealPackageCreateRequest,
    DocuSealPackageResponse,
)
from adaptix_contracts.schemas.trustsign_contracts import (
    SignaturePackageCreateRequest,
    SignaturePackageResponse,
)


def test_docuseal_package_create_request_warns_on_instantiation() -> None:
    with pytest.warns(
        DeprecationWarning, match="DocuSealPackageCreateRequest is deprecated"
    ):
        request = DocuSealPackageCreateRequest(
            tenant_id="tenant-1",
            correlation_id="corr-1",
            template_id="template-1",
        )
    # Legacy shape still validates during the overlap period.
    assert request.tenant_id == "tenant-1"
    assert request.correlation_id == "corr-1"
    assert request.template_id == "template-1"


def test_docuseal_package_response_warns_on_instantiation() -> None:
    with pytest.warns(
        DeprecationWarning, match="DocuSealPackageResponse is deprecated"
    ):
        response = DocuSealPackageResponse(
            vendor_state="created",
            available=True,
            tenant_id="tenant-1",
            correlation_id="corr-1",
        )
    # Legacy shape still validates during the overlap period.
    assert response.vendor_state == "created"
    assert response.available is True
    assert response.package_id is None
    assert response.reason is None


def test_docuseal_deprecation_warning_names_trustsign_replacement_and_removal_version() -> (
    None
):
    with pytest.warns(DeprecationWarning) as records:
        DocuSealPackageCreateRequest(
            tenant_id="tenant-1", correlation_id="corr-1", template_id="template-1"
        )
    message = str(records[0].message)
    assert "trustsign_contracts" in message
    assert "3.0.0" in message


def test_importing_docuseal_contracts_module_does_not_warn() -> None:
    """Import-time must stay silent.

    This module is eagerly imported by ``adaptix_contracts.schemas`` on
    behalf of every consumer of the package, not just DocuSeal callers — a
    module-level warning would spam all 26 pinned consumer repos. Only
    instantiation may warn.
    """
    sys.modules.pop("adaptix_contracts.schemas.docuseal_contracts", None)
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        importlib.import_module("adaptix_contracts.schemas.docuseal_contracts")


def test_trustsign_replacement_instantiates_without_warning() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        request = SignaturePackageCreateRequest(
            tenant_id="tenant-1",
            correlation_id="corr-1",
            document_ref="doc-1",
        )
        response = SignaturePackageResponse(
            status="created",
            signed=False,
            available=True,
            tenant_id="tenant-1",
            correlation_id="corr-1",
        )
    assert request.tenant_id == "tenant-1"
    assert response.status == "created"
