"""Inventory domain contract schemas for cross-domain communication and UI/API surfaces."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
import uuid

from pydantic import BaseModel, Field


class InventoryItemCreateRequest(BaseModel):
    """Request to create a new inventory item."""

    item_name: str
    item_category: Any
    sku: str
    unit_of_measure: str
    reorder_level: int = 0
    reorder_quantity: int = 0
    storage_location: str | None = None
    supplier_id: uuid.UUID | None = None
    cost_per_unit: Decimal | None = None
    current_stock: int = 0
    expiration_date: date | None = None
    lot_number: str | None = None
    description: str | None = None


class InventoryItemUpdateRequest(BaseModel):
    """Request to update an inventory item."""

    version: int
    item_name: str | None = None
    reorder_level: int | None = None
    reorder_quantity: int | None = None
    storage_location: str | None = None
    supplier_id: uuid.UUID | None = None
    cost_per_unit: Decimal | None = None
    status: Any = None
    current_stock: int | None = None
    barcode: str | None = None
    expiration_date: date | None = None
    lot_number: str | None = None
    description: str | None = None


class InventoryItemResponse(BaseModel):
    """Canonical inventory item response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    item_name: str
    item_category: str
    sku: str
    unit_of_measure: str
    reorder_level: int
    reorder_quantity: int
    storage_location: str | None
    supplier_id: uuid.UUID | None
    cost_per_unit: Decimal | None
    status: str
    current_stock: int
    barcode: str | None
    expiration_date: date | None
    lot_number: str | None
    last_counted_at: datetime | None
    description: str | None
    created_at: datetime
    updated_at: datetime
    version: int

    model_config = {"from_attributes": True}


class InventoryItemListResponse(BaseModel):
    """List response for inventory items."""

    items: list[InventoryItemResponse]
    total: int


class InventoryTransactionCreateRequest(BaseModel):
    """Authoritative stock mutation request."""

    item_id: uuid.UUID
    transaction_type: Any
    quantity: int
    unit_id: uuid.UUID | None = None
    location_from: uuid.UUID | None = None
    location_to: uuid.UUID | None = None
    reference_incident_id: uuid.UUID | None = None
    reference_po_id: uuid.UUID | None = None
    unit_cost: Decimal | None = None
    notes: str | None = None


