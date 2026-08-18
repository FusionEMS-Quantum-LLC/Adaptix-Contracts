"""Service-specific error types for the Community Risk Reduction service.

Two layers are provided, matching the two error surfaces used elsewhere in
Adaptix-Contracts:

1. **Exception classes.** In-process CRR code raises these when something goes
   wrong. They all inherit from :class:`CrrError`, a single project-wide base so
   consumers can ``except CrrError`` and catch every CRR failure.

2. **Envelope factories.** When a CRR failure needs to cross a service boundary
   as an HTTP or Signal Bus response, the :func:`to_error_envelope` helper wraps
   the exception in the canonical
   :class:`adaptix_contracts.errors.envelope.AdaptixErrorEnvelope`. That
   envelope is the platform's shared error contract; CRR does not invent its
   own wire format.
"""

from __future__ import annotations

from enum import StrEnum

from adaptix_contracts.errors.envelope import (
    AdaptixErrorCode,
    AdaptixErrorEnvelope,
    AdaptixTraceContext,
)


class CrrErrorCode(StrEnum):
    """CRR-specific machine-readable error identifiers.

    These are additive to :class:`AdaptixErrorCode` — they carry the CRR
    subdomain a caller needs to reason about the failure, while the wire
    envelope still uses the platform-wide :class:`AdaptixErrorCode`
    enumeration.
    """

    CAMPAIGN_NOT_FOUND = "crr.campaign.not_found"
    CAMPAIGN_ALREADY_LAUNCHED = "crr.campaign.already_launched"
    CAMPAIGN_INVALID_STATE = "crr.campaign.invalid_state"

    HOUSEHOLD_NOT_FOUND = "crr.household.not_found"
    HOUSEHOLD_DUPLICATE = "crr.household.duplicate"

    INTERVENTION_NOT_FOUND = "crr.intervention.not_found"
    INTERVENTION_TYPE_UNSUPPORTED = "crr.intervention.type_unsupported"
    INTERVENTION_MISSING_TARGET = "crr.intervention.missing_target"

    OUTCOME_COHORT_NOT_FOUND = "crr.outcome.cohort_not_found"
    OUTCOME_MEASUREMENT_WINDOW_INVALID = "crr.outcome.measurement_window_invalid"

    ISO_PACKAGE_INSUFFICIENT_EVIDENCE = "crr.iso.insufficient_evidence"
    ISO_PACKAGE_GENERATION_FAILED = "crr.iso.generation_failed"


