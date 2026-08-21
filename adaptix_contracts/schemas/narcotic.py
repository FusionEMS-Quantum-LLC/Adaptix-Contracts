"""Narcotics domain contract schemas for cross-domain communication and API surfaces."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class NarcoticVaultType(str, Enum):
    """Supported narcotic vault deployment topologies."""

    STATION = "station"
    VEHICLE = "vehicle"
    AIRCRAFT = "aircraft"
    SUPERVISOR = "supervisor"
    BACKUP = "backup"


class NarcoticVaultStatus(str, Enum):
    """Operational state of a narcotic vault."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"


class ControlledSubstanceSchedule(str, Enum):
    """DEA schedule classification."""

    SCHEDULE_I = "I"
    SCHEDULE_II = "II"
    SCHEDULE_III = "III"
    SCHEDULE_IV = "IV"
    SCHEDULE_V = "V"


class NarcoticMedicationStatus(str, Enum):
    """Inventory state of a narcotic medication package."""

    AVAILABLE = "available"
    QUARANTINED = "quarantined"
    RECALLED = "recalled"
    DESTROYED = "destroyed"
    EXPIRED = "expired"


class NarcoticTransactionType(str, Enum):
    """Supported narcotic ledger transaction categories."""

    ISSUE = "issue"
    RETURN = "return"
    ADMINISTRATION = "administration"
    WASTE = "waste"
    TRANSFER = "transfer"


class NarcoticInvestigationStatus(str, Enum):
    """Investigation lifecycle for discrepancies."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class NarcoticAccessType(str, Enum):
    """Vault access categories tracked for audit purposes.

    Each value corresponds to a DEA 21 CFR 1304.04 immutable access event
    on the controlled-substance vault. Service-layer code in
    ``Adaptix-Narcotics-Service.core_app.narcotic.service._log_vault_access``
    writes a ``NarcoticAccess`` row with one of these values on every
    dispensing operation.

    Added 2026-06-06 (v3 readiness pass):
      - ``ADMINISTER`` -- patient administration (was previously logged as ``ISSUE``)
      - ``WASTE``      -- documented narcotic waste with witness
      - ``TRANSFER_OUT`` -- vault-to-vault outbound transfer leg
      - ``TRANSFER_IN``  -- vault-to-vault inbound transfer leg
    Backfill of legacy rows is handled by the Narcotics-Service Alembic
    migration that adds these enum members at the DB level.
    """

    AUDIT = "audit"
    COUNT = "count"
    ISSUE = "issue"
    RETURN = "return"
    EMERGENCY = "emergency"
    ADMINISTER = "administer"
    WASTE = "waste"
    TRANSFER_OUT = "transfer_out"
    TRANSFER_IN = "transfer_in"


class CountType(str, Enum):
    """Shift count categories used during narcotics accountability workflows."""

    START_SHIFT = "start_shift"
    END_SHIFT = "end_shift"
    MID_SHIFT = "mid_shift"
    BLIND = "blind"
    SUPERVISOR = "supervisor"
    SPOT_CHECK = "spot_check"


class ShiftPhase(str, Enum):
    """Lifecycle phase for a narcotics shift count."""

    START = "start"
    MIDDLE = "middle"
    END = "end"
    EMERGENCY = "emergency"


class RecallStatus(str, Enum):
    """Lifecycle state for narcotic recall tracking."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class WitnessEventType(str, Enum):
    """Witnessed narcotics workflow events."""

    ADMINISTRATION = "administration"
    WASTE = "waste"
    COUNT = "count"
    TRANSFER = "transfer"
    DESTRUCTION = "destruction"
    EMERGENCY_ACCESS = "emergency_access"


class ComplianceType(str, Enum):
    """Compliance record categories for narcotics operations."""

    DEA_222 = "dea_222"
    DEA_106 = "dea_106"
    PERIODIC_AUDIT = "periodic_audit"
    INVENTORY = "inventory"
    WITNESS_VERIFICATION = "witness_verification"


