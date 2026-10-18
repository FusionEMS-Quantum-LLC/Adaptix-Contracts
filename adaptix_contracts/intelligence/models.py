"""Frontier Intelligence shared contracts (work package C01).

Nine envelopes the six engines (Chronos, Aegis, Sentinel, Helix, Atlas, Forge)
exchange across service boundaries. None of them owns domain truth: each one
points at records the canonical service still owns (CAD dispatch, ePCR
clinical, Billing money, Audit evidence), so no engine needs to write into
another domain's database.

The validators encode the directive's safety rules at the contract level, so a
consumer cannot build a value that breaks them:

* an AI agent never approves anything, and nobody approves their own action;
* a clinical proposal is never clinical truth until a human reviews it;
* a simulated recommendation is always advisory and can only be adopted
  through a governed action;
* a violation is resolved, and a recovery succeeds, only with evidence;
* Tier 5 is claimable only from runtime evidence covering every category.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

from adaptix_contracts.ai.connection import DataClassification
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
from adaptix_contracts.schemas.execution_contracts import RiskLevel

_COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")


def _require_aware(value: datetime | None, name: str) -> None:
    if value is not None and value.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware")


class EvidenceReference(BaseModel):
    """A pointer to the record a claim rests on, never a copy of it.

    The owning service, record type and id are always required, so a reference
    can be resolved even before an Evidence Graph node exists. ``evidence_id``
    links the matching :class:`~adaptix_contracts.evidence.EvidenceNode` when
    one does. ``content_hash`` pins the version that was relied on: if the
    record changes later, the reference is known to describe a superseded state.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: str = Field(..., min_length=1)
    source_service: str = Field(..., min_length=1)
    source_resource_type: str = Field(..., min_length=1)
    source_resource_id: str = Field(..., min_length=1)
    content_hash: str = Field(..., min_length=1)
    observed_at: datetime
    evidence_id: str | None = Field(default=None, min_length=1)
    sensitivity: DataClassification = Field(default=DataClassification.INTERNAL)

    @field_validator("sensitivity")
    @classmethod
    def _reject_secret(cls, value: DataClassification) -> DataClassification:
        if value is DataClassification.SECRET:
            raise ValueError("a credential is not evidence")
        return value

    @model_validator(mode="after")
    def _aware(self) -> EvidenceReference:
        _require_aware(self.observed_at, "observed_at")
        return self


def _same_tenant(tenant_id: str, refs: list[EvidenceReference], name: str) -> None:
    for ref in refs:
        if ref.tenant_id != tenant_id:
            raise ValueError(f"{name} references another tenant's record")


