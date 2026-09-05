"""DEPRECATED — do not adopt. Scheduled for removal in adaptix-contracts 6.0.0.

Audit 2026-09-05: no service in the Adaptix polyrepo imports
``common.error_envelope`` (org-wide code search for
``common.error_envelope`` / ``CredentialGatedResponse``: zero hits), and
nothing inside this package re-exports or constructs it either.

AdaptixCore has exactly TWO real, live, in-production error-envelope shapes
today — deliberately not collapsed to one by this deprecation, because both
are genuinely load-bearing at different layers and unifying them is a
separate, larger correction:

* ``adaptix_contracts.error_contracts.ErrorCode`` / ``make_error_response``
  — ``{"error": {"code": "VALIDATION_ERROR", "message": ..., "details": ...,
  "trace_id": ...}}``. Verified live: Billing/Core/CAD/EPCR/NEMSIS/Labor each
  import this directly into their global FastAPI exception handler
  (``*_app/error_handlers.py``), so it is what those services return for
  every unhandled and mapped HTTP error today.
* ``adaptix_contracts.errors.envelope.AdaptixErrorEnvelope`` —
  ``{"error_code": ..., "message": ..., "success": false, ...}``. Verified
  live at the Gateway edge: ``Adaptix-Gateway/backend/app/middleware/
  cognito_auth.py::_error_response`` hand-constructs this exact flat shape
  for 401s raised before a request reaches a domain service (Gateway does
  not depend on this package), and ``Adaptix-Web-App/src/lib/
  error-handler.ts`` parses ``body.error_code`` first specifically because
  of this. Every per-domain ``errors.py`` inside this package (cct, citizen,
  crr, edge, family_bridge, hydrant, mih, preplan, qa, qhin, wildland, xr)
  also derives from it.

These two shapes are structurally incompatible at the top level (nested
``error.code`` vs. flat ``error_code``); the frontend parser above is
defensive specifically because nobody has unified them. That is a real,
separate, cross-repo contract-duplication defect — this module is not it.
``common.error_envelope.ErrorEnvelope`` (``error: str, code, detail, field,
correlation_id, tenant_id``; 13 lowercase ``ErrorCode`` members) matches
NEITHER live shape and has zero consumers of either, so unlike the two
above it is pure dead weight, not a second load-bearing convention.

Per DEPRECATION_POLICY.md the import path is preserved (with a
DeprecationWarning) until the next major version.
"""

import warnings
from enum import Enum
from typing import Optional
from pydantic import BaseModel

warnings.warn(
    "adaptix_contracts.common.error_envelope is deprecated, has zero known "
    "importers fleet-wide, and will be removed in adaptix-contracts 6.0.0. "
    "Use adaptix_contracts.error_contracts.make_error_response (domain-service "
    "internal errors) or adaptix_contracts.errors.envelope.AdaptixErrorEnvelope "
    "(Gateway-edge errors) depending on which layer is raising the error.",
    DeprecationWarning,
    stacklevel=2,
)


class ErrorCode(str, Enum):
    VALIDATION_ERROR = "validation_error"
    NOT_FOUND = "not_found"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    CONFLICT = "conflict"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    CREDENTIAL_GATED = "credential_gated"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    VALIDATION_FAILED = "validation_failed"
    EXPORT_FAILED = "export_failed"
    ARTIFACT_UNAVAILABLE = "artifact_unavailable"
    NOT_CONFIGURED = "not_configured"
    INTERNAL_ERROR = "internal_error"


class ErrorEnvelope(BaseModel):
    error: str
    code: ErrorCode
    detail: Optional[str] = None
    field: Optional[str] = None
    correlation_id: Optional[str] = None
    tenant_id: Optional[str] = None


class CredentialGatedResponse(BaseModel):
    status: str = "credential_gated"
    provider: str
    reason: str
    configuration_required: str
    affected_features: list[str] = []
