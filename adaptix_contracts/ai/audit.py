"""AI audit policy contracts for Adaptix platform."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import uuid


class AIAuditEventType(str, Enum):
    GENERATION_REQUESTED = "ai.generation.requested"
    GENERATION_COMPLETED = "ai.generation.completed"
    GENERATION_FAILED = "ai.generation.failed"
    HUMAN_REVIEW_REQUIRED = "ai.human_review.required"
    HUMAN_REVIEW_COMPLETED = "ai.human_review.completed"
    HUMAN_REVIEW_REJECTED = "ai.human_review.rejected"
    SMART_TEXT_GENERATED = "ai.smart_text.generated"
    SMART_TEXT_ACCEPTED = "ai.smart_text.accepted"
    SMART_TEXT_EDITED = "ai.smart_text.edited"
    SMART_TEXT_REJECTED = "ai.smart_text.rejected"
    SMART_TEXT_REGENERATED = "ai.smart_text.regenerated"
    PROVIDER_HEALTH_CHECK = "ai.provider.health_check"
    CAPABILITY_INVOKED = "ai.capability.invoked"
    CAPABILITY_DISABLED = "ai.capability.disabled"


@dataclass
class AIAuditPolicy:
    """Policy governing AI audit behavior."""

    # PHI rules - ALWAYS False
    log_phi: bool = False
    log_prompts: bool = False
    log_completions: bool = False
    log_secrets: bool = False
    log_tokens: bool = False
    log_credentials: bool = False

    # What IS logged
    log_module: bool = True
    log_capability_key: bool = True
    log_model_provider: bool = True
    log_model_name: bool = True
    log_risk_level: bool = True
    log_human_review_required: bool = True
    log_confidence: bool = True
    log_error: bool = True
    log_correlation_id: bool = True
    log_causation_id: bool = True

    # Hard rules - ALWAYS False
    ai_can_sign_forms: bool = False
    ai_can_mark_complete: bool = False
    ai_can_auto_lock_charts: bool = False
    ai_can_bypass_provider_requirements: bool = False
    ai_can_override_clinical_review: bool = False
    ai_can_override_legal_review: bool = False
    ai_can_submit_claims_silently: bool = False
    ai_can_dispatch_resources: bool = False
    ai_can_invent_facts: bool = False
    ai_can_invent_signatures: bool = False
    ai_can_invent_medications: bool = False
    ai_can_invent_interventions: bool = False

    def __post_init__(self):
        # Enforce all hard rules
        self.log_phi = False
        self.log_prompts = False
        self.log_completions = False
        self.log_secrets = False
        self.log_tokens = False
        self.log_credentials = False
        self.ai_can_sign_forms = False
        self.ai_can_mark_complete = False
        self.ai_can_auto_lock_charts = False
        self.ai_can_bypass_provider_requirements = False
        self.ai_can_override_clinical_review = False
        self.ai_can_override_legal_review = False
        self.ai_can_submit_claims_silently = False
        self.ai_can_dispatch_resources = False
        self.ai_can_invent_facts = False
        self.ai_can_invent_signatures = False
        self.ai_can_invent_medications = False
        self.ai_can_invent_interventions = False


@dataclass
class AIAuditEvent:
    """An AI audit event (safe for logging - no PHI/prompts/completions)."""

    audit_event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: AIAuditEventType = AIAuditEventType.GENERATION_REQUESTED
    tenant_id: str = ""
    actor_id: str = ""
    module: str = ""
    capability_key: str = ""
    source_record_id: str = ""
    model_provider: str = ""
    model_name: str = ""
    risk_level: str = "unknown"
    human_review_required: bool = False
    confidence: Optional[float] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    causation_id: Optional[str] = None
    error: Optional[str] = None
    # Explicitly NOT included: prompt_text, completion_text, phi_data, tokens, secrets
