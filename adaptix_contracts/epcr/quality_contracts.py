"""Quality module Pydantic DTOs: Medical Director, QA, and QI contracts.

Architecture rules:
- AI suggestions always include source references, confidence, and human review status.
- AI never auto-closes cases, auto-approves findings, or auto-accepts reviews.
- Providers can only receive their own feedback and education — never protected QA records.
- Medical Director notes are separate artifacts — they never appear as chart fields.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums as Literals
# ---------------------------------------------------------------------------

TriggerType = Literal["mandatory", "optional"]
Priority = Literal["critical", "high", "standard", "low"]
QACaseStatus = Literal[
    "new",
    "assigned",
    "in_review",
    "provider_clarification",
    "medical_director_escalated",
    "findings_documented",
    "education_assigned",
    "closed",
    "appealed",
]
QATriggerSource = Literal[
    "automatic",
    "random",
    "supervisor",
    "medical_director",
    "provider_request",
    "billing",
    "sentinel",
    "adverse",
    "peer_review",
    "accreditation",
]
FindingType = Literal[
    "documentation_deficiency",
    "protocol_deviation",
    "medication_variance",
    "procedure_variance",
    "adverse_event",
    "near_miss",
    "sentinel_event",
    "exemplary_performance",
    "education_opportunity",
    "process_improvement",
]
Severity = Literal["critical", "major", "minor", "informational", "commendation"]
ScoreDomain = Literal[
    "documentation", "protocol", "timeliness", "clinical", "operational"
]
MDReviewStatus = Literal[
    "pending",
    "in_review",
    "clarification_requested",
    "completed",
    "closed",
]
MDReviewType = Literal[
    "high_risk_case",
    "qa_escalation",
    "protocol_review",
    "provider_performance",
    "sentinel_event",
    "adverse_event",
]
FindingClassification = Literal[
    "protocol_deviation",
    "medication_variance",
    "exemplary_care",
    "adverse_event",
    "sentinel_event",
    "near_miss",
    "no_finding",
]
PeerReviewStatus = Literal[
    "assigned", "in_review", "provider_clarification", "completed", "closed"
]
ProtocolStatus = Literal["draft", "published", "retired"]
ProtocolVersionStatus = Literal["draft", "approved", "published", "retired"]
EducationType = Literal[
    "remedial",
    "informational",
    "protocol_review",
    "skills_review",
    "documentation_training",
    "commendation_recognition",
]
EducationStatus = Literal[
    "assigned", "acknowledged", "in_progress", "completed", "overdue", "waived"
]
FeedbackType = Literal[
    "informational",
    "clarification_requested",
    "documentation_correction",
    "education_assigned",
    "protocol_reminder",
    "commendation",
    "medical_director_note",
    "supervisor_followup",
]
FeedbackStatus = Literal["sent", "acknowledged", "responded", "closed"]
QIInitiativeStatus = Literal[
    "identified",
    "baseline_measured",
    "goal_defined",
    "intervention_planned",
    "active",
    "follow_up",
    "outcome_measured",
    "sustained_monitoring",
    "closed",
    "reopened",
]
QICategory = Literal[
    "documentation_quality",
    "medication_safety",
    "airway_management",
    "cardiac_arrest_outcomes",
    "stroke_care",
    "STEMI_care",
    "sepsis_care",
    "trauma_care",
    "pediatric_care",
    "neonatal_care",
    "refusal_documentation",
    "CCT_documentation",
    "transfer_documentation",
    "response_time",
    "turnaround_time",
    "controlled_substances",
    "provider_education",
    "protocol_compliance",
    "NEMSIS_compliance",
    "billing_documentation",
    "patient_safety",
    "operational_safety",
]
AuditEventType = Literal[
    "qa_case_created",
    "qa_case_assigned",
    "qa_score_submitted",
    "qa_finding_added",
    "qa_case_escalated",
    "qa_case_closed",
    "md_review_created",
    "md_note_added",
    "md_review_completed",
    "md_clarification_requested",
    "peer_review_assigned",
    "peer_review_completed",
    "education_assigned",
    "education_completed",
    "provider_feedback_sent",
    "provider_feedback_acknowledged",
    "protocol_created",
    "protocol_published",
    "standing_order_created",
    "standing_order_published",
    "protocol_acknowledgment_recorded",
    "qi_initiative_created",
    "qi_initiative_status_changed",
    "qi_initiative_closed",
    "accreditation_package_generated",
    "trigger_configuration_changed",
    "clinical_variance_created",
]

HumanReviewStatus = Literal["pending", "accepted", "edited", "rejected"]


# ---------------------------------------------------------------------------
# AI Suggestion Wrapper
# ---------------------------------------------------------------------------


class AISuggestion(BaseModel):
    """Wrapper for any AI-assisted suggestion in the quality module.

    AI suggestions NEVER auto-close cases, auto-approve reviews, or
    auto-finalize scores. Every suggestion requires human accept/edit/reject.
    """

    model_config = ConfigDict(extra="forbid")

    source_data_references: list[str] = Field(
        description="Chart fields, finding IDs, or case IDs that support this suggestion"
    )
    confidence_level: float = Field(
        ge=0.0, le=1.0, description="0.0=low confidence, 1.0=high confidence"
    )
    suggested_action: str
    human_review_status: HumanReviewStatus = "pending"
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# QA Trigger Configuration
# ---------------------------------------------------------------------------


class QATriggerConfigurationDTO(BaseModel):
    id: str
    tenant_id: str
    trigger_key: str
    trigger_type: TriggerType
    trigger_label: str
    priority: Priority
    is_active: bool
    condition_json: dict
    created_by: str
    created_at: datetime
    updated_at: datetime


class CreateQATriggerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trigger_key: str = Field(..., min_length=1, max_length=128)
    trigger_type: TriggerType
    trigger_label: str = Field(..., min_length=1, max_length=255)
    priority: Priority = "standard"
    condition_json: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# QA Case
# ---------------------------------------------------------------------------


class QACaseDTO(BaseModel):
    id: str
    tenant_id: str
    agency_id: str | None
    source_chart_id: str
    case_number: str
    trigger_key: str
    trigger_type: QATriggerSource
    priority: Priority
    status: QACaseStatus
    assigned_to: str | None
    assigned_at: datetime | None
    due_date: datetime | None
    qa_score: float | None
    score_version: str | None
    education_assigned: bool
    medical_director_escalated: bool
    closure_notes: str | None
    closed_at: datetime | None
    closed_by: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime


class CreateQACaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_chart_id: str
    trigger_key: str
    trigger_type: QATriggerSource = "supervisor"
    priority: Priority = "standard"
    agency_id: str | None = None
    due_date: datetime | None = None


class AssignQACaseRequest(BaseModel):
    reviewer_id: str
    due_date: datetime | None = None


class CloseQACaseRequest(BaseModel):
    closure_notes: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# QA Score
# ---------------------------------------------------------------------------


class QAScoreDTO(BaseModel):
    id: str
    tenant_id: str
    qa_case_id: str
    reviewer_id: str
    score_version: str
    documentation_quality_score: float
    protocol_adherence_score: float
    timeliness_score: float
    clinical_quality_score: float
    operational_quality_score: float
    composite_score: float
    context_flags_json: dict
    call_complexity_adjustment: float
    is_finalized: bool
    created_at: datetime


class SubmitQAScoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    documentation_quality_score: float = Field(..., ge=0, le=100)
    protocol_adherence_score: float = Field(..., ge=0, le=100)
    timeliness_score: float = Field(..., ge=0, le=100)
    clinical_quality_score: float = Field(..., ge=0, le=100)
    operational_quality_score: float = Field(..., ge=0, le=100)
    reviewer_notes: str | None = None
    context_flags: dict = Field(default_factory=dict)
    call_complexity_adjustment: float = Field(default=0.0, ge=-10, le=10)
    documentation_weight: float = Field(default=0.25, ge=0.0, le=1.0)
    protocol_weight: float = Field(default=0.25, ge=0.0, le=1.0)
    timeliness_weight: float = Field(default=0.15, ge=0.0, le=1.0)
    clinical_weight: float = Field(default=0.25, ge=0.0, le=1.0)
    operational_weight: float = Field(default=0.10, ge=0.0, le=1.0)


class QAScoreInterpretation(BaseModel):
    """Standard QA score interpretation bands."""

    composite_score: float
    band: Literal["exemplary", "meets_standard", "opportunity", "education_recommended"]
    label: str

    @classmethod
    def from_score(cls, score: float) -> QAScoreInterpretation:
        if score >= 90:
            return cls(composite_score=score, band="exemplary", label="Exemplary")
        elif score >= 80:
            return cls(
                composite_score=score, band="meets_standard", label="Meets Standard"
            )
        elif score >= 70:
            return cls(
                composite_score=score,
                band="opportunity",
                label="Opportunity for Improvement",
            )
        else:
            return cls(
                composite_score=score,
                band="education_recommended",
                label="Education Recommended",
            )


# ---------------------------------------------------------------------------
# QA Review Finding
# ---------------------------------------------------------------------------


class QAReviewFindingDTO(BaseModel):
    id: str
    tenant_id: str
    qa_case_id: str
    reviewer_id: str
    finding_type: FindingType
    severity: Severity
    domain: ScoreDomain
    description: str
    recommendation: str | None
    education_recommended: bool
    process_improvement_recommended: bool
    medical_director_review_recommended: bool
    status: str
    provider_response: str | None
    created_at: datetime


class AddFindingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    finding_type: FindingType
    severity: Severity = "minor"
    domain: ScoreDomain = "documentation"
    description: str = Field(..., min_length=1)
    recommendation: str | None = None
    chart_reference: dict = Field(default_factory=dict)
    education_recommended: bool = False
    process_improvement_recommended: bool = False
    medical_director_review_recommended: bool = False


# ---------------------------------------------------------------------------
# Peer Review
# ---------------------------------------------------------------------------


class PeerReviewDTO(BaseModel):
    id: str
    tenant_id: str
    qa_case_id: str
    source_chart_id: str
    reviewer_id: str
    assignor_id: str
    is_blind: bool
    conflict_of_interest_checked: bool
    status: PeerReviewStatus
    strengths_notes: str | None
    improvement_notes: str | None
    education_recommendation: str | None
    exemplary_care_flag: bool
    is_protected: bool
    completed_at: datetime | None
    created_at: datetime


class AssignPeerReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    qa_case_id: str
    reviewer_id: str
    chart_provider_id: str
    crew_member_ids: list[str] = Field(default_factory=list)
    is_blind: bool = False
    due_date: datetime | None = None


class CompletePeerReviewRequest(BaseModel):
    strengths_notes: str | None = None
    improvement_notes: str | None = None
    education_recommendation: str | None = None
    process_improvement_suggestion: str | None = None
    exemplary_care_flag: bool = False
    reviewer_signature: str | None = None


# ---------------------------------------------------------------------------
# Medical Director Review + Note
# ---------------------------------------------------------------------------


class MedicalDirectorReviewDTO(BaseModel):
    id: str
    tenant_id: str
    qa_case_id: str
    source_chart_id: str
    medical_director_id: str
    escalated_by: str
    escalation_reason: str
    status: MDReviewStatus
    review_type: MDReviewType
    finding_classification: FindingClassification | None
    protocol_deviation_identified: bool
    exemplary_care_identified: bool
    education_recommended: bool
    protocol_revision_recommended: bool
    agency_leadership_flag: bool
    completed_at: datetime | None
    created_at: datetime


class MedicalDirectorNoteDTO(BaseModel):
    """Protected MD note — stored as separate artifact, never in original chart."""

    id: str
    tenant_id: str
    medical_director_review_id: str
    source_chart_id: str
    author_id: str
    author_role: str
    note_type: str
    note_text: str
    recommendation: str | None
    finding_type: str | None
    is_protected: bool  # always True
    created_at: datetime


class AddMDNoteRequest(BaseModel):
    note_type: str = "finding"
    note_text: str = Field(..., min_length=1)
    recommendation: str | None = None
    finding_type: str | None = None


class CompleteMDReviewRequest(BaseModel):
    finding_classification: FindingClassification | None = None
    protocol_deviation_identified: bool = False
    exemplary_care_identified: bool = False
    education_recommended: bool = False
    protocol_revision_recommended: bool = False
    agency_leadership_flag: bool = False


class EscalateToMDRequest(BaseModel):
    escalation_reason: str = Field(..., min_length=1)
    medical_director_id: str
    review_type: MDReviewType = "qa_escalation"


# ---------------------------------------------------------------------------
# Protocol Document + Version
# ---------------------------------------------------------------------------


class ProtocolDocumentDTO(BaseModel):
    id: str
    tenant_id: str
    protocol_code: str
    protocol_name: str
    protocol_category: str
    current_version_id: str | None
    status: ProtocolStatus
    acknowledgment_required: bool
    created_at: datetime


class ProtocolVersionDTO(BaseModel):
    id: str
    tenant_id: str
    protocol_id: str
    version_number: str
    effective_date: datetime
    expiration_date: datetime | None
    status: ProtocolVersionStatus
    approved_at: datetime | None
    published_at: datetime | None
    created_at: datetime


class CreateProtocolRequest(BaseModel):
    protocol_code: str
    protocol_name: str
    protocol_category: str
    acknowledgment_required: bool = False
    linked_qa_trigger_keys: list[str] = Field(default_factory=list)


class CreateProtocolVersionRequest(BaseModel):
    version_number: str
    effective_date: datetime
    expiration_date: datetime | None = None
    content_text: str | None = None
    content_url: str | None = None
    scope_applicability: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Education Follow-Up
# ---------------------------------------------------------------------------


class EducationFollowUpDTO(BaseModel):
    id: str
    tenant_id: str
    provider_id: str
    assigned_by: str
    assigned_by_role: str
    education_type: EducationType
    education_title: str
    education_description: str | None
    education_resource_url: str | None
    due_date: datetime | None
    completed_at: datetime | None
    status: EducationStatus
    effectiveness_measured: bool
    qa_case_id: str | None
    created_at: datetime


class AssignEducationRequest(BaseModel):
    provider_id: str
    education_type: EducationType = "remedial"
    education_title: str = Field(..., min_length=1)
    education_description: str | None = None
    education_resource_url: str | None = None
    due_date: datetime | None = None
    qa_case_id: str | None = None
    medical_director_review_id: str | None = None
    qi_initiative_id: str | None = None


# ---------------------------------------------------------------------------
# Provider Feedback
# ---------------------------------------------------------------------------


class ProviderFeedbackDTO(BaseModel):
    id: str
    tenant_id: str
    provider_id: str
    sent_by: str
    sent_by_role: str
    feedback_type: FeedbackType
    subject: str
    message_text: str
    is_protected: bool
    acknowledged_at: datetime | None
    status: FeedbackStatus
    created_at: datetime


class SendFeedbackRequest(BaseModel):
    provider_id: str
    feedback_type: FeedbackType = "informational"
    subject: str = Field(..., min_length=1)
    message_text: str = Field(..., min_length=1)
    qa_case_id: str | None = None
    medical_director_review_id: str | None = None


# ---------------------------------------------------------------------------
# QI Initiative
# ---------------------------------------------------------------------------


class QIInitiativeDTO(BaseModel):
    id: str
    tenant_id: str
    initiative_title: str
    category: QICategory
    source_trend_description: str
    baseline_metric_value: float | None
    baseline_metric_label: str | None
    target_metric_value: float | None
    target_metric_label: str | None
    current_metric_value: float | None
    start_date: datetime
    target_completion_date: datetime | None
    owner_id: str
    status: QIInitiativeStatus
    outcome_summary: str | None
    accreditation_evidence_included: bool
    closed_at: datetime | None
    created_at: datetime


class CreateQIInitiativeRequest(BaseModel):
    initiative_title: str = Field(..., min_length=1)
    category: QICategory
    source_trend_description: str = Field(..., min_length=1)
    intervention_plan: str = Field(..., min_length=1)
    owner_id: str
    start_date: datetime | None = None
    baseline_metric_value: float | None = None
    baseline_metric_label: str | None = None
    target_metric_value: float | None = None
    target_metric_label: str | None = None
    target_completion_date: datetime | None = None
    stakeholder_ids: list[str] = Field(default_factory=list)


class AdvanceQIStatusRequest(BaseModel):
    new_status: QIInitiativeStatus
    notes: str | None = None
    outcome_summary: str | None = None
    current_metric_value: float | None = None


class RecordQIMetricRequest(BaseModel):
    metric_key: str
    metric_value: float
    metric_label: str
    measurement_period: str = Field(..., description="e.g. '2025-04' or '2025-Q1'")
    notes: str | None = None


# ---------------------------------------------------------------------------
# Quality Audit Event
# ---------------------------------------------------------------------------


class QualityAuditEventDTO(BaseModel):
    id: str
    tenant_id: str
    actor_id: str
    actor_role: str
    event_type: str
    reference_type: str
    reference_id: str
    source_chart_id: str | None
    event_metadata_json: dict
    occurred_at: datetime


# ---------------------------------------------------------------------------
# Dashboard DTOs
# ---------------------------------------------------------------------------


class QADashboardDTO(BaseModel):
    open_cases: int
    pending_reviews: int
    overdue_reviews: int
    high_priority_cases: int
    avg_qa_score: float
    trigger_breakdown: dict
    education_assignments_pending: int
    medical_director_escalations_pending: int
    status_breakdown: dict
    total_cases: int


class MDDashboardDTO(BaseModel):
    pending_reviews: int
    in_review: int
    completed_reviews: int
    protocol_deviations_identified: int
    standing_orders_requiring_attention: int
    status_breakdown: dict


class QIDashboardDTO(BaseModel):
    active_initiatives: int
    completed_initiatives: int
    identified_issues: int
    initiative_status_breakdown: dict
    education_completion_rate: float
    total_education_assigned: int
    total_education_completed: int


# ---------------------------------------------------------------------------
# Accreditation Evidence Package
# ---------------------------------------------------------------------------


class AccreditationEvidencePackageDTO(BaseModel):
    id: str
    tenant_id: str
    package_name: str
    accreditation_type: str
    period_start: datetime
    period_end: datetime
    status: str
    generated_by: str
    qa_evidence_json: dict
    qi_evidence_json: dict
    peer_review_summary_json: dict
    education_completion_json: dict
    protocol_compliance_json: dict
    compiled_at: datetime | None
    created_at: datetime


class GenerateAccreditationPackageRequest(BaseModel):
    package_name: str
    accreditation_type: str = "internal_audit"
    period_start: datetime
    period_end: datetime