class ActorRef(BaseModel):
    """A verified actor. ``actor_id`` comes from the authenticated context."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_id: str = Field(..., min_length=1)
    kind: ActorKind


class IncidentRelationship(BaseModel):
    """A time-bounded relationship between two incident-scoped records (Chronos).

    ``valid_to`` of ``None`` means the relationship still holds. An inferred
    relationship must say how confident the inference is; a deterministic or
    human-asserted one must not carry a confidence it does not have.
    """

    model_config = ConfigDict(extra="forbid")

    relationship_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    kind: IncidentRelationKind
    from_record: EvidenceReference
    to_record: EvidenceReference
    basis: AssertionBasis
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    asserted_by: ActorRef
    valid_from: datetime
    valid_to: datetime | None = None
    supporting_evidence: list[EvidenceReference] = Field(default_factory=list)
    recorded_at: datetime

    @model_validator(mode="after")
    def _check(self) -> IncidentRelationship:
        for name in ("valid_from", "valid_to", "recorded_at"):
            _require_aware(getattr(self, name), name)
        _same_tenant(
            self.tenant_id,
            [self.from_record, self.to_record, *self.supporting_evidence],
            "relationship",
        )
        if (
            self.from_record.source_service == self.to_record.source_service
            and self.from_record.source_resource_type
            == self.to_record.source_resource_type
            and self.from_record.source_resource_id == self.to_record.source_resource_id
        ):
            raise ValueError("a record may not relate to itself")
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be after valid_from")
        if self.basis is AssertionBasis.INFERRED:
            if self.confidence is None:
                raise ValueError("an inferred relationship must state its confidence")
            if not self.supporting_evidence:
                raise ValueError("an inferred relationship must cite evidence")
        elif self.confidence is not None:
            raise ValueError("only an inferred relationship carries a confidence")
        if (
            self.basis is AssertionBasis.HUMAN_ASSERTED
            and self.asserted_by.kind is not ActorKind.HUMAN
        ):
            raise ValueError("a human-asserted relationship needs a human actor")
        return self


class GovernedAction(BaseModel):
    """An envelope for any consequential action an engine wants taken (Aegis).

    The owning service executes the action; the envelope records who asked,
    under which permission, against which record version, with which approval,
    and until when. ``idempotency_key`` is required so a retry cannot run the
    action twice. ``expected_version`` is the optimistic-concurrency token the
    owning service checks before it writes.
    """

    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    action_type: str = Field(..., min_length=1)
    owning_service: str = Field(..., min_length=1)
    target: EvidenceReference
    requested_by: ActorRef
    required_permission: str = Field(..., min_length=1)
    idempotency_key: str = Field(..., min_length=8)
    expected_version: str | None = Field(default=None, min_length=1)
    risk_level: RiskLevel
    requires_approval: bool
    founder_reserved: bool = False
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    justification: list[EvidenceReference] = Field(default_factory=list)
    status: GovernedActionStatus
    approved_by: ActorRef | None = None
    approved_at: datetime | None = None
    rejection_reason: str | None = Field(default=None, min_length=1)
    failure_reason: str | None = Field(default=None, min_length=1)
    created_at: datetime
    expires_at: datetime
    max_execution_seconds: int = Field(default=300, ge=1, le=3600)

    @model_validator(mode="after")
    def _check(self) -> GovernedAction:
        for name in ("created_at", "expires_at", "approved_at"):
            _require_aware(getattr(self, name), name)
        _same_tenant(self.tenant_id, [self.target, *self.justification], "action")
        if self.target.source_service != self.owning_service:
            raise ValueError("an action must target a record its owning service owns")
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be after created_at")
        if self.founder_reserved and not self.requires_approval:
            raise ValueError("a founder-reserved action always requires approval")
        if (
            self.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
            and not self.requires_approval
        ):
            raise ValueError("a high or critical risk action requires approval")
        if self.requested_by.kind is ActorKind.AI_AGENT and not self.requires_approval:
            raise ValueError("an action an AI agent asks for requires approval")

        approved_states = {
            GovernedActionStatus.APPROVED,
            GovernedActionStatus.EXECUTING,
            GovernedActionStatus.SUCCEEDED,
            GovernedActionStatus.FAILED,
        }
        if self.approved_by is not None:
            if self.approved_by.kind is not ActorKind.HUMAN:
                raise ValueError("only a human may approve a governed action")
            if self.approved_by.actor_id == self.requested_by.actor_id:
                raise ValueError("an actor may not approve their own action")
            if self.approved_at is None:
                raise ValueError("an approval needs approved_at")
            if not (self.created_at <= self.approved_at < self.expires_at):
                raise ValueError("approval must fall inside the action's lifetime")
        elif self.approved_at is not None:
            raise ValueError("approved_at without approved_by")
        if (
            self.requires_approval
            and self.status in approved_states
            and self.approved_by is None
        ):
            raise ValueError(f"status {self.status} needs a recorded approval")
        if (
            self.status is GovernedActionStatus.REJECTED
            and self.rejection_reason is None
        ):
            raise ValueError("a rejection needs a reason")
        if self.status is GovernedActionStatus.FAILED and self.failure_reason is None:
            raise ValueError("a failure needs a reason")
        return self

    def can_transition_to(self, new_status: GovernedActionStatus) -> bool:
        """Return whether ``new_status`` is a legal next state from this one."""

        return new_status in GOVERNED_ACTION_TRANSITIONS.get(self.status, frozenset())

    def is_executable_at(self, now: datetime) -> bool:
        """Return whether the owning service may start executing now.

        Fails closed: a naive ``now``, an expired envelope, or a missing
        approval all answer ``False``.
        """

        if now.tzinfo is None or now >= self.expires_at:
            return False
        if self.status is not GovernedActionStatus.APPROVED and not (
            self.status is GovernedActionStatus.PROPOSED and not self.requires_approval
        ):
            return False
        return not (self.requires_approval and self.approved_by is None)

    @property
    def is_terminal(self) -> bool:
        return self.status in GOVERNED_ACTION_TERMINAL_STATUSES


class InvariantViolation(BaseModel):
    """A broken platform invariant, detected by Sentinel.

    A violation cannot be resolved without evidence that the invariant holds
    again; "the alert went quiet" is not resolution.
    """

    model_config = ConfigDict(extra="forbid")

    violation_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    invariant_key: str = Field(..., min_length=1)
    invariant_version: str = Field(..., min_length=1)
    owning_service: str = Field(..., min_length=1)
    severity: ViolationSeverity
    subject: EvidenceReference
    detection_evidence: list[EvidenceReference] = Field(..., min_length=1)
    detected_at: datetime
    status: ViolationStatus
    acknowledged_by: ActorRef | None = None
    resolved_at: datetime | None = None
    resolution_evidence: list[EvidenceReference] = Field(default_factory=list)
    detail: dict[str, Any] = Field(
        default_factory=dict,
        description="Structural context only; never PHI, PII or credentials.",
    )

    @model_validator(mode="after")
    def _check(self) -> InvariantViolation:
        for name in ("detected_at", "resolved_at"):
            _require_aware(getattr(self, name), name)
        _same_tenant(
            self.tenant_id,
            [self.subject, *self.detection_evidence, *self.resolution_evidence],
            "violation",
        )
        if self.status is ViolationStatus.RESOLVED:
            if self.resolved_at is None or not self.resolution_evidence:
                raise ValueError("a resolved violation needs resolved_at and evidence")
            if self.resolved_at < self.detected_at:
                raise ValueError("resolved_at precedes detected_at")
        elif self.resolved_at is not None:
            raise ValueError("only a resolved violation has resolved_at")
        if self.status is ViolationStatus.ACKNOWLEDGED and self.acknowledged_by is None:
            raise ValueError("an acknowledged violation names who acknowledged it")
        return self


class RecoveryAttempt(BaseModel):
    """One bounded attempt to restore a violated invariant.

    Recovery is itself a consequential action, so every attempt runs through a
    :class:`GovernedAction`. Success needs verification evidence taken after
    the attempt finished.
    """

    model_config = ConfigDict(extra="forbid")

    attempt_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    violation_id: str = Field(..., min_length=1)
    governed_action_id: str = Field(..., min_length=1)
    attempt_number: int = Field(..., ge=1)
    max_attempts: int = Field(..., ge=1, le=10)
    strategy: str = Field(..., min_length=1)
    started_at: datetime
    finished_at: datetime | None = None
    outcome: RecoveryOutcome
    verification_evidence: list[EvidenceReference] = Field(default_factory=list)
    error_code: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _check(self) -> RecoveryAttempt:
        for name in ("started_at", "finished_at"):
            _require_aware(getattr(self, name), name)
        _same_tenant(self.tenant_id, self.verification_evidence, "recovery")
        if self.attempt_number > self.max_attempts:
            raise ValueError("attempt_number exceeds max_attempts")
        if self.outcome is RecoveryOutcome.PENDING:
            if self.finished_at is not None:
                raise ValueError("a pending attempt has not finished")
            return self
        if self.finished_at is None or self.finished_at < self.started_at:
            raise ValueError("a finished attempt needs finished_at after started_at")
        if self.outcome is RecoveryOutcome.SUCCEEDED:
            if not self.verification_evidence:
                raise ValueError("a successful recovery needs verification evidence")
            if any(
                ref.observed_at < self.finished_at for ref in self.verification_evidence
            ):
                raise ValueError(
                    "verification evidence must be observed after the attempt"
                )
        if self.outcome is RecoveryOutcome.FAILED and self.error_code is None:
            raise ValueError("a failed attempt needs an error_code")
        return self


class ClinicalEvidenceProposal(BaseModel):
    """An AI-derived value proposed for a chart field (Helix).

    It is never clinical truth on its own: ``is_proposal`` is fixed ``True``,
    and only a human review moves it to accepted, edited or rejected. The ePCR
    service writes the chart; this envelope only carries the proposal and its
    review. A signed chart is never a target; corrections go through ePCR's
    amendment path.
    """

    model_config = ConfigDict(extra="forbid")

    proposal_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    chart: EvidenceReference
    field_path: str = Field(..., min_length=1)
    proposed_value: JsonValue
    source_evidence: list[EvidenceReference] = Field(..., min_length=1)
    model_execution_id: str = Field(..., min_length=1)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    is_proposal: Literal[True] = True
    status: ProposalStatus
    reviewed_by: ActorRef | None = None
    reviewed_at: datetime | None = None
    final_value: JsonValue | None = None
    rejection_reason: str | None = Field(default=None, min_length=1)
    created_at: datetime
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def _check(self) -> ClinicalEvidenceProposal:
        for name in ("reviewed_at", "created_at", "expires_at"):
            _require_aware(getattr(self, name), name)
        _same_tenant(self.tenant_id, [self.chart, *self.source_evidence], "proposal")
        if self.chart.source_service != "adaptix-epcr-service":
            raise ValueError(
                "a clinical proposal targets a chart owned by the ePCR service"
            )
        reviewed = {
            ProposalStatus.ACCEPTED,
            ProposalStatus.EDITED,
            ProposalStatus.REJECTED,
        }
        if self.status in reviewed:
            if self.reviewed_by is None or self.reviewed_by.kind is not ActorKind.HUMAN:
                raise ValueError(
                    "only a human clinician may review a clinical proposal"
                )
            if self.reviewed_at is None or self.reviewed_at < self.created_at:
                raise ValueError("a review needs reviewed_at after created_at")
        elif self.reviewed_by is not None or self.reviewed_at is not None:
            raise ValueError(f"a {self.status} proposal has not been reviewed")
        if self.status is ProposalStatus.EDITED:
            if self.final_value is None or self.final_value == self.proposed_value:
                raise ValueError("an edited proposal carries a changed final_value")
        elif self.status is ProposalStatus.ACCEPTED:
            if self.final_value is not None and self.final_value != self.proposed_value:
                raise ValueError(
                    "an accepted proposal keeps the proposed value; use edited"
                )
        elif self.final_value is not None:
            raise ValueError(f"a {self.status} proposal writes no value")
        if self.status is ProposalStatus.REJECTED and self.rejection_reason is None:
            raise ValueError("a rejection needs a reason")
        if self.expires_at is not None and self.expires_at <= self.created_at:
            raise ValueError("expires_at must be after created_at")
        return self

    @property
    def chart_value(self) -> JsonValue | None:
        """The value ePCR may write, or ``None`` when nothing may be written."""

        if self.status is ProposalStatus.EDITED:
            return self.final_value
        if self.status is ProposalStatus.ACCEPTED:
            return self.proposed_value
        return None


class OptimizationScenario(BaseModel):
    """A simulated what-if (Atlas). Always a simulation, never live state."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    kind: str = Field(..., min_length=1, description="e.g. coverage, posting, staffing")
    is_simulation: Literal[True] = True
    inputs_as_of: datetime
    input_evidence: list[EvidenceReference] = Field(..., min_length=1)
    assumptions: dict[str, JsonValue] = Field(default_factory=dict)
    horizon_start: datetime
    horizon_end: datetime
    model_version: str = Field(..., min_length=1)
    requested_by: ActorRef
    created_at: datetime

    @model_validator(mode="after")
    def _check(self) -> OptimizationScenario:
        for name in ("inputs_as_of", "horizon_start", "horizon_end", "created_at"):
            _require_aware(getattr(self, name), name)
        _same_tenant(self.tenant_id, self.input_evidence, "scenario")
        if self.horizon_end <= self.horizon_start:
            raise ValueError("horizon_end must be after horizon_start")
        if self.inputs_as_of > self.created_at:
            raise ValueError("inputs cannot be newer than the scenario")
        return self


