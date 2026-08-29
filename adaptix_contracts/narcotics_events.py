"""Narcotics service event contracts.

Canonical event schemas for controlled substance domain mutations:
- Vial creation, transfer, usage, waste
- Chain-of-custody tracking (immutable ledger)
- Narcotic discrepancy alerts and escalation
- Count reconciliation and audit events

All events include tenant_id, unit_id (optional), timestamp, and trace_id for
cross-service correlation and audit. Chain-of-custody is immutable.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field


class NarcoticsEventType(str, Enum):
    """Canonical narcotics event types."""

    VIAL_CREATED = "narcotics.vial.created"
    VIAL_TRANSFERRED = "narcotics.vial.transferred"
    VIAL_USAGE_RECORDED = "narcotics.vial.usage_recorded"
    VIAL_WASTE_RECORDED = "narcotics.vial.waste_recorded"

    SUBSTANCE_CREATED = "narcotics.substance.created"
    SUBSTANCE_UPDATED = "narcotics.substance.updated"

    COUNT_RECORDED = "narcotics.count.recorded"
    COUNT_RECONCILED = "narcotics.count.reconciled"

    DISCREPANCY_OPENED = "narcotics.discrepancy.opened"
    DISCREPANCY_ALERT = "narcotics.alert.discrepancy"
    DISCREPANCY_ESCALATED = "narcotics.discrepancy.escalated"
    DISCREPANCY_RESOLVED = "narcotics.discrepancy.resolved"

    CHAIN_OF_CUSTODY_ENTRY = "narcotics.chain_of_custody.entry"
    SEAL_VERIFIED = "narcotics.seal.verified"
    SEAL_BROKEN = "narcotics.seal.broken"

    USAGE_EVENT = "narcotics.usage.recorded"
    WASTE_EVENT = "narcotics.waste.recorded"
    TRANSFER_EVENT = "narcotics.transfer.recorded"
    COST_EVENT = "narcotics.cost.recorded"


class NarcoticsVialEvent(BaseModel):
    """Event published when a narcotics vial is created/transferred/used/wasted."""

    event_type: NarcoticsEventType = Field(...)
    tenant_id: UUID = Field(..., description="Tenant context")
    unit_id: str = Field(..., description="Unit/station ID")

    substance_id: str = Field(..., description="Substance UUID")
    substance_name: str = Field(
        ..., description="Controlled substance name (e.g., 'Fentanyl')"
    )
    substance_dea_schedule: str = Field(..., description="DEA schedule (e.g., 'C-II')")

    vial_id: str = Field(..., description="Vial/unit UUID")
    lot_id: str = Field(..., description="Lot/batch ID")
    expiration_date: datetime = Field(..., description="Vial expiration date")

    quantity: int = Field(..., description="Quantity (in base units)")
    unit_of_measure: str = Field(..., description="Unit of measure (mg, mL, etc)")
    cost_per_unit: Decimal = Field(..., description="Cost per unit")
    total_cost: Decimal = Field(..., description="Total vial cost")

    # For transfers
    from_unit_id: Optional[str] = Field(default=None, description="Source unit")
    to_unit_id: Optional[str] = Field(default=None, description="Destination unit")

    # For usage
    patient_id: Optional[str] = Field(
        default=None, description="Patient (if applicable)"
    )
    used_by: Optional[str] = Field(
        default=None, description="Clinician who used substance"
    )

    # For waste
    waste_reason: Optional[str] = Field(default=None, description="Reason for waste")
    witness: Optional[str] = Field(default=None, description="Witness to waste")

    actor_user_id: Optional[str] = Field(
        default=None, description="User performing action"
    )
    timestamp: datetime = Field(...)
    correlation_id: Optional[str] = Field(default=None)
    trace_id: Optional[str] = Field(default=None)


class NarcoticsChainOfCustodyEntry(BaseModel):
    """Immutable ledger entry for chain-of-custody tracking.

    This entry is IMMUTABLE once created and serves as authoritative COC ledger.
    Every vial transfer, usage, or waste creates a ledger entry that cannot be
    modified or deleted, only read for inspection.
    """

    event_type: NarcoticsEventType = Field(
        default=NarcoticsEventType.CHAIN_OF_CUSTODY_ENTRY
    )
    tenant_id: UUID = Field(..., description="Tenant context")
    unit_id: str = Field(..., description="Unit/station ID")

    # Vial identification
    substance_id: str = Field(..., description="Substance UUID")
    substance_name: str = Field(...)
    vial_id: str = Field(..., description="Vial/unit UUID")
    lot_id: str = Field(...)

    # COC entry type
    entry_type: str = Field(
        ..., description="Type: RECEIVED/TRANSFERRED/USED/WASTED/COUNTED"
    )

    # Quantity tracking
    quantity_involved: int = Field(..., description="Quantity in this event")
    unit_of_measure: str = Field(...)
    balance_before: int = Field(..., description="Balance before this event")
    balance_after: int = Field(..., description="Balance after this event")

    # Responsible parties
    responsible_party: str = Field(
        ..., description="User ID responsible for this entry"
    )
    witness_party: Optional[str] = Field(
        default=None, description="Witness user ID (if required)"
    )

    # Location tracking
    from_location: Optional[str] = Field(default=None, description="Source location")
    to_location: Optional[str] = Field(default=None, description="Destination location")

    # Seal status
    seal_intact_before: Optional[bool] = Field(
        default=None, description="Seal status before"
    )
    seal_intact_after: Optional[bool] = Field(
        default=None, description="Seal status after"
    )

    # Immutable metadata
    entry_id: str = Field(..., description="Unique entry ID (UUID)")
    created_at: datetime = Field(..., description="When entry was created (immutable)")
    created_by: str = Field(..., description="User who created entry (immutable)")

    correlation_id: Optional[str] = Field(default=None)
    trace_id: Optional[str] = Field(default=None)


class NarcoticsDiscrepancyAlert(BaseModel):
    """Alert event when a discrepancy is detected."""

    event_type: NarcoticsEventType = Field(default=NarcoticsEventType.DISCREPANCY_ALERT)
    tenant_id: UUID = Field(..., description="Tenant context")
    unit_id: str = Field(..., description="Unit/station ID")

    substance_id: str = Field(..., description="Substance UUID")
    substance_name: str = Field(...)
    substance_dea_schedule: str = Field(...)

    discrepancy_id: str = Field(..., description="Discrepancy record UUID")
    discrepancy_type: str = Field(..., description="Type: MISSING/OVER/VARIANCE")

    expected_balance: int = Field(..., description="Expected quantity per records")
    actual_balance: int = Field(..., description="Actual quantity counted")
    missing_quantity: int = Field(..., description="Signed difference")
    unit_of_measure: str = Field(...)

    opened_at: datetime = Field(...)
    time_since_last_count: Optional[int] = Field(
        default=None, description="Hours since last count"
    )

    # Escalation
    escalation_flag: bool = Field(..., description="True if unresolved > 24h")
    notify_role: str = Field(default="narcotics_officer", description="Role to notify")
    escalate_to_role: Optional[str] = Field(
        default=None, description="Secondary escalation role"
    )
    severity: str = Field(..., description="Severity: low/medium/high/critical")

    timestamp: datetime = Field(...)
    correlation_id: Optional[str] = Field(default=None)
    trace_id: Optional[str] = Field(default=None)


class NarcoticsCountEvent(BaseModel):
    """Event published when controlled substances are counted."""

    event_type: NarcoticsEventType = Field(...)
    tenant_id: UUID = Field(...)
    unit_id: str = Field(...)

    substance_id: str = Field(...)
    substance_name: str = Field(...)

    scheduled_count: bool = Field(..., description="True if scheduled vs spot check")
    count_date: datetime = Field(...)
    count_performed_by: str = Field(...)

    vials_counted: int = Field(..., description="Number of vials counted")
    total_quantity: int = Field(..., description="Total quantity units")
    unit_of_measure: str = Field(...)

    discrepancies_found: int = Field(..., description="Number of discrepancies")
    critical_discrepancies: int = Field(..., description="Number > 24h old")

    timestamp: datetime = Field(...)
    correlation_id: Optional[str] = Field(default=None)
    trace_id: Optional[str] = Field(default=None)


class NarcoticsAnalyticsEvent(BaseModel):
    """Generic analytics event for narcotics."""

    event_type: NarcoticsEventType = Field(...)
    tenant_id: UUID = Field(...)
    unit_id: str = Field(...)

    timestamp: datetime = Field(...)
    category: str = Field(..., description="Event category")

    # Generic metrics
    quantity: Optional[int] = Field(default=None)
    cost: Optional[Decimal] = Field(default=None)

    # Risk indicators
    risk_score: Optional[float] = Field(
        default=None, description="Diversion risk 0-100"
    )
    risk_level: Optional[str] = Field(default=None, description="green/yellow/red")

    # Custom metadata
    metadata: Optional[dict[str, Any]] = Field(default=None)

    correlation_id: Optional[str] = Field(default=None)
    trace_id: Optional[str] = Field(default=None)


__all__ = [
    "NarcoticsEventType",
    "NarcoticsVialEvent",
    "NarcoticsChainOfCustodyEntry",
    "NarcoticsDiscrepancyAlert",
    "NarcoticsCountEvent",
    "NarcoticsAnalyticsEvent",
]