class InventoryTransactionResponse(BaseModel):
    """Transaction ledger response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    item_id: uuid.UUID
    transaction_type: str
    quantity: int
    user_id: uuid.UUID
    transaction_date: datetime
    unit_id: uuid.UUID | None
    location_from: uuid.UUID | None
    location_to: uuid.UUID | None
    reference_incident_id: uuid.UUID | None
    reference_po_id: uuid.UUID | None
    unit_cost: Decimal | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InventoryTransactionListResponse(BaseModel):
    """Transaction list response."""

    items: list[InventoryTransactionResponse]
    total: int


class InventoryBatchTransactionRequest(BaseModel):
    """Batch transaction request."""

    transactions: list[InventoryTransactionCreateRequest]


class InventoryBatchTransactionResponse(BaseModel):
    """Batch transaction response."""

    items: list[InventoryTransactionResponse]
    total: int


class InventoryTransferRequest(BaseModel):
    """Transfer request between two location identifiers."""

    item_id: uuid.UUID
    from_location: uuid.UUID
    to_location: uuid.UUID
    quantity: int
    notes: str | None = None


class InventoryUsageLineItem(BaseModel):
    """Usage line item tied to an incident or operational event."""

    item_id: uuid.UUID
    quantity: int
    location_id: uuid.UUID | None = None


class InventoryUsageRequest(BaseModel):
    """Record documented operational usage."""

    incident_id: uuid.UUID
    items: list[InventoryUsageLineItem]
    notes: str | None = None


class InventoryBarcodeLookupRequest(BaseModel):
    """Lookup request for barcode-like identifiers."""

    barcode: str


class InventoryBarcodeLookupResponse(BaseModel):
    """Lookup resolution response."""

    matched: bool
    match_type: str | None = None
    item: InventoryItemResponse | None = None


class StockLevelReport(BaseModel):
    """Low-stock report line."""

    item_id: uuid.UUID
    item_name: str
    sku: str
    current_stock: int
    reorder_level: int
    status: Any


class StockLevelReportResponse(BaseModel):
    """Low-stock report response."""

    items: list[StockLevelReport]
    total: int


class ExpiringItemReport(BaseModel):
    """Expiring inventory report line."""

    item_id: uuid.UUID
    item_name: str
    sku: str
    current_stock: int
    expiration_date: date
    days_until_expiration: int


class ExpiringItemReportResponse(BaseModel):
    """Expiring inventory response."""

    items: list[ExpiringItemReport]
    total: int


class InventoryStatsByTypeEntry(BaseModel):
    """Count and value rollup entry."""

    count: int
    value: Decimal


class InventoryMonthlyUsageEntry(BaseModel):
    """Monthly transaction trend entry."""

    month: str
    total_transactions: int
    total_cost: Decimal


class InventoryStatsResponse(BaseModel):
    """Operational inventory dashboard statistics."""

    total_items: int
    total_value: Decimal
    low_stock_count: int
    out_of_stock_count: int
    expiring_soon_count: int
    cycle_counts_open: int
    discrepancies_open: int
    by_type: dict[str, InventoryStatsByTypeEntry]
    by_location: dict[str, InventoryStatsByTypeEntry]
    monthly_usage_trend: list[InventoryMonthlyUsageEntry]


class InventoryAlertResponse(BaseModel):
    """Operational alert line."""

    id: str
    item_name: str
    current_quantity: int
    min_quantity: int
    unit: str
    location: str
    severity: str
    category: str
    expiring_soon: bool


class NarcoticDiscrepancyResponse(BaseModel):
    """Controlled item discrepancy response."""

    id: str
    medication_name: str
    expected_count: int
    actual_count: int
    difference: int
    last_audit: str
    unit_id: str
    status: str


class InventoryAlertMetricsResponse(BaseModel):
    """Alert metric summary."""

    low_stock_alerts: int
    critical_stock_items: int
    narcotic_discrepancies: int
    items_expiring_30_days: int


class InventoryAlertsDashboardResponse(BaseModel):
    """Alert dashboard response."""

    alerts: list[InventoryAlertResponse]
    narcotic_discrepancies: list[NarcoticDiscrepancyResponse]
    metrics: InventoryAlertMetricsResponse


class InventoryLocationCreateRequest(BaseModel):
    """Create a new location in the storage graph."""

    location_name: str
    location_type: Any
    parent_location_id: uuid.UUID | None = None
    capacity: int | None = None
    address: str | None = None
    notes: str | None = None


class InventoryLocationResponse(BaseModel):
    """Location response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    location_name: str
    location_type: str
    parent_location_id: uuid.UUID | None
    capacity: int | None
    address: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InventoryLocationListResponse(BaseModel):
    """List response for locations."""

    items: list[InventoryLocationResponse]
    total: int


class EquipmentAssetCreateRequest(BaseModel):
    """Create a durable equipment asset."""

    asset_name: str
    asset_type: str
    serial_number: str
    purchase_date: date | None = None
    warranty_expiration: date | None = None
    maintenance_schedule: str | None = None
    assigned_location_id: uuid.UUID | None = None
    manufacturer: str | None = None
    model: str | None = None
    purchase_price: Decimal | None = None
    description: str | None = None


class EquipmentAssetUpdateRequest(BaseModel):
    """Update a durable equipment asset."""

    version: int
    asset_name: str | None = None
    status: Any = None
    assigned_location_id: uuid.UUID | None = None
    maintenance_schedule: str | None = None
    notes: str | None = None


class EquipmentAssetResponse(BaseModel):
    """Equipment asset response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    asset_name: str
    asset_type: str
    serial_number: str
    purchase_date: date | None
    warranty_expiration: date | None
    maintenance_schedule: str | None
    assigned_location_id: uuid.UUID | None
    status: str
    manufacturer: str | None
    model: str | None
    purchase_price: Decimal | None
    description: str | None
    created_at: datetime
    updated_at: datetime
    version: int

    model_config = {"from_attributes": True}


class EquipmentAssetListResponse(BaseModel):
    """Equipment asset list response."""

    items: list[EquipmentAssetResponse]
    total: int


class MaintenanceRecordCreateRequest(BaseModel):
    """Create a maintenance record."""

    asset_id: uuid.UUID
    maintenance_type: Any
    maintenance_date: datetime
    next_due_date: date | None = None
    cost: Decimal | None = None
    notes: str | None = None
    work_performed: str | None = None
    parts_used: dict[str, Any] | None = None


class MaintenanceRecordResponse(BaseModel):
    """Maintenance record response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    asset_id: uuid.UUID
    maintenance_type: str
    performed_by: uuid.UUID
    maintenance_date: datetime
    next_due_date: date | None
    cost: Decimal | None
    notes: str | None
    work_performed: str | None
    parts_used: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MaintenanceRecordListResponse(BaseModel):
    """Maintenance record list response."""

    items: list[MaintenanceRecordResponse]
    total: int


