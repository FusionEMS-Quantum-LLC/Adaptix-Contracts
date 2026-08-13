"""Smart text contracts for Adaptix platform."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid

from .capabilities import AIRiskLevel, AISourceField


class SmartTextModule(str, Enum):
    CAD = "cad"
    EPCR = "epcr"
    BILLING = "billing"
    TRANSPORTLINK = "transportlink"
    FIRE = "fire"
    HEMS = "hems"
    INVENTORY = "inventory"
    NARCOTICS = "narcotics"
    MEDICATIONS = "medications"
    WORKFORCE = "workforce"
    COMMUNICATIONS = "communications"
    DOCUMENTS = "documents"
    FOUNDER = "founder"


class SmartTextCapability(str, Enum):
    # CAD
    CAD_INTAKE_SUMMARY = "cad.intake_summary"
    CAD_DISPATCH_RATIONALE = "cad.dispatch_rationale"
    CAD_CREW_BRIEFING = "cad.crew_briefing"
    CAD_MEDICAL_NECESSITY_SUPPORT = "cad.medical_necessity_support"
    # ePCR - uses Adaptix ePCR narrative intelligence (not external naming)
    EPCR_ADAPTIX_NARRATIVE_INTELLIGENCE = "epcr.adaptix_narrative_intelligence"
    EPCR_NEMSIS_VALIDATION_EXPLANATION = "epcr.nemsis_validation_explanation"
    EPCR_CLINICAL_CONTRADICTION_DETECTION = "epcr.clinical_contradiction_detection"
    EPCR_BILLING_READINESS_SUMMARY = "epcr.billing_readiness_summary"
    # Billing
    BILLING_CLAIM_READINESS = "billing.claim_readiness_explanation"
    BILLING_DENIAL_APPEAL = "billing.denial_appeal_draft"
    BILLING_PATIENT_STATEMENT = "billing.patient_statement_plain_language"
    BILLING_PAYMENT_REMINDER = "billing.payment_reminder_text"
    # TransportLink
    TRANSPORTLINK_DOCUMENT_INTELLIGENCE = "transportlink.document_intelligence"
    TRANSPORTLINK_PCS_SUPPORT = "transportlink.pcs_support_text"
    TRANSPORTLINK_ABN_RISK = "transportlink.abn_risk_explanation"
    # Fire
    FIRE_INCIDENT_SUMMARY = "fire.incident_summary"
    FIRE_NERIS_VALIDATION = "fire.neris_validation_explanation"
    FIRE_PREPLAN_SUMMARY = "fire.preplan_summary"
    # HEMS
    HEMS_GO_NO_GO = "hems.go_no_go_support"
    HEMS_WEATHER_RISK = "hems.weather_risk_summary"
    # Inventory
    INVENTORY_READINESS = "inventory.readiness_summary"
    # Narcotics
    NARCOTICS_DISCREPANCY = "narcotics.discrepancy_narrative"
    # Medications
    MEDICATIONS_SAFETY_WARNING = "medications.safety_warning"
    # Workforce
    WORKFORCE_FATIGUE_RISK = "workforce.fatigue_risk_summary"
    # Communications
    COMMUNICATIONS_CALL_SUMMARY = "communications.call_summary"
    # Documents
    DOCUMENTS_CLASSIFICATION = "documents.classification_summary"
    # Founder
    FOUNDER_PLATFORM_READINESS = "founder.platform_readiness_summary"


@dataclass
class SmartTextRequest:
    """Request for smart text generation."""

    tenant_id: str
    actor_id: str
    module: SmartTextModule
    capability: SmartTextCapability
    source_record_id: str
    source_fields: list[AISourceField]
    prompt_policy_version: str = "1.0"
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    causation_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class SmartTextResponse:
    """Response from smart text generation."""

    tenant_id: str
    actor_id: str
    module: SmartTextModule
    capability: SmartTextCapability
    source_record_id: str
    # draft_text is returned to caller but NEVER logged
    draft_text: str | None
    human_review_required: bool
    risk_level: AIRiskLevel
    missing_fields: list[str]
    warnings: list[str]
    audit_event_id: str
    correlation_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: str | None = None
    provider_status: str = "unknown"
    # Hard rules
    ai_signed: bool = False
    ai_marked_complete: bool = False

    def __post_init__(self):
        self.ai_signed = False
        self.ai_marked_complete = False


@dataclass
class SmartTextAuditEntry:
    """Audit entry for smart text (no PHI/prompts/completions)."""

    audit_event_id: str
    tenant_id: str
    actor_id: str
    module: str
    capability: str
    source_record_id: str
    model_provider: str
    model_name: str
    risk_level: str
    human_review_required: bool
    created_at: datetime
    correlation_id: str
    causation_id: str | None = None
    error: str | None = None
    # Lifecycle tracking
    accepted: bool | None = None
    edited: bool = False
    rejected: bool = False
    regenerated: bool = False
    human_reviewer_id: str | None = None
    human_reviewed_at: datetime | None = None
