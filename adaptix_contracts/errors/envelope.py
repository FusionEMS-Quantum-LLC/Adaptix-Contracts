"""
Adaptix Shared Error Envelope Contracts
=========================================
All backend services MUST use these models for error responses.
No raw exception text may be returned to clients.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional, Self
from pydantic import BaseModel, Field
import uuid
from datetime import datetime, timezone


class AdaptixErrorCode(str, Enum):
    """Canonical error codes for Adaptix platform."""

    # Auth errors
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    TOKEN_EXPIRED = "token_expired"
    TOKEN_INVALID = "token_invalid"
    SESSION_REVOKED = "session_revoked"
    TENANT_INACTIVE = "tenant_inactive"
    INSUFFICIENT_ROLE = "insufficient_role"
    MODULE_NOT_ENABLED = "module_not_enabled"

    # Validation errors
    VALIDATION_FAILED = "validation_failed"
    REQUIRED_FIELD_MISSING = "required_field_missing"
    INVALID_VALUE = "invalid_value"
    DUPLICATE_RECORD = "duplicate_record"
    INVALID_STATE_TRANSITION = "invalid_state_transition"
    CONSTRAINT_VIOLATION = "constraint_violation"

    # Not found
    NOT_FOUND = "not_found"
    RECORD_NOT_FOUND = "record_not_found"

    # Conflict
    CONFLICT = "conflict"
    ALREADY_EXISTS = "already_exists"

    # Provider errors
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_ERROR = "provider_error"
    CREDENTIAL_GATED = "credential_gated"
    NOT_CONFIGURED = "not_configured"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"

    # Business logic errors
    MEDICAL_NECESSITY_BLOCKED = "medical_necessity_blocked"
    CLAIM_NOT_READY = "claim_not_ready"
    EXPORT_FAILED = "export_failed"
    VALIDATION_PIPELINE_FAILED = "validation_pipeline_failed"
    ARTIFACT_UNAVAILABLE = "artifact_unavailable"
    WORKFLOW_BLOCKED = "workflow_blocked"

    # System errors
    INTERNAL_ERROR = "internal_error"
    DATABASE_ERROR = "database_error"
    MIGRATION_REQUIRED = "migration_required"
    SERVICE_UNAVAILABLE = "service_unavailable"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"

    # Audit/compliance
    AUDIT_WRITE_FAILED = "audit_write_failed"
    PHI_ACCESS_DENIED = "phi_access_denied"


class AdaptixValidationErrorDetail(BaseModel):
    """Detail for a single field validation failure."""

    field: str
    message: str
    value: Any | None = None
    code: str = "invalid_value"


class AdaptixProviderErrorDetail(BaseModel):
    """Detail for a provider integration failure."""

    provider: str
    status: str  # provider_unavailable | credential_gated | not_configured | error
    message: str
    provider_code: str | None = None
    retryable: bool = False


class AdaptixTraceContext(BaseModel):
    """Trace context for correlating errors across services."""

    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str | None = None
    causation_id: str | None = None
    tenant_id: str | None = None
    actor_id: str | None = None
    service_name: str | None = None
    route: str | None = None
    duration_ms: float | None = None


class AdaptixErrorEnvelopeBase(BaseModel):
    """Every part of the Adaptix error envelope EXCEPT ``error_code``.

    Domain subpackages (Edge, QA) need an envelope whose ``error_code`` accepts
    their own code enum in addition to the platform-wide one. Expressing that by
    subclassing :class:`AdaptixErrorEnvelope` and re-declaring ``error_code`` as
    a wider union is a Liskov violation — a function handed an
    ``AdaptixErrorEnvelope`` could receive a domain code it cannot handle — and
    the type checker rejects it.

    The two available alternatives are both worse:

    * widening ``AdaptixErrorEnvelope.error_code`` to include domain codes would
      make EVERY service's envelope accept Edge and QA codes at runtime, since
      Pydantic validates from the annotation. That weakens validation
      platform-wide, and it inverts the import direction — ``errors.envelope``
      would have to import from the subpackages that import it.
    * making the envelope generic in its code type is a remodel of a contract
      with nine subclasses and every downstream consumer.

    So the shared parts live here and each concrete envelope declares its own
    ``error_code``. The domain envelopes become SIBLINGS of
    :class:`AdaptixErrorEnvelope` rather than subclasses. Fields, validation,
    the factory helpers and ``to_http_response`` are all inherited unchanged, so
    every concrete class behaves exactly as it did before.
    """

    success: bool = False
    message: str
    detail: str | None = None
    validation_errors: Optional[list[AdaptixValidationErrorDetail]] = None
    provider_error: AdaptixProviderErrorDetail | None = None
    trace: AdaptixTraceContext | None = None
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @classmethod
    def unauthorized(
        cls,
        message: str = "Authentication required",
        trace: AdaptixTraceContext | None = None,
    ) -> Self:
        return cls(
            error_code=AdaptixErrorCode.UNAUTHORIZED,
            message=message,
            trace=trace,
        )

    @classmethod
    def forbidden(
        cls,
        message: str = "Access denied",
        trace: AdaptixTraceContext | None = None,
    ) -> Self:
        return cls(
            error_code=AdaptixErrorCode.FORBIDDEN,
            message=message,
            trace=trace,
        )

    @classmethod
    def not_found(
        cls,
        resource: str,
        trace: AdaptixTraceContext | None = None,
    ) -> Self:
        return cls(
            error_code=AdaptixErrorCode.NOT_FOUND,
            message=f"{resource} not found",
            trace=trace,
        )

    @classmethod
    def validation_failed(
        cls,
        errors: list[AdaptixValidationErrorDetail],
        message: str = "Validation failed",
        trace: AdaptixTraceContext | None = None,
    ) -> Self:
        return cls(
            error_code=AdaptixErrorCode.VALIDATION_FAILED,
            message=message,
            validation_errors=errors,
            trace=trace,
        )

    @classmethod
    def provider_unavailable(
        cls,
        provider: str,
        message: str,
        retryable: bool = False,
        trace: AdaptixTraceContext | None = None,
    ) -> Self:
        return cls(
            error_code=AdaptixErrorCode.PROVIDER_UNAVAILABLE,
            message=f"Provider unavailable: {provider}",
            provider_error=AdaptixProviderErrorDetail(
                provider=provider,
                status="provider_unavailable",
                message=message,
                retryable=retryable,
            ),
            trace=trace,
        )

    @classmethod
    def credential_gated(
        cls,
        provider: str,
        trace: AdaptixTraceContext | None = None,
    ) -> Self:
        return cls(
            error_code=AdaptixErrorCode.CREDENTIAL_GATED,
            message=f"Provider {provider} requires credentials not configured in this environment",
            provider_error=AdaptixProviderErrorDetail(
                provider=provider,
                status="credential_gated",
                message="Credentials required but not configured",
                retryable=False,
            ),
            trace=trace,
        )

    @classmethod
    def internal_error(
        cls,
        message: str = "An internal error occurred",
        trace: AdaptixTraceContext | None = None,
    ) -> Self:
        return cls(
            error_code=AdaptixErrorCode.INTERNAL_ERROR,
            message=message,
            trace=trace,
        )

    def to_http_response(self) -> dict[str, Any]:
        """Return dict suitable for FastAPI JSONResponse."""
        return self.model_dump(exclude_none=True)


class AdaptixErrorEnvelope(AdaptixErrorEnvelopeBase):
    """
    Standard error response envelope for ALL Adaptix services.

    Every error response MUST use this model.
    No raw exception text, stack traces, or internal details may be returned.

    ``error_code`` accepts platform-wide codes only. A domain subpackage that
    also needs its own codes subclasses :class:`AdaptixErrorEnvelopeBase` and
    declares the wider union there — see ``edge.errors.EdgeErrorEnvelope``.
    """

    error_code: AdaptixErrorCode
