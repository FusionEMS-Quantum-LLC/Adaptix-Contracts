"""Inventory service event contracts.

Canonical event schemas for inventory domain mutations:
- Stock transfers, adjustments, counts
- Readiness scores and tracking
- Low-stock alerts and par level tracking
- Expiration risk events

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


class InventoryEventType(str, Enum):
    """Canonical inventory event types."""

    ITEM_CREATED = "inventory.item.created"
    ITEM_UPDATED = "inventory.item.updated"
    ITEM_DELETED = "inventory.item.deleted"

    STOCK_ADJUSTED = "inventory.stock.adjusted"
    STOCK_TRANSFERRED = "inventory.stock.transferred"
    COUNT_RECORDED = "inventory.count.recorded"
    READINESS_CALCULATED = "inventory.readiness.calculated"

    LOW_STOCK_ALERT = "inventory.alert.low_stock"
    EXPIRATION_ALERT = "inventory.alert.expiration"
    RECALL_ALERT = "inventory.alert.recall"

    READINESS_SCORE_UPDATED = "inventory.readiness.score_updated"
    USAGE_EVENT = "inventory.usage.recorded"
    WASTE_EVENT = "inventory.waste.recorded"
    COST_EVENT = "inventory.cost.recorded"


class InventoryItemEvent(BaseModel):
    """Event published when an inventory item is created/updated/deleted."""

    event_type: InventoryEventType = Field(
        ..., description="One of: item.created, item.updated, item.deleted"
    )
    tenant_id: UUID = Field(..., description="Tenant context")
    item_id: str = Field(..., description="Inventory item UUID")
    item_name: str = Field(..., description="Item name")
    category: str = Field(..., description="Item category")
    location: str = Field(..., description="Storage location")
    par_level: int = Field(..., description="Par stock level")
    current_stock: int = Field(..., description="Current stock count")
    unit: str = Field(..., description="Unit of measure")
    cost_per_unit: Decimal = Field(..., description="Cost per unit")

    # Before/after for updates
    before_state: Optional[dict[str, Any]] = Field(
        None, description="State before mutation"
    )
    after_state: Optional[dict[str, Any]] = Field(
        None, description="State after mutation"
    )

    actor_user_id: Optional[str] = Field(None, description="User performing action")
    timestamp: datetime = Field(..., description="Event timestamp")
    correlation_id: Optional[str] = Field(
        None, description="Correlation ID for tracing"
    )
    trace_id: Optional[str] = Field(None, description="Distributed trace ID")


class InventoryStockAdjustmentEvent(BaseModel):
    """Event published when inventory stock is adjusted."""

    event_type: InventoryEventType = Field(default=InventoryEventType.STOCK_ADJUSTED)
    tenant_id: UUID = Field(..., description="Tenant context")
    unit_id: Optional[str] = Field(None, description="Unit/station ID")
    item_id: str = Field(..., description="Inventory item UUID")
    item_name: str = Field(..., description="Item name")
    category: str = Field(..., description="Item category")
    location: str = Field(..., description="Storage location")

    previous_balance: int = Field(..., description="Stock before adjustment")
    new_balance: int = Field(..., description="Stock after adjustment")
    adjustment_quantity: int = Field(..., description="Signed adjustment amount")
    adjustment_reason: str = Field(..., description="Reason for adjustment")

    par_level: int = Field(..., description="Par stock level")
    cost_per_unit: Decimal = Field(..., description="Cost per unit")
    adjustment_cost: Decimal = Field(..., description="Cost impact of adjustment")

    actor_user_id: Optional[str] = Field(None, description="User performing action")
    timestamp: datetime = Field(..., description="Event timestamp")
    correlation_id: Optional[str] = Field(None, description="Correlation ID")
    trace_id: Optional[str] = Field(None, description="Distributed trace ID")


class InventoryLowStockAlert(BaseModel):
    """Alert event published when inventory drops below par level."""

    event_type: InventoryEventType = Field(default=InventoryEventType.LOW_STOCK_ALERT)
    tenant_id: UUID = Field(..., description="Tenant context")
    unit_id: Optional[str] = Field(None, description="Unit/station ID")

    item_id: str = Field(..., description="Inventory item UUID")
    item_name: str = Field(..., description="Item name")
    category: str = Field(..., description="Item category")
    location: str = Field(..., description="Storage location")

    current_stock: int = Field(..., description="Current stock level")
    par_level: int = Field(..., description="Par/target stock level")
    recommended_order_quantity: int = Field(
        ..., description="Recommended reorder amount"
    )

    cost_per_unit: Decimal = Field(..., description="Cost per unit")
    total_reorder_cost: Decimal = Field(
        ..., description="Est. cost of recommended reorder"
    )

    # Who should be notified
    notify_role: str = Field(default="supply_officer", description="Role to notify")
    severity: str = Field(
        default="medium", description="Alert severity: low/medium/high"
    )

    timestamp: datetime = Field(..., description="Event timestamp")
    correlation_id: Optional[str] = Field(None, description="Correlation ID")
    trace_id: Optional[str] = Field(None, description="Distributed trace ID")


class InventoryExpirationAlert(BaseModel):
    """Alert event published when item is within 30 days of expiration."""

    event_type: InventoryEventType = Field(default=InventoryEventType.EXPIRATION_ALERT)
    tenant_id: UUID = Field(..., description="Tenant context")
    unit_id: Optional[str] = Field(None, description="Unit/station ID")

    item_id: str = Field(..., description="Inventory item UUID")
    item_name: str = Field(..., description="Item name")
    category: str = Field(..., description="Item category")
    location: str = Field(..., description="Storage location")

    expiration_date: datetime = Field(..., description="Item expiration date")
    days_until_expiration: int = Field(..., description="Days until expiration")
    current_stock: int = Field(..., description="Stock count")
    cost_per_unit: Decimal = Field(..., description="Cost per unit")
    waste_forecast: Decimal = Field(..., description="Est. cost of waste if not used")

    notify_role: str = Field(default="supply_officer", description="Role to notify")
    severity: str = Field(
        default="medium", description="Alert severity: low/medium/high"
    )

    timestamp: datetime = Field(..., description="Event timestamp")
    correlation_id: Optional[str] = Field(None, description="Correlation ID")
    trace_id: Optional[str] = Field(None, description="Distributed trace ID")


class InventoryReadinessScoreEvent(BaseModel):
    """Event published when readiness score is calculated."""

    event_type: InventoryEventType = Field(
        default=InventoryEventType.READINESS_CALCULATED
    )
    tenant_id: UUID = Field(..., description="Tenant context")
    unit_id: str = Field(..., description="Unit/station ID")

    readiness_score: float = Field(..., description="Readiness score 0-100")
    items_below_par: int = Field(..., description="Count of items below par")
    items_at_risk: int = Field(..., description="Count of items at expiration risk")
    total_items: int = Field(..., description="Total unique items in inventory")

    # Risk indicators
    high_risk_items: list[str] = Field(
        default_factory=list, description="Item IDs at risk"
    )
    critical_items: list[str] = Field(
        default_factory=list, description="Critical shortages"
    )

    timestamp: datetime = Field(..., description="Event timestamp")
    correlation_id: Optional[str] = Field(None, description="Correlation ID")
    trace_id: Optional[str] = Field(None, description="Distributed trace ID")


class InventoryAnalyticsEvent(BaseModel):
    """Base event for analytics ingestion."""

    event_type: InventoryEventType = Field(...)
    tenant_id: UUID = Field(..., description="Tenant context")
    unit_id: Optional[str] = Field(None, description="Unit/station ID")

    timestamp: datetime = Field(..., description="Event timestamp")
    category: str = Field(..., description="Item category or event category")

    # Generic metrics
    quantity: Optional[int] = Field(None, description="Quantity involved")
    cost: Optional[Decimal] = Field(None, description="Cost impact")

    # Custom fields for different event types
    metadata: Optional[dict[str, Any]] = Field(
        None, description="Event-specific metadata"
    )

    correlation_id: Optional[str] = Field(None, description="Correlation ID")
    trace_id: Optional[str] = Field(None, description="Distributed trace ID")


__all__ = [
    "InventoryEventType",
    "InventoryItemEvent",
    "InventoryStockAdjustmentEvent",
    "InventoryLowStockAlert",
    "InventoryExpirationAlert",
    "InventoryReadinessScoreEvent",
    "InventoryAnalyticsEvent",
]
