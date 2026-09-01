"""MIH remote-monitoring and high-utilizer contracts.

These pin the vocabulary and invariants Adaptix-MIH-Service enforces
server-side so a producer or consumer cannot drift from them silently:
strict event/source enums, reachable policy thresholds, a trigger score that
is exactly the count of satisfied dimensions, a recommendation that never
means "enrolled by the system", and deterministic event idempotency keys.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from adaptix_contracts.events.envelope import AdaptixEventEnvelope
from adaptix_contracts.mih import (
    MIH_ENROLLMENT_RECOMMENDATION_CHANGED,
    MIH_EVENTS,
    MIH_HIGH_UTILIZER_EVALUATED,
    MIH_UTILIZATION_OBSERVATION_RECORDED,
    EnrollmentRecommendationStatus,
    HighUtilizerRecommendedAction,
    HighUtilizerSignal,
    MihEnrollmentRecommendation,
    MihEnrollmentRecommendationChangedPayload,
    MihErrorCode,
    MihEscalation,
    MihEscalationState,
    MihHighUtilizerEvaluatedPayload,
    MihMonitoringThreshold,
    MihRemoteReading,
    MihUtilizationObservation,
    MihUtilizationObservationRecordedPayload,
    MihUtilizationPolicy,
    RemoteReadingMetric,
    UtilizationEvaluationOrigin,
    UtilizationEventType,
    UtilizationPolicyStatus,
    UtilizationSourceSystem,
    build_mih_enrollment_recommendation_changed_event,
    build_mih_high_utilizer_evaluated_event,
    build_mih_utilization_observation_recorded_event,
    recommendation_invalid_transition,
    recommendation_not_found,
    to_adaptix_error_code,
    utilization_policy_not_configured,
)
from adaptix_contracts.errors.envelope import AdaptixErrorCode

TENANT = "00000000-0000-0000-0000-00000000aaaa"
NOW = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Vocabulary — must equal the strings Adaptix-MIH-Service stores and accepts
# ---------------------------------------------------------------------------


def test_utilization_vocabulary_matches_the_service() -> None:
    assert {e.value for e in UtilizationEventType} == {
        "911_call",
        "ed_visit",
        "hospital_admission",
    }
    assert {e.value for e in UtilizationSourceSystem} == {
        "epcr",
        "qhin",
        "manual_verified",
    }
    assert {e.value for e in UtilizationPolicyStatus} == {"active", "superseded"}
    assert {e.value for e in UtilizationEvaluationOrigin} == {
        "observation_ingest",
        "explicit",
    }
    assert {e.value for e in EnrollmentRecommendationStatus} == {
        "open",
        "acknowledged",
        "dismissed",
        "enrolled",
        "expired",
    }
    assert {e.value for e in RemoteReadingMetric} == {
        "systolic_bp",
        "diastolic_bp",
        "heart_rate",
        "spo2",
        "weight_kg",
        "glucose_mg_dl",
        "hrv_ms",
    }
    assert {e.value for e in MihEscalationState} == {"open", "acknowledged"}


def test_no_demo_or_sample_source_system_exists() -> None:
    for banned in ("demo", "sample", "fake", "test"):
        assert banned not in {e.value for e in UtilizationSourceSystem}


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


def _policy(**overrides):
    body = {
        "tenant_id": TENANT,
        "id": uuid4(),
        "version": 1,
        "status": UtilizationPolicyStatus.ACTIVE,
        "lookback_days": 30,
        "min_911_calls": 2,
        "recommendation_min_score": 1,
        "created_by": "user-1",
        "created_at": NOW,
    }
    body.update(overrides)
    return MihUtilizationPolicy(**body)


def test_policy_round_trips_and_counts_enabled_dimensions() -> None:
    policy = _policy(min_ed_visits=3, recommendation_min_score=2)
    assert policy.enabled_dimensions == 2
    assert policy.min_admissions is None
    assert MihUtilizationPolicy.model_validate(policy.model_dump()) == policy


@pytest.mark.parametrize(
    "overrides",
    [
        {"min_911_calls": 0},
        {"min_ed_visits": 0},
        {"lookback_days": 0},
        {"lookback_days": 366},
        {"recommendation_min_score": 0},
        {"recommendation_min_score": 4},
        {"version": 0},
    ],
)
def test_policy_rejects_out_of_range_values(overrides) -> None:
    with pytest.raises(ValidationError):
        _policy(**overrides)


def test_policy_rejects_no_enabled_dimension() -> None:
    with pytest.raises(ValidationError, match="at least one utilization dimension"):
        _policy(min_911_calls=None)


def test_policy_rejects_unreachable_recommendation_score() -> None:
    with pytest.raises(ValidationError, match="can never be reached"):
        _policy(min_ed_visits=2, recommendation_min_score=3)


# ---------------------------------------------------------------------------
# Observation
# ---------------------------------------------------------------------------


def _observation(**overrides) -> MihUtilizationObservation:
    body = {
        "tenant_id": TENANT,
        "id": uuid4(),
        "patient_identity_id": "identity-1",
        "event_type": UtilizationEventType.CALL_911,
        "source_system": UtilizationSourceSystem.EPCR,
        "source_event_id": "epcr-run-1",
        "occurred_at": NOW - timedelta(hours=1),
        "recorded_by": "user-1",
        "recorded_at": NOW,
    }
    body.update(overrides)
    return MihUtilizationObservation(**body)


def test_observation_requires_timezone_aware_occurred_at() -> None:
    with pytest.raises(ValidationError, match="timezone offset"):
        _observation(occurred_at=datetime(2026, 9, 1, 11, 0))


def test_observation_normalises_occurred_at_to_utc() -> None:
    local = datetime(2026, 9, 1, 6, 0, tzinfo=timezone(timedelta(hours=-5)))
    obs = _observation(occurred_at=local)
    assert obs.occurred_at == datetime(2026, 9, 1, 11, 0, tzinfo=timezone.utc)


def test_observation_rejects_unknown_vocabulary_and_phi_fields() -> None:
    with pytest.raises(ValidationError):
        _observation(event_type="er_visit")
    with pytest.raises(ValidationError):
        _observation(source_system="demo")
    with pytest.raises(ValidationError):
        _observation(display_name="Jordan Rivera")


# ---------------------------------------------------------------------------
# HighUtilizerSignal — the transparent score
# ---------------------------------------------------------------------------


def _signal(**overrides) -> HighUtilizerSignal:
    body = {
        "tenant_id": TENANT,
        "evaluation_id": uuid4(),
        "patient_identity_id": "identity-1",
        "policy_id": uuid4(),
        "policy_version": 1,
        "window_start": NOW - timedelta(days=30),
        "window_end": NOW,
        "count_911_calls": 5,
        "count_ed_visits": 3,
        "count_admissions": 1,
        "trigger_911": True,
        "trigger_ed": True,
        "trigger_admission": None,
        "trigger_score": 2,
        "recommendation_triggered": True,
        "already_enrolled": False,
        "recommended_action": HighUtilizerRecommendedAction.CONSIDER_ENROLLMENT,
        "evaluated_at": NOW,
        "evaluated_by": "user-1",
        "evaluation_origin": UtilizationEvaluationOrigin.OBSERVATION_INGEST,
    }
    body.update(overrides)
    return HighUtilizerSignal(**body)


def test_signal_spec_example_two_of_three_dimensions() -> None:
    signal = _signal()
    assert signal.trigger_score == 2
    assert signal.trigger_admission is None  # disabled dimension: not evaluated
    assert (
        signal.recommended_action is HighUtilizerRecommendedAction.CONSIDER_ENROLLMENT
    )


def test_signal_score_must_equal_satisfied_dimensions() -> None:
    with pytest.raises(ValidationError, match="does not equal"):
        _signal(trigger_score=3)
    with pytest.raises(ValidationError, match="does not equal"):
        _signal(trigger_911=False, trigger_score=2)


def test_signal_recommended_action_follows_flags() -> None:
    with pytest.raises(ValidationError, match="recommended_action"):
        _signal(recommended_action=HighUtilizerRecommendedAction.NONE)
    enrolled = _signal(
        already_enrolled=True,
        recommended_action=HighUtilizerRecommendedAction.ALREADY_ENROLLED,
    )
    assert enrolled.recommendation_triggered is True
    below = _signal(
        trigger_911=False,
        trigger_ed=False,
        trigger_score=0,
        recommendation_triggered=False,
        recommended_action=HighUtilizerRecommendedAction.NONE,
    )
    assert below.trigger_score == 0


def test_signal_window_must_be_ordered_and_score_bounded() -> None:
    with pytest.raises(ValidationError, match="window_end"):
        _signal(window_end=NOW - timedelta(days=31))
    with pytest.raises(ValidationError):
        _signal(trigger_score=4)


# ---------------------------------------------------------------------------
# Recommendation
# ---------------------------------------------------------------------------


def _recommendation(**overrides) -> MihEnrollmentRecommendation:
    body = {
        "tenant_id": TENANT,
        "id": uuid4(),
        "patient_identity_id": "identity-1",
        "policy_id": uuid4(),
        "policy_version": 1,
        "latest_evaluation_id": uuid4(),
        "trigger_score": 2,
        "count_911_calls": 5,
        "count_ed_visits": 3,
        "count_admissions": 0,
        "status": EnrollmentRecommendationStatus.OPEN,
        "created_at": NOW,
        "updated_at": NOW,
    }
    body.update(overrides)
    return MihEnrollmentRecommendation(**body)


def test_recommendation_dismissed_requires_reason() -> None:
    with pytest.raises(ValidationError, match="dismissal_reason"):
        _recommendation(status=EnrollmentRecommendationStatus.DISMISSED)
    with pytest.raises(ValidationError, match="dismissal_reason"):
        _recommendation(
            status=EnrollmentRecommendationStatus.DISMISSED, dismissal_reason="  "
        )
    ok = _recommendation(
        status=EnrollmentRecommendationStatus.DISMISSED,
        dismissal_reason="declined outreach",
        dismissed_by="sup-1",
        dismissed_at=NOW,
    )
    assert ok.status is EnrollmentRecommendationStatus.DISMISSED


def test_recommendation_enrolled_must_reference_existing_patient() -> None:
    with pytest.raises(ValidationError, match="resolved_patient_id"):
        _recommendation(status=EnrollmentRecommendationStatus.ENROLLED)
    with pytest.raises(ValidationError, match="only valid when status=enrolled"):
        _recommendation(resolved_patient_id=uuid4())
    ok = _recommendation(
        status=EnrollmentRecommendationStatus.ENROLLED,
        resolved_patient_id=uuid4(),
        resolved_by="sup-1",
        resolved_at=NOW,
    )
    assert ok.resolved_patient_id is not None


def test_recommendation_has_no_way_to_create_an_enrollment() -> None:
    fields = set(MihEnrollmentRecommendation.model_fields)
    assert "consent_obtained" not in fields
    assert "display_name" not in fields
    assert "enroll" not in " ".join(fields)


# ---------------------------------------------------------------------------
# Remote monitoring
# ---------------------------------------------------------------------------


def test_threshold_needs_a_bound_and_ordered_bounds() -> None:
    base = {
        "tenant_id": TENANT,
        "metric": RemoteReadingMetric.SPO2,
        "updated_by": "admin-1",
        "updated_at": NOW,
    }
    with pytest.raises(ValidationError, match="at least one"):
        MihMonitoringThreshold(**base)
    with pytest.raises(ValidationError, match="below max_value"):
        MihMonitoringThreshold(**base, min_value=95.0, max_value=90.0)
    ok = MihMonitoringThreshold(**base, min_value=90.0)
    assert ok.max_value is None


def test_reading_threshold_breached_is_tri_state_and_breach_is_typed() -> None:
    base = {
        "tenant_id": TENANT,
        "id": uuid4(),
        "patient_id": uuid4(),
        "client_reference_id": "ref-1",
        "metric": RemoteReadingMetric.HEART_RATE,
        "value": 145.0,
        "unit": "bpm",
        "taken_at": NOW,
        "created_at": NOW,
    }
    not_evaluated = MihRemoteReading(**base)
    assert not_evaluated.threshold_breached is None
    breached = MihRemoteReading(
        **base,
        threshold_breached=True,
        breach_detail={
            "bound": "max",
            "limit": 120.0,
            "observed": 145.0,
            "metric": "heart_rate",
        },
    )
    assert breached.breach_detail is not None
    assert breached.breach_detail.bound == "max"
    with pytest.raises(ValidationError):
        MihRemoteReading(**{**base, "taken_at": datetime(2026, 9, 1, 12, 0)})
    with pytest.raises(ValidationError):
        MihRemoteReading(**{**base, "metric": "banana_ripeness"})


def test_escalation_defaults_open() -> None:
    esc = MihEscalation(
        tenant_id=TENANT,
        id=uuid4(),
        patient_id=uuid4(),
        reading_id=uuid4(),
        reason="heart_rate 145.0 bpm breached the max threshold 120.0",
        created_at=NOW,
    )
    assert esc.state is MihEscalationState.OPEN
    assert esc.acknowledged_by is None


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


def test_new_event_names_are_registered() -> None:
    assert {
        MIH_UTILIZATION_OBSERVATION_RECORDED,
        MIH_HIGH_UTILIZER_EVALUATED,
        MIH_ENROLLMENT_RECOMMENDATION_CHANGED,
    } <= MIH_EVENTS
    assert (
        MIH_UTILIZATION_OBSERVATION_RECORDED == "mih.utilization.observation_recorded"
    )
    assert MIH_HIGH_UTILIZER_EVALUATED == "mih.high_utilizer.evaluated"
    assert (
        MIH_ENROLLMENT_RECOMMENDATION_CHANGED == "mih.enrollment_recommendation.changed"
    )


def test_observation_recorded_event_is_idempotent_on_observation_id() -> None:
    observation_id = uuid4()
    payload = MihUtilizationObservationRecordedPayload(
        tenant_id=TENANT,
        observation_id=observation_id,
        patient_identity_id="identity-1",
        event_type=UtilizationEventType.ED_VISIT,
        source_system=UtilizationSourceSystem.QHIN,
        source_event_id="qhin-visit-9",
        recorded_by="sup-1",
    )
    first = build_mih_utilization_observation_recorded_event(payload, actor_id="sup-1")
    second = build_mih_utilization_observation_recorded_event(payload)
    assert isinstance(first, AdaptixEventEnvelope)
    assert first.event_type == MIH_UTILIZATION_OBSERVATION_RECORDED
    assert first.tenant_id == TENANT
    assert first.source_service == "mih"
    assert first.idempotency_key == second.idempotency_key
    assert first.idempotency_key.endswith(str(observation_id))
    assert first.payload["event_type"] == "ed_visit"
    assert "display_name" not in first.payload


def test_high_utilizer_evaluated_event_carries_the_signal() -> None:
    signal = _signal()
    payload = MihHighUtilizerEvaluatedPayload(
        tenant_id=TENANT,
        signal=signal,
        recommendation_id=uuid4(),
        recommendation_status=EnrollmentRecommendationStatus.OPEN,
    )
    envelope = build_mih_high_utilizer_evaluated_event(payload)
    assert envelope.event_type == MIH_HIGH_UTILIZER_EVALUATED
    assert envelope.idempotency_key.endswith(str(signal.evaluation_id))
    assert envelope.payload["signal"]["trigger_score"] == 2
    assert envelope.payload["signal"]["recommended_action"] == "consider_enrollment"


def test_recommendation_changed_event_keys_on_transition() -> None:
    rec_id, eval_id, policy_id = uuid4(), uuid4(), uuid4()

    def payload(action: str, status: EnrollmentRecommendationStatus):
        return MihEnrollmentRecommendationChangedPayload(
            tenant_id=TENANT,
            recommendation_id=rec_id,
            patient_identity_id="identity-1",
            policy_id=policy_id,
            policy_version=1,
            status=status,
            action=action,
            trigger_score=2,
            latest_evaluation_id=eval_id,
        )

    created = build_mih_enrollment_recommendation_changed_event(
        payload("created", EnrollmentRecommendationStatus.OPEN)
    )
    created_again = build_mih_enrollment_recommendation_changed_event(
        payload("created", EnrollmentRecommendationStatus.OPEN)
    )
    acknowledged = build_mih_enrollment_recommendation_changed_event(
        payload("acknowledged", EnrollmentRecommendationStatus.ACKNOWLEDGED)
    )
    assert created.idempotency_key == created_again.idempotency_key
    assert created.idempotency_key != acknowledged.idempotency_key
    assert acknowledged.payload["status"] == "acknowledged"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


def test_new_error_codes_map_to_platform_codes() -> None:
    expected = {
        MihErrorCode.UTILIZATION_POLICY_NOT_CONFIGURED: AdaptixErrorCode.NOT_CONFIGURED,
        MihErrorCode.UTILIZATION_POLICY_VERSION_CONFLICT: AdaptixErrorCode.CONFLICT,
        MihErrorCode.UTILIZATION_SOURCE_EVENT_CONFLICT: AdaptixErrorCode.CONFLICT,
        MihErrorCode.UTILIZATION_EVALUATION_CONFLICT: AdaptixErrorCode.CONFLICT,
        MihErrorCode.UTILIZATION_INVALID_EVENT_TYPE: AdaptixErrorCode.INVALID_VALUE,
        MihErrorCode.RECOMMENDATION_NOT_FOUND: AdaptixErrorCode.NOT_FOUND,
        MihErrorCode.RECOMMENDATION_ALREADY_DISMISSED: (
            AdaptixErrorCode.INVALID_STATE_TRANSITION
        ),
        MihErrorCode.RECOMMENDATION_ENROLLMENT_NOT_ACTIVE: (
            AdaptixErrorCode.WORKFLOW_BLOCKED
        ),
        MihErrorCode.READING_INVALID_METRIC: AdaptixErrorCode.INVALID_VALUE,
    }
    for mih_code, platform_code in expected.items():
        assert to_adaptix_error_code(mih_code) is platform_code
    # Every code has a mapping — a new code without one raises KeyError here.
    for code in MihErrorCode:
        to_adaptix_error_code(code)


def test_error_constructors_produce_mih_envelopes() -> None:
    env = utilization_policy_not_configured()
    assert env.mih_error_code is MihErrorCode.UTILIZATION_POLICY_NOT_CONFIGURED
    assert env.error_code is AdaptixErrorCode.NOT_CONFIGURED
    assert "no default thresholds" in env.message
    missing = recommendation_not_found("rec-1")
    assert missing.error_code is AdaptixErrorCode.NOT_FOUND
    bad = recommendation_invalid_transition("rec-1", "expired", "acknowledge")
    assert bad.mih_error_code is MihErrorCode.RECOMMENDATION_INVALID_TRANSITION
    assert "cannot acknowledge from status expired" in bad.message
