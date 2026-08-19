"""Service-specific error types for the Critical Care Transport (CCT) service.

Two layers are provided, matching the two error surfaces used elsewhere in
Adaptix-Contracts:

1. **Exception classes.** In-process CCT code raises these when something goes
   wrong. They all inherit from :class:`CctError`, a single project-wide base so
   consumers can ``except CctError`` and catch every CCT failure.

2. **Envelope factories.** When a CCT failure needs to cross a service boundary
   as an HTTP or Signal Bus response, the :meth:`CctError.to_error_envelope`
   helper wraps the exception in the canonical
   :class:`adaptix_contracts.errors.envelope.AdaptixErrorEnvelope`. That
   envelope is the platform's shared error contract; CCT does not invent its
   own wire format.
"""

from __future__ import annotations

from enum import StrEnum

from adaptix_contracts.errors.envelope import (
    AdaptixErrorCode,
    AdaptixErrorEnvelope,
    AdaptixTraceContext,
)


class CctErrorCode(StrEnum):
    """CCT-specific machine-readable error identifiers.

    These are additive to :class:`AdaptixErrorCode` — they carry the CCT
    subdomain a caller needs to reason about the failure, while the wire
    envelope still uses the platform-wide :class:`AdaptixErrorCode`
    enumeration.
    """

    MISSION_NOT_FOUND = "cct.mission.not_found"
    MISSION_ALREADY_ACCEPTED = "cct.mission.already_accepted"
    MISSION_INVALID_STATE = "cct.mission.invalid_state"

    CREW_CREDENTIAL_INSUFFICIENT = "cct.crew.credential_insufficient"
    CREW_NOT_ASSIGNED = "cct.crew.not_assigned"

    LOADOUT_NOT_FOUND = "cct.loadout.not_found"
    LOADOUT_INCOMPLETE = "cct.loadout.incomplete"

    HANDOFF_NOT_FOUND = "cct.handoff.not_found"
    HANDOFF_PHYSICIAN_MISSING = "cct.handoff.physician_missing"

    CAMTS_CHECKLIST_INCOMPLETE = "cct.camts.checklist_incomplete"
    CAMTS_STANDARD_UNSATISFIED = "cct.camts.standard_unsatisfied"


class CctError(Exception):
    """Base class for every CCT service exception.

    Instances carry the platform-wide :attr:`platform_code` (mapped to
    :class:`AdaptixErrorCode`) *and* the CCT-specific :attr:`code` so callers
    can either handle the failure generically or branch on the CCT subdomain.
    """

    #: Default platform error code emitted when the concrete subclass does not
    #: override it. Subclasses SHOULD override this with the most specific
    #: :class:`AdaptixErrorCode` value that fits.
    platform_code: AdaptixErrorCode = AdaptixErrorCode.INTERNAL_ERROR

    #: Default CCT-specific error code. Every concrete subclass MUST override.
    code: CctErrorCode

    def __init__(
        self,
        message: str,
        *,
        code: CctErrorCode | None = None,
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
        # Always surface the CCT-specific code on the envelope's ``detail``
        # field so a consumer that only sees the wire format still knows which
        # CCT subdomain reported the failure.
        detail_parts.append(f"cct_code={self.code.value}")
        return AdaptixErrorEnvelope(
            error_code=self.platform_code,
            message=self.message,
            detail=" | ".join(detail_parts),
            trace=trace,
        )


# ---------------------------------------------------------------------------
# Mission errors
# ---------------------------------------------------------------------------


class CctMissionNotFoundError(CctError):
    platform_code = AdaptixErrorCode.NOT_FOUND
    code = CctErrorCode.MISSION_NOT_FOUND


class CctMissionAlreadyAcceptedError(CctError):
    platform_code = AdaptixErrorCode.CONFLICT
    code = CctErrorCode.MISSION_ALREADY_ACCEPTED


class CctMissionInvalidStateError(CctError):
    platform_code = AdaptixErrorCode.INVALID_STATE_TRANSITION
    code = CctErrorCode.MISSION_INVALID_STATE


# ---------------------------------------------------------------------------
# Crew errors
# ---------------------------------------------------------------------------


class CctCrewCredentialInsufficientError(CctError):
    """Raised when an assigned crew member's credential level does not meet
    the mission's ``required_credential_level``."""

    platform_code = AdaptixErrorCode.VALIDATION_FAILED
    code = CctErrorCode.CREW_CREDENTIAL_INSUFFICIENT


class CctCrewNotAssignedError(CctError):
    platform_code = AdaptixErrorCode.WORKFLOW_BLOCKED
    code = CctErrorCode.CREW_NOT_ASSIGNED


# ---------------------------------------------------------------------------
# Equipment loadout errors
# ---------------------------------------------------------------------------


class CctLoadoutNotFoundError(CctError):
    platform_code = AdaptixErrorCode.NOT_FOUND
    code = CctErrorCode.LOADOUT_NOT_FOUND


class CctLoadoutIncompleteError(CctError):
    platform_code = AdaptixErrorCode.VALIDATION_FAILED
    code = CctErrorCode.LOADOUT_INCOMPLETE


# ---------------------------------------------------------------------------
# Handoff errors
# ---------------------------------------------------------------------------


class CctHandoffNotFoundError(CctError):
    platform_code = AdaptixErrorCode.NOT_FOUND
    code = CctErrorCode.HANDOFF_NOT_FOUND


class CctHandoffPhysicianMissingError(CctError):
    platform_code = AdaptixErrorCode.VALIDATION_FAILED
    code = CctErrorCode.HANDOFF_PHYSICIAN_MISSING


# ---------------------------------------------------------------------------
# CAMTS accreditation errors
# ---------------------------------------------------------------------------


class CctCamtsChecklistIncompleteError(CctError):
    platform_code = AdaptixErrorCode.WORKFLOW_BLOCKED
    code = CctErrorCode.CAMTS_CHECKLIST_INCOMPLETE


class CctCamtsStandardUnsatisfiedError(CctError):
    platform_code = AdaptixErrorCode.VALIDATION_FAILED
    code = CctErrorCode.CAMTS_STANDARD_UNSATISFIED


__all__ = [
    "CctCamtsChecklistIncompleteError",
    "CctCamtsStandardUnsatisfiedError",
    "CctCrewCredentialInsufficientError",
    "CctCrewNotAssignedError",
    "CctError",
    "CctErrorCode",
    "CctHandoffNotFoundError",
    "CctHandoffPhysicianMissingError",
    "CctLoadoutIncompleteError",
    "CctLoadoutNotFoundError",
    "CctMissionAlreadyAcceptedError",
    "CctMissionInvalidStateError",
    "CctMissionNotFoundError",
]
