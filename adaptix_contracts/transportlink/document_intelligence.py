"""TransportLink AI document intelligence contracts for Adaptix platform.

AI may determine missing data, draft PCS support text, explain ABN risk.
AI may NOT sign, mark complete, override provider status, or submit to CAD.
All AI output requires human review for PCS/ABN decisions.
No PHI, prompts, completions, tokens, or secrets are logged.
"""

from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel


class DocumentRequirementContract(BaseModel):
    required: bool
    reason: str
    missing_fields: list[str] = []
    contradictions: list[str] = []
    requires_human_review: bool = True


class MedicalNecessitySupportContract(BaseModel):
    draft_pcs_narrative: str | None = None
    confidence: float | None = None
    human_review_required: bool = True
    no_invented_facts: bool = True


class DocumentReadinessContract(BaseModel):
    ready_for_signature_packet: bool
    ready_for_cad: bool
    blocking_reasons: list[str] = []


class DocumentIntelligenceAuditContract(BaseModel):
    model_provider: str
    model_name: str
    policy_version: str
    created_at: datetime
    phi_logged: bool = False
    prompt_logged: bool = False
    completion_logged: bool = False


class DocumentIntelligenceAssessmentContract(BaseModel):
    """
    Full AI document intelligence assessment for a TransportLink request.

    Required output schema per directive:
    - request_id
    - required_documents.pcs.required / reason / missing_fields / contradictions
    - required_documents.aob.required / reason / missing_fields
    - required_documents.abn.required / reason / requires_human_review
    - medical_necessity_support.draft_pcs_narrative / confidence
    - readiness.ready_for_signature_packet / ready_for_cad / blocking_reasons
    - audit.model_provider / model_name / policy_version / created_at
    """

    assessment_id: str
    request_id: str
    tenant_id: str
    actor_id: str
    pcs: DocumentRequirementContract
    aob: DocumentRequirementContract
    abn: DocumentRequirementContract
    medical_necessity_support: MedicalNecessitySupportContract
    readiness: DocumentReadinessContract
    audit: DocumentIntelligenceAuditContract
    human_review_required: bool = True
    ai_may_not_sign: bool = True
    ai_may_not_mark_complete: bool = True
    ai_may_not_override_provider: bool = True
    ai_may_not_submit_to_cad: bool = True


class DocumentIntelligenceAssessRequest(BaseModel):
    request_id: str
    tenant_id: str
    actor_id: str
    request_data: dict[str, Any] = {}
    idempotency_key: str | None = None


class DocumentIntelligenceLatestResponse(BaseModel):
    assessment: DocumentIntelligenceAssessmentContract | None = None
    has_assessment: bool = False
    credential_gated: bool = False
    credential_gated_reason: str | None = None
