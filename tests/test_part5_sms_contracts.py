"""Regression tests for the Play P14 Part 5 SMS contract subpackage."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from pydantic import BaseModel

from adaptix_contracts.part5_sms import (
    PART5_SMS_EVENTS,
    SMS_AUDIT_OPENED,
    SMS_CORRECTIVE_ACTION_CLOSED,
    SMS_HAZARD_REPORTED,
    SMS_MITIGATION_IMPLEMENTED,
    SMS_RISK_ASSESSED,
    CorrectiveAction,
    HazardReport,
    HazardSeverity,
    InternalAudit,
    Mitigation,
    Part5Pillar,
    RiskAssessment,
    RiskLevel,
    SafetyPolicy,
    SmsBinder,
)
from adaptix_contracts.part5_sms import enums as enums_module
from adaptix_contracts.part5_sms import events as events_module
from adaptix_contracts.part5_sms import models as models_module


_NOW = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)
_TODAY = date(2026, 8, 18)


def test_part5_pillar_values_match_the_play_p14_contract() -> None:
    assert Part5Pillar.POLICY.value == "policy"
    assert Part5Pillar.SRM.value == "srm"
    assert Part5Pillar.SA.value == "sa"
    assert Part5Pillar.SP.value == "sp"
    assert {p.value for p in Part5Pillar} == {"policy", "srm", "sa", "sp"}


def test_hazard_severity_covers_the_faa_five_level_scale() -> None:
    assert {s.value for s in HazardSeverity} == {
        "NEGLIGIBLE",
        "MINOR",
        "MAJOR",
        "HAZARDOUS",
        "CATASTROPHIC",
    }


def test_risk_level_covers_low_medium_high_extreme() -> None:
    assert {r.value for r in RiskLevel} == {"LOW", "MEDIUM", "HIGH", "EXTREME"}


def test_event_names_match_the_play_p14_contract() -> None:
    assert SMS_HAZARD_REPORTED == "sms.hazard.reported"
    assert SMS_RISK_ASSESSED == "sms.risk.assessed"
    assert SMS_MITIGATION_IMPLEMENTED == "sms.mitigation.implemented"
    assert SMS_AUDIT_OPENED == "sms.audit.opened"
    assert SMS_CORRECTIVE_ACTION_CLOSED == "sms.corrective_action.closed"
    assert PART5_SMS_EVENTS == frozenset(
        {
            SMS_HAZARD_REPORTED,
            SMS_RISK_ASSESSED,
            SMS_MITIGATION_IMPLEMENTED,
            SMS_AUDIT_OPENED,
            SMS_CORRECTIVE_ACTION_CLOSED,
        }
    )


def test_safety_policy_round_trips_and_pins_the_policy_pillar() -> None:
    policy = SafetyPolicy(
        policy_id="policy-1",
        tenant_id="tenant-1",
        title="Adaptix Aviation Safety Policy",
        version="2026.08",
        accountable_executive_id="user-ceo",
        safety_manager_id="user-sm",
        effective_date=_TODAY,
        document_uri="s3://adaptix-docs/tenant-1/policy-1.pdf",
        created_at=_NOW,
        updated_at=_NOW,
    )
    assert policy.pillar is Part5Pillar.POLICY
    round_tripped = SafetyPolicy.model_validate_json(policy.model_dump_json())
    assert round_tripped == policy


def test_hazard_report_defaults_to_the_srm_pillar_and_open_triage() -> None:
    report = HazardReport(
        hazard_report_id="hazard-1",
        tenant_id="tenant-1",
        reported_at=_NOW,
        system_or_operation="rotor-wing preflight",
        description="Rotor blade tape lifting on ship 71.",
        created_at=_NOW,
        updated_at=_NOW,
    )
    assert report.pillar is Part5Pillar.SRM
    assert report.triage_status == "OPEN"


def test_risk_assessment_bounds_likelihood_score_to_one_through_five() -> None:
    kwargs = dict(
        risk_assessment_id="ra-1",
        tenant_id="tenant-1",
        hazard_report_id="hazard-1",
        assessor_user_id="user-sm",
        assessed_at=_NOW,
        severity=HazardSeverity.MAJOR,
        initial_risk_level=RiskLevel.HIGH,
        acceptability="REVIEW",
        rationale="Recurrent pattern across two aircraft.",
        created_at=_NOW,
        updated_at=_NOW,
    )
    assert RiskAssessment(likelihood_score=3, **kwargs).likelihood_score == 3
    for out_of_range in (0, 6):
        try:
            RiskAssessment(likelihood_score=out_of_range, **kwargs)
        except Exception:
            continue
        raise AssertionError(
            f"likelihood_score={out_of_range} should have been rejected"
        )


def test_mitigation_defaults_to_proposed_and_srm_pillar() -> None:
    mitigation = Mitigation(
        mitigation_id="mit-1",
        tenant_id="tenant-1",
        risk_assessment_id="ra-1",
        control_type="PROCEDURE_CHANGE",
        description="Add second inspector to preflight checklist step 14.",
        owner_user_id="user-chief-pilot",
        created_at=_NOW,
        updated_at=_NOW,
    )
    assert mitigation.pillar is Part5Pillar.SRM
    assert mitigation.status == "PROPOSED"


def test_internal_audit_defaults_to_the_sa_pillar_and_planned_status() -> None:
    audit = InternalAudit(
        audit_id="audit-1",
        tenant_id="tenant-1",
        title="Q3 dispatch audit",
        scope="Dispatch handoff to Adaptix-CAD-Service",
        scheduled_date=_TODAY,
        opened_at=_NOW,
        lead_auditor_user_id="user-auditor",
        created_at=_NOW,
        updated_at=_NOW,
    )
    assert audit.pillar is Part5Pillar.SA
    assert audit.status == "PLANNED"
    assert audit.findings_count == 0


def test_corrective_action_defaults_to_open_and_the_sa_pillar() -> None:
    ca = CorrectiveAction(
        corrective_action_id="ca-1",
        tenant_id="tenant-1",
        finding_reference="NC-2026-014",
        description="Update dispatch SOP to record supervisor override.",
        owner_user_id="user-ops-director",
        due_date=_TODAY,
        opened_at=_NOW,
        created_at=_NOW,
        updated_at=_NOW,
    )
    assert ca.pillar is Part5Pillar.SA
    assert ca.status == "OPEN"


def test_sms_binder_accepts_a_pillar_filter_and_defaults_to_full_view() -> None:
    full_binder = SmsBinder(
        sms_binder_id="binder-1",
        tenant_id="tenant-1",
        binder_version="2026.08",
        accountable_executive_id="user-ceo",
        safety_manager_id="user-sm",
        generated_at=_NOW,
        updated_at=_NOW,
    )
    assert full_binder.pillar is None

    srm_view = SmsBinder(
        sms_binder_id="binder-1-srm",
        tenant_id="tenant-1",
        binder_version="2026.08",
        pillar=Part5Pillar.SRM,
        accountable_executive_id="user-ceo",
        safety_manager_id="user-sm",
        safety_reporting_rate_per_1000_hours=Decimal("4.25"),
        generated_at=_NOW,
        updated_at=_NOW,
    )
    assert srm_view.pillar is Part5Pillar.SRM
    assert srm_view.safety_reporting_rate_per_1000_hours == Decimal("4.25")


def test_every_exported_symbol_is_importable_from_the_subpackage() -> None:
    from adaptix_contracts import part5_sms as pkg

    for name in pkg.__all__:
        assert hasattr(pkg, name), f"Missing export: {name}"


def test_every_model_can_emit_a_json_schema() -> None:
    for symbol_name in models_module.__all__:
        symbol = getattr(models_module, symbol_name)
        if isinstance(symbol, type) and issubclass(symbol, BaseModel):
            assert isinstance(symbol.model_json_schema(), dict)


def test_module_all_lists_are_self_consistent() -> None:
    assert set(enums_module.__all__) == {"HazardSeverity", "Part5Pillar", "RiskLevel"}
    assert set(events_module.__all__) == {
        "PART5_SMS_EVENTS",
        "SMS_AUDIT_OPENED",
        "SMS_CORRECTIVE_ACTION_CLOSED",
        "SMS_HAZARD_REPORTED",
        "SMS_MITIGATION_IMPLEMENTED",
        "SMS_RISK_ASSESSED",
    }
    assert set(models_module.__all__) == {
        "CorrectiveAction",
        "HazardReport",
        "InternalAudit",
        "Mitigation",
        "RiskAssessment",
        "SafetyPolicy",
        "SmsBinder",
    }
