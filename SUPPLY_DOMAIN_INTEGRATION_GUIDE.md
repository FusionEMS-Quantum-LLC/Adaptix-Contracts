# Supply Domain Integration Guide

Complete integration specification for Inventory, Medications, and Narcotics
services with Notifications, Search, Analytics, and Audit services.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Event Contracts](#event-contracts)
3. [Integration Clients](#integration-clients)
4. [Inventory Service Integration](#inventory-service-integration)
5. [Medications Service Integration](#medications-service-integration)
6. [Narcotics Service Integration](#narcotics-service-integration)
7. [Configuration](#configuration)
8. [Testing](#testing)
9. [Deployment](#deployment)

## Architecture Overview

The supply domain services (Inventory, Medications, Narcotics) integrate with
four external services:

```text
┌──────────────────────────────────────────────────────────────┐
│ Inventory / Medications / Narcotics Services                 │
└──────────────────────────────────────────────────────────────┘
         │              │              │              │
         ├──────────────┼──────────────┼──────────────┤
         │              │              │              │
    ┌────▼────┐   ┌────▼────┐   ┌────▼────┐   ┌────▼────┐
    │Notif.   │   │ Search  │   │Analytics│   │ Audit   │
    │Service  │   │Service  │   │Service  │   │Service  │
    └─────────┘   └─────────┘   └─────────┘   └─────────┘
```

### Design Principles

- **Event-Driven**: All mutations trigger events published to external services
- **Best-Effort**: Integration failures do NOT block business operations
- **Immutable Audit**: All mutations create immutable audit records
- **Tenant-Isolated**: All events include tenant_id for strict isolation
- **Trace-Enabled**: Correlation IDs enable cross-service request tracking
- **Graceful Degradation**: Services continue if integration services unavailable

## Event Contracts

### Inventory Events

All inventory events are defined in `adaptix_contracts.inventory_events`:

#### InventoryLowStockAlert

Fired when item drops below par level:

```python
InventoryLowStockAlert(
    tenant_id=tenant_id,
    item_id="item-123",
    item_name="Saline 0.9%",
    current_stock=5,
    par_level=20,
    recommended_order_quantity=15,
    notify_role="supply_officer",
    severity="medium",
)
```

#### InventoryExpirationAlert

Fired when item is within 30 days of expiration:

```python
InventoryExpirationAlert(
    tenant_id=tenant_id,
    item_id="item-123",
    item_name="Saline 0.9%",
    expiration_date=datetime(...),
    days_until_expiration=25,
    waste_forecast=125.00,
    notify_role="supply_officer",
)
```

#### InventoryStockAdjustmentEvent

Fired on every stock adjustment:

```python
InventoryStockAdjustmentEvent(
    tenant_id=tenant_id,
    item_id="item-123",
    item_name="Saline 0.9%",
    previous_balance=15,
    new_balance=5,
    adjustment_quantity=-10,
    adjustment_reason="used",
)
```

### Medications Events

All medication events are defined in `adaptix_contracts.medications_events`:

#### MedicationLotEvent

Fired on lot creation/update:

```python
MedicationLotEvent(
    tenant_id=tenant_id,
    medication_id="med-123",
    medication_name="Aspirin",
    lot_id="LOT-001",
    expiration_date=datetime(...),
    quantity_received=1000,
    current_quantity=950,
)
```

#### MedicationAdministrationEvent

Fired when medication is administered:

```python
MedicationAdministrationEvent(
    tenant_id=tenant_id,
    medication_id="med-123",
    medication_name="Aspirin",
    lot_id="LOT-001",
    quantity_administered=2,
    administered_by="user-123",
)
```

#### MedicationWasteEvent

Fired when medication is wasted/disposed:

```python
MedicationWasteEvent(
    tenant_id=tenant_id,
    medication_id="med-123",
    medication_name="Aspirin",
    lot_id="LOT-001",
    quantity_wasted=100,
    waste_reason="expired",
    witness="user-456",
)
```

#### MedicationRecallAlert

Fired when recall is detected:

```python
MedicationRecallAlert(
    tenant_id=tenant_id,
    medication_id="med-123",
    medication_name="Aspirin",
    recall_id="FDA-2026-001",
    affected_lots=["LOT-001", "LOT-002"],
    recommended_action="Quarantine and return",
)
```

### Narcotics Events

All narcotics events are defined in `adaptix_contracts.narcotics_events`:

#### NarcoticsVialEvent

Fired on vial creation/transfer/use/waste:

```python
NarcoticsVialEvent(
    tenant_id=tenant_id,
    unit_id="unit-123",
    substance_id="subst-123",
    substance_name="Fentanyl",
    substance_dea_schedule="C-II",
    vial_id="vial-123",
    quantity=5,
    event_type="transferred",
    from_unit_id="unit-123",
    to_unit_id="unit-456",
)
```

#### NarcoticsChainOfCustodyEntry (IMMUTABLE LEDGER)

Fired on every vial transfer/usage/waste - creates immutable ledger entry:

```python
NarcoticsChainOfCustodyEntry(
    tenant_id=tenant_id,
    unit_id="unit-123",
    substance_id="subst-123",
    vial_id="vial-123",
    entry_type="TRANSFERRED",
    quantity_involved=5,
    balance_before=10,
    balance_after=5,
    responsible_party="user-123",
    entry_id="coc-entry-uuid",
    created_at=datetime(...),
)
```

**IMPORTANT**: COC entries are immutable. Once created, they cannot be modified
or deleted. They serve as the authoritative ledger for DEA Form 222/41
compliance.

#### NarcoticsDiscrepancyAlert

Fired when discrepancy is opened:

```python
NarcoticsDiscrepancyAlert(
    tenant_id=tenant_id,
    unit_id="unit-123",
    substance_name="Fentanyl",
    expected_balance=10,
    actual_balance=5,
    missing_quantity=5,
    escalation_flag=True,  # True if unresolved > 24h
    notify_role="narcotics_officer",
)
```

## Integration Clients

All integrations use shared clients from `adaptix_contracts.supply_integrations`:

### NotificationClient

Send alerts to users:

```python
from adaptix_contracts.supply_integrations import NotificationClient

# Low-stock alert
await NotificationClient.send_low_stock_alert(
    tenant_id=tenant_id,
    recipient_user_id="user-123",
    item_name="Saline 0.9%",
    current_stock=5,
    par_level=20,
    recommended_quantity=15,
    unit="boxes",
    cost_estimate=75.00,
)

# Expiration alert
await NotificationClient.send_expiration_alert(
    tenant_id=tenant_id,
    recipient_user_id="user-123",
    item_name="Saline 0.9%",
    expiration_date=datetime(...),
    current_stock=10,
    waste_forecast=50.00,
)

# Recall alert
await NotificationClient.send_recall_alert(
    tenant_id=tenant_id,
    recipient_user_id="user-123",
    item_name="Medication X",
    recall_id="FDA-2026-001",
    affected_lots=["LOT-001", "LOT-002"],
    recommended_action="Quarantine and return",
)

# Discrepancy alert
await NotificationClient.send_discrepancy_alert(
    tenant_id=tenant_id,
    recipient_user_id="user-123",
    substance_name="Fentanyl",
    missing_quantity=5,
    unit="vials",
    escalation_flag=True,
)
```

### SearchClient — REMOVED

There is no SearchClient. One existed and was removed because it had never
indexed a
single row. Its six call sites across Inventory / Medications / Narcotics were all
unreachable, and the client was wrong on three axes at once against
Adaptix-Search-Service: it POSTed to `/api/v1/search/index/{index}`
(not a route —
the real one is `POST /api/v1/search/index`), authenticated with
`Authorization: Bearer` instead of the required `X-Internal-Service-Key`, and
sent a
payload carrying none of `IndexEntityRequest`'s required
`entity_type` / `entity_id` / `title` fields. `_index_document` caught the resulting
exception and returned `False`, so none of it ever surfaced.

**The role-gate blocker is CLOSED — the supply entity types are now gated.**

This section previously warned that `GET /api/v1/search` applied no
`entity_type` predicate beyond a three-value deny-list
(`SENSITIVE_ENTITY_TYPES = {patient, epcr_chart, billing_claim}`), so
`inventory_items` / `medication_lots` / `narcotic_vials` — in neither that
deny-list nor `VALID_SCOPES` — would have been returned by the default global
search box to **every** role, `viewer` and `dispatch` included.

Adaptix-Search-Service PR #118 (merge `63845f4`, deployed as task definition
`adaptix-production-search:138`) inverted that gate to a positive allow-list in
`search_app/permissions.py`, and classified the three supply entity types with
entitlements copied from this repo's own `adaptix_contracts/rbac_contracts.py`:

- `narcotic_vials` — entitled to the `narcotics:read` role set:
  `founder`, `agency_admin`, `operations_chief`, `narcotics_officer`,
  `medical_director`, `supervisor`, `paramedic`, `auditor`, `inspector`.
- `medication_lots` — entitled to the `medications:read` role set:
  `founder`, `agency_admin`, `operations_chief`,
  `pharmacy_medication_manager`, `medical_director`, `supervisor`,
  `paramedic`, `emt`, `auditor`, `inspector`.
- `inventory_items` — entitled to the `inventory:read_items` role set:
  `founder`, `agency_admin`, `operations_chief`, `supply_officer`,
  `fleet_equipment_manager`, `supervisor`, `paramedic`, `emt`, `auditor`,
  `inspector`.

`narcotic_vials` excludes `viewer`, `dispatch`, `emt` and `billing_operator`, so
`substance_name` / `vial_id` / `lot_id` / `unit_id` / `seal_status` /
`chain_of_custody_status` are no longer reachable by an unentitled role via the
global search box or via autocomplete. A Search test asserts equality with the
permission sets above, so changing a read permission in `rbac_contracts.py`
fails Search CI rather than silently widening search visibility.

**What a future supply SearchClient must still do:**

1. Use exactly the three registered `entity_type` strings above. Any other value
   is rejected on the write path (`IndexEntityRequest` -> HTTP 422) and would
   return no rows to any non-founder role — the gate is fail-closed on an
   unclassified type. Register a new type in `search_app/permissions.py` first.
2. `POST /api/v1/search/index` (not `/index/{index}`), with the
   `X-Internal-Service-Key` header (not `Authorization: Bearer`), and a full
   `IndexEntityRequest` body including `entity_type` / `entity_id` / `title`.
   Those three defects are what made the removed client a permanent no-op.
3. Never put PHI in `title` — the title is what autocomplete returns.

### AnalyticsClient

Publish metrics for trend analysis:

```python
from adaptix_contracts.supply_integrations import AnalyticsClient

# Usage event
await AnalyticsClient.publish_usage_event(
    tenant_id=tenant_id,
    unit_id="unit-123",
    event_type="medication_administered",
    quantity=10,
    cost=50.00,
    metadata={"patient_id": "patient-123"},
)

# Waste event
await AnalyticsClient.publish_waste_event(
    tenant_id=tenant_id,
    unit_id="unit-123",
    waste_reason="expired",
    quantity=100,
    cost=500.00,
)

# Risk event
await AnalyticsClient.publish_risk_event(
    tenant_id=tenant_id,
    unit_id="unit-123",
    risk_type="expiration_risk",
    risk_score=75.5,
    risk_level="yellow",
    metadata={"items_at_risk": 5},
)
```

### AuditClient

Log immutable audit entries:

```python
from adaptix_contracts.supply_integrations import AuditClient

# Log mutation
await AuditClient.log_mutation(
    tenant_id=tenant_id,
    entity_type="inventory_item",
    entity_id="item-123",
    action="stock_adjusted",
    actor_user_id="user-123",
    before_state={"stock": 15},
    after_state={"stock": 5},
    reason="usage",
)

# Log approval
await AuditClient.log_approval(
    tenant_id=tenant_id,
    entity_type="narcotic_discrepancy",
    entity_id="disc-123",
    approver_user_id="user-456",
    approval_type="supervisor_review",
    reason="Discrepancy resolved",
)
```

## Inventory Service Integration

The Inventory Service uses `InventoryIntegrationService` to publish events.

### Key Integration Points

1. **Item Creation** (`on_item_created`)
   - Indexes item in Search
   - Logs creation to Audit

2. **Stock Adjustment** (`on_stock_adjusted`)
   - Checks if below par → sends low-stock notification
   - Indexes updated stock in Search
   - Publishes usage event to Analytics
   - Logs adjustment to Audit

3. **Expiration Tracking** (`on_expiration_approaching`)
   - Sends expiration alert to user

4. **Count Recording** (`on_count_recorded`)
   - Publishes to Analytics
   - Logs to Audit

5. **Restock Recording** (`on_restock_recorded`)
   - Publishes to Analytics
   - Logs to Audit
   - **NOTE**: Controlled-substance restocks also emit to event bus for
     Narcotics service

### Usage in API Endpoints

```python
from inventory_app.integrations import InventoryIntegrationService


@router.post("/items")
async def create_supply_item(req: CreateItemRequest, session: AsyncSession):
    item = await InventoryService.create_supply_item(...)

    # Trigger integrations
    await InventoryIntegrationService.on_item_created(
        tenant_id=req.tenant_id,
        item_id=item.id,
        item_name=item.item_name,
        category=req.category,
        location=req.location,
        par_level=item.par_level,
        cost_per_unit=req.cost_per_unit,
    )

    return item


@router.post("/items/{item_id}/stock-adjustment")
async def adjust_stock(
    item_id: str, req: StockAdjustmentRequest, session: AsyncSession
):
    old_stock = item.current_stock
    new_stock = await InventoryService.adjust_stock(item_id, req.quantity)

    # Trigger integrations
    await InventoryIntegrationService.on_stock_adjusted(
        tenant_id=req.tenant_id,
        item_id=item_id,
        item_name=item.item_name,
        previous_balance=old_stock,
        new_balance=new_stock,
        adjustment_quantity=req.quantity,
        adjustment_reason=req.reason,
        cost_per_unit=item.cost_per_unit,
    )

    return {"old": old_stock, "new": new_stock}
```

## Medications Service Integration

The Medications Service uses `MedicationsIntegrationService` to publish events.

### Key Integration Points

1. **Lot Creation** (`on_medication_lot_created`)
   - Indexes lot in Search
   - Logs creation to Audit

2. **Administration** (`on_medication_administered`)
   - Publishes usage event to Analytics
   - Logs to Audit

3. **Waste** (`on_medication_wasted`)
   - Publishes waste event to Analytics
   - Logs to Audit

4. **Expiration Alerts** (`on_expiration_approaching`)
   - Sends expiration alert to user

5. **Recalls** (`on_recall_detected`)
   - Sends recall alert to user
   - Logs to Audit

6. **Stock Updates** (`on_lot_stock_updated`)
   - Updates lot in Search index

### Usage in API Endpoints

```python
from medications.integrations import MedicationsIntegrationService


@router.post("/lots")
async def create_medication_lot(req: CreateLotRequest, session: AsyncSession):
    lot = await MedicationsService.create_lot(...)

    # Trigger integrations
    await MedicationsIntegrationService.on_medication_lot_created(
        tenant_id=req.tenant_id,
        medication_id=req.medication_id,
        medication_name=req.medication_name,
        lot_id=lot.id,
        expiration_date=req.expiration_date,
        quantity_received=req.quantity,
        storage_location=req.storage_location,
        cost_per_unit=req.cost_per_unit,
    )

    return lot


@router.post("/lots/{lot_id}/administer")
async def administer_medication(
    lot_id: str, req: AdministerRequest, session: AsyncSession
):
    result = await MedicationsService.administer(lot_id, req.quantity)

    # Trigger integrations
    await MedicationsIntegrationService.on_medication_administered(
        tenant_id=req.tenant_id,
        medication_id=req.medication_id,
        medication_name=req.medication_name,
        lot_id=lot_id,
        quantity_administered=req.quantity,
        cost_per_unit=req.cost_per_unit,
        administered_by=req.user_id,
    )

    return result
```

## Narcotics Service Integration

The Narcotics Service uses `NarcoticsIntegrationService` to publish events.

### Key Integration Points

1. **Vial Creation** (`on_vial_created`)
   - Indexes vial in Search
   - Logs creation to Audit

2. **Vial Transfer** (`on_vial_transferred`)
   - Indexes vial in Search with new unit
   - Publishes to Analytics
   - Logs to Audit
   - **Also calls `on_chain_of_custody_entry` to create immutable ledger**

3. **Vial Usage** (`on_vial_used`)
   - Publishes usage to Analytics
   - Logs to Audit
   - **Also calls `on_chain_of_custody_entry` to create immutable ledger**

4. **Vial Waste** (`on_vial_wasted`)
   - Publishes waste to Analytics
   - Logs to Audit
   - **Also calls `on_chain_of_custody_entry` to create immutable ledger**

5. **Discrepancy Detection** (`on_discrepancy_detected`)
   - Sends discrepancy alert with escalation flag
   - Logs to Audit

6. **Count Recording** (`on_count_recorded`)
   - Publishes to Analytics
   - Logs to Audit

7. **Chain-of-Custody** (`on_chain_of_custody_entry`)
   - **Creates immutable ledger entry in Audit Service**
   - **Cannot be modified or deleted once created**
   - Records: entry_type, quantity, responsible_party, witness, seal status

### IMMUTABLE CHAIN-OF-CUSTODY LEDGER

Every vial transfer, usage, or waste creates an immutable ledger entry:

```python
await NarcoticsIntegrationService.on_chain_of_custody_entry(
    tenant_id=tenant_id,
    unit_id="unit-123",
    substance_id="subst-123",
    substance_name="Fentanyl",
    vial_id="vial-123",
    lot_id="LOT-001",
    entry_type="TRANSFERRED",  # TRANSFERRED, USED, WASTED, COUNTED, RECEIVED
    quantity_involved=5,
    balance_before=10,
    balance_after=5,
    responsible_party="user-123",
    entry_id="coc-entry-uuid",
    created_at=datetime(...),
    witness_party="user-456",  # Required for waste
    seal_intact_before=True,
    seal_intact_after=True,
)
```

This entry is written to the Audit Service and becomes immutable. It cannot be
modified or deleted, only read for inspection.

### Usage in API Endpoints

```python
from core_app.integrations import NarcoticsIntegrationService


@router.post("/vials/{vial_id}/transfer")
async def transfer_vial(vial_id: str, req: TransferRequest, session: AsyncSession):
    vial = await NarcoticsService.transfer_vial(vial_id, req.to_unit_id)

    # Trigger integrations
    await NarcoticsIntegrationService.on_vial_transferred(
        tenant_id=req.tenant_id,
        from_unit_id=req.from_unit_id,
        to_unit_id=req.to_unit_id,
        substance_id=vial.substance_id,
        substance_name=vial.substance_name,
        vial_id=vial_id,
        quantity=vial.quantity,
        transferred_by=req.user_id,
    )

    # Create immutable ledger entry
    await NarcoticsIntegrationService.on_chain_of_custody_entry(
        tenant_id=req.tenant_id,
        unit_id=req.to_unit_id,
        substance_id=vial.substance_id,
        substance_name=vial.substance_name,
        vial_id=vial_id,
        lot_id=vial.lot_id,
        entry_type="TRANSFERRED",
        quantity_involved=vial.quantity,
        balance_before=old_balance,
        balance_after=new_balance,
        responsible_party=req.user_id,
        entry_id=str(uuid4()),
        created_at=datetime.now(timezone.utc),
    )

    return vial
```

## Configuration

All services are configured via environment variables:

### Notifications Service

```bash
NOTIFICATIONS_SERVICE_URL=http://notifications:8000
NOTIFICATIONS_SERVICE_TOKEN=<service-token>
NOTIFICATIONS_TIMEOUT_SECONDS=5
INVENTORY_ENABLE_NOTIFICATIONS=true
MEDICATIONS_ENABLE_NOTIFICATIONS=true
NARCOTICS_ENABLE_NOTIFICATIONS=true
```

### Search Service

None. `SEARCH_SERVICE_URL`, `SEARCH_SERVICE_TOKEN`, `SEARCH_TIMEOUT_SECONDS`, and
the per-service `*_ENABLE_SEARCH` flags were removed along with SearchClient. Do
not
set them — nothing reads them.

### Analytics Service

```bash
ANALYTICS_SERVICE_URL=http://analytics:8000
ANALYTICS_SERVICE_TOKEN=<service-token>
ANALYTICS_TIMEOUT_SECONDS=5
INVENTORY_ENABLE_ANALYTICS=true
MEDICATIONS_ENABLE_ANALYTICS=true
NARCOTICS_ENABLE_ANALYTICS=true
```

### Audit Service

```bash
AUDIT_SERVICE_URL=http://audit:8000
AUDIT_SERVICE_TOKEN=<service-token>
AUDIT_TIMEOUT_SECONDS=5
INVENTORY_ENABLE_AUDIT=true
MEDICATIONS_ENABLE_AUDIT=true
NARCOTICS_ENABLE_AUDIT=true
```

## Testing

### Unit Tests

Run integration tests:

```bash
pytest tests/test_supply_integrations.py -v
```

### Integration Tests

Create end-to-end test:

```python
import pytest
from uuid import uuid4
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_low_stock_alert_flow():
    """Test: stock adjustment → low-stock alert → notification."""
    tenant_id = uuid4()

    # 1. Create inventory item
    item = await create_inventory_item(
        tenant_id=tenant_id,
        item_name="Saline 0.9%",
        par_level=20,
    )

    # 2. Adjust stock below par
    await adjust_stock(item.id, -16)  # 20 → 4

    # 3. Verify notification was sent
    notifications = await get_notifications(tenant_id)
    assert len(notifications) > 0
    assert "Low Stock" in notifications[0].title

    # 4. Verify indexed in Search
    search_result = await search_inventory("Saline")
    assert search_result["current_stock"] == 4

    # 5. Verify Audit logged
    audit_entries = await get_audit_entries(tenant_id, "inventory_item", item.id)
    assert any(e.action == "stock_adjusted" for e in audit_entries)


@pytest.mark.asyncio
async def test_chain_of_custody_immutability():
    """Test: COC entries are immutable."""
    tenant_id = uuid4()

    # 1. Create vial
    vial = await create_narcotic_vial(...)

    # 2. Transfer vial (creates COC entry)
    coc_entry_id = await transfer_vial(...)

    # 3. Verify entry cannot be modified
    with pytest.raises(AuditError):
        await update_audit_entry(coc_entry_id, ...)

    # 4. Verify entry cannot be deleted
    with pytest.raises(AuditError):
        await delete_audit_entry(coc_entry_id)

    # 5. Verify entry can be read
    entry = await get_audit_entry(coc_entry_id)
    assert entry.action == "coc_transferred"
```

## Deployment

### Pre-Deployment Checklist

- [ ] All environment variables configured in AWS Secrets Manager
- [ ] Integration services are deployed and healthy
- [ ] Tests pass: `pytest tests/test_supply_integrations.py`
- [ ] Inventory Service deployed with `integrations.py`
- [ ] Medications Service deployed with `integrations.py`
- [ ] Narcotics Service deployed with `integrations.py`
- [ ] Audit Service is configured for immutability (COC entries)

### Deployment Steps

1. **Deploy Contracts Update**

   ```bash
   cd Adaptix-Contracts
   git checkout -b feature/supply-integrations
   git add adaptix_contracts/inventory_events.py \
            adaptix_contracts/medications_events.py \
            adaptix_contracts/narcotics_events.py \
            adaptix_contracts/supply_integrations.py
   git commit -m "feat(contracts): add supply domain integration contracts"
   git push origin feature/supply-integrations
   ```

2. **Deploy Inventory Service**

   ```bash
   cd Adaptix-Inventory-Service
   git checkout -b feature/notifications-integration
   git add backend/inventory_app/integrations.py
   git commit -m "feat(inventory): add notifications/search/analytics/audit integration"
   git push origin feature/notifications-integration
   ```

3. **Deploy Medications Service**

   ```bash
   cd Adaptix-Medications-Service
   git checkout -b feature/notifications-integration
   git add backend/medications/integrations.py
   git commit -m "feat(medications): add notifications/search/analytics/audit integration"
   git push origin feature/notifications-integration
   ```

4. **Deploy Narcotics Service**

   ```bash
   cd Adaptix-Narcotics-Service
   git checkout -b feature/notifications-integration
   git add backend/core_app/integrations.py
   git commit -m "feat(narcotics): add notifications/search/analytics/audit integration including immutable COC ledger"
   git push origin feature/notifications-integration
   ```

5. **Verify End-to-End**

   ```bash
   # Create test inventory item
   curl -X POST http://localhost:8000/api/v1/inventory/items \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "tenant_id": "...",
       "item_name": "Test Item",
       "par_level": 20,
       "category": "Test"
     }'
   
   # Adjust stock below par
   curl -X POST http://localhost:8000/api/v1/inventory/items/{id}/adjust \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"quantity": -25, "reason": "test"}'
   
   # Verify notification received
   # Verify Search index updated
   # Verify Audit log created
   ```

## Real Integrations

All integrations are **production-ready with real notifications, real search,
real analytics, and real audit trails**:

- **Notifications**: SMS/email/push via Notifications Service
- **Search**: Full-text search via Elasticsearch/OpenSearch
- **Analytics**: Real-time metrics and trends via Analytics Service
- **Audit**: Immutable ledger in Postgres/RDS with COC ledger for narcotics

Zero mocks anywhere in production. All data flows are real.
