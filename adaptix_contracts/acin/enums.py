"""ACIN (AdaptixCore Clinical Intelligence Narrative) canonical enums.

These enums define the fixed vocabularies for the ACIN record surface. They are
shared across EPCR, NEMSIS, Billing, Medical-Necessity, QA/QI, Legal, CMS-audit,
AI-review, and Clinical-Decision-Support consumers so the same string values are
used everywhere and never re-invented per service.
"""

from __future__ import annotations

from enum import Enum


class ACINSection(str, Enum):
    """The seven ACIN sections (A-C-I-N-E-L-S)."""

    ACTIVATION = "activation"  # A
    CLINICAL_PICTURE = "clinical_picture"  # C
    INTELLIGENCE = "intelligence"  # I
    NARRATIVE = "narrative"  # N
    EVIDENCE = "evidence"  # E
    LOGIC = "logic"  # L
    SUMMARY = "summary"  # S

    @property
    def letter(self) -> str:
        """Return the single-letter code for the section (A, C, I, N, E, L, S)."""

        return {
            ACINSection.ACTIVATION: "A",
            ACINSection.CLINICAL_PICTURE: "C",
            ACINSection.INTELLIGENCE: "I",
            ACINSection.NARRATIVE: "N",
            ACINSection.EVIDENCE: "E",
            ACINSection.LOGIC: "L",
            ACINSection.SUMMARY: "S",
        }[self]


class ACINRecordStatus(str, Enum):
    """Lifecycle status of an ACIN record.

    An ACIN record is generated advisory output. It is never authoritative until
    a human accepts it. It becomes immutable once the underlying chart is locked
    (a regenerate produces a new version, not an in-place edit).
    """

    DRAFT = "draft"
    GENERATED = "generated"
    HUMAN_REVIEWING = "human_reviewing"
    HUMAN_ACCEPTED = "human_accepted"
    LOCKED = "locked"


class ACINClaimReviewState(str, Enum):
    """Per-item / per-section human review state.

    AI-generated content is ALWAYS ``pending_review`` at creation and is never
    auto-accepted (mirrors the EPCR ImpressionBinding / SmartText / Vision rules).
    """

    PENDING_REVIEW = "pending_review"
    ACCEPTED = "accepted"
    EDITED_ACCEPTED = "edited_accepted"
    REJECTED = "rejected"


class ACINReviewType(str, Enum):
    """The four Cortex review lenses applied to an ACIN record."""

    CLINICAL = "clinical"
    BILLING = "billing"
    QA = "qa"
    LEGAL = "legal"


class ACINReviewStatus(str, Enum):
    """Status of a single Cortex review.

    ``failed_unavailable`` is a truthful terminal state used when the Bedrock
    broker is unreachable — the review is never stubbed or faked as complete.
    """

    PENDING = "pending"
    COMPLETE = "complete"
    FAILED_UNAVAILABLE = "failed_unavailable"


class ACINReviewSeverity(str, Enum):
    """Severity of an individual review finding."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


__all__ = [
    "ACINSection",
    "ACINRecordStatus",
    "ACINClaimReviewState",
    "ACINReviewType",
    "ACINReviewStatus",
    "ACINReviewSeverity",
]