class CrrError(Exception):
    """Base class for every CRR service exception.

    Instances carry the platform-wide :attr:`platform_code` (mapped to
    :class:`AdaptixErrorCode`) *and* the CRR-specific :attr:`code` so callers
    can either handle the failure generically or branch on the CRR subdomain.
    """

    #: Default platform error code emitted when the concrete subclass does not
    #: override it. Subclasses SHOULD override this with the most specific
    #: :class:`AdaptixErrorCode` value that fits.
    platform_code: AdaptixErrorCode = AdaptixErrorCode.INTERNAL_ERROR

    #: Default CRR-specific error code. Every concrete subclass MUST override.
    code: CrrErrorCode

    def __init__(
        self,
        message: str,
        *,
        code: CrrErrorCode | None = None,
        detail: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        self.detail = detail

    def to_error_envelope(
        self, trace: AdaptixTraceContext | None = None
    ) -> AdaptixErrorEnvelope:
        """Return the canonical wire envelope for this exception."""

        detail_parts: list[str] = []
        if self.detail:
            detail_parts.append(self.detail)
        # Always surface the CRR-specific code on the envelope's ``detail``
        # field so a consumer that only sees the wire format still knows which
        # CRR subdomain reported the failure.
        detail_parts.append(f"crr_code={self.code.value}")
        return AdaptixErrorEnvelope(
            error_code=self.platform_code,
            message=self.message,
            detail=" | ".join(detail_parts),
            trace=trace,
        )


# ---------------------------------------------------------------------------
# Campaign errors
# ---------------------------------------------------------------------------


class CrrCampaignNotFoundError(CrrError):
    platform_code = AdaptixErrorCode.NOT_FOUND
    code = CrrErrorCode.CAMPAIGN_NOT_FOUND


class CrrCampaignAlreadyLaunchedError(CrrError):
    platform_code = AdaptixErrorCode.CONFLICT
    code = CrrErrorCode.CAMPAIGN_ALREADY_LAUNCHED


class CrrCampaignInvalidStateError(CrrError):
    platform_code = AdaptixErrorCode.INVALID_STATE_TRANSITION
    code = CrrErrorCode.CAMPAIGN_INVALID_STATE


# ---------------------------------------------------------------------------
# Household errors
# ---------------------------------------------------------------------------


class CrrHouseholdNotFoundError(CrrError):
    platform_code = AdaptixErrorCode.NOT_FOUND
    code = CrrErrorCode.HOUSEHOLD_NOT_FOUND


class CrrHouseholdDuplicateError(CrrError):
    platform_code = AdaptixErrorCode.DUPLICATE_RECORD
    code = CrrErrorCode.HOUSEHOLD_DUPLICATE


# ---------------------------------------------------------------------------
# Intervention errors
# ---------------------------------------------------------------------------


class CrrInterventionNotFoundError(CrrError):
    platform_code = AdaptixErrorCode.NOT_FOUND
    code = CrrErrorCode.INTERVENTION_NOT_FOUND


class CrrInterventionTypeUnsupportedError(CrrError):
    platform_code = AdaptixErrorCode.INVALID_VALUE
    code = CrrErrorCode.INTERVENTION_TYPE_UNSUPPORTED


class CrrInterventionMissingTargetError(CrrError):
    """Raised when neither a household nor a community_group target is given."""

    platform_code = AdaptixErrorCode.VALIDATION_FAILED
    code = CrrErrorCode.INTERVENTION_MISSING_TARGET


# ---------------------------------------------------------------------------
# Outcome errors
# ---------------------------------------------------------------------------


class CrrOutcomeCohortNotFoundError(CrrError):
    platform_code = AdaptixErrorCode.NOT_FOUND
    code = CrrErrorCode.OUTCOME_COHORT_NOT_FOUND


class CrrOutcomeMeasurementWindowInvalidError(CrrError):
    platform_code = AdaptixErrorCode.VALIDATION_FAILED
    code = CrrErrorCode.OUTCOME_MEASUREMENT_WINDOW_INVALID


# ---------------------------------------------------------------------------
# ISO credit-package errors
# ---------------------------------------------------------------------------


class CrrIsoPackageInsufficientEvidenceError(CrrError):
    platform_code = AdaptixErrorCode.WORKFLOW_BLOCKED
    code = CrrErrorCode.ISO_PACKAGE_INSUFFICIENT_EVIDENCE


class CrrIsoPackageGenerationFailedError(CrrError):
    platform_code = AdaptixErrorCode.EXPORT_FAILED
    code = CrrErrorCode.ISO_PACKAGE_GENERATION_FAILED


__all__ = [
    "CrrCampaignAlreadyLaunchedError",
    "CrrCampaignInvalidStateError",
    "CrrCampaignNotFoundError",
    "CrrError",
    "CrrErrorCode",
    "CrrHouseholdDuplicateError",
    "CrrHouseholdNotFoundError",
    "CrrInterventionMissingTargetError",
    "CrrInterventionNotFoundError",
    "CrrInterventionTypeUnsupportedError",
    "CrrIsoPackageGenerationFailedError",
    "CrrIsoPackageInsufficientEvidenceError",
    "CrrOutcomeCohortNotFoundError",
    "CrrOutcomeMeasurementWindowInvalidError",
]
