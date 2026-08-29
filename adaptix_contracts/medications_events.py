"""Medications service event contracts.

Canonical event schemas for medication domain mutations:
- Medication lot creation, usage, waste
- Medication recalls and alerts
- Expiration tracking and disposal
- Protocol compliance events

All events include tenant_id, unit_id (optional), timestamp, and trace_id for
cross-service correlation and audit.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field


class MedicationEventType(str, Enum):
    """Canonical medication event types."""

    MEDICATION_CREATED = "medications.medication.created"
    MEDICATION_UPDATED = "medications.medication.updated"
    MEDICATION_DELETED = "medications.medication.deleted"

    LOT_CREATED = "medications.lot.created"
    LOT_UPDATED = "medications.lot.updated"
    LOT_DELETED = "medications.lot.deleted"

    ADMINISTRATION_RECORDED = "medications.administration.recorded"
    WASTE_RECORDED = "medications.waste.recorded"
    EXPIRATION_DISPOSED = "medications.expiration.disposed"

    RECALL_DETECTED = "medications.recall.detected"
    RECALL_ALERT = "medications.alert.recall"
    EXPIRATION_ALERT = "medications.alert.expiration"
    # Emitted by Adaptix-Medications-Service's drug-shortage matcher when one of a
    # tenant's catalog medications is newly matched to a live FDA Drug Shortages
    # list entry (openFDA ``drug/shortages``); see ``MedicationShortageAlert``.
    SHORTAGE_ALERT = "medications.alert.shortage"

    STOCK_ADJUSTED = "medications.stock.adjusted"
    PROTOCOL_UPDATED = "medications.protocol.updated"


class MedicationLotEvent(BaseModel):
    """Event published when a medication lot is created/updated."""

    event_type: MedicationEventType = Field(...)
    tenant_id: UUID = Field(..., description="Tenant context")
    unit_id: Optional[str] = Field(default=None, description="Unit/station ID")

    medication_id: str = Field(..., description="Medication UUID")
    medication_name: str = Field(..., description="Medication name")
    lot_id: str = Field(..., description="Lot/batch ID")

    expiration_date: datetime = Field(..., description="Lot expiration date")
    received_date: datetime = Field(..., description="When lot was received")
    quantity_received: int = Field(..., description="Initial quantity")
    current_quantity: int = Field(..., description="Current remaining quantity")

    storage_location: str = Field(..., description="Storage location")
    storage_temperature: Optional[str] = Field(
        default=None, description="Storage conditions"
    )
    unit_of_measure: str = Field(..., description="Unit of measure")
    cost_per_unit: Decimal = Field(..., description="Cost per unit")

    # Before/after for updates
    before_state: Optional[dict[str, Any]] = Field(default=None)
    after_state: Optional[dict[str, Any]] = Field(default=None)

    actor_user_id: Optional[str] = Field(default=None)
    timestamp: datetime = Field(...)
    correlation_id: Optional[str] = Field(default=None)
    trace_id: Optional[str] = Field(default=None)


class MedicationAdministrationEvent(BaseModel):
    """Event published when medication is administered."""

    event_type: MedicationEventType = Field(
        default=MedicationEventType.ADMINISTRATION_RECORDED
    )
    tenant_id: UUID = Field(..., description="Tenant context")
    unit_id: Optional[str] = Field(default=None, description="Unit/station ID")

    medication_id: str = Field(..., description="Medication UUID")
    medication_name: str = Field(..., description="Medication name")
    lot_id: str = Field(..., description="Lot/batch ID")
    patient_id: Optional[str] = Field(
        default=None, description="Patient (if applicable)"
    )

    quantity_administered: int = Field(..., description="Amount given")
    unit_of_measure: str = Field(...)
    cost_per_unit: Decimal = Field(...)
    total_cost: Decimal = Field(..., description="Cost of administration")

    administered_by: Optional[str] = Field(default=None, description="Clinician")
    administered_date: datetime = Field(...)
    protocol_id: Optional[str] = Field(
        default=None, description="Protocol being followed"
    )

    timestamp: datetime = Field(...)
    correlation_id: Optional[str] = Field(default=None)
    trace_id: Optional[str] = Field(default=None)


class MedicationWasteEvent(BaseModel):
    """Event published when medication is wasted (expired, disposal, etc)."""

    event_type: MedicationEventType = Field(...)
    tenant_id: UUID = Field(..., description="Tenant context")
    unit_id: Optional[str] = Field(default=None, description="Unit/station ID")

    medication_id: str = Field(..., description="Medication UUID")
    medication_name: str = Field(..., description="Medication name")
    lot_id: str = Field(..., description="Lot/batch ID")

    quantity_wasted: int = Field(..., description="Quantity disposed")
    unit_of_measure: str = Field(...)
    waste_reason: str = Field(
        ..., description="Reason: expired/damaged/contaminated/other"
    )
    cost_per_unit: Decimal = Field(...)
    waste_cost: Decimal = Field(..., description="Value of wasted medication")

    disposed_by: Optional[str] = Field(
        default=None, description="Person performing disposal"
    )
    witness: Optional[str] = Field(
        default=None, description="Witness to disposal (if required)"
    )
    witness_signature: Optional[str] = Field(
        default=None, description="Witness signature blob key"
    )

    disposal_date: datetime = Field(...)
    timestamp: datetime = Field(...)
    correlation_id: Optional[str] = Field(default=None)
    trace_id: Optional[str] = Field(default=None)


class MedicationRecallAlert(BaseModel):
    """Alert event when medication recall is detected/imported."""

    event_type: MedicationEventType = Field(default=MedicationEventType.RECALL_ALERT)
    tenant_id: UUID = Field(..., description="Tenant context")
    unit_id: Optional[str] = Field(default=None, description="Unit/station ID")

    medication_id: str = Field(..., description="Medication UUID")
    medication_name: str = Field(..., description="Medication name")
    recall_id: str = Field(..., description="FDA/manufacturer recall ID")

    affected_lots: list[str] = Field(..., description="Lot IDs affected by recall")
    affected_quantity: int = Field(..., description="Total units affected")
    recall_reason: str = Field(..., description="Reason for recall")
    severity: str = Field(..., description="Severity: low/medium/high/critical")

    recommended_action: str = Field(..., description="Recommended action")
    affected_patients: Optional[list[str]] = Field(
        default=None, description="Patient IDs affected"
    )

    notify_role: str = Field(default="pharmacy_manager", description="Role to notify")

    timestamp: datetime = Field(...)
    correlation_id: Optional[str] = Field(default=None)
    trace_id: Optional[str] = Field(default=None)


class MedicationExpirationAlert(BaseModel):
    """Alert event when medication lot is within expiration window."""

    event_type: MedicationEventType = Field(
        default=MedicationEventType.EXPIRATION_ALERT
    )
    tenant_id: UUID = Field(..., description="Tenant context")
    unit_id: Optional[str] = Field(default=None, description="Unit/station ID")

    medication_id: str = Field(..., description="Medication UUID")
    medication_name: str = Field(..., description="Medication name")
    lot_id: str = Field(..., description="Lot/batch ID")

    expiration_date: datetime = Field(...)
    days_until_expiration: int = Field(...)
    current_quantity: int = Field(...)
    cost_per_unit: Decimal = Field(...)
    waste_forecast: Decimal = Field(..., description="Est. cost if expired")

    notify_role: str = Field(default="pharmacy_manager", description="Role to notify")
    severity: str = Field(..., description="Severity: low/medium/high")

    timestamp: datetime = Field(...)
    correlation_id: Optional[str] = Field(default=None)
    trace_id: Optional[str] = Field(default=None)


class MedicationShortageAlert(BaseModel):
    """Alert event when a tenant medication is matched to a live FDA drug-shortage entry.

    Inventory / reference data only — carries no patient linkage. ``match_basis``
    is ``rxcui`` (the catalog row's RxNorm code appears in the FDA entry's
    ``openfda.rxcui`` list) or ``generic_name`` (whole-word generic-name match).
    ``on_hand_units`` is the tenant's real stock-balance total at evaluation time
    and is ``None`` when no stock row exists — never an estimate.
    """

    event_type: MedicationEventType = Field(default=MedicationEventType.SHORTAGE_ALERT)
    tenant_id: UUID = Field(..., description="Tenant context")
    unit_id: Optional[str] = Field(default=None, description="Unit/station ID")

    match_id: str = Field(..., description="tenant_drug_shortage_matches row id")
    medication_id: str = Field(..., description="Medication UUID (tenant catalog row)")
    medication_name: str = Field(..., description="Medication generic name")

    shortage_entry_id: str = Field(..., description="drug_shortage_entries row id")
    shortage_generic_name: str = Field(..., description="FDA listing generic name")
    company_name: Optional[str] = Field(default=None, description="Reporting company")
    package_ndc: Optional[str] = Field(
        default=None, description="Package NDC as listed"
    )
    presentation: Optional[str] = Field(
        default=None, description="Presentation as listed"
    )
    status: str = Field(..., description="FDA status as published, e.g. Current")
    availability: Optional[str] = Field(
        default=None, description="Availability as published"
    )
    shortage_reason: Optional[str] = Field(
        default=None, description="Shortage reason as published"
    )

    match_basis: str = Field(..., description="rxcui | generic_name")
    matched_value: str = Field(
        ..., description="The RxCUI or normalised name that matched"
    )
    on_hand_units: Optional[int] = Field(
        default=None,
        description="Tenant on-hand units at evaluation; None when unknown",
    )
    source_update_date: Optional[str] = Field(
        default=None, description="FDA update_date (ISO date)"
    )
    detected_at: datetime = Field(..., description="When the match was first made")

    timestamp: datetime = Field(...)
    correlation_id: Optional[str] = Field(default=None)
    trace_id: Optional[str] = Field(default=None)


class MedicationAnalyticsEvent(BaseModel):
    """Generic analytics event for medications."""

    event_type: MedicationEventType = Field(...)
    tenant_id: UUID = Field(...)
    unit_id: Optional[str] = Field(default=None)

    timestamp: datetime = Field(...)
    category: str = Field(..., description="Event category")

    # Generic metrics
    quantity: Optional[int] = Field(default=None)
    cost: Optional[Decimal] = Field(default=None)

    # Custom metadata
    metadata: Optional[dict[str, Any]] = Field(default=None)

    correlation_id: Optional[str] = Field(default=None)
    trace_id: Optional[str] = Field(default=None)


__all__ = [
    "MedicationEventType",
    "MedicationLotEvent",
    "MedicationAdministrationEvent",
    "MedicationWasteEvent",
    "MedicationRecallAlert",
    "MedicationExpirationAlert",
    "MedicationShortageAlert",
    "MedicationAnalyticsEvent",
]
