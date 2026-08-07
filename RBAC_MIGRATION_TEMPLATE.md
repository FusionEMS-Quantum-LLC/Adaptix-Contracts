# RBAC Migration Template for Services

This template shows how to add complete auth/RBAC/entitlement wiring to any
service (Inventory, Medications, or Narcotics).

## Phase 1: Contracts Integration (15 min)

### 1.1 Copy RBAC Contracts

```bash
# In service repository root:
cp ../Adaptix-Contracts/adaptix_contracts/rbac_contracts.py ./backend/
cp ../Adaptix-Contracts/adaptix_contracts/core_service_integration.py ./backend/
cp -r ../Adaptix-Contracts/adaptix_contracts/auth ./backend/auth_contracts/
```

### 1.2 Update service pyproject.toml

```toml
[project]
dependencies = [
    "adaptix_contracts>=0.1.0",  # Add this
    "httpx>=0.25.0",             # For Core Service client
    "python-jose>=3.3.0",
    "fastapi>=0.104.0",
    ...
]
```

---

## Phase 2: Auth Dependencies (30 min)

### 2.1 Enhance `auth/dependencies.py`

Replace the simple role check with permission computation:

```python
# BEFORE
async def require_founder(auth=Depends(require_auth)):
    if "founder" not in extract_roles(auth):
        raise HTTPException(status_code=403)
    return auth


# AFTER
from adaptix_contracts.rbac_contracts import compute_inventory_permissions


async def require_inventory_permission(permission: str) -> Callable:
    """Check if user has a specific inventory permission."""

    async def dependency(auth=Depends(require_auth)):
        roles = extract_roles(auth)
        permissions = compute_inventory_permissions(roles)
        if permission not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission}",
            )
        return auth

    return Depends(dependency)
```

### 2.2 Add Tenant Isolation Verification

```python
async def verify_tenant_isolation(
    requested_tenant_id: str,
    auth=Depends(require_tenant),
) -> None:
    """Verify user's tenant matches requested tenant."""
    if auth.tenant_id != requested_tenant_id:
        logger.error(
            f"Tenant isolation violation: user={auth.user_id} "
            f"auth_tenant={auth.tenant_id} requested={requested_tenant_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this tenant",
        )
```

---

## Phase 3: Route Decoration (1-2 hours per service)

### 3.1 Example: Inventory Service Routes

**Pattern**: Add permission dependency + tenant filter to EVERY route

```python
# LIST ROUTE: Read permission
@router.get("/items")
async def list_items(
    rbac=Depends(require_inventory_permission("inventory:read_items")),
    auth=Depends(require_tenant),
    session: AsyncSession = Depends(get_session),
):
    """List items for tenant."""
    tenant_id = auth.tenant_id
    q = select(SupplyItem).where(
        SupplyItem.tenant_id == tenant_id,  # ← CRITICAL
        SupplyItem.deleted_at.is_(None),
    )
    rows = (await session.execute(q)).scalars().all()
    return {"tenant_id": tenant_id, "items": [...]}


# CREATE ROUTE: Write permission
@router.post("/items", status_code=201)
async def create_item(
    body: CreateItemBody,
    rbac=Depends(require_inventory_permission("inventory:create_items")),
    auth=Depends(require_tenant),
    session: AsyncSession = Depends(get_session),
):
    """Create new item (Supply Officer+)."""
    item = SupplyItem(
        id=str(uuid.uuid4()),
        tenant_id=auth.tenant_id,  # ← From auth, never from request
        name=body.name,
        ...
    )
    session.add(item)
    await session.commit()
    return _item_to_dict(item)


# UPDATE ROUTE: Write permission + tenant check
@router.patch("/items/{item_id}")
async def update_item(
    item_id: str,
    body: UpdateItemBody,
    rbac=Depends(require_inventory_permission("inventory:update_items")),
    auth=Depends(require_tenant),
    session: AsyncSession = Depends(get_session),
):
    """Update item."""
    # ALWAYS verify tenant context on retrieval
    item = await session.get(
        SupplyItem,
        item_id,
    )
    if not item or item.tenant_id != auth.tenant_id:  # ← CRITICAL
        raise HTTPException(status_code=404)
    
    # Apply updates
    if body.name:
        item.name = body.name
    ...
    
    await session.commit()
    return _item_to_dict(item)


# DELETE ROUTE: Admin-only permission
@router.delete("/items/{item_id}")
async def delete_item(
    item_id: str,
    rbac=Depends(require_inventory_permission("inventory:delete_items")),
    auth=Depends(require_tenant),
    session: AsyncSession = Depends(get_session),
):
    """Delete item (Admin/Founder only)."""
    item = await session.get(SupplyItem, item_id)
    if not item or item.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404)
    
    item.deleted_at = datetime.now(UTC)
    await session.commit()
    return {"deleted": True}


# CROSS-TENANT ROUTE (Founder only)
@router.get("/founder/health")
async def founder_inventory_health(
    rbac=Depends(require_inventory_permission("inventory:full_access")),  # Founder only
    auth=Depends(require_founder),  # Extra founder check
    session: AsyncSession = Depends(get_session),
):
    """Cross-tenant health summary (Founder only)."""
    # NO tenant_id filter here — intended to be cross-tenant
    ...
```

