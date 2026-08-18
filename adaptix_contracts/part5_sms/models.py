"""Pydantic models for Play P14 — Adaptix Part 5 SMS.

Each model is the shared cross-domain contract for the corresponding artifact
in an FAA Part 5 Safety Management System. Field docstrings name the pillar
the artifact belongs to so consumers do not have to re-derive that mapping.

Producer: Adaptix-Compliance-Service (service-registry slug ``compliance``).
Downstream consumers: Adaptix-Analytics-Service (safety dashboards),
Adaptix-Audit-Service (regulator-facing audit trail), Adaptix-Workforce-Service
(training linkage for Safety Promotion), and Adaptix-Legal-Service (regulator
correspondence + corrective-action commitments).

The subpackage deliberately owns its own enums (see
:mod:`adaptix_contracts.part5_sms.enums`) rather than reaching into
``adaptix_contracts.schemas`` — Part 5 SMS is domain-specific vocabulary that
must not silently drift as other domain enums evolve.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from adaptix_contracts.part5_sms.enums import (
    HazardSeverity,
    Part5Pillar,
    RiskLevel,
)


# ---------------------------------------------------------------------------
# Pillar 1 — Safety Policy
# ---------------------------------------------------------------------------


class SafetyPolicy(BaseModel):
    """A signed safety-policy document. Pillar: ``policy``.

    Represents a versioned Safety Policy statement issued by the accountable
    executive. Signature evidence is a TrustSign envelope reference — the
    signature bytes live in the TrustSign authority, not on this row.
    """

    policy_id: str
    tenant_id: str
    pillar: Literal[Part5Pillar.POLICY] = Field(
        default=Part5Pillar.POLICY,
        description="Fixed to ``policy`` — the Safety Policy pillar.",
    )
    title: str
    version: str
    accountable_executive_id: str = Field(
        description=(
            "User id of the accountable executive who owns this policy under "
            "14 CFR Part 5.25(a)."
        ),
    )
    safety_manager_id: str = Field(
        description=("User id of the appointed safety manager (Part 5.25(b))."),
    )
    effective_date: date
    review_due_date: date | None = None
    trustsign_envelope_id: str | None = Field(
        default=None,
        description=(
            "TrustSign envelope id carrying the accountable executive's "
            "signature. Absent while the policy is still in draft."
        ),
    )
    document_uri: str = Field(
        description=(
            "S3 or object-store URI of the signed policy PDF managed by "
            "Adaptix-Documents-Service."
        ),
    )
    superseded_by_policy_id: str | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Pillar 2 — Safety Risk Management (SRM)
# ---------------------------------------------------------------------------


class HazardReport(BaseModel):
    """A hazard identified by an employee, audit, or telemetry signal.

    Pillar: ``srm``. Corresponds to the SRM process required by 14 CFR
    Part 5.53. The report is the raw input to a :class:`RiskAssessment`; it
    does NOT itself carry a risk classification.
    """

    hazard_report_id: str
    tenant_id: str
    pillar: Literal[Part5Pillar.SRM] = Field(default=Part5Pillar.SRM)
    reporter_user_id: str | None = Field(
        default=None,
        description=(
            "User id of the person who filed the report, or ``None`` if the "
            "safety programme accepts anonymous reports (Part 5.71 "
            "confidential-reporting protection)."
        ),
    )
    reported_at: datetime
    location: str | None = Field(
        default=None,
        description=(
            "Free-text location — station, base, mission id, or geographic "
            "descriptor. Structured coordinates live in the related mission "
            "or incident record."
        ),
    )
    system_or_operation: str = Field(
        description=(
            "The operational system, procedure, or process the hazard was "
            "observed in (e.g. ``rotor-wing preflight``, ``narcotics chain "
            "of custody``, ``dispatch handoff``)."
        ),
    )
    description: str
    severity: HazardSeverity | None = Field(
        default=None,
        description=(
            "Reporter's initial severity estimate. The authoritative severity "
            "is set on the resulting :class:`RiskAssessment`."
        ),
    )
    likely_consequences: list[str] = Field(default_factory=list)
    linked_incident_ids: list[str] = Field(default_factory=list)
    linked_mission_ids: list[str] = Field(default_factory=list)
    attachments: list[str] = Field(
        default_factory=list,
        description="Object-store URIs for photos, video, or referenced docs.",
    )
    triage_status: Literal[
        "OPEN", "TRIAGED", "ASSESSED", "MITIGATED", "CLOSED", "DUPLICATE"
    ] = "OPEN"
    duplicate_of_hazard_report_id: str | None = None
    created_at: datetime
    updated_at: datetime


class RiskAssessment(BaseModel):
    """The severity/likelihood analysis of a :class:`HazardReport`.

    Pillar: ``srm``. Produced by the safety manager or an assigned assessor
    and captures the assessed risk level plus the residual risk level after
    the linked mitigations are considered.
    """

    risk_assessment_id: str
    tenant_id: str
    pillar: Literal[Part5Pillar.SRM] = Field(default=Part5Pillar.SRM)
    hazard_report_id: str = Field(
        description="The :class:`HazardReport` this assessment scores.",
    )
    assessor_user_id: str
    assessed_at: datetime
    severity: HazardSeverity
    likelihood_score: int = Field(
        ge=1,
        le=5,
        description=(
            "Likelihood on the 5-point Part 5 SRM matrix: 1=Extremely "
            "Improbable, 2=Improbable, 3=Remote, 4=Occasional, 5=Frequent."
        ),
    )
    initial_risk_level: RiskLevel = Field(
        description=(
            "Risk level implied by ``severity`` and ``likelihood_score`` "
            "BEFORE any mitigations from this assessment are applied."
        ),
    )
    residual_risk_level: RiskLevel | None = Field(
        default=None,
        description=(
            "Risk level projected AFTER the linked mitigations are in place. "
            "``None`` while mitigations are still being designed."
        ),
    )
    acceptability: Literal["ACCEPTABLE", "REVIEW", "UNACCEPTABLE"] = Field(
        description=(
            "The accept/review/reject decision on this residual risk. Must "
            "not be ``ACCEPTABLE`` when ``residual_risk_level`` is EXTREME."
        ),
    )
    mitigation_ids: list[str] = Field(default_factory=list)
    rationale: str
    reviewed_by_user_id: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class Mitigation(BaseModel):
    """A control implemented to reduce risk from a :class:`RiskAssessment`.

    Pillar: ``srm``. Tracks the control from design through verification, so
    Safety Assurance (Pillar 3) can measure whether the control is actually
    effective in operation.
    """

    mitigation_id: str
    tenant_id: str
    pillar: Literal[Part5Pillar.SRM] = Field(default=Part5Pillar.SRM)
    risk_assessment_id: str
    hazard_report_id: str | None = Field(
        default=None,
        description=(
            "Convenience back-reference to the originating hazard. Must match "
            "the ``hazard_report_id`` on the linked risk assessment when set."
        ),
    )
    control_type: Literal[
        "ELIMINATION",
        "SUBSTITUTION",
        "ENGINEERING",
        "ADMINISTRATIVE",
        "PPE",
        "TRAINING",
        "PROCEDURE_CHANGE",
        "MONITORING",
    ] = Field(
        description=(
            "Hierarchy-of-controls classification. ``ELIMINATION`` is highest "
            "preference; ``PPE`` and ``ADMINISTRATIVE`` are lowest."
        ),
    )
    description: str
    owner_user_id: str
    planned_implementation_date: date | None = None
    implemented_at: datetime | None = None
    implementation_evidence_uri: str | None = None
    effectiveness_verified_at: datetime | None = None
    effectiveness_verified_by_user_id: str | None = None
    status: Literal[
        "PROPOSED",
        "APPROVED",
        "IN_PROGRESS",
        "IMPLEMENTED",
        "VERIFIED_EFFECTIVE",
        "INEFFECTIVE",
        "SUPERSEDED",
    ] = "PROPOSED"
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Pillar 3 — Safety Assurance (SA)
# ---------------------------------------------------------------------------


class InternalAudit(BaseModel):
    """An internal Safety Assurance audit or evaluation.

    Pillar: ``sa``. Records the audit's scope, lead auditor, findings, and
    the corrective-action items opened as a result. Corrective-action closure
    is tracked on :class:`CorrectiveAction`.
    """

    audit_id: str
    tenant_id: str
    pillar: Literal[Part5Pillar.SA] = Field(default=Part5Pillar.SA)
    title: str
    scope: str
    scheduled_date: date
    opened_at: datetime
    closed_at: datetime | None = None
    lead_auditor_user_id: str
    auditor_user_ids: list[str] = Field(default_factory=list)
    audited_processes: list[str] = Field(
        default_factory=list,
        description=(
            "The operational processes covered by the audit (e.g. "
            "``dispatch``, ``narcotics``, ``crew scheduling``)."
        ),
    )
    findings_count: int = Field(
        default=0,
        ge=0,
        description="Total findings recorded. Includes conforming findings.",
    )
    nonconformance_count: int = Field(
        default=0,
        ge=0,
        description="Number of findings that are non-conformances.",
    )
    corrective_action_ids: list[str] = Field(default_factory=list)
    status: Literal[
        "PLANNED", "OPEN", "FIELDWORK", "REPORTING", "CLOSED", "CANCELLED"
    ] = "PLANNED"
    report_uri: str | None = None
    created_at: datetime
    updated_at: datetime


class CorrectiveAction(BaseModel):
    """A corrective action opened to resolve an audit finding or hazard.

    Pillar: ``sa``. Closes the Safety Assurance loop back to Safety Risk
    Management by proving a finding has been addressed and the fix is
    effective.
    """

    corrective_action_id: str
    tenant_id: str
    pillar: Literal[Part5Pillar.SA] = Field(default=Part5Pillar.SA)
    source_audit_id: str | None = None
    source_hazard_report_id: str | None = None
    source_risk_assessment_id: str | None = None
    finding_reference: str = Field(
        description=(
            "Human-readable finding identifier from the source audit or "
            "regulator letter (e.g. ``NC-2026-014``)."
        ),
    )
    description: str
    root_cause: str | None = None
    owner_user_id: str
    due_date: date
    opened_at: datetime
    closed_at: datetime | None = None
    closed_by_user_id: str | None = None
    verification_evidence_uri: str | None = Field(
        default=None,
        description=(
            "Object-store URI of the evidence that closed this action "
            "(inspection photo, retraining certificate, procedure diff)."
        ),
    )
    effectiveness_check_due_date: date | None = None
    effectiveness_check_completed_at: datetime | None = None
    status: Literal[
        "OPEN",
        "IN_PROGRESS",
        "AWAITING_VERIFICATION",
        "CLOSED",
        "REOPENED",
        "CANCELLED",
    ] = "OPEN"
    linked_mitigation_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Aggregate — SMS binder (spans all four pillars)
# ---------------------------------------------------------------------------


class SmsBinder(BaseModel):
    """Tenant-level SMS binder — the aggregate FAA regulators inspect.

    Not scoped to a single pillar; the binder is the regulator-facing rollup
    of the tenant's Part 5 SMS state. ``pillar`` is nullable and, when set,
    means the binder view is filtered to that pillar (e.g. the SRM section
    of the binder in Adaptix Founder Command).
    """

    sms_binder_id: str
    tenant_id: str
    binder_version: str
    pillar: Part5Pillar | None = Field(
        default=None,
        description=(
            "Optional pillar filter for a scoped binder view. ``None`` means "
            "the full four-pillar binder."
        ),
    )
    accountable_executive_id: str
    safety_manager_id: str
    active_policy_id: str | None = None
    open_hazard_count: int = Field(default=0, ge=0)
    open_high_or_extreme_risk_count: int = Field(default=0, ge=0)
    open_corrective_action_count: int = Field(default=0, ge=0)
    overdue_corrective_action_count: int = Field(default=0, ge=0)
    last_audit_id: str | None = None
    last_audit_closed_at: datetime | None = None
    next_audit_scheduled_date: date | None = None
    safety_reporting_rate_per_1000_hours: Decimal | None = Field(
        default=None,
        description=(
            "Hazard reports per 1000 exposure hours across the reporting "
            "window. Decimal keeps the regulator-facing number precise."
        ),
    )
    reporting_period_start: date | None = None
    reporting_period_end: date | None = None
    binder_pdf_uri: str | None = Field(
        default=None,
        description=(
            "Object-store URI of the currently published binder PDF used for "
            "regulator hand-off."
        ),
    )
    generated_at: datetime
    updated_at: datetime


__all__ = [
    "CorrectiveAction",
    "HazardReport",
    "InternalAudit",
    "Mitigation",
    "RiskAssessment",
    "SafetyPolicy",
    "SmsBinder",
]