class SupplierCreateRequest(BaseModel):
    """Create a supplier."""

    supplier_name: str
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    address: str | None = None
    payment_terms: str | None = None
    lead_time_days: int | None = None
    notes: str | None = None


class SupplierResponse(BaseModel):
    """Supplier response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    supplier_name: str
    contact_name: str | None
    contact_email: str | None
    contact_phone: str | None
    address: str | None
    payment_terms: str | None
    lead_time_days: int | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SupplierListResponse(BaseModel):
    """Supplier list response."""

    items: list[SupplierResponse]
    total: int


class PurchaseOrderItemRequest(BaseModel):
    """Line item for purchase order creation."""

    item_id: uuid.UUID
    quantity: int
    unit_cost: Decimal


class PurchaseOrderCreateRequest(BaseModel):
    """Create purchase order request."""

    supplier_id: uuid.UUID
    expected_delivery: date | None = None
    notes: str | None = None
    items: list[PurchaseOrderItemRequest]


class PurchaseOrderUpdateRequest(BaseModel):
    """Update purchase order request."""

    version: int
    status: Any = None
    expected_delivery: date | None = None
    actual_delivery: date | None = None
    notes: str | None = None


class PurchaseOrderResponse(BaseModel):
    """Purchase order response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    po_number: str
    supplier_id: uuid.UUID
    order_date: datetime
    expected_delivery: date | None
    actual_delivery: date | None
    status: str
    total_cost: Decimal
    items_json: dict[str, Any]
    notes: str | None
    created_by: uuid.UUID
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int

    model_config = {"from_attributes": True}


class PurchaseOrderListResponse(BaseModel):
    """Purchase order list response."""

    items: list[PurchaseOrderResponse]
    total: int


class PurchaseOrderItemReceived(BaseModel):
    """Received purchase order line item."""

    item_id: uuid.UUID
    quantity_received: int
    quantity_expected: int | None = None


class PurchaseOrderReceiveRequest(BaseModel):
    """Receive purchase order request."""

    version: int
    actual_delivery: date
    items_received: list[PurchaseOrderItemReceived]


class ReceivingVarianceEntry(BaseModel):
    """Receiving variance line entry."""

    item_id: uuid.UUID
    item_name: str
    sku: str
    quantity_ordered: int
    quantity_received: int
    variance: int
    variance_pct: float


class InventoryCycleCountCreateRequest(BaseModel):
    """Start a cycle count."""

    count_name: str
    location_id: uuid.UUID | None = None
    item_category: Any = None
    notes: str | None = None
    is_controlled_substance: bool = False


class InventoryCycleCountResponse(BaseModel):
    """Cycle count response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    count_name: str
    status: str
    location_id: uuid.UUID | None
    scope_snapshot: dict[str, Any]
    started_by: uuid.UUID
    started_at: datetime
    completed_by: uuid.UUID | None


# ---------------------------------------------------------------------------
# Status enums
# ---------------------------------------------------------------------------


class InventoryItemStatus(str):
    """Valid status values for an inventory item."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    LOW_STOCK = "low_stock"
    OUT_OF_STOCK = "out_of_stock"
    DISCONTINUED = "discontinued"


class EquipmentAssetStatus(str):
    """Valid status values for an equipment asset."""

    ACTIVE = "active"
    IN_MAINTENANCE = "in_maintenance"
    RETIRED = "retired"
    LOST = "lost"


class PurchaseOrderStatus(str):
    """Valid status values for a purchase order."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    PARTIALLY_RECEIVED = "partially_received"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class CycleCountStatus(str):
    """Valid status values for a cycle count."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    RECONCILED = "reconciled"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Domain events
# ---------------------------------------------------------------------------


