"""ACIN — AdaptixCore Clinical Intelligence Narrative shared contracts.

One structured clinical record (sections A-C-I-N-E-L-S), documented once, that
fans out to EPCR, NEMSIS, Billing, Medical-Necessity, QA/QI, Legal, CMS-audit,
AI-review, and Clinical-Decision-Support. This subpackage defines only the
shared, versioned DTOs — no business logic, no ORM, no routes (those live in the
EPCR / AI / Bedrock services).

Contract-enforced non-negotiables:
- Every generated clinical claim is grounded in >= 1 source field id
  (``ACINClaimDTO`` fails closed on zero references — no fabrication).
- AI-generated content always sets ``ai_generated=True`` and
  ``requires_human_review=True`` — nothing is auto-committed or signed.
- Contradictions are FLAGGED, never resolved (resolution stays None).
- Narrative and Summary are derived output — never authoritative truth.
- Reviews record ``failed_unavailable`` truthfully when the broker is down.

Import example:
    from adaptix_contracts.acin import ACINRecordDTO, ACINScoreSetDTO
"""

from .enums import (
    ACINClaimReviewState,
    ACINRecordStatus,
    ACINReviewSeverity,
    ACINReviewStatus,
    ACINReviewType,
    ACINSection,
)
from .provenance import (
    ACINClaimDTO,
    ACINProvenanceMixin,
    ACINSourceRef,
)
from .record import ACINRecordDTO
from .reviews import (
    ACINReviewDTO,
    ACINReviewFindingDTO,
)
from .scores import ACINScoreSetDTO
from .sections import (
    ACINActivationDTO,
    ACINClinicalPictureDTO,
    ACINConditionFlagsDTO,
    ACINContradictionFlagDTO,
    ACINDifferentialDTO,
    ACINEvidenceDTO,
    ACINIntelligenceDTO,
    ACINLogicDTO,
    ACINNarrativeDTO,
    ACINSummaryDTO,
    ACINTimelineEntryDTO,
    ACINWitnessStatementDTO,
)

__all__ = [
    # enums
    "ACINSection",
    "ACINRecordStatus",
    "ACINClaimReviewState",
    "ACINReviewType",
    "ACINReviewStatus",
    "ACINReviewSeverity",
    # provenance
    "ACINSourceRef",
    "ACINProvenanceMixin",
    "ACINClaimDTO",
    # sections + sub-DTOs
    "ACINTimelineEntryDTO",
    "ACINWitnessStatementDTO",
    "ACINContradictionFlagDTO",
    "ACINConditionFlagsDTO",
    "ACINActivationDTO",
    "ACINClinicalPictureDTO",
    "ACINDifferentialDTO",
    "ACINIntelligenceDTO",
    "ACINNarrativeDTO",
    "ACINEvidenceDTO",
    "ACINLogicDTO",
    "ACINSummaryDTO",
    # scores
    "ACINScoreSetDTO",
    # reviews
    "ACINReviewFindingDTO",
    "ACINReviewDTO",
    # record
    "ACINRecordDTO",
]
