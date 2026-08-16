"""DocuSeal package contracts.

.. deprecated:: 2.10.0
    Non-canonical. TrustSign is the only active AdaptixCore
    electronic-signature authority — see README.md "Canonical signature
    provider" and DEPRECATION_POLICY.md. DocuSeal must not be used as an
    active, queued, underlying, fallback, shadow, or customer-facing signing
    engine (Adaptix-Governance ``registries/providers.yml`` ``trustsign``
    entry; Adaptix-Gateway README "Does NOT own"; Adaptix-Billing-Service
    ``TRUSTSIGN_BUILD_DIRECTIVE.md``).

    These two models were added in 1.5.0 (#94) alongside the other
    service-separation contracts and were never adopted. Re-verified
    2026-08-16: zero consumers of ``DocuSealPackageCreateRequest`` or
    ``DocuSealPackageResponse`` — repo-wide grep of this package, an
    org-wide GitHub code search across FusionEMS-Quantum-LLC, and a direct
    8-repo clone-and-grep spot check (Adaptix-DocuSeal-Service,
    Adaptix-TrustSign-Service, Adaptix-Gateway, Adaptix-Billing-Service,
    Adaptix-CAD-Service, Adaptix-Core-Service, Adaptix-Partner-Service,
    Adaptix-EPCR-Service) all found none. Notably, the standalone
    ``Adaptix-DocuSeal-Service`` itself does not import these contracts —
    it defines and uses its own local
    ``backend/app/schemas/docuseal_package.py`` instead.

    Per DEPRECATION_POLICY.md the import path is preserved and both models
    remain fully functional; a ``DeprecationWarning`` is raised on
    **instantiation** (not on import) — this module is eagerly imported by
    ``adaptix_contracts.schemas.__init__`` (and therefore by every consumer
    of ``adaptix_contracts``), so a module-level warning would fire for all
    pinned consumers rather than only the (currently zero) callers that
    construct these models. Replacement:
    :class:`adaptix_contracts.schemas.trustsign_contracts.SignaturePackageCreateRequest`
    / :class:`~adaptix_contracts.schemas.trustsign_contracts.SignaturePackageResponse`.
    Slated for removal in adaptix-contracts 3.0.0.

Typed request/response contracts for the newly-separated DocuSeal signing
integration service. Covers creation of a DocuSeal package and the service
response describing vendor state and availability.
"""

import warnings
from typing import Any

from pydantic import BaseModel, Field


def _warn_docuseal_deprecated(class_name: str) -> None:
    warnings.warn(
        f"adaptix_contracts.schemas.docuseal_contracts.{class_name} is "
        "deprecated and will be removed in adaptix-contracts 3.0.0. "
        "TrustSign is the only active AdaptixCore electronic-signature "
        "authority; DocuSeal is non-canonical. Use "
        "adaptix_contracts.schemas.trustsign_contracts "
        "(SignaturePackageCreateRequest / SignaturePackageResponse) instead. "
        "See README.md 'Canonical signature provider' and "
        "DEPRECATION_POLICY.md.",
        DeprecationWarning,
        stacklevel=3,
    )


class DocuSealPackageCreateRequest(BaseModel):
    """Request to create a DocuSeal package.

    .. deprecated:: 2.10.0
        Non-canonical — TrustSign is the only active AdaptixCore
        electronic-signature authority. Use
        :class:`~adaptix_contracts.schemas.trustsign_contracts.SignaturePackageCreateRequest`.
        Slated for removal in adaptix-contracts 3.0.0.
    """

    tenant_id: str = Field(..., description="Tenant ID")
    correlation_id: str = Field(..., description="Request correlation identifier")
    template_id: str = Field(..., description="DocuSeal template identifier")

    def model_post_init(self, context: Any, /) -> None:
        _warn_docuseal_deprecated("DocuSealPackageCreateRequest")


class DocuSealPackageResponse(BaseModel):
    """DocuSeal package response.

    .. deprecated:: 2.10.0
        Non-canonical — TrustSign is the only active AdaptixCore
        electronic-signature authority. Use
        :class:`~adaptix_contracts.schemas.trustsign_contracts.SignaturePackageResponse`.
        Slated for removal in adaptix-contracts 3.0.0.
    """

    package_id: str | None = Field(
        None, description="Created package identifier, if any"
    )
    vendor_state: str = Field(..., description="Vendor-reported package state")
    available: bool = Field(
        ..., description="Whether the DocuSeal service was available"
    )
    reason: str | None = Field(None, description="Reason for the current state, if any")
    tenant_id: str = Field(..., description="Tenant ID")
    correlation_id: str = Field(..., description="Request correlation identifier")

    def model_post_init(self, context: Any, /) -> None:
        _warn_docuseal_deprecated("DocuSealPackageResponse")