class InventorySupplyItemCreatedEvent(BaseModel):
    """Published when a new supply item is added to the catalog."""

    event_type: str = "inventory.supply_item.created"

    tenant_id: uuid.UUID
    item_id: uuid.UUID
    item_code: str
    item_name: str
    unit_of_measure: str
    par_level: int
    reorder_point: int
    actor_user_id: uuid.UUID
    occurred_at: datetime


class InventoryStockCountRecordedEvent(BaseModel):
    """Published when a stock count snapshot is persisted."""

    event_type: str = "inventory.stock.count_recorded"

    tenant_id: uuid.UUID
    count_id: uuid.UUID
    item_id: uuid.UUID
    quantity_on_hand: int
    previous_quantity: int | None = None
    counted_at: datetime
    actor_user_id: uuid.UUID
    occurred_at: datetime


class InventoryReorderThresholdCrossedEvent(BaseModel):
    """Published when stock drops below the reorder point on a count record."""

    event_type: str = "inventory.stock.reorder_threshold_crossed"

    tenant_id: uuid.UUID
    item_id: uuid.UUID
    item_name: str
    sku: str
    quantity_on_hand: int
    reorder_point: int
    par_level: int
    location_id: uuid.UUID | None = None
    actor_user_id: uuid.UUID
    occurred_at: datetime


class InventoryStockUsageRecordedEvent(BaseModel):
    """Published when items are consumed against an incident."""

    event_type: str = "inventory.stock.usage_recorded"

    tenant_id: uuid.UUID
    incident_id: uuid.UUID
    total_cost: Decimal
    actor_user_id: uuid.UUID
    occurred_at: datetime


class InventoryStockTransferCompletedEvent(BaseModel):
    """Published when stock is moved between locations."""

    event_type: str = "inventory.stock.transfer_completed"

    tenant_id: uuid.UUID
    transaction_id: uuid.UUID
    item_id: uuid.UUID
    quantity: int
    from_location_id: uuid.UUID
    to_location_id: uuid.UUID
    unit_cost: Decimal | None = None
    actor_user_id: uuid.UUID
    occurred_at: datetime


class InventoryPurchaseOrderReceivedEvent(BaseModel):
    """Published when a purchase order is received and stock levels updated."""

    event_type: str = "inventory.purchase_order.received"

    tenant_id: uuid.UUID
    po_id: uuid.UUID
    po_number: str
    supplier_id: uuid.UUID
    has_variance: bool
    total_cost: Decimal
    actor_user_id: uuid.UUID
    occurred_at: datetime


class InventoryCycleCountCompletedEvent(BaseModel):
    """Published when a cycle count is closed."""

    event_type: str = "inventory.cycle_count.completed"

    tenant_id: uuid.UUID
    cycle_count_id: uuid.UUID
    count_name: str
    location_id: uuid.UUID | None = None
    total_items: int
    counted_items: int
    discrepancy_count: int
    auto_reconciled: bool
    is_controlled_substance: bool
    witness_user_id: uuid.UUID | None = None
    completed_by: uuid.UUID
    completed_at: datetime
    occurred_at: datetime


class InventoryDiscrepancyFlaggedEvent(BaseModel):
    """Published when a variance or narcotic discrepancy is detected."""

    event_type: str = "inventory.discrepancy.flagged"

    tenant_id: uuid.UUID
    discrepancy_id: uuid.UUID
    item_id: uuid.UUID
    item_name: str
    sku: str
    cycle_count_id: uuid.UUID | None = None
    expected_quantity: int
    actual_quantity: int
    variance_quantity: int
    is_controlled_substance: bool
    unit_id: uuid.UUID | None = None
    actor_user_id: uuid.UUID
    severity: str
    occurred_at: datetime

    completed_at: datetime | None
    total_items: int
    counted_items: int
    discrepancy_count: int
    notes: str | None
    witness_user_id: uuid.UUID | None
    witness_affirmed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int

    model_config = {"from_attributes": True}


class InventoryCycleCountListResponse(BaseModel):
    """Cycle count list response."""

    items: list[InventoryCycleCountResponse]
    total: int


class InventoryCycleCountLineUpsertRequest(BaseModel):
    """Upsert a cycle count line."""

    item_id: uuid.UUID
    counted_quantity: int
    scanned_barcode: str | None = None
    notes: str | None = None