class RecommendedChange(BaseModel):
    """One change a recommendation suggests, against a record its owner holds."""

    model_config = ConfigDict(extra="forbid")

    target: EvidenceReference
    change_type: str = Field(..., min_length=1)
    parameters: dict[str, JsonValue] = Field(default_factory=dict)


class OptimizationRecommendation(BaseModel):
    """An advisory output of a scenario (Atlas).

    ``presentation`` is fixed ``"advisory"`` so no consumer can render it as an
    actual dispatch assignment. Adoption happens only through a
    :class:`GovernedAction` the owning service executes.
    """

    model_config = ConfigDict(extra="forbid")

    recommendation_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    scenario_id: str = Field(..., min_length=1)
    presentation: Literal["advisory"] = "advisory"
    summary: str = Field(..., min_length=1, max_length=500)
    changes: list[RecommendedChange] = Field(..., min_length=1)
    expected_effects: dict[str, float] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    status: RecommendationStatus
    adopted_via_action_id: str | None = Field(default=None, min_length=1)
    dismissed_by: ActorRef | None = None
    created_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def _check(self) -> OptimizationRecommendation:
        for name in ("created_at", "expires_at"):
            _require_aware(getattr(self, name), name)
        _same_tenant(self.tenant_id, [c.target for c in self.changes], "recommendation")
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be after created_at")
        if (self.status is RecommendationStatus.ADOPTED) != (
            self.adopted_via_action_id is not None
        ):
            raise ValueError(
                "adoption is recorded if and only if a governed action adopted it"
            )
        if self.status is RecommendationStatus.DISMISSED and self.dismissed_by is None:
            raise ValueError("a dismissal names who dismissed it")
        return self


