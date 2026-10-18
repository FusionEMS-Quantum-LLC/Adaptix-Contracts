"""CareGraph clinical truth contracts.

These contracts define the typed DTOs for CareGraph nodes, edges,
OPQRST symptoms, and reassessment deltas.

Rules:
- CareGraph is the sole source of clinical truth
- Narrative is NEVER a CareGraph field
- Every node is evidence-backed, timestamped, provider-attributed, tenant-scoped
- Vision proposals require review before becoming CareGraph nodes
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field


class CareGraphNodeTypeDTO(str, Enum):
    PATIENT_STATE = "patient_state"
    SYMPTOM = "symptom"
    PHYSICAL_FINDING = "physical_finding"
    VITAL = "vital"
    IMPRESSION = "impression"
    INTERVENTION = "intervention"
    MEDICATION = "medication"
    DEVICE_STATE = "device_state"
    PROTOCOL_STATE = "protocol_state"
    TRANSPORT_STATE = "transport_state"
    DISPOSITION = "disposition"
    RESPONSE = "response"
    REASSESSMENT = "reassessment"
    OUTCOME = "outcome"


class CareGraphEdgeTypeDTO(str, Enum):
    CAUSALITY = "causality"
    TIMING = "timing"
    INTENT = "intent"
    EVIDENCE_SUPPORT = "evidence_support"
    CLINICAL_RESPONSE = "clinical_response"
    ESCALATION = "escalation"
    DOWNGRADE = "downgrade"
    PROTOCOL_LINKAGE = "protocol_linkage"
    TERMINOLOGY_BINDING = "terminology_binding"
    EXPORT_MAPPING = "export_mapping"
    REASSESSMENT_DELTA = "reassessment_delta"
    INTERVENTION_RESPONSE = "intervention_response"


class EvidenceStrengthDTO(str, Enum):
    CONFIRMED = "confirmed"
    PROBABLE = "probable"
    POSSIBLE = "possible"
    RULED_OUT = "ruled_out"


class CareGraphNodeDTO(BaseModel):
    """CareGraph node DTO — single clinical statement."""

    id: str
    chart_id: str
    tenant_id: str
    node_type: CareGraphNodeTypeDTO
    label: str
    description: str | None = None
    evidence_strength: EvidenceStrengthDTO
    evidence_source_ids: list[str] | None = None
    snomed_code: str | None = None
    snomed_display: str | None = None
    icd10_code: str | None = None
    icd10_display: str | None = None
    rxnorm_code: str | None = None
    nemsis_element: str | None = None
    nemsis_value: str | None = None
    clinical_payload: dict | None = None
    provider_id: str
    provider_role: str | None = None
    sync_state: str
    occurred_at: datetime
    created_at: datetime
    version: int

    model_config = ConfigDict(from_attributes=True)


class CareGraphEdgeDTO(BaseModel):
    """CareGraph edge DTO — relationship between clinical statements."""

    id: str
    chart_id: str
    tenant_id: str
    source_node_id: str
    target_node_id: str
    edge_type: CareGraphEdgeTypeDTO
    weight: float | None = None
    metadata: dict | None = None
    provider_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OPQRSTSymptomDTO(BaseModel):
    """OPQRST symptom DTO — structured, not plain text."""

    id: str
    chart_id: str
    tenant_id: str
    caregraph_node_id: str | None = None
    symptom_category: str
    symptom_label: str
    onset_description: str | None = None
    onset_time: datetime | None = None
    onset_sudden: bool | None = None
    provocation_factors: list[str] | None = None
    palliation_factors: list[str] | None = None
    quality_descriptors: list[str] | None = None
    radiation_present: bool | None = None
    radiation_locations: list[str] | None = None
    region_primary: str | None = None
    severity_scale: int | None = Field(default=None, ge=0, le=10)
    time_duration_minutes: int | None = None
    time_progression: str | None = None
    associated_symptoms: list[str] | None = None
    provider_id: str
    documented_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReassessmentDeltaDTO(BaseModel):
    """Reassessment delta DTO."""

    id: str
    chart_id: str
    tenant_id: str
    prior_node_id: str
    reassessment_node_id: str
    delta_type: str
    delta_description: str
    intervention_trigger_id: str | None = None
    reassessed_at: datetime
    provider_id: str

    model_config = ConfigDict(from_attributes=True)