class ActionStatus(str, Enum):
    """Corrective action lifecycle state."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"


class KitStatus(str, Enum):
    """Operational status for narcotic kits."""

    ACTIVE = "active"
    CHECKED_OUT = "checked_out"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    RESTOCKING = "restocking"
    COMPROMISED = "compromised"
    RETIRED = "retired"


class VaultCreateRequest(BaseModel):
    """Request to create a narcotic vault."""

    vault_name: str = Field(min_length=1, max_length=128)
    location: str = Field(min_length=1, max_length=255)
    vault_type: NarcoticVaultType
    next_audit_date: datetime | None = None


class VaultUpdateRequest(BaseModel):
    """Request to update a narcotic vault."""

    version: int = Field(ge=1)
    vault_name: str | None = Field(default=None, min_length=1, max_length=128)
    location: str | None = Field(default=None, min_length=1, max_length=255)
    status: NarcoticVaultStatus | None = None
    next_audit_date: datetime | None = None


class VaultResponse(BaseModel):
    """Canonical narcotic vault response."""

    id: UUID
    tenant_id: UUID
    vault_name: str
    location: str
    vault_type: NarcoticVaultType
    status: NarcoticVaultStatus
    last_audit_date: datetime | None
    next_audit_date: datetime | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    version: int

    model_config = {"from_attributes": True}


class VaultListResponse(BaseModel):
    """List response for narcotic vaults."""

    items: list[VaultResponse]
    total: int


class MedicationCreateRequest(BaseModel):
    """Request to add a narcotic medication to a vault."""

    drug_name: str = Field(min_length=1, max_length=255)
    dea_schedule: ControlledSubstanceSchedule
    strength: str = Field(min_length=1, max_length=64)
    form: str = Field(min_length=1, max_length=64)
    vault_id: UUID
    quantity: Decimal = Field(ge=Decimal("0"))
    lot_number: str = Field(min_length=1, max_length=128)
    expiration_date: datetime
    concentration: str | None = Field(default=None, max_length=64)
    formulation: str | None = Field(default=None, max_length=128)
    route: str | None = Field(default=None, max_length=64)
    serial_number: str | None = Field(default=None, max_length=128)
    ndc_code: str | None = Field(default=None, max_length=64)
    manufacturer: str | None = Field(default=None, max_length=255)
    package_type: str | None = Field(default=None, max_length=64)
    package_size: str | None = Field(default=None, max_length=64)
    seal_number: str | None = Field(default=None, max_length=128)


class MedicationUpdateRequest(BaseModel):
    """Request to update a narcotic medication inventory record."""

    version: int = Field(ge=1)
    quantity: Decimal | None = Field(default=None, ge=Decimal("0"))
    status: NarcoticMedicationStatus | None = None
    expiration_date: datetime | None = None
    seal_number: str | None = Field(default=None, max_length=128)
    seal_intact: bool | None = None


class MedicationResponse(BaseModel):
    """Canonical narcotic medication response."""

    id: UUID
    tenant_id: UUID
    drug_name: str
    dea_schedule: ControlledSubstanceSchedule
    strength: str
    concentration: str | None
    form: str
    formulation: str | None
    route: str | None
    vault_id: UUID
    quantity: Decimal
    lot_number: str
    serial_number: str | None
    ndc_code: str | None
    manufacturer: str | None
    expiration_date: datetime
    package_type: str | None
    package_size: str | None
    seal_number: str | None
    seal_intact: bool
    container_opened: bool
    status: NarcoticMedicationStatus
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    version: int

    model_config = {"from_attributes": True}


class MedicationListResponse(BaseModel):
    """List response for narcotic medications."""

    items: list[MedicationResponse]
    total: int


class IssueNarcoticRequest(BaseModel):
    """Request to issue a narcotic from a vault."""

    medication_id: UUID
    quantity: Decimal = Field(gt=Decimal("0"))
    issued_to_user_id: UUID
    witnessed_by: UUID | None = None
    notes: str | None = Field(default=None, max_length=1000)


class ReturnNarcoticRequest(BaseModel):
    """Request to return a narcotic to a vault."""

    medication_id: UUID
    quantity: Decimal = Field(gt=Decimal("0"))
    returned_by_user_id: UUID
    witnessed_by: UUID | None = None
    reason: str | None = Field(default=None, max_length=1000)


class AdministerNarcoticRequest(BaseModel):
    """Request to document narcotic administration."""

    medication_id: UUID
    dose: Decimal = Field(gt=Decimal("0"))
    administered_by: UUID
    patient_incident_id: UUID
    witnessed_by: UUID | None = None
    waste_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    waste_witnessed_by: UUID | None = None
    notes: str | None = Field(default=None, max_length=1000)


class WasteNarcoticRequest(BaseModel):
    """Request to waste an unused narcotic quantity."""

    medication_id: UUID
    waste_amount: Decimal = Field(gt=Decimal("0"))
    wasted_by: UUID
    witnessed_by: UUID
    reason: str = Field(min_length=1, max_length=1000)


class TransferNarcoticRequest(BaseModel):
    """Request to transfer a narcotic between vaults."""

    medication_id: UUID
    from_vault_id: UUID
    to_vault_id: UUID
    quantity: Decimal = Field(gt=Decimal("0"))
    transferred_by: UUID
    witnessed_by: UUID | None = None
    notes: str | None = Field(default=None, max_length=1000)


class TransactionResponse(BaseModel):
    """Canonical narcotic transaction ledger response."""

    id: UUID
    tenant_id: UUID
    medication_id: UUID
    transaction_type: NarcoticTransactionType
    quantity: Decimal
    administered_by: UUID
    witnessed_by: UUID | None
    patient_incident_id: UUID | None
    transaction_time: datetime
    pre_count: Decimal
    post_count: Decimal
    waste_amount: Decimal | None
    waste_witnessed_by: UUID | None
    signature_required: bool
    signature_captured: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    version: int

    model_config = {"from_attributes": True}


class TransactionListResponse(BaseModel):
    """List response for narcotic transactions."""

    items: list[TransactionResponse]
    total: int


class ConductAuditRequest(BaseModel):
    """Request to conduct a narcotic vault audit."""

    vault_id: UUID
    auditor_id: UUID
    witness_id: UUID
    medication_counts: dict[str, Decimal] = Field(default_factory=dict)
    notes: str | None = Field(default=None, max_length=2000)


class AuditResponse(BaseModel):
    """Canonical narcotic audit response."""

    id: UUID
    tenant_id: UUID
    vault_id: UUID
    audit_date: datetime
    auditor_id: UUID
    witness_id: UUID
    discrepancies_found: bool
    discrepancy_details_json: dict
    resolved: bool
    resolution_notes: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    version: int

    model_config = {"from_attributes": True}


class AuditListResponse(BaseModel):
    """List response for narcotic audits."""

    items: list[AuditResponse]
    total: int


class RecordDiscrepancyRequest(BaseModel):
    """Request to create a narcotic discrepancy record."""

    audit_id: UUID
    medication_id: UUID
    expected_count: Decimal = Field(ge=Decimal("0"))
    actual_count: Decimal = Field(ge=Decimal("0"))
    variance: Decimal


class ResolveDiscrepancyRequest(BaseModel):
    """Request to resolve a narcotic discrepancy."""

    version: int = Field(ge=1)
    resolved_by: UUID
    resolution_notes: str | None = Field(default=None, max_length=2000)


class DiscrepancyResponse(BaseModel):
    """Canonical discrepancy response."""

    id: UUID
    tenant_id: UUID
    audit_id: UUID
    medication_id: UUID
    expected_count: Decimal
    actual_count: Decimal
    variance: Decimal
    investigation_status: NarcoticInvestigationStatus
    resolved_by: UUID | None
    resolution_date: datetime | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    version: int

    model_config = {"from_attributes": True}


class DiscrepancyListResponse(BaseModel):
    """List response for narcotic discrepancies."""

    items: list[DiscrepancyResponse]
    total: int


class ExpiringMedicationsRequest(BaseModel):
    """Request to retrieve expiring narcotic medications."""

    days_ahead: int = Field(default=30, ge=1, le=365)


class ExpiringMedicationResponse(BaseModel):
    """Expiring narcotic medication summary."""

    medication_id: UUID
    vault_id: UUID
    drug_name: str
    lot_number: str
    quantity: Decimal
    expiration_date: datetime
    days_until_expiration: int
    status: NarcoticMedicationStatus


class DEAReportRequest(BaseModel):
    """Request to generate a DEA-aligned narcotic activity report."""

    start_date: datetime
    end_date: datetime


class DEAReportResponse(BaseModel):
    """Summary DEA report response for narcotic operations."""

    report_period_start: datetime
    report_period_end: datetime
    generated_at: datetime
    total_transactions: int
    total_administered_quantity: Decimal
    total_wasted_quantity: Decimal
    discrepancies_found: int
    audits_conducted: int
    report_data: dict = Field(default_factory=dict)


class AccessLogResponse(BaseModel):
    """Canonical vault access log response."""

    id: UUID
    tenant_id: UUID
    vault_id: UUID
    user_id: UUID
    access_time: datetime
    access_type: NarcoticAccessType
    authorized_by: UUID | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    version: int

    model_config = {"from_attributes": True}


class AccessLogListResponse(BaseModel):
    """List response for narcotic access logs."""

    items: list[AccessLogResponse]
    total: int


class NarcoticVaultCreatedEvent(BaseModel):
    """Published when a narcotic vault is created."""

    event_type: str = "narcotic.vault.created"
    vault_id: UUID
    tenant_id: UUID
    vault_name: str
    created_at: datetime


class NarcoticMedicationAddedEvent(BaseModel):
    """Published when a narcotic medication is added to a vault."""

    event_type: str = "narcotic.medication.added"
    medication_id: UUID
    tenant_id: UUID
    vault_id: UUID
    drug_name: str
    quantity: Decimal
    occurred_at: datetime


class NarcoticTransactionRecordedEvent(BaseModel):
    """Published when a narcotic transaction is written to the ledger."""

    event_type: str = "narcotic.transaction.recorded"
    transaction_id: UUID
    tenant_id: UUID
    medication_id: UUID
    transaction_type: NarcoticTransactionType
    quantity: Decimal
    occurred_at: datetime


class NarcoticDiscrepancyRecordedEvent(BaseModel):
    """Published when a discrepancy record is opened."""

    event_type: str = "narcotic.discrepancy.recorded"
    discrepancy_id: UUID
    tenant_id: UUID
    audit_id: UUID
    medication_id: UUID
    variance: Decimal
    occurred_at: datetime
