"""ePCR domain contract schemas for cross-domain communication."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EpcrChartCreatedEvent(BaseModel):
    """Published when an ePCR chart is created."""

    event_type: str = "epcr.chart.created"

    chart_id: str
    tenant_id: str
    call_number: str
    incident_type: str

    created_at: datetime


class EpcrChartFinalizedEvent(BaseModel):
    """Published when an ePCR chart is finalized."""

    event_type: str = "epcr.chart.finalized"

    chart_id: str
    tenant_id: str
    call_number: str

    finalized_at: datetime
    is_nemsis_compliant: bool

    missing_fields: list[str] = Field(default_factory=list)

    # Test-record isolation. True for a non-production ePCR (e.g. a Founder
    # WARDS Lab record), which must never enter billing, patient-identity
    # matching, production NEMSIS/WARDS submission, notifications, or
    # analytics. EPCR is the authoritative chokepoint and does not emit this
    # event for test charts at all; the flag exists so every consumer can
    # additionally defend itself instead of trusting upstream filtering.
    #
    # Defaults to False so existing producers and persisted events remain
    # valid, and so an omitted value fails CLOSED toward production semantics
    # (a real encounter is never silently dropped from billing).
    is_test: bool = False


class EpcrChartContract(BaseModel):
    """Read-only ePCR chart contract for cross-domain consumption."""

    id: str
    tenant_id: str

    call_number: str
    status: str
    incident_type: str

    created_at: datetime
    updated_at: Optional[datetime] = None
    finalized_at: Optional[datetime] = None


class EpcrPatientProfileContract(BaseModel):
    """Chart-scoped patient demographics owned by the ePCR domain."""

    chart_id: str
    tenant_id: str
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    age_years: Optional[int] = None
    sex: Optional[str] = None
    phone_number: Optional[str] = None
    weight_kg: Optional[float] = None
    allergies: list[str] = Field(default_factory=list)
    updated_at: datetime


class EpcrVitalSetContract(BaseModel):
    """Single chart-scoped vital set used for reassessment-aware workflows."""

    id: str
    chart_id: str
    tenant_id: str
    bp_sys: Optional[int] = None
    bp_dia: Optional[int] = None
    hr: Optional[int] = None
    rr: Optional[int] = None
    temp_f: Optional[float] = None
    spo2: Optional[int] = None
    glucose: Optional[int] = None
    recorded_at: datetime


class EpcrClinicalImpressionContract(BaseModel):
    """Structured impression contract for field and downstream read models."""

    chart_id: str
    tenant_id: str
    chief_complaint: Optional[str] = None
    field_diagnosis: Optional[str] = None
    primary_impression: Optional[str] = None
    secondary_impression: Optional[str] = None
    impression_notes: Optional[str] = None
    snomed_code: Optional[str] = None
    icd10_code: Optional[str] = None
    acuity: Optional[str] = None
    documented_at: datetime


class EpcrMedicationAdministrationContract(BaseModel):
    """Medication administration contract owned by the ePCR truth model."""

    id: str
    chart_id: str
    tenant_id: str
    medication_name: str
    rxnorm_code: Optional[str] = None
    dose_value: Optional[str] = None
    dose_unit: Optional[str] = None
    route: str
    indication: str
    response: Optional[str] = None
    export_state: str
    administered_at: datetime


class EpcrSignatureArtifactContract(BaseModel):
    """Authoritative signature artifact contract for chart completion workflows."""

    id: str
    chart_id: str
    tenant_id: str
    source_domain: str
    source_capture_id: str
    signature_class: str
    signature_method: str
    workflow_policy: str
    policy_pack_version: str
    payer_class: str
    signer_identity: Optional[str] = None
    signer_relationship: Optional[str] = None
    patient_capable_to_sign: Optional[bool] = None
    receiving_facility: Optional[str] = None
    transfer_of_care_time: Optional[datetime] = None
    signature_artifact_data_url: Optional[str] = None
    signature_on_file_reference: Optional[str] = None
    compliance_decision: str
    compliance_why: str
    chart_completion_effect: str
    billing_readiness_effect: str
    missing_requirements: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class EpcrNemsissComplianceContract(BaseModel):
    """NEMSIS 3.5.1 compliance status for a chart."""

    chart_id: str

    is_fully_compliant: bool
    compliance_percentage: float

    missing_mandatory_fields: list[str] = Field(default_factory=list)


class EpcrBillingHandoffPayload(BaseModel):
    """Authoritative payload for ePCR-to-Billing handoff on chart submission.

    Triggered when an ePCR chart is finalized and ready for billing.
    Contains all essential clinical data needed to auto-populate a billing claim.
    """

    chart_id: str
    tenant_id: str
    call_number: str

    # Test-record isolation. True for a non-production ePCR (e.g. a Founder
    # WARDS Lab record). A consumer MUST NOT create a Claim, ClaimIntakeRecord,
    # or any payer-facing artifact from a payload where this is True.
    #
    # Defaults to False so existing producers stay valid and an omitted value
    # fails CLOSED toward production (a real encounter is never silently
    # dropped from billing).
    is_test: bool = False

    # Patient demographics from ePCR
    patient_first_name: Optional[str] = None
    patient_last_name: Optional[str] = None
    patient_date_of_birth: Optional[str] = None
    patient_phone: Optional[str] = None

    # Clinical data for claim coding
    chief_complaint: Optional[str] = None
    primary_icd10_code: Optional[str] = None
    secondary_icd10_codes: list[str] = Field(default_factory=list)
    field_diagnosis: Optional[str] = None

    # Transport/Response info
    incident_type: str
    response_started_at: Optional[datetime] = None
    response_completed_at: Optional[datetime] = None

    # Service-level charge (configurable by org)
    base_charge_cents: int = Field(default=0, ge=0)
    mileage_km: Optional[float] = None
    mileage_charge_cents: int = Field(default=0, ge=0)

    # Compliance & readiness
    is_nemsis_compliant: bool
    missing_fields: list[str] = Field(default_factory=list)

    # Audit trail
    finalized_at: datetime
    created_at: datetime


class EpcrBillingHandoffResponse(BaseModel):
    """Response from Billing service after claim auto-population."""

    claim_id: str
    status: str
    total_charge_cents: int
    message: Optional[str] = None
    created_at: datetime