### 3.2 Route Coverage Checklist

For each route, add:

```python
# READ routes
@router.get("/{resource_id}")
async def get_resource(
    resource_id: str,
    rbac=Depends(require_XXXX_permission("XXXX:read")),
    auth=Depends(require_tenant),
    ...
):
    # Include tenant filter
    obj = await session.get(Model, resource_id)
    if not obj or obj.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404)
    return obj


# WRITE routes (POST)
@router.post("/")
async def create_resource(
    body: CreateBody,
    rbac=Depends(require_XXXX_permission("XXXX:create")),
    auth=Depends(require_tenant),
    ...
):
    # Use auth.tenant_id, never from request
    obj = Model(
        id=str(uuid.uuid4()),
        tenant_id=auth.tenant_id,  # ← From auth
        ...
    )
    session.add(obj)
    await session.commit()
    return obj


# WRITE routes (PATCH/PUT)
@router.patch("/{resource_id}")
async def update_resource(
    resource_id: str,
    body: UpdateBody,
    rbac=Depends(require_XXXX_permission("XXXX:update")),
    auth=Depends(require_tenant),
    ...
):
    obj = await session.get(Model, resource_id)
    if not obj or obj.tenant_id != auth.tenant_id:  # ← Tenant check
        raise HTTPException(status_code=404)
    
    # Apply updates
    if body.field:
        obj.field = body.field
    ...
    
    await session.commit()
    return obj


# WRITE routes (DELETE)
@router.delete("/{resource_id}")
async def delete_resource(
    resource_id: str,
    rbac=Depends(require_XXXX_permission("XXXX:delete")),
    auth=Depends(require_tenant),
    ...
):
    obj = await session.get(Model, resource_id)
    if not obj or obj.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404)
    
    obj.deleted_at = datetime.now(UTC)
    await session.commit()
    return {"deleted": True}
```

---

## Phase 4: Entitlement Checks (15 min)

### 4.1 Add to main.py

```python
from adaptix_contracts.core_service_integration import (
    init_core_service_client,
    close_core_service_client,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Service starting...")
    await init_db()
    await init_core_service_client()  # ← Add this
    logger.info("Service ready")

    yield

    # Shutdown
    await close_core_service_client()  # ← Add this
    logger.info("Service shut down")
```

### 4.2 Add Module Entitlement Check (if needed)

```python
async def require_module_entitlement(
    module: str,
    auth=Depends(require_tenant),
):
    """Verify tenant has purchased module."""
    if module not in auth.tenant_context.modules_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Module not enabled: {module}"
        )
    return auth

# Use in routes:
@router.get("/items")
async def list_items(
    _=Depends(require_module_entitlement("inventory")),
    rbac=Depends(...),
    ...
):
    ...
```

---

## Phase 5: Billing Access Gates (15 min)

### 5.1 Create Billing Access Dependency

```python
async def require_billing_access(
    auth=Depends(require_tenant),
):
    """Verify user has billing access (cost reports)."""
    allowed_roles = {"founder", "agency_admin", "billing_operator"}

    roles = extract_roles(auth)
    if not any(r in allowed_roles for r in roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Billing access requires Billing Operator, Admin, or Founder role",
        )
    return auth
```

### 5.2 Apply to Cost Report Routes

```python
@router.get("/cost-reports")
async def get_cost_reports(
    _=Depends(require_billing_access),  # ← Add this gate
    rbac=Depends(require_inventory_permission("inventory:read_cost_reports")),
    auth=Depends(require_tenant),
    session: AsyncSession = Depends(get_session),
):
    """Cost reports (Billing only)."""
    ...


@router.get("/cost-attribution")
async def get_cost_attribution(
    _=Depends(require_billing_access),  # ← Add this gate
    rbac=Depends(require_narcotics_permission("narcotics:read_cost_attribution")),
    auth=Depends(require_tenant),
    session: AsyncSession = Depends(get_session),
):
    """Cost attribution per dosage (Billing only)."""
    ...
```

---

## Phase 6: Testing (1-2 hours)

