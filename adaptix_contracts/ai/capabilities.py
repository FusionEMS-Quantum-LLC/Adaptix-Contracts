"""AI capability contracts for Adaptix platform."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
# import uuid # REMOVED IN PYTHON 3.14


class AIProviderStatus(str, Enum):
    CONFIGURED = "configured"
    CREDENTIAL_GATED = "credential_gated"
    LIVE_VERIFIED = "live_verified"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


class AIRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AISourceField:
    """Represents a source field used in AI generation (no PHI in logs)."""

    field_name: str
    field_path: str
    redacted: bool = True
    included_in_prompt: bool = False


@dataclass
class AIRedactionPolicy:
    """Policy for redacting PHI/PII from AI inputs/outputs."""

    redact_phi: bool = True
    redact_pii: bool = True
    redact_prompts_from_logs: bool = True
    redact_completions_from_logs: bool = True
    allowed_log_fields: list[str] = field(
        default_factory=lambda: [
            "module",
            "capability_key",
            "model_provider",
            "model_name",
            "risk_level",
            "human_review_required",
            "confidence",
            "created_at",
        ]
    )

    def __post_init__(self):
        # Hard enforcement
        self.redact_phi = True
        self.redact_prompts_from_logs = True
        self.redact_completions_from_logs = True


@dataclass
class AICapabilityRegistryEntry:
    """Registry entry for an AI capability."""

    capability_key: str
    module: str
    description: str
    route: str
    input_schema: str
    output_schema: str
    risk_level: AIRiskLevel
    human_review_required: bool
    phi_in_input: bool
    phi_in_output: bool
    provider_required: str
    enabled: bool = True
    version: str = "1.0"


@dataclass
class AITextGenerationRequest:
    """Request for AI text generation."""

    tenant_id: str
    actor_id: str
    module: str
    capability_key: str
    source_record_id: str
    source_fields: list[AISourceField]
    prompt_policy_version: str
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    causation_id: str | None = None
    context_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AITextGenerationResponse:
    """Response from AI text generation."""

    tenant_id: str
    actor_id: str
    module: str
    capability_key: str
    source_record_id: str
    model_provider: str
    model_name: str
    input_redacted: bool
    output_redacted: bool
    human_review_required: bool
    confidence: float | None
    risk_level: AIRiskLevel
    created_at: datetime
    correlation_id: str
    audit_event_id: str
    # NOTE: generated_text is NOT logged - only returned to caller
    generated_text: str | None = None
    validation_passed: bool = False
    error: str | None = None
    # Hard rules - AI never signs or marks complete
    ai_signed: bool = False
    ai_marked_complete: bool = False

    def __post_init__(self):
        self.ai_signed = False
        self.ai_marked_complete = False


@dataclass
class AIReadinessAssessment:
    """AI-generated readiness assessment."""

    tenant_id: str
    actor_id: str
    module: str
    record_id: str
    assessment_type: str
    missing_fields: list[str]
    contradictions: list[str]
    warnings: list[str]
    readiness_score: float  # 0.0 - 1.0
    human_review_required: bool
    risk_level: AIRiskLevel
    created_at: datetime
    audit_event_id: str
    correlation_id: str


@dataclass
class AIDraftNarrative:
    """AI-drafted narrative (requires human review before use)."""

    tenant_id: str
    actor_id: str
    module: str
    record_id: str
    narrative_type: str
    draft_text: str  # NOT logged
    human_review_required: bool = True
    ai_signed: bool = False  # ALWAYS False - AI never signs
    ai_marked_complete: bool = False  # ALWAYS False
    ai_auto_locked: bool = False  # ALWAYS False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    audit_event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self):
        # Hard enforcement: AI never signs, marks complete, or auto-locks
        self.ai_signed = False
        self.ai_marked_complete = False
        self.ai_auto_locked = False


@dataclass
class AIHumanReviewRequirement:
    """Requirement for human review of AI output."""

    record_id: str
    module: str
    capability_key: str
    reason: str
    risk_level: AIRiskLevel
    required_reviewer_role: str
    deadline: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AIAuditRecord:
    """Audit record for AI operations (no PHI/prompts/completions)."""

    audit_event_id: str
    tenant_id: str
    actor_id: str
    module: str
    capability_key: str
    source_record_id: str
    prompt_policy_version: str
    model_provider: str
    model_name: str
    input_redacted: bool
    output_redacted: bool
    human_review_required: bool
    confidence: float | None
    risk_level: str
    created_at: datetime
    correlation_id: str
    causation_id: str | None = None
    # Explicitly excluded: prompt_text, completion_text, PHI, tokens, secrets
    error: str | None = None
    validation_passed: bool = False


@dataclass
class AIGeneratedTextMetadata:
    """Metadata about AI-generated text (no actual text content)."""

    generation_id: str
    module: str
    capability_key: str
    model_provider: str
    model_name: str
    risk_level: AIRiskLevel
    human_review_required: bool
    human_reviewed: bool = False
    human_reviewer_id: str | None = None
    human_reviewed_at: datetime | None = None
    accepted: bool | None = None
    edited: bool = False
    rejected: bool = False
    regenerated: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
