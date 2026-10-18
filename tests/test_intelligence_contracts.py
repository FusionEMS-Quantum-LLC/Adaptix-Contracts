"""C01 Frontier Intelligence contracts: the safety rules hold at construction."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from adaptix_contracts.ai.connection import DataClassification
from adaptix_contracts.intelligence import (
    ActorKind,
    ActorRef,
    AssertionBasis,
    ClinicalEvidenceProposal,
    EngineeringProofManifest,
    EvidenceReference,
    GovernedAction,
    GovernedActionStatus,
    IncidentRelationKind,
    IncidentRelationship,
    InvariantViolation,
    OptimizationRecommendation,
    OptimizationScenario,
    ProofCategory,
    ProofClaim,
    ProofLevel,
    ProposalStatus,
    RecommendationStatus,
    RecommendedChange,
    RecoveryAttempt,
    RecoveryOutcome,
    ViolationSeverity,
    ViolationStatus,
)
from adaptix_contracts.schemas.execution_contracts import RiskLevel

T0 = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)
SHA = "a" * 40
HUMAN = ActorRef(actor_id="user-1", kind=ActorKind.HUMAN)
OTHER_HUMAN = ActorRef(actor_id="user-2", kind=ActorKind.HUMAN)
AGENT = ActorRef(actor_id="cortex", kind=ActorKind.AI_AGENT)


def ref(
    rid: str = "r1",
    *,
    tenant: str = "t1",
    service: str = "adaptix-cad-service",
    rtype: str = "incident",
    at: datetime = T0,
) -> EvidenceReference:
    return EvidenceReference(
        tenant_id=tenant,
        source_service=service,
        source_resource_type=rtype,
        source_resource_id=rid,
        content_hash="sha256:x",
        observed_at=at,
    )


# EvidenceReference ---------------------------------------------------------


def test_reference_rejects_secret_and_naive_time() -> None:
    with pytest.raises(ValidationError, match="credential"):
        EvidenceReference(
            **{**ref().model_dump(), "sensitivity": DataClassification.SECRET}
        )
    with pytest.raises(ValidationError, match="timezone-aware"):
        ref(at=datetime(2026, 10, 18, 12, 0))


def test_reference_is_immutable_and_strict() -> None:
    r = ref()
    with pytest.raises(ValidationError):
        r.source_resource_id = "other"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        EvidenceReference(**r.model_dump(), extra_field=1)


# IncidentRelationship -------------------------------------------------------


def relationship(**overrides: Any) -> IncidentRelationship:
    data: dict[str, Any] = {
        "relationship_id": "rel-1",
        "tenant_id": "t1",
        "kind": IncidentRelationKind.DUPLICATE_OF,
        "from_record": ref("a"),
        "to_record": ref("b"),
        "basis": AssertionBasis.DETERMINISTIC,
        "asserted_by": ActorRef(actor_id="chronos", kind=ActorKind.SERVICE),
        "valid_from": T0,
        "recorded_at": T0,
    }
    data.update(overrides)
    return IncidentRelationship(**data)


def test_relationship_valid() -> None:
    assert relationship().valid_to is None


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"to_record": ref("b", tenant="t2")}, "another tenant"),
        ({"to_record": ref("a")}, "itself"),
        ({"valid_to": T0}, "valid_to"),
        (
            {"basis": AssertionBasis.INFERRED, "supporting_evidence": [ref("e")]},
            "confidence",
        ),
        ({"basis": AssertionBasis.INFERRED, "confidence": 0.8}, "cite evidence"),
        ({"confidence": 0.9}, "only an inferred"),
        ({"basis": AssertionBasis.HUMAN_ASSERTED}, "human actor"),
    ],
)
def test_relationship_rules(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        relationship(**overrides)


# GovernedAction -------------------------------------------------------------


def action(**overrides: Any) -> GovernedAction:
    data: dict[str, Any] = {
        "action_id": "act-1",
        "tenant_id": "t1",
        "action_type": "unit.reassign",
        "owning_service": "adaptix-cad-service",
        "target": ref("unit-7", rtype="unit"),
        "requested_by": AGENT,
        "required_permission": "cad.unit.reassign",
        "idempotency_key": "idem-0001",
        "expected_version": "v3",
        "risk_level": RiskLevel.MEDIUM,
        "requires_approval": True,
        "status": GovernedActionStatus.PENDING_APPROVAL,
        "created_at": T0,
        "expires_at": T0 + timedelta(minutes=10),
    }
    data.update(overrides)
    return GovernedAction(**data)


def approved(**overrides: Any) -> GovernedAction:
    return action(
        status=GovernedActionStatus.APPROVED,
        approved_by=HUMAN,
        approved_at=T0 + timedelta(minutes=1),
        **overrides,
    )


def test_ai_request_needs_human_approval_before_it_can_run() -> None:
    pending = action()
    assert not pending.is_executable_at(T0 + timedelta(minutes=2))
    ok = approved()
    assert ok.is_executable_at(T0 + timedelta(minutes=2))
    assert not ok.is_executable_at(T0 + timedelta(minutes=10))
    assert not ok.is_executable_at(datetime(2026, 10, 18, 12, 2))


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"requires_approval": False}, "AI agent asks"),
        ({"approved_by": AGENT, "approved_at": T0}, "only a human"),
        (
            {"requested_by": HUMAN, "approved_by": HUMAN, "approved_at": T0},
            "own action",
        ),
        ({"status": GovernedActionStatus.APPROVED}, "needs a recorded approval"),
        ({"status": GovernedActionStatus.REJECTED}, "needs a reason"),
        ({"expires_at": T0}, "expires_at"),
        ({"target": ref("x", service="adaptix-billing-service")}, "owning service"),
        ({"target": ref("x", tenant="t2")}, "another tenant"),
        ({"idempotency_key": "short"}, "idempotency_key"),
        (
            {"approved_by": HUMAN, "approved_at": T0 + timedelta(minutes=30)},
            "lifetime",
        ),
    ],
)
def test_governed_action_rules(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        action(**overrides)


@pytest.mark.parametrize("risk", [RiskLevel.HIGH, RiskLevel.CRITICAL])
def test_high_risk_and_founder_reserved_always_need_approval(risk: RiskLevel) -> None:
    base = {
        "requested_by": HUMAN,
        "requires_approval": False,
        "status": GovernedActionStatus.PROPOSED,
    }
    with pytest.raises(ValidationError, match="high or critical"):
        action(**base, risk_level=risk)
    with pytest.raises(ValidationError, match="founder-reserved"):
        action(**base, founder_reserved=True)


def test_low_risk_human_action_may_run_without_approval() -> None:
    a = action(
        requested_by=HUMAN,
        requires_approval=False,
        status=GovernedActionStatus.PROPOSED,
    )
    assert a.is_executable_at(T0 + timedelta(seconds=1))


def test_transitions_are_one_way() -> None:
    a = approved()
    assert a.can_transition_to(GovernedActionStatus.EXECUTING)
    assert not a.can_transition_to(GovernedActionStatus.PENDING_APPROVAL)
    done = approved().model_copy(update={"status": GovernedActionStatus.SUCCEEDED})
    assert done.is_terminal
    assert not done.can_transition_to(GovernedActionStatus.EXECUTING)


# InvariantViolation / RecoveryAttempt --------------------------------------


def violation(**overrides: Any) -> InvariantViolation:
    data: dict[str, Any] = {
        "violation_id": "v-1",
        "tenant_id": "t1",
        "invariant_key": "cad.unit.single_active_assignment",
        "invariant_version": "1",
        "owning_service": "adaptix-cad-service",
        "severity": ViolationSeverity.HIGH,
        "subject": ref("unit-7", rtype="unit"),
        "detection_evidence": [ref("snap-1", rtype="unit_snapshot")],
        "detected_at": T0,
        "status": ViolationStatus.OPEN,
    }
    data.update(overrides)
    return InvariantViolation(**data)


def test_violation_needs_detection_evidence_and_resolution_proof() -> None:
    with pytest.raises(ValidationError):
        violation(detection_evidence=[])
    with pytest.raises(ValidationError, match="resolved violation"):
        violation(status=ViolationStatus.RESOLVED, resolved_at=T0)
    with pytest.raises(ValidationError, match="acknowledged"):
        violation(status=ViolationStatus.ACKNOWLEDGED)
    ok = violation(
        status=ViolationStatus.RESOLVED,
        resolved_at=T0 + timedelta(minutes=5),
        resolution_evidence=[ref("snap-2", rtype="unit_snapshot")],
    )
    assert ok.status is ViolationStatus.RESOLVED


def attempt(**overrides: Any) -> RecoveryAttempt:
    data: dict[str, Any] = {
        "attempt_id": "ra-1",
        "tenant_id": "t1",
        "violation_id": "v-1",
        "governed_action_id": "act-1",
        "attempt_number": 1,
        "max_attempts": 3,
        "strategy": "release_stale_assignment",
        "started_at": T0,
        "outcome": RecoveryOutcome.PENDING,
    }
    data.update(overrides)
    return RecoveryAttempt(**data)


def test_recovery_is_bounded_and_success_needs_later_evidence() -> None:
    with pytest.raises(ValidationError, match="max_attempts"):
        attempt(attempt_number=4)
    end = T0 + timedelta(minutes=1)
    with pytest.raises(ValidationError, match="verification evidence"):
        attempt(outcome=RecoveryOutcome.SUCCEEDED, finished_at=end)
    with pytest.raises(ValidationError, match="observed after"):
        attempt(
            outcome=RecoveryOutcome.SUCCEEDED,
            finished_at=end,
            verification_evidence=[ref(at=T0)],
        )
    with pytest.raises(ValidationError, match="error_code"):
        attempt(outcome=RecoveryOutcome.FAILED, finished_at=end)
    with pytest.raises(ValidationError, match="not finished"):
        attempt(finished_at=end)
    ok = attempt(
        outcome=RecoveryOutcome.SUCCEEDED,
        finished_at=end,
        verification_evidence=[ref(at=end + timedelta(seconds=5))],
    )
    assert ok.outcome is RecoveryOutcome.SUCCEEDED


# ClinicalEvidenceProposal ---------------------------------------------------


def proposal(**overrides: Any) -> ClinicalEvidenceProposal:
    data: dict[str, Any] = {
        "proposal_id": "p-1",
        "tenant_id": "t1",
        "chart": ref("chart-1", service="adaptix-epcr-service", rtype="chart"),
        "field_path": "vitals[0].heart_rate_bpm",
        "proposed_value": 88,
        "source_evidence": [
            ref("cap-1", service="adaptix-epcr-service", rtype="vision_capture")
        ],
        "model_execution_id": "exec-1",
        "confidence": 0.95,
        "status": ProposalStatus.PROPOSED,
        "created_at": T0,
    }
    data.update(overrides)
    return ClinicalEvidenceProposal(**data)


def reviewed(status: ProposalStatus, **overrides: Any) -> ClinicalEvidenceProposal:
    return proposal(
        status=status,
        reviewed_by=HUMAN,
        reviewed_at=T0 + timedelta(minutes=1),
        **overrides,
    )


def test_an_unreviewed_proposal_writes_nothing() -> None:
    p = proposal()
    assert p.is_proposal is True
    assert p.chart_value is None
    with pytest.raises(ValidationError):
        proposal(is_proposal=False)


def test_only_a_human_review_produces_a_chart_value() -> None:
    assert reviewed(ProposalStatus.ACCEPTED).chart_value == 88
    assert reviewed(ProposalStatus.EDITED, final_value=92).chart_value == 92
    assert (
        reviewed(ProposalStatus.REJECTED, rejection_reason="wrong patient").chart_value
        is None
    )
    with pytest.raises(ValidationError, match="only a human"):
        proposal(status=ProposalStatus.ACCEPTED, reviewed_by=AGENT, reviewed_at=T0)
    with pytest.raises(ValidationError, match="only a human"):
        proposal(status=ProposalStatus.ACCEPTED)


@pytest.mark.parametrize(
    ("status", "overrides", "message"),
    [
        (ProposalStatus.EDITED, {}, "changed final_value"),
        (ProposalStatus.EDITED, {"final_value": 88}, "changed final_value"),
        (ProposalStatus.ACCEPTED, {"final_value": 90}, "use edited"),
        (ProposalStatus.REJECTED, {}, "needs a reason"),
    ],
)
def test_review_rules(
    status: ProposalStatus, overrides: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        reviewed(status, **overrides)


def test_proposal_targets_epcr_charts_in_the_same_tenant() -> None:
    with pytest.raises(ValidationError, match="ePCR"):
        proposal(chart=ref("chart-1", service="adaptix-billing-service", rtype="chart"))
    with pytest.raises(ValidationError, match="another tenant"):
        proposal(source_evidence=[ref("cap-1", tenant="t2")])
    with pytest.raises(ValidationError):
        proposal(source_evidence=[])


# Atlas ----------------------------------------------------------------------


def test_scenario_is_always_a_simulation() -> None:
    s = OptimizationScenario(
        scenario_id="s-1",
        tenant_id="t1",
        kind="coverage",
        inputs_as_of=T0,
        input_evidence=[ref()],
        horizon_start=T0,
        horizon_end=T0 + timedelta(hours=4),
        model_version="atlas-1",
        requested_by=HUMAN,
        created_at=T0,
    )
    assert s.is_simulation is True
    with pytest.raises(ValidationError):
        OptimizationScenario(**{**s.model_dump(), "is_simulation": False})
    with pytest.raises(ValidationError, match="horizon_end"):
        OptimizationScenario(**{**s.model_dump(), "horizon_end": T0})


def recommendation(**overrides: Any) -> OptimizationRecommendation:
    data: dict[str, Any] = {
        "recommendation_id": "rec-1",
        "tenant_id": "t1",
        "scenario_id": "s-1",
        "summary": "Post Medic 7 at Station 3 to close the north coverage gap.",
        "changes": [
            RecommendedChange(target=ref("unit-7", rtype="unit"), change_type="post")
        ],
        "status": RecommendationStatus.ADVISORY,
        "created_at": T0,
        "expires_at": T0 + timedelta(hours=1),
    }
    data.update(overrides)
    return OptimizationRecommendation(**data)


def test_recommendation_is_advisory_and_adopted_only_through_an_action() -> None:
    assert recommendation().presentation == "advisory"
    with pytest.raises(ValidationError):
        recommendation(presentation="assignment")
    with pytest.raises(ValidationError, match="governed action"):
        recommendation(status=RecommendationStatus.ADOPTED)
    with pytest.raises(ValidationError, match="governed action"):
        recommendation(adopted_via_action_id="act-1")
    assert recommendation(
        status=RecommendationStatus.ADOPTED, adopted_via_action_id="act-1"
    )
    with pytest.raises(ValidationError, match="dismissal"):
        recommendation(status=RecommendationStatus.DISMISSED)


# Forge ----------------------------------------------------------------------


def claim(
    level: ProofLevel, category: ProofCategory, revision: str | None = SHA
) -> ProofClaim:
    return ProofClaim(
        level=level,
        category=category,
        statement="checked",
        evidence_uris=["https://example.invalid/evidence"],
        observed_revision=revision,
        observed_at=T0,
    )


def manifest(claims: list[ProofClaim]) -> EngineeringProofManifest:
    return EngineeringProofManifest(
        manifest_id="m-1",
        repository="Adaptix-Contracts",
        commit_sha=SHA,
        work_package="C01",
        claims=claims,
        generated_at=T0,
    )


def test_ci_green_is_not_tier5() -> None:
    m = manifest([claim(ProofLevel.CI_GREEN, c, None) for c in ProofCategory])
    assert m.highest_level is ProofLevel.CI_GREEN
    assert not m.tier5
    assert manifest([]).highest_level is None


def test_tier5_needs_runtime_evidence_on_this_commit_for_every_category() -> None:
    full = [claim(ProofLevel.RUNTIME_VERIFIED, c) for c in ProofCategory]
    assert manifest(full).tier5
    partial = manifest(full[:-1])
    assert not partial.tier5
    assert partial.missing_tier5_categories == {list(ProofCategory)[-1]}
    drifted = [claim(ProofLevel.RUNTIME_VERIFIED, c, "b" * 40) for c in ProofCategory]
    assert not manifest(drifted).tier5


def test_runtime_claims_name_a_real_revision() -> None:
    with pytest.raises(ValidationError, match="commit SHA"):
        claim(ProofLevel.DEPLOYED, ProofCategory.FUNCTIONAL, None)
    with pytest.raises(ValidationError, match="commit SHA"):
        claim(ProofLevel.RUNTIME_VERIFIED, ProofCategory.FUNCTIONAL, "latest")
    with pytest.raises(ValidationError, match="40-character"):
        EngineeringProofManifest(
            manifest_id="m",
            repository="r",
            commit_sha="abc",
            work_package="C01",
            generated_at=T0,
        )
    with pytest.raises(ValidationError):
        ProofClaim(
            level=ProofLevel.CI_GREEN,
            category=ProofCategory.FUNCTIONAL,
            statement="x",
            evidence_uris=[],
            observed_at=T0,
        )