### 6.1 Copy Test Suite

```bash
cp Adaptix-Inventory-Service/backend/tests/test_cross_tenant_isolation.py \
   ./backend/tests/
```

### 6.2 Adapt Test Fixtures

Update fixtures to match your service's models:

```python
# For Medications
@pytest.fixture
async def medication_a(tenant_a_id: str, db_session: AsyncSession):
    med = Medication(
        id=str(uuid.uuid4()),
        tenant_id=tenant_a_id,
        name="Aspirin 500mg",
        ...
    )
    db_session.add(med)
    await db_session.commit()
    return med

# For Narcotics
@pytest.fixture
async def narcotic_a(tenant_a_id: str, db_session: AsyncSession):
    narc = NarcoticItem(
        id=str(uuid.uuid4()),
        tenant_id=tenant_a_id,
        name="Morphine 100mg",
        dea_schedule="II",
        ...
    )
    db_session.add(narc)
    await db_session.commit()
    return narc
```

### 6.3 Run Tests

```bash
# Run isolation tests
pytest tests/test_cross_tenant_isolation.py -v

# Run all tests
pytest tests/ -v

# Check coverage
pytest tests/ --cov=service_app --cov-report=term-missing
```

---

## Phase 7: Validation Checklist

Before creating PR:

- [ ] All `get` routes have permission dependency
- [ ] All `post` routes have permission dependency  
- [ ] All `patch` routes have permission dependency
- [ ] All `put` routes have permission dependency
- [ ] All `delete` routes have permission dependency
- [ ] Every SELECT query includes `Model.tenant_id == auth.tenant_id`
- [ ] Every GET-by-ID includes tenant check:
  `or obj.tenant_id != auth.tenant_id: raise 404`
- [ ] Soft-delete queries exclude deleted: `.where(Model.deleted_at.is_(None))`
- [ ] Cost reports gated to `require_billing_access`
- [ ] Cross-tenant routes use explicit Founder check
- [ ] All `create` operations use `auth.tenant_id`, never from request
- [ ] Audit logs written with `actor_user_id`, `tenant_id`
- [ ] Cross-tenant isolation tests all pass
- [ ] No linting/typing warnings
- [ ] CI builds successfully

---

## Phase 8: PR Creation

Create PR with title:

```text
feat(auth): add complete RBAC and tenant isolation for [service]

- Add RBAC permission matrix for 13+ roles
- Implement tenant isolation on all routes (100% coverage)
- Add module entitlement checks
- Add billing access gates on cost reports
- Add comprehensive cross-tenant isolation tests
- All routes return 404 for cross-tenant access attempts
```

And description:

```markdown
## Summary
This PR implements complete authentication, authorization, and tenant isolation 
for [service] per Adaptix governance rules.

## Changes
- [ ] RBAC decorators on all routes
- [ ] Tenant filters on all queries
- [ ] Billing gates on cost reports
- [ ] Cross-tenant isolation tests
- [ ] Zero cross-tenant data leaks

## Test Coverage
- All 47 isolation tests passing
- No linting warnings
- CI green

## Deployment Notes
- Requires Core Service JWT key in Secrets Manager
- No breaking changes
- Backward compatible with existing data
```

---

## Debugging Guide

### "Permission denied" on valid user

**Cause**: Role not in permission matrix
**Fix**: Add role to permission dict in `rbac_contracts.py`

```python
"inventory:read_items": {"roles": [
    InventoryRole.FOUNDER,
    InventoryRole.AGENCY_ADMIN,
    InventoryRole.YOUR_NEW_ROLE,  # ← Add here
    ...
]}
```

### "Item not found" for valid item

**Cause**: Tenant filter missing from query
**Fix**: Add `.where(Model.tenant_id == auth.tenant_id)` to SELECT

### "tenant_isolation_violation" error

**Cause**: User trying to access different tenant's data (security feature)
**Fix**: Verify auth context tenant_id matches resource

---

## Rollback Plan

If issues discovered in production:

```bash
# 1. Identify affected routes
grep -r "require_.*_permission" backend/ | grep -v "\.pyc"

# 2. Temporarily disable RBAC (revert to simple require_auth)
# Edit auth/dependencies.py

# 3. Deploy hotfix
git checkout main  # Go back
git apply patch.diff
git push origin hotfix-auth

# 4. Root cause analysis in follow-up PR
```

---

## References

- Contracts: `adaptix_contracts/rbac_contracts.py`
- Integration: `adaptix_contracts/core_service_integration.py`
- Auth: `adaptix_contracts/auth/context.py`
- Integration Doc: `INVENTORY_MEDICATIONS_NARCOTICS_INTEGRATION.md`
