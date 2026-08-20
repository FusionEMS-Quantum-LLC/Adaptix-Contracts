"""Adaptix error envelope contracts."""

from adaptix_contracts.errors.envelope import (
    AdaptixErrorCode,
    AdaptixValidationErrorDetail,
    AdaptixProviderErrorDetail,
    AdaptixTraceContext,
    AdaptixErrorEnvelope,
    AdaptixErrorEnvelopeBase,
)

__all__ = [
    "AdaptixErrorCode",
    "AdaptixValidationErrorDetail",
    "AdaptixProviderErrorDetail",
    "AdaptixTraceContext",
    "AdaptixErrorEnvelope",
    "AdaptixErrorEnvelopeBase",
]
