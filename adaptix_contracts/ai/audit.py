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


# ---------------------------------------------------------------------------
# AI model flight recorder (shared platform primitive H)
# ---------------------------------------------------------------------------
#
# AIAuditEvent above records that a generation happened. The flight recorder
# records what it was actually made from and what happened next — the difference
# between "the model ran" and "we can investigate, regression-test, compare
# model versions, and analyse overrides months later".
#
# The prohibition in AIAuditPolicy still holds and is enforced structurally
# here: there is no field for prompt text, completion text, or hidden
# chain-of-thought, and adding one would be a defect. What is recorded instead
# is hashes, ids, structured reason codes, and the human's disposition.


class AIExecutionFailureClass(str, Enum):
    """Why an execution did not produce a usable result.

    ``INVALID_STRUCTURED_OUTPUT`` and ``LOW_CONFIDENCE`` are separated from
    ``PROVIDER_ERROR`` on purpose: the first two are model-quality signals worth
    tracking per prompt version, the third is an availability problem.
    """

    NONE = "none"
    PROVIDER_ERROR = "provider_error"
    PROVIDER_TIMEOUT = "provider_timeout"
    INVALID_STRUCTURED_OUTPUT = "invalid_structured_output"
    LOW_CONFIDENCE = "low_confidence"
    TOOL_DENIED = "tool_denied"
    EVIDENCE_MISSING = "evidence_missing"
    GUARDRAIL_BLOCKED = "guardrail_blocked"
    INTERNAL_ERROR = "internal_error"


@dataclass
class AIModelExecutionRecord:
    """One replayable record of one model execution.

    Deliberately *not* a copy of the conversation. ``input_hash`` and
    ``output_hash`` pin exactly what went in and came out so a later
    investigation can prove two runs were the same, without the platform storing
    prompts or completions that routinely carry PHI.

    ``downstream_action`` names what the platform did as a result — the field
    that turns an audit log into an answer to "did this model change anything?".
    Left empty when nothing acted on the output.

    ``human_confirmation_receipt_id`` points at a ``HumanConfirmationReceipt``
    (``adaptix_contracts.schemas.human_confirmation_contracts``). ``None`` means
    no person has dispositioned this execution, which for anything beyond an
    advisory result is itself the finding.
    """

    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    model_provider: str = ""
    model_id: str = ""
    model_version: str = ""
    prompt_template_id: str = ""
    prompt_template_version: str = ""
    tool_contract_versions: list[str] = field(default_factory=list)
    input_evidence_ids: list[str] = field(default_factory=list)
    input_hash: str = ""
    output_hash: str = ""
    structured_output_schema: str = ""
    confidence: Optional[float] = None
    regulatory_mode: str = ""
    human_confirmation_receipt_id: Optional[str] = None
    latency_ms: Optional[int] = None
    input_token_count: Optional[int] = None
    output_token_count: Optional[int] = None
    estimated_cost_usd: Optional[str] = None
    failure_class: AIExecutionFailureClass = AIExecutionFailureClass.NONE
    downstream_action: str = ""
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # Explicitly NOT included, and must never be added: prompt_text,
    # completion_text, reasoning_trace, chain_of_thought, phi_data, secrets.

    def succeeded(self) -> bool:
        """Return ``True`` when the execution produced a usable result."""

        return self.failure_class is AIExecutionFailureClass.NONE

    def acted_on_anything(self) -> bool:
        """Return ``True`` when the platform changed state because of this run."""

        return bool(self.downstream_action)


#: Field names that must never appear on an AI audit or flight-recorder record.
#: Asserted by the contract tests so a future edit cannot quietly add one.
FORBIDDEN_AI_RECORD_FIELDS: frozenset[str] = frozenset(
    {
        "prompt_text",
        "prompt",
        "completion_text",
        "completion",
        "reasoning_trace",
        "chain_of_thought",
        "thinking",
        "phi_data",
        "patient_name",
        "secrets",
        "credentials",
        "api_key",
    }
)
