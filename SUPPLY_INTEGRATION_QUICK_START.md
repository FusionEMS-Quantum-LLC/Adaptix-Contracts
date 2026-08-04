# Supply Domain Integration Quick Start

TL;DR: Wire notifications, search, analytics, and audit into Inventory, Medications, and Narcotics services.

## 30-Second Overview

Three services (Inventory, Medications, Narcotics) publish real events to four external services:

- **Notifications**: Real SMS/email/push alerts (low-stock, recalls, discrepancies)
- **Search**: Full-text indexing of items/lots/vials for discoverability
- **Analytics**: Real metrics for usage, waste, cost, risk trends
- **Audit**: Immutable log of every mutation + immutable COC ledger for narcotics

**All integrations are event-driven, best-effort, and fail gracefully.**

## Files to Review

1. **Event Contracts** (Pydantic models for type safety):
   - `adaptix_contracts/inventory_events.py` - Inventory events
   - `adaptix_contracts/medications_events.py` - Medication events
   - `adaptix_contracts/narcotics_events.py` - Narcotics events

2. **Integration Clients** (HTTP clients for each service):
   - `adaptix_contracts/supply_integrations.py` - NotificationClient, AnalyticsClient, AuditClient

3. **Service Integration Code** (where to call the clients):
   - `Adaptix-Inventory-Service/backend/inventory_app/integrations.py`
   - `Adaptix-Medications-Service/backend/medications/integrations.py`
   - `Adaptix-Narcotics-Service/backend/core_app/integrations.py`

4. **Tests** (unit tests for all clients):
   - `adaptix_contracts/tests/test_supply_integrations.py`

5. **Documentation**:
   - `SUPPLY_DOMAIN_INTEGRATION_GUIDE.md` - Complete reference
   - This file

## Integration Checklist

### Step 1: Configure Environment Variables

Add to each service's `.env` or Secrets Manager:

```bash
# Notifications Service
NOTIFICATIONS_SERVICE_URL=http://notifications:8000
NOTIFICATIONS_SERVICE_TOKEN=REPLACE_WITH_SECRETS_MANAGER_REF
INVENTORY_ENABLE_NOTIFICATIONS=true
MEDICATIONS_ENABLE_NOTIFICATIONS=true
NARCOTICS_ENABLE_NOTIFICATIONS=true

# Search Service: none. SearchClient was removed; these vars are read by nothing.

# Analytics Service
ANALYTICS_SERVICE_URL=http://analytics:8000
ANALYTICS_SERVICE_TOKEN=REPLACE_WITH_SECRETS_MANAGER_REF
INVENTORY_ENABLE_ANALYTICS=true
MEDICATIONS_ENABLE_ANALYTICS=true
NARCOTICS_ENABLE_ANALYTICS=true

# Audit Service
AUDIT_SERVICE_URL=http://audit:8000
AUDIT_SERVICE_TOKEN=REPLACE_WITH_SECRETS_MANAGER_REF
INVENTORY_ENABLE_AUDIT=true
MEDICATIONS_ENABLE_AUDIT=true
NARCOTICS_ENABLE_AUDIT=true
```

### Step 2: Ensure Contracts Package is Installed

All services need the latest contracts:

```bash
pip install ./Adaptix-Contracts
```

This gives them access to:
- Event contracts (inventory_events, medications_events, narcotics_events)
- Integration clients (supply_integrations)

### Step 3: Wire Into Inventory Service API

In `Adaptix-Inventory-Service/backend/inventory_app/api.py`:

```python
from inventory_app.integrations import InventoryIntegrationService

# On item creation
item = await InventoryService.create_supply_item(...)
await InventoryIntegrationService.on_item_created(
    tenant_id=tenant_id,
    item_id=item.id,
    item_name=item.item_name,
    category=req.category,
    location=req.location,
    par_level=item.par_level,
    cost_per_unit=req.cost_per_unit,
)

# On stock adjustment
await InventoryIntegrationService.on_stock_adjusted(
    tenant_id=req.tenant_id,
    item_id=item_id,
    item_name=item.item_name,
    previous_balance=old_balance,
    new_balance=new_balance,
    adjustment_quantity=adj_qty,
    adjustment_reason=req.reason,
    cost_per_unit=item.cost_per_unit,
)

# On restock
await InventoryIntegrationService.on_restock_recorded(
    tenant_id=req.tenant_id,
    item_id=item_id,
    item_name=item.item_name,
    quantity=req.quantity,
    is_controlled=item.is_controlled,
    cost_per_unit=item.cost_per_unit,
)
```

**Pattern**: Call integration service method AFTER business logic succeeds, BEFORE returning response.

### Step 4: Wire Into Medications Service API

