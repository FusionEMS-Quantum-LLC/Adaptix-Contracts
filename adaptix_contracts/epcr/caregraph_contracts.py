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
from typing import Optional
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
    description: Optional[str] = None
    evidence_strength: EvidenceStrengthDTO
    evidence_source_ids: Optional[list[str]] = None
    snomed_code: Optional[str] = None
    snomed_display: Optional[str] = None
    icd10_code: Optional[str] = None
    icd10_display: Optional[str] = None
    rxnorm_code: Optional[str] = None
    nemsis_element: Optional[str] = None
    nemsis_value: Optional[str] = None
    clinical_payload: Optional[dict] = None
    provider_id: str
    provider_role: Optional[str] = None
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
    weight: Optional[float] = None
    metadata: Optional[dict] = None
    provider_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OPQRSTSymptomDTO(BaseModel):
    """OPQRST symptom DTO — structured, not plain text."""

    id: str
    chart_id: str
    tenant_id: str
    caregraph_node_id: Optional[str] = None
    symptom_category: str
    symptom_label: str
    onset_description: Optional[str] = None
    onset_time: Optional[datetime] = None
    onset_sudden: Optional[bool] = None
    provocation_factors: Optional[list[str]] = None
    palliation_factors: Optional[list[str]] = None
    quality_descriptors: Optional[list[str]] = None
    radiation_present: Optional[bool] = None
    radiation_locations: Optional[list[str]] = None
    region_primary: Optional[str] = None
    severity_scale: Optional[int] = Field(default=None, ge=0, le=10)
    time_duration_minutes: Optional[int] = None
    time_progression: Optional[str] = None
    associated_symptoms: Optional[list[str]] = None
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
    intervention_trigger_id: Optional[str] = None
    reassessed_at: datetime
    provider_id: str

    model_config = ConfigDict(from_attributes=True)
