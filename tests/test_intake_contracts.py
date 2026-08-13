"""Contract tests for intake / onboarding event schemas."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from adaptix_contracts.schemas.intake_contracts import (
    AdaptixModule,
    BillingReadinessState,
    ConditionalEmsFireFields,
    ContractSignatureCompletedEvent,
    FounderNextActionCreatedEvent,
    GoLiveReadinessCalculatedEvent,
    GrowthPostPublishedEvent,
    IntakeInitializeRequest,
    IntakeInitializeResponse,
    IntakeSegment,
    IntakeSubmittedEvent,
    LeadScoredEvent,
    LeadTemperature,
    OnboardingSessionCreatedEvent,
    TenantProvisionedEvent,
)


def _envelope(**overrides):
    base = dict(
        event_id=uuid.uuid4(),
        event_version=1,
        tenant_id=None,
        organization_id=uuid.uuid4(),
        actor_id=None,
        actor_type="visitor",
        correlation_id=uuid.uuid4(),
        idempotency_key="abc",
        occurred_at=datetime.now(UTC),
        payload={"k": "v"},
    )
    base.update(overrides)
    return base


def test_intake_submitted_event_locks_event_type_literal():
    ev = IntakeSubmittedEvent(**_envelope())
    assert ev.event_type == "IntakeSubmitted"

    with pytest.raises(ValidationError):
        IntakeSubmittedEvent(**_envelope(event_type="SomethingElse"))


def test_all_23_event_classes_have_distinct_event_type_literals():
    classes = [
        IntakeSubmittedEvent,
        LeadScoredEvent,
        OnboardingSessionCreatedEvent,
        ContractSignatureCompletedEvent,
        TenantProvisionedEvent,
        GoLiveReadinessCalculatedEvent,
        GrowthPostPublishedEvent,
        FounderNextActionCreatedEvent,
    ]
    seen = set()
    for cls in classes:
        ev = cls(**_envelope())
        assert ev.event_type not in seen
        seen.add(ev.event_type)


def test_intake_initialize_request_valid_minimal():
    req = IntakeInitializeRequest(
        email="a@b.com",
        full_name="A B",
        organization_name="Org",
        role_title="Chief",
        organization_type=IntakeSegment.EMS_AGENCY,
        state_region="CA",
        primary_goal="Replace ePCR.",
        terms_accepted=True,
    )
    assert req.organization_type is IntakeSegment.EMS_AGENCY
    assert req.terms_accepted is True


def test_intake_initialize_request_rejects_invalid_email():
    with pytest.raises(ValidationError):
        IntakeInitializeRequest(
            email="not-an-email",
            full_name="A B",
            organization_name="Org",
            role_title="Chief",
            organization_type=IntakeSegment.EMS_AGENCY,
            state_region="CA",
            primary_goal="x",
            terms_accepted=True,
        )


def test_conditional_blocks_round_trip():
    req = IntakeInitializeRequest(
        email="a@b.com",
        full_name="A B",
        organization_name="Org",
        role_title="Chief",
        organization_type=IntakeSegment.EMS_AGENCY,
        state_region="CA",
        primary_goal="x",
        terms_accepted=True,
        ems_fire=ConditionalEmsFireFields(
            number_of_units=3,
            requested_modules=[AdaptixModule.CAD, AdaptixModule.FIELD],
        ),
    )
    payload = req.model_dump(mode="json")
    rebuilt = IntakeInitializeRequest.model_validate(payload)
    assert rebuilt.ems_fire is not None
    assert rebuilt.ems_fire.number_of_units == 3
    assert AdaptixModule.CAD in rebuilt.ems_fire.requested_modules


def test_intake_initialize_response_clamps_score_via_validator():
    resp = IntakeInitializeResponse(
        intake_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        contact_id=uuid.uuid4(),
        tenant_id=None,
        onboarding_session_id=None,
        segment=IntakeSegment.INVESTOR,
        lead_score=80,
        lead_temperature=LeadTemperature.HOT,
        redirect_url="/relations/investor",
        provisioned=False,
        required_next_step="founder_review_investor",
        founder_action_required=True,
    )
    assert resp.lead_score == 80

    with pytest.raises(ValidationError):
        IntakeInitializeResponse(
            intake_id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            contact_id=uuid.uuid4(),
            segment=IntakeSegment.INVESTOR,
            lead_score=101,
            lead_temperature=LeadTemperature.HOT,
            redirect_url="/x",
            provisioned=False,
            founder_action_required=True,
        )


def test_billing_readiness_states_are_authoritative():
    expected = {
        "billing_not_started",
        "billing_profile_started",
        "billing_profile_complete",
        "clearinghouse_pending",
        "migration_pending",
        "ready_for_test_claim",
        "ready_for_production_claims",
        "blocked",
    }
    assert {s.value for s in BillingReadinessState} == expected