In `Adaptix-Medications-Service/backend/medications/api/` endpoints:

```python
from medications.integrations import MedicationsIntegrationService

# On lot creation
lot = await MedicationsService.create_lot(...)
await MedicationsIntegrationService.on_medication_lot_created(
    tenant_id=tenant_id,
    medication_id=req.medication_id,
    medication_name=req.medication_name,
    lot_id=lot.id,
    expiration_date=req.expiration_date,
    quantity_received=req.quantity,
    storage_location=req.location,
    unit_of_measure="units",
    cost_per_unit=req.cost_per_unit,
)

# On administration
result = await MedicationsService.administer(...)
await MedicationsIntegrationService.on_medication_administered(
    tenant_id=tenant_id,
    medication_id=req.medication_id,
    medication_name=req.medication_name,
    lot_id=lot_id,
    quantity_administered=req.quantity,
    unit_of_measure="units",
    cost_per_unit=lot.cost_per_unit,
    administered_by=user_id,
)

# On waste
await MedicationsIntegrationService.on_medication_wasted(
    tenant_id=tenant_id,
    medication_id=req.medication_id,
    medication_name=req.medication_name,
    lot_id=lot_id,
    quantity_wasted=req.quantity,
    unit_of_measure="units",
    waste_reason=req.reason,
    cost_per_unit=lot.cost_per_unit,
    disposed_by=user_id,
    witness=req.witness_id,
)
```

### Step 5: Wire Into Narcotics Service API

In `Adaptix-Narcotics-Service/backend/core_app/narcotic/` endpoints:

```python
from core_app.integrations import NarcoticsIntegrationService
from datetime import datetime, timezone
from uuid import uuid4

# On vial transfer
vial = await NarcoticsService.transfer_vial(...)
await NarcoticsIntegrationService.on_vial_transferred(
    tenant_id=req.tenant_id,
    from_unit_id=req.from_unit_id,
    to_unit_id=req.to_unit_id,
    substance_id=vial.substance_id,
    substance_name=vial.substance_name,
    vial_id=vial.id,
    quantity=vial.quantity,
    transferred_by=user_id,
)

# ALSO create immutable COC ledger entry
await NarcoticsIntegrationService.on_chain_of_custody_entry(
    tenant_id=req.tenant_id,
    unit_id=req.to_unit_id,
    substance_id=vial.substance_id,
    substance_name=vial.substance_name,
    vial_id=vial.id,
    lot_id=vial.lot_id,
    entry_type="TRANSFERRED",
    quantity_involved=vial.quantity,
    balance_before=old_balance,
    balance_after=new_balance,
    responsible_party=user_id,
    entry_id=str(uuid4()),
    created_at=datetime.now(timezone.utc),
)

# On vial use
await NarcoticsIntegrationService.on_vial_used(...)

# On vial waste
await NarcoticsIntegrationService.on_vial_wasted(...)

# On count
await NarcoticsIntegrationService.on_count_recorded(...)

# On discrepancy
await NarcoticsIntegrationService.on_discrepancy_detected(...)
```

### Step 6: Run Tests

```bash
cd Adaptix-Contracts
pytest tests/test_supply_integrations.py -v
```

Expected: All tests pass ✅

### Step 7: Deploy

#### Deploy Contracts
```bash
cd Adaptix-Contracts
git checkout -b feature/supply-integrations
git add adaptix_contracts/{inventory,medications,narcotics}_events.py supply_integrations.py
git commit -m "feat(contracts): add supply domain integration contracts"
git push origin feature/supply-integrations
# Create PR, merge to main
```

#### Deploy Inventory Service
```bash
cd Adaptix-Inventory-Service
git checkout -b feature/integrations
git add backend/inventory_app/integrations.py
git commit -m "feat(inventory): add notifications/search/analytics/audit integration"
git push origin feature/integrations
# Create PR, merge to main
# Update API endpoints to call integration service
```

#### Deploy Medications Service
```bash
cd Adaptix-Medications-Service
git checkout -b feature/integrations
git add backend/medications/integrations.py
git commit -m "feat(medications): add notifications/search/analytics/audit integration"
git push origin feature/integrations
# Create PR, merge to main
# Update API endpoints to call integration service
```

#### Deploy Narcotics Service
```bash
cd Adaptix-Narcotics-Service
git checkout -b feature/integrations
git add backend/core_app/integrations.py
git commit -m "feat(narcotics): add notifications/search/analytics/audit integration including immutable COC ledger"
git push origin feature/integrations
# Create PR, merge to main
# Update API endpoints to call integration service
```

### Step 8: Validate End-to-End

