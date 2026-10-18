"""Frontier Intelligence shared contracts (work package C01).

The envelopes the six engines exchange: Chronos (``IncidentRelationship``),
Aegis (``GovernedAction``), Sentinel (``InvariantViolation``,
``RecoveryAttempt``), Helix (``ClinicalEvidenceProposal``), Atlas
(``OptimizationScenario``, ``OptimizationRecommendation``) and Forge
(``EngineeringProofManifest``), all resting on ``EvidenceReference``.

These are contracts only. Storage and execution stay with the canonical
owning services; an envelope points at their records and never replaces them.
"""

from adaptix_contracts.intelligence.enums import (
    GOVERNED_ACTION_TERMINAL_STATUSES,
    GOVERNED_ACTION_TRANSITIONS,
    TIER5_REQUIRED_CATEGORIES,
    ActorKind,
    AssertionBasis,
    GovernedActionStatus,
    IncidentRelationKind,
    ProofCategory,
    ProofLevel,
    ProposalStatus,
    RecommendationStatus,
    RecoveryOutcome,
    ViolationSeverity,
    ViolationStatus,
)
from adaptix_contracts.intelligence.models import (
    ActorRef,
    ClinicalEvidenceProposal,
    EngineeringProofManifest,
    EvidenceReference,
    GovernedAction,
    IncidentRelationship,
    InvariantViolation,
    OptimizationRecommendation,
    OptimizationScenario,
    ProofClaim,
    RecommendedChange,
    RecoveryAttempt,
)

__all__ = [
    "GOVERNED_ACTION_TERMINAL_STATUSES",
    "GOVERNED_ACTION_TRANSITIONS",
    "TIER5_REQUIRED_CATEGORIES",
    "ActorKind",
    "ActorRef",
    "AssertionBasis",
    "ClinicalEvidenceProposal",
    "EngineeringProofManifest",
    "EvidenceReference",
    "GovernedAction",
    "GovernedActionStatus",
    "IncidentRelationKind",
    "IncidentRelationship",
    "InvariantViolation",
    "OptimizationRecommendation",
    "OptimizationScenario",
    "ProofCategory",
    "ProofClaim",
    "ProofLevel",
    "ProposalStatus",
    "RecommendationStatus",
    "RecommendedChange",
    "RecoveryAttempt",
    "RecoveryOutcome",
    "ViolationSeverity",
    "ViolationStatus",
]