class ProofClaim(BaseModel):
    """One claim in a proof manifest, with the evidence that backs it."""

    model_config = ConfigDict(extra="forbid")

    level: ProofLevel
    category: ProofCategory
    statement: str = Field(..., min_length=1)
    evidence_uris: list[str] = Field(..., min_length=1)
    observed_revision: str | None = Field(
        default=None,
        description="Commit SHA actually observed running, for deployed/runtime claims",
    )
    observed_at: datetime

    @model_validator(mode="after")
    def _check(self) -> ProofClaim:
        _require_aware(self.observed_at, "observed_at")
        if self.level in (ProofLevel.DEPLOYED, ProofLevel.RUNTIME_VERIFIED):
            if self.observed_revision is None or not _COMMIT_SHA.match(
                self.observed_revision
            ):
                raise ValueError(
                    "a deployed or runtime claim names the observed commit SHA"
                )
        return self


class EngineeringProofManifest(BaseModel):
    """What a change has actually been proven to do (Forge).

    ``tier5`` is derived, never asserted: it is ``True`` only when runtime
    claims observed on this exact commit cover every required category.
    """

    model_config = ConfigDict(extra="forbid")

    manifest_id: str = Field(..., min_length=1)
    repository: str = Field(..., min_length=1)
    commit_sha: str
    pull_request: int | None = Field(default=None, ge=1)
    work_package: str = Field(..., min_length=1)
    claims: list[ProofClaim] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    generated_at: datetime

    @field_validator("commit_sha")
    @classmethod
    def _sha(cls, value: str) -> str:
        if not _COMMIT_SHA.match(value):
            raise ValueError("commit_sha must be a full 40-character lowercase SHA")
        return value

    @model_validator(mode="after")
    def _check(self) -> EngineeringProofManifest:
        _require_aware(self.generated_at, "generated_at")
        return self

    @property
    def highest_level(self) -> ProofLevel | None:
        order = list(ProofLevel)
        levels = [c.level for c in self.claims]
        return max(levels, key=order.index) if levels else None

    @property
    def tier5(self) -> bool:
        covered = {
            c.category
            for c in self.claims
            if c.level is ProofLevel.RUNTIME_VERIFIED
            and c.observed_revision == self.commit_sha
        }
        return TIER5_REQUIRED_CATEGORIES <= covered

    @property
    def missing_tier5_categories(self) -> frozenset[ProofCategory]:
        covered = {
            c.category
            for c in self.claims
            if c.level is ProofLevel.RUNTIME_VERIFIED
            and c.observed_revision == self.commit_sha
        }
        return TIER5_REQUIRED_CATEGORIES - covered


__all__ = [
    "ActorRef",
    "ClinicalEvidenceProposal",
    "EngineeringProofManifest",
    "EvidenceReference",
    "GovernedAction",
    "IncidentRelationship",
    "InvariantViolation",
    "OptimizationRecommendation",
    "OptimizationScenario",
    "ProofClaim",
    "RecommendedChange",
    "RecoveryAttempt",
]
