"""Enums for the Frontier Intelligence contracts (work package C01).

Every enum is a ``StrEnum`` so the wire format is a stable string, matching the
sibling contract subpackages (``adaptix_contracts.evidence.enums``).
"""

from __future__ import annotations

from enum import StrEnum


class ActorKind(StrEnum):
    """Who asked for, or decided, a governed transition.

    ``AI_AGENT`` is separate from ``SERVICE`` on purpose: an AI agent may
    propose and may execute an approved action, but it is never an approver.
    """

    HUMAN = "human"
    SERVICE = "service"
    AI_AGENT = "ai_agent"


class IncidentRelationKind(StrEnum):
    """How two incident-scoped records relate in time (Chronos)."""

    SAME_INCIDENT = "same_incident"
    DUPLICATE_OF = "duplicate_of"
    PRECEDES = "precedes"
    CAUSED_BY = "caused_by"
    TRANSFERRED_TO = "transferred_to"
    SUPERSEDES = "supersedes"


class AssertionBasis(StrEnum):
    """Whether a relationship was derived deterministically or inferred."""

    DETERMINISTIC = "deterministic"
    INFERRED = "inferred"
    HUMAN_ASSERTED = "human_asserted"


class GovernedActionStatus(StrEnum):
    """Lifecycle of a governed action envelope (Aegis)."""

    PROPOSED = "proposed"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ViolationSeverity(StrEnum):
    """Severity of a broken invariant (Sentinel)."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ViolationStatus(StrEnum):
    """Lifecycle of an invariant violation."""

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RECOVERING = "recovering"
    RESOLVED = "resolved"


class RecoveryOutcome(StrEnum):
    """Outcome of one recovery attempt."""

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABANDONED = "abandoned"


class ProposalStatus(StrEnum):
    """Review state of a clinical evidence proposal (Helix)."""

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"
    EXPIRED = "expired"


class RecommendationStatus(StrEnum):
    """State of an optimization recommendation (Atlas)."""

    ADVISORY = "advisory"
    ADOPTED = "adopted"
    DISMISSED = "dismissed"
    EXPIRED = "expired"


class ProofLevel(StrEnum):
    """Evidence levels a proof claim may assert (Forge).

    Ordered lowest to highest. ``RUNTIME_VERIFIED`` is the only level that can
    support an AdaptixCore Tier 5 claim, and only with the categories in
    :data:`TIER5_REQUIRED_CATEGORIES`.
    """

    LOCAL_VALIDATED = "local_validated"
    CI_GREEN = "ci_green"
    MERGED = "merged"
    DEPLOYED = "deployed"
    RUNTIME_VERIFIED = "runtime_verified"


class ProofCategory(StrEnum):
    """What a proof claim is evidence about."""

    FUNCTIONAL = "functional"
    SECURITY = "security"
    TENANCY = "tenancy"
    PERSISTENCE = "persistence"
    OBSERVABILITY = "observability"
    RECOVERY = "recovery"
    DOWNSTREAM = "downstream"


GOVERNED_ACTION_TERMINAL_STATUSES: frozenset[GovernedActionStatus] = frozenset(
    {
        GovernedActionStatus.REJECTED,
        GovernedActionStatus.EXPIRED,
        GovernedActionStatus.SUCCEEDED,
        GovernedActionStatus.FAILED,
        GovernedActionStatus.CANCELLED,
    }
)

GOVERNED_ACTION_TRANSITIONS: dict[
    GovernedActionStatus, frozenset[GovernedActionStatus]
] = {
    GovernedActionStatus.PROPOSED: frozenset(
        {
            GovernedActionStatus.PENDING_APPROVAL,
            GovernedActionStatus.APPROVED,
            GovernedActionStatus.CANCELLED,
            GovernedActionStatus.EXPIRED,
        }
    ),
    GovernedActionStatus.PENDING_APPROVAL: frozenset(
        {
            GovernedActionStatus.APPROVED,
            GovernedActionStatus.REJECTED,
            GovernedActionStatus.EXPIRED,
            GovernedActionStatus.CANCELLED,
        }
    ),
    GovernedActionStatus.APPROVED: frozenset(
        {
            GovernedActionStatus.EXECUTING,
            GovernedActionStatus.EXPIRED,
            GovernedActionStatus.CANCELLED,
        }
    ),
    GovernedActionStatus.EXECUTING: frozenset(
        {GovernedActionStatus.SUCCEEDED, GovernedActionStatus.FAILED}
    ),
}

TIER5_REQUIRED_CATEGORIES: frozenset[ProofCategory] = frozenset(ProofCategory)

__all__ = [
    "GOVERNED_ACTION_TERMINAL_STATUSES",
    "GOVERNED_ACTION_TRANSITIONS",
    "TIER5_REQUIRED_CATEGORIES",
    "ActorKind",
    "AssertionBasis",
    "GovernedActionStatus",
    "IncidentRelationKind",
    "ProofCategory",
    "ProofLevel",
    "ProposalStatus",
    "RecommendationStatus",
    "RecoveryOutcome",
    "ViolationSeverity",
    "ViolationStatus",
]
