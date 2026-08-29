"""Fire domain contract schemas for cross-domain communication."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class FireIncidentCreatedEvent(BaseModel):
    """Published when a fire incident is created."""

    event_type: str = "fire.incident.created"

    incident_id: str
    tenant_id: str
    incident_number: str

    address: str
    incident_type: str

    created_at: datetime


class FireIncidentStatusUpdatedEvent(BaseModel):
    """Published when fire incident status changes."""

    event_type: str = "fire.incident.status_updated"

    incident_id: str
    tenant_id: str
    incident_number: str

    old_status: str
    new_status: str

    updated_at: datetime


class FireIncidentContract(BaseModel):
    """Read-only fire incident contract for cross-domain consumption."""

    id: str
    tenant_id: str

    incident_number: str
    address: str
    incident_type: str

    status: str
    created_at: datetime


class NerisReadinessContract(BaseModel):
    """NERIS export readiness status for a fire incident."""

    incident_id: str

    ready: bool

    missing_fields: list[str] = Field(default_factory=list)
    filled_fields: list[str] = Field(default_factory=list)

    total_required: int
    total_filled: int


class FireOperationalEventContract(BaseModel):
    """Canonical operational event for FireGraph timeline exchange."""

    id: str
    incident_id: str
    tenant_id: str
    event_type: str
    occurred_at: datetime
    actor_user_id: str | None = None
    unit_reference: str | None = None
    zone: str | None = None
    phase: str | None = None
    objective: str | None = None
    outcome: str | None = None
    source_kind: str
    evidence_bound: bool = False
    details: dict = Field(default_factory=dict)


class SceneStateSnapshotContract(BaseModel):
    """Canonical scene state snapshot for current or replayed fireground state."""

    id: str
    incident_id: str
    tenant_id: str
    operational_phase: str
    structure_state: str | None = None
    smoke_conditions: str | None = None
    fire_behavior: str | None = None
    hazard_summary: str | None = None
    exposure_involved: bool = False
    water_supply_state: str | None = None
    suppression_state: str | None = None
    search_state: str | None = None
    ventilation_state: str | None = None
    rescue_state: str | None = None
    control_state: str | None = None
    investigation_needed: bool = False
    data_source: str
    captured_at: datetime
    version: int


class InspectionCaseContract(BaseModel):
    """Canonical inspection and enforcement lifecycle root."""

    id: str
    tenant_id: str
    incident_id: str | None = None
    property_id: str | None = None
    inspection_type: str
    legal_authority: str | None = None
    trigger_reason: str
    assigned_inspector: str | None = None
    status: str
    due_at: datetime | None = None
    opened_at: datetime
    closed_at: datetime | None = None
    notice_reference: str | None = None
    export_state: str
    version: int


class InspectionFindingContract(BaseModel):
    """Canonical structured inspection finding."""

    id: str
    inspection_case_id: str
    tenant_id: str
    incident_id: str | None = None
    property_id: str | None = None
    code_family: str
    citation_reference: str
    severity: str
    condition_observed: str
    exact_location: str
    corrective_action: str
    due_at: datetime | None = None
    recurrence_flag: bool = False
    immediate_hazard: bool = False
    closure_state: str
    evidence_ids: list[str] = Field(default_factory=list)
    version: int


class ResourceExecutionContract(BaseModel):
    """Canonical resource, medication, and narcotic execution event."""

    id: str
    incident_id: str
    tenant_id: str
    patient_care_link_id: str | None = None
    actor_user_id: str | None = None
    witness_user_id: str | None = None
    category: str
    action: str
    item_reference: str
    quantity: Decimal | None = Field(default=None, ge=Decimal("0"))
    unit_of_measure: str | None = None
    narcotic_chain_id: str | None = None
    occurred_at: datetime
    source_kind: str
    details: dict = Field(default_factory=dict)


class FirePatientCareLinkContract(BaseModel):
    """Canonical Fire-to-Care linkage record."""

    id: str
    incident_id: str
    tenant_id: str
    patient_external_id: str
    epcr_encounter_id: str | None = None
    patient_location: str | None = None
    rescue_context: str | None = None
    injury_context: str | None = None
    disposition: str | None = None
    destination: str | None = None
    linked_at: datetime


class AfterburnReplayContract(BaseModel):
    """Canonical AFTERBURN replay artifact."""

    id: str
    incident_id: str
    tenant_id: str
    generated_by: str | None = None
    generated_at: datetime
    replay_summary: dict = Field(default_factory=dict)
    gap_analysis: list[str] = Field(default_factory=list)
    learning_points: list[str] = Field(default_factory=list)