class InventoryCycleCountLineResponse(BaseModel):
    """Cycle count line response."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    cycle_count_id: uuid.UUID
    item_id: uuid.UUID
    expected_quantity: int
    counted_quantity: int
    variance_quantity: int
    counted_by: uuid.UUID
    counted_at: datetime
    scanned_barcode: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InventoryCycleCountCompleteRequest(BaseModel):
    """Complete a cycle count."""

    auto_reconcile: bool = False


class CycleCountWitnessAffirmRequest(BaseModel):
    """Witness affirmation request for controlled counts."""

    witness_user_id: uuid.UUID


class AutoDraftPoSummaryEntry(BaseModel):
    """Auto-drafted purchase order summary line."""

    supplier_id: uuid.UUID
    supplier_name: str
    po_id: uuid.UUID
    po_number: str
    item_count: int
    total_cost: Decimal


class AutoDraftPoSummaryResponse(BaseModel):
    """Auto-draft purchase order response."""

    total_pos_created: int
    skipped_no_supplier: int
    skipped_no_reorder_quantity: int
    purchase_orders: list[AutoDraftPoSummaryEntry]


class IncidentCostLineItem(BaseModel):
    """Line item for incident cost review."""

    transaction_id: uuid.UUID
    item_id: uuid.UUID
    item_name: str
    sku: str
    quantity: int
    unit_cost: Decimal
    total_cost: Decimal
    transaction_date: datetime


class IncidentCostReportResponse(BaseModel):
    """Incident cost rollup response."""

    incident_id: uuid.UUID
    total_cost: Decimal
    transaction_count: int
    line_items: list[IncidentCostLineItem]


class InventoryEngineStatusResponse(BaseModel):
    """Per-engine operational status for the gravity-level Inventory OS."""

    engine_key: str
    engine_name: str
    status: Literal["healthy", "attention", "degraded", "not_enabled"]
    summary: str
    metrics: dict[str, int | float | str] = Field(default_factory=dict)


class InventoryEngineOverviewResponse(BaseModel):
    """Inventory engine overview."""

    generated_at: datetime
    engines: list[InventoryEngineStatusResponse]


class InventoryBalanceItemResponse(BaseModel):
    """Stockgraph balance projection line."""

    item_id: uuid.UUID
    item_name: str
    sku: str
    item_category: str
    location_name: str
    on_hand: int
    available: int
    reserved: int = 0
    quarantined: int = 0
    status: str
    reorder_level: int
    days_until_expiration: int | None = None


class InventoryBalanceSummaryResponse(BaseModel):
    """Stockgraph balance explorer response."""

    total_items: int
    total_on_hand: int
    total_low_stock: int
    total_expiring_soon: int
    balances: list[InventoryBalanceItemResponse]


class InventoryLocationTreeNodeResponse(BaseModel):
    """Recursive location node used by LOCUSMAP."""

    id: uuid.UUID
    location_name: str
    location_type: str
    parent_location_id: uuid.UUID | None = None
    capacity: int | None = None
    item_count: int = 0
    low_stock_items: int = 0
    child_count: int = 0
    children: list[InventoryLocationTreeNodeResponse] = Field(default_factory=list)


class InventoryLocationMapResponse(BaseModel):
    """Location hierarchy response."""

    generated_at: datetime
    roots: list[InventoryLocationTreeNodeResponse]


class InventoryReadinessLocationResponse(BaseModel):
    """PARAFLOW readiness score for a location."""

    location_id: uuid.UUID
    location_name: str
    location_type: str
    readiness_score: int
    low_stock_items: int
    out_of_stock_items: int
    expiring_items: int
    asset_blockers: int
    cycle_count_variances: int
    blockers: list[str] = Field(default_factory=list)


class InventoryReadinessResponse(BaseModel):
    """PARAFLOW readiness dashboard response."""

    generated_at: datetime
    overall_readiness_score: int
    locations: list[InventoryReadinessLocationResponse]


class InventoryReplayEventResponse(BaseModel):
    """AFTERSTOCK replay event."""

    occurred_at: datetime
    event_type: str
    summary: str
    actor_user_id: uuid.UUID | None = None
    reference_id: uuid.UUID | None = None
    severity: Literal["info", "warning", "critical"] = "info"


class InventoryReplayResponse(BaseModel):
    """AFTERSTOCK replay response."""

    generated_at: datetime
    incident_id: uuid.UUID | None = None
    location_id: uuid.UUID | None = None
    events: list[InventoryReplayEventResponse]
