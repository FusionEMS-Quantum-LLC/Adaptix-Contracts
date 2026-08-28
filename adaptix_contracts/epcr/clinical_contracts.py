"""EPCR clinical system contracts — CPAE, VAS, Vision, CriticalCare, Terminology, SmartText, Sync, Dashboard, Validation, Desktop.

These contracts define typed DTOs for all EPCR clinical systems.
Frontend and Android must consume these typed contracts — never untyped JSON.

Architecture rules enforced by these contracts:
- Vision proposals are always pending_review — never auto-accepted
- Smart Text proposals preserve raw_text — never silently mutate
- AI impressions require review before acceptance
- Interventions require response documentation or explicit unavailability
- VAS overlays require physical_finding_id (CPAE linkage)
- Narrative is derived output — never authoritative truth
- Sync events have idempotency_key — safe for retry
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


# ===========================================================================
# CPAE Contracts
# ===========================================================================


class PhysicalFindingDTO(BaseModel):
    """CPAE physical finding DTO — requires anatomy and physiologic_system."""

    id: str
    chart_id: str
    tenant_id: str
    caregraph_node_id: Optional[str] = None
    anatomy: str  # REQUIRED — no orphan findings
    physiologic_system: str  # REQUIRED — no orphan findings
    finding_class: str
    severity: str
    finding_label: str
    finding_description: Optional[str] = None
    laterality: Optional[str] = None
    detection_method: str
    review_state: str  # direct_confirmed, vision_proposed, smart_text_proposed, accepted, rejected
    snomed_code: Optional[str] = None
    snomed_display: Optional[str] = None
    nemsis_exam_element: Optional[str] = None
    nemsis_exam_value: Optional[str] = None
    has_contradiction: bool
    contradiction_detail: Optional[str] = None
    provider_id: str
    observed_at: datetime
    version: int

    model_config = ConfigDict(from_attributes=True)


class FindingReassessmentDTO(BaseModel):
    """CPAE finding reassessment DTO."""

    id: str
    finding_id: str
    chart_id: str
    tenant_id: str
    evolution: str  # improving, worsening, unchanged, resolved
    severity_at_reassessment: Optional[str] = None
    description: Optional[str] = None
    intervention_trigger_id: Optional[str] = None
    provider_id: str
    reassessed_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ===========================================================================
# VAS Contracts
# ===========================================================================


class VASOverlayDTO(BaseModel):
    """VAS overlay DTO — requires physical_finding_id (CPAE linkage)."""

    id: str
    chart_id: str
    physical_finding_id: str  # REQUIRED — no free-floating overlays
    caregraph_node_id: Optional[str] = None
    tenant_id: str
    patient_model: str  # adult, pediatric, neonatal
    anatomical_view: str  # front, posterior, left_lateral, right_lateral, regional_zoom
    overlay_type: str
    anchor_region: str
    geometry: dict  # structured geometry — not free-form SVG
    severity: str
    evolution: str
    review_state: str  # direct_confirmed, vision_proposed, accepted, rejected
    provider_id: str
    rendered_at: datetime
    version: int

    model_config = ConfigDict(from_attributes=True)


class VASProjectionReviewDTO(BaseModel):
    """VAS projection review DTO — Vision proposals require review."""

    id: str
    chart_id: str
    tenant_id: str
    vision_artifact_id: str
    proposed_overlay: dict
    confidence: float
    model_version: Optional[str] = None
    review_state: (
        str  # pending, accepted, rejected, edited_accepted — NEVER auto-accepted
    )
    reviewer_id: Optional[str] = None  # None until reviewed
    reviewed_at: Optional[datetime] = None  # None until reviewed
    proposed_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ===========================================================================
# Vision Contracts
# ===========================================================================


class VisionArtifactDTO(BaseModel):
    """Vision artifact DTO — internal storage path only, never public URL."""

    id: str
    chart_id: str
    tenant_id: str
    ingestion_source: str
    content_type: str
    # storage_path is intentionally omitted from DTO — internal only
    processing_status: str
    uploaded_by_user_id: str
    uploaded_at: datetime
    version: int

    model_config = ConfigDict(from_attributes=True)


class VisionExtractionDTO(BaseModel):
    """Vision extraction DTO — always pending_review at creation."""

    id: str
    artifact_id: str
    tenant_id: str
    proposal_target: str
    extracted_value: dict
    raw_text: Optional[str] = None
    confidence: float
    model_version: Optional[str] = None
    review_state: str  # pending_review, accepted, rejected, edited_and_accepted — NEVER auto-accepted
    reviewer_id: Optional[str] = None  # None until reviewed
    reviewed_at: Optional[datetime] = None  # None until reviewed
    accepted_chart_field: Optional[str] = None
    extracted_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VisionReviewQueueDTO(BaseModel):
    """Vision review queue DTO."""

    id: str
    extraction_id: str
    chart_id: str
    tenant_id: str
    priority: int
    queue_state: str  # pending, in_review, completed, escalated
    assigned_to_user_id: Optional[str] = None
    queued_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VisionProvenanceDTO(BaseModel):
    """Vision provenance DTO — provenance is never destroyed."""

    id: str
    extraction_id: str
    tenant_id: str
    provenance_type: str  # source, model, review, acceptance
    provenance_detail: dict
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ===========================================================================
# Critical Care Contracts
# ===========================================================================


class InfusionRunDTO(BaseModel):
    """Infusion run DTO — requires indication."""

    id: str
    chart_id: str
    tenant_id: str
    medication_name: str
    rxnorm_code: Optional[str] = None
    concentration: Optional[str] = None
    initial_rate_value: float
    initial_rate_unit: str
    indication: str  # REQUIRED — no interventions without indication
    protocol_family: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    provider_id: str

    model_config = ConfigDict(from_attributes=True)


class VentilatorSessionDTO(BaseModel):
    """Ventilator session DTO."""

    id: str
    chart_id: str
    tenant_id: str
    mode: str
    tidal_volume_ml: Optional[int] = None
    respiratory_rate: Optional[int] = None
    fio2_percent: Optional[int] = None
    peep_cmh2o: Optional[float] = None
    airway_type: Optional[str] = None
    indication: str  # REQUIRED
    started_at: datetime
    provider_id: str

    model_config = ConfigDict(from_attributes=True)


class ResponseWindowDTO(BaseModel):
    """Response window DTO — intervention completeness rule enforced."""

    id: str
    chart_id: str
    intervention_id: str
    tenant_id: str
    expected_response: str
    expected_response_window_minutes: Optional[int] = None
    actual_response: Optional[str] = None
    response_availability: str  # documented, unavailable_transport_time, unavailable_patient_condition, pending
    unavailability_reason: Optional[str] = None  # REQUIRED if unavailable
    response_adequate: Optional[bool] = None
    escalation_triggered: bool
    provider_id: str

    model_config = ConfigDict(from_attributes=True)


# ===========================================================================
# Terminology Contracts
# ===========================================================================


class ImpressionBindingDTO(BaseModel):
    """Impression binding DTO — multi-layer terminology, AI requires review."""

    id: str
    chart_id: str
    tenant_id: str
    caregraph_node_id: Optional[str] = None
    impression_class: str  # primary, secondary, differential, ruled_out, billing
    adaptix_label: str
    snomed_code: Optional[str] = None
    snomed_display: Optional[str] = None
    icd10_code: Optional[str] = None
    icd10_display: Optional[str] = None
    nemsis_element: Optional[str] = None
    nemsis_value: Optional[str] = None
    nemsis_export_valid: Optional[bool] = None
    is_ai_suggested: bool  # if True, review_state must be pending_review until reviewed
    review_state: str  # direct_confirmed, pending_review, accepted, rejected
    reviewer_id: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    provider_id: str
    documented_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ===========================================================================
# Smart Text Contracts
# ===========================================================================


class SmartTextProposalDTO(BaseModel):
    """Smart text proposal DTO — raw text preserved, requires review."""

    id: str
    session_id: str
    chart_id: str
    tenant_id: str
    raw_source_text: str  # ALWAYS preserved
    entity_type: str
    entity_label: str
    entity_payload: dict
    target_chart_field: Optional[str] = None
    confidence: float
    proposal_state: str  # pending_review, accepted, rejected, edited_and_accepted, ignored — NEVER auto-accepted
    reviewer_id: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    is_contradiction: bool
    contradiction_detail: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ===========================================================================
# Sync Contracts
# ===========================================================================


class SyncEventDTO(BaseModel):
    """Sync event DTO — append-only, idempotent."""

    id: str
    tenant_id: str
    chart_id: Optional[str] = None
    device_id: str
    user_id: str
    event_type: str
    entity_type: str
    entity_id: str
    local_sequence_number: int
    device_timestamp: datetime
    status: str  # pending, uploading, uploaded, failed, conflict_detected
    idempotency_key: str  # REQUIRED — safe for retry
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SyncHealthDTO(BaseModel):
    """Sync health DTO — always visible, never hidden."""

    device_id: str
    health_state: str  # healthy, degraded, offline, sync_failed, partial
    pending_events_count: int
    failed_events_count: int
    pending_uploads_count: int
    failed_uploads_count: int
    unresolved_conflicts_count: int
    is_degraded: bool
    degraded_reason: Optional[str] = None
    last_successful_sync_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UploadQueueItemDTO(BaseModel):
    """Upload queue item DTO — resumable upload support."""

    id: str
    tenant_id: str
    chart_id: Optional[str] = None
    upload_type: str  # vision_artifact, signature, attachment
    content_type: str
    file_size_bytes: Optional[int] = None
    upload_status: str  # pending, uploading, completed, failed
    bytes_uploaded: int
    idempotency_key: str
    queued_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ===========================================================================
# Dashboard Contracts
# ===========================================================================


class DashboardProfileDTO(BaseModel):
    """Dashboard profile DTO — customization never affects clinical truth."""

    id: str
    user_id: str
    tenant_id: str
    profile_name: str
    density: str  # compact, normal, expanded
    theme_mode: str  # light, dark, field, high_contrast, system
    accent_color: Optional[str] = None
    card_order: Optional[list[str]] = None
    hidden_cards: Optional[list[str]] = None
    # No clinical fields — dashboard cannot affect clinical truth

    model_config = ConfigDict(from_attributes=True)


class WorkspaceProfileDTO(BaseModel):
    """Workspace profile DTO — cannot hide mandatory blockers."""

    id: str
    user_id: str
    tenant_id: str
    profile_type: str
    profile_name: str
    is_default: bool
    critical_care_mode: bool
    show_ventilator_panel: bool
    show_infusion_panel: bool
    # hide_mandatory_blockers is intentionally absent — cannot be hidden

    model_config = ConfigDict(from_attributes=True)


# ===========================================================================
# Validation Contracts
# ===========================================================================


class ValidationIssueDTO(BaseModel):
    """Validation issue DTO — explicit, never hidden."""

    layer: int  # 1-5
    severity: str  # error, warning, info
    code: str
    message: str
    field: Optional[str] = None
    entity_id: Optional[str] = None
    entity_type: Optional[str] = None
    nemsis_element: Optional[str] = None
    remediation: Optional[str] = None


class ValidationResultDTO(BaseModel):
    """5-layer validation result DTO — export blockers never hidden."""

    chart_id: str
    tenant_id: str
    validated_at: datetime
    all_layers_passed: bool
    layer_1_clinical: bool
    layer_2_nemsis_structural: bool
    layer_3_xsd: bool
    layer_4_export: bool
    layer_5_custom_audit: bool
    export_blocked: bool  # NEVER hidden
    export_blockers: list[str]  # NEVER hidden
    error_count: int
    warning_count: int
    issues: list[ValidationIssueDTO]


# ===========================================================================
# Desktop QA Contracts
# ===========================================================================


class NEMSISReadinessDashboardDTO(BaseModel):
    """NEMSIS readiness dashboard DTO — false readiness never presented."""

    tenant_id: str
    total_charts_with_compliance: int
    fully_compliant: int
    partially_compliant: int
    non_compliant: int
    not_started: int
    in_progress: int
    compliance_rate_pct: float
    export_blocked_count: int  # NEVER hidden


class MappingTraceDTO(BaseModel):
    """NEMSIS mapping trace DTO — full provenance."""

    id: str
    chart_id: str
    nemsis_field: str
    nemsis_value: Optional[str] = None
    source: str  # manual, ocr, device, system
    created_at: datetime
    version: int

    model_config = ConfigDict(from_attributes=True)


class AuditEventDTO(BaseModel):
    """Audit event DTO — immutable, never modified."""

    id: str
    chart_id: str
    tenant_id: str
    user_id: str
    action: str
    detail: Optional[dict] = None
    performed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DerivedOutputDTO(BaseModel):
    """Derived output DTO — NEVER authoritative truth."""

    id: str
    chart_id: str
    output_type: str  # narrative, handoff, clinical_summary, billing_justification
    content_text: str
    source_revision: str
    generated_at: datetime
    generated_by_user_id: str
    is_authoritative_truth: bool = False  # ALWAYS False

    model_config = ConfigDict(from_attributes=True)


class ChartReviewDTO(BaseModel):
    """Desktop chart review DTO — export blockers never hidden."""

    chart_id: str
    call_number: str
    incident_type: str
    status: str
    version: int
    nemsis_compliance_status: str
    mandatory_fields_filled: int
    mandatory_fields_required: int
    missing_mandatory_fields: list[str]
    physical_findings_count: int
    impressions_count: int
    unreviewed_vision_proposals: int
    unresolved_sync_conflicts: int
    export_blockers: list[str]  # NEVER hidden
    export_blocked: bool  # NEVER hidden
    audit_event_count: int
