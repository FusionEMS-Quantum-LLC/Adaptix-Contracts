"""Medication operations contracts shared across Adaptix services."""

from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MedicationRouteOfAdmin(str, enum.Enum):
    ORAL = "oral"
    INTRAVENOUS = "intravenous"
    INTRAMUSCULAR = "intramuscular"
    SUBCUTANEOUS = "subcutaneous"
    INHALATION = "inhalation"
    TOPICAL = "topical"
    SUBLINGUAL = "sublingual"
    RECTAL = "rectal"
    INTRANASAL = "intranasal"
    INTRAOSSEOUS = "intraosseous"
    ENDOTRACHEAL = "endotracheal"
    NEBULIZED = "nebulized"
    OPHTHALMIC = "ophthalmic"
    OTIC = "otic"
    OTHER = "other"


class DoseSafetyStatus(str, enum.Enum):
    SAFE = "safe"
    WARNING = "warning"
    CONTRAINDICATED = "contraindicated"
    REQUIRES_OVERRIDE = "requires_override"


class MedicationCatalogContract(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    generic_name: str | None = None
    rxcui: str | None = None
    ndc: str | None = None
    drug_class: str | None = None
    controlled_substance: bool = False
    dea_schedule: str | None = None
    default_dose: str | None = None
    default_unit: str | None = None
    default_route: MedicationRouteOfAdmin | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime | None = None


class MedicationAdministrationContract(BaseModel):
    id: UUID
    tenant_id: UUID
    medication_id: UUID
    patient_id: UUID | None = None
    incident_id: UUID | None = None
    chart_id: UUID | None = None
    administered_by: UUID
    dose: str
    unit: str
    route: MedicationRouteOfAdmin
    administered_at: datetime
    site: str | None = None
    response: str | None = None
    notes: str | None = None
    lot_number: str | None = None
    expiration_date: datetime | None = None
    created_at: datetime


class MedicationProtocolRuleContract(BaseModel):
    id: UUID
    tenant_id: UUID
    medication_id: UUID
    protocol_name: str
    indication: str
    min_dose: str | None = None
    max_dose: str | None = None
    allowed_routes: list[MedicationRouteOfAdmin] = Field(default_factory=list)
    contraindications: list[str] = Field(default_factory=list)
    requires_medical_control: bool = False
    age_restriction_min: int | None = None
    age_restriction_max: int | None = None
    weight_based: bool = False
    is_active: bool = True


class DoseSafetyCheckRequest(BaseModel):
    medication_id: UUID
    patient_id: UUID | None = None
    dose: str
    unit: str
    route: MedicationRouteOfAdmin
    patient_weight_kg: float | None = None
    patient_age_years: int | None = None


class DoseSafetyCheckResponse(BaseModel):
    status: DoseSafetyStatus
    warnings: list[str] = Field(default_factory=list)
    max_dose_exceeded: bool = False
    contraindications_found: list[str] = Field(default_factory=list)
    requires_medical_control: bool = False


class MedicationExpirationAlertContract(BaseModel):
    id: UUID
    tenant_id: UUID
    medication_id: UUID
    lot_number: str
    expiration_date: datetime
    days_until_expiration: int
    location: str | None = None
    unit_id: UUID | None = None


class UnitMedicationReadinessContract(BaseModel):
    tenant_id: UUID
    unit_id: UUID
    total_medications: int
    expired_count: int
    expiring_soon_count: int
    missing_count: int
    readiness_percentage: float
    snapshot_at: datetime


class MedicationAdministeredEvent(BaseModel):
    administration_id: UUID
    tenant_id: UUID
    medication_id: UUID
    patient_id: UUID | None = None
    administered_by: UUID
    administered_at: datetime


class MedicationExpirationWarningEvent(BaseModel):
    tenant_id: UUID
    medication_id: UUID
    lot_number: str
    expiration_date: datetime
    days_until_expiration: int