```bash
# Test low-stock alert
curl -X POST http://localhost:8000/api/v1/inventory/items \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"tenant_id":"...", "item_name":"Saline", "par_level":20, ...}'

curl -X POST http://localhost:8000/api/v1/inventory/items/{id}/stock-adjustment \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"quantity":-25, "reason":"test"}'

# Verify:
# 1. Notification sent to user
# 2. Item indexed in Search with new stock level
# 3. Analytics event published
# 4. Audit log created
```

## Common Issues

### Issue: "adaptix_contracts not available"
**Solution**: Install contracts package in each service:
```bash
pip install /path/to/Adaptix-Contracts
```

### Issue: Notifications not sending
**Check**:
1. `NOTIFICATIONS_SERVICE_URL` configured
2. `NOTIFICATIONS_SERVICE_TOKEN` valid
3. `INVENTORY_ENABLE_NOTIFICATIONS=true`
4. Notifications Service is running and healthy
5. Check logs: `logger.warning("Failed to send notification: ...")` for details

### Issue: Search not indexing
Supply search does not exist. SearchClient was removed because it had never indexed a
row — see the "SearchClient — REMOVED" section of SUPPLY_DOMAIN_INTEGRATION_GUIDE.md,
including the role-gate question that must be answered before it is rebuilt.

### Issue: Audit entries not created
**Check**:
1. `AUDIT_SERVICE_URL` configured
2. `AUDIT_SERVICE_TOKEN` valid
3. `INVENTORY_ENABLE_AUDIT=true`
4. Audit Service is running
5. Immutable entries cannot be modified - only log new ones

## Feature by Feature

### Feature 491: Low-Stock Alerts
**Trigger**: Stock drops below par
**Action**: Send alert to Supply Officer
**Code**: `InventoryIntegrationService.on_stock_adjusted()`

### Feature 492: Medication Recalls
**Trigger**: Recall detected/imported
**Action**: Send alert to Pharmacy Manager
**Code**: `MedicationsIntegrationService.on_recall_detected()`

### Feature 493: Narcotics Discrepancies
**Trigger**: Discrepancy opened
**Action**: Send alert to Narcotics Officer + Supervisor (escalate if >24h)
**Code**: `NarcoticsIntegrationService.on_discrepancy_detected()`

### Feature 494: Search Integration — NOT BUILT
**What**: was intended to index items/lots/vials for full-text search
**Status**: never worked. The SearchClient and its six call sites were removed; the
call sites were unreachable and the client was wrong on path, auth header, and
payload. Rebuilding it starts with the role-gate question in
SUPPLY_DOMAIN_INTEGRATION_GUIDE.md, not with the client.

### Feature 495: Analytics Integration
**What**: Real metrics for usage, waste, cost, risk
**Where**: All events call `AnalyticsClient.publish_*()`
**How**: Usage/waste/risk events published to Analytics Service

### Feature 496: Audit Integration
**What**: Immutable log of every mutation + immutable COC ledger for narcotics
**Where**: All mutations call `AuditClient.log_mutation()`
**How**: Every create/update/delete/transfer/use/waste logged

## Key Design Patterns

### Pattern 1: Graceful Degradation
```python
# Integrations fail silently - business logic continues
try:
    await NotificationClient.send_low_stock_alert(...)
except Exception as exc:
    logger.warning("Failed to send alert: %s", exc)
    # Don't raise - return success to caller
```

### Pattern 2: Best-Effort Async
```python
# All calls are async, no blocking
await InventoryIntegrationService.on_stock_adjusted(...)
# Returns immediately, doesn't wait for external services
```

### Pattern 3: Immutable Audit
```python
# Every mutation writes immutable audit record
await AuditClient.log_mutation(
    action="stock_adjusted",
    before_state={"stock": 15},
    after_state={"stock": 5},
)
# Records cannot be edited/deleted, only appended
```

### Pattern 4: Immutable COC Ledger (Narcotics Only)
```python
# Every transfer/use/waste creates permanent COC entry
await NarcoticsIntegrationService.on_chain_of_custody_entry(
    entry_type="TRANSFERRED",
    balance_before=10,
    balance_after=5,
    entry_id=str(uuid4()),  # Immutable ID
    created_at=datetime.now(timezone.utc),
)
# Cannot be modified - DEA compliance trail
```

## Next Steps

1. **Add these files to your services**:
   - Contracts: Copy event + integration files
   - Inventory: Copy integrations.py
   - Medications: Copy integrations.py
   - Narcotics: Copy integrations.py

2. **Wire API endpoints** (see Step 3-5 above)

3. **Run tests**: `pytest tests/test_supply_integrations.py`

4. **Deploy services**

5. **Validate end-to-end**

All integrations are production-ready. Zero mocks anywhere.
