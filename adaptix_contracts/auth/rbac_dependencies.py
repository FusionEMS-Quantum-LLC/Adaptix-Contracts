"""DEPRECATED — do not adopt. Scheduled for removal in adaptix-contracts 2.0.0.

RBAC Auth Dependencies (legacy, unused)
=======================================
Audit 2026-07-03: no service in the Adaptix polyrepo imports this module, and
it must not be adopted as-is because:

1. ``auth: AdaptixAuthContext = Depends()`` makes FastAPI construct the auth
   model from REQUEST DATA (query parameters), not from any verified
   dependency — an attacker-controllable identity source.
2. ``require_module_entitlement`` here conflicts with the real, enforced gate
   in ``adaptix_contracts.auth.module_entitlement_gate`` (the 402 gate that
   verifies the gateway-signed context).
3. ``rbac_decorator`` is a no-op marker that enforces nothing.

Replacement path (see CHANGELOG and README "Canonical auth surfaces"):
* Service-edge identity: ``adaptix_contracts.auth_contracts.get_auth_context``
  (gateway header contract + HMAC-signed context verification).
* Module entitlement: ``adaptix_contracts.auth.module_entitlement_gate``.
* Role/permission checks: service-side logic over the verified AuthContext.

Per DEPRECATION_POLICY.md the import path is preserved (with a
DeprecationWarning) until the next major version.
"""

from __future__ import annotations

import logging
import warnings
from functools import wraps

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer

from adaptix_contracts.auth.context import AdaptixAuthContext
from adaptix_contracts.rbac_contracts import (
    RBACContext,
    compute_inventory_permissions,
    compute_medications_permissions,
    compute_narcotics_permissions,
)

warnings.warn(
    "adaptix_contracts.auth.rbac_dependencies is deprecated and will be removed "
    "in adaptix-contracts 2.0.0. Use auth_contracts.get_auth_context + "
    "auth.module_entitlement_gate instead (see module docstring).",
    DeprecationWarning,
    stacklevel=2,
)

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


async def require_permission(
    permission: str,
    permission_computer: Callable[[list[str]], set],
    auth: AdaptixAuthContext = Depends(),
) -> RBACContext:
    """
    Dependency factory for enforcing a specific permission.

    Args:
        permission: Permission string to check (e.g., "inventory:read_items")
        permission_computer: Function to compute all permissions from roles
        auth: Verified auth context (from auth dependencies)

    Returns:
        RBACContext with verified permissions

    Raises:
        HTTPException 403: If user lacks the permission
    """
    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "unauthorized", "message": "Authentication required"},
        )

    # Compute all permissions for this user from their roles
    roles = [str(r) for r in auth.role_set.roles] if auth.role_set else []
    permissions = permission_computer(roles)

    # Create RBAC context
    rbac_context = RBACContext(
        user_id=auth.user_id,
        tenant_id=auth.tenant_id,
        roles=roles,
        permissions=permissions,
        modules_enabled=auth.tenant_context.modules_enabled,
    )

    # Check permission
    if not rbac_context.has_permission(permission):
        logger.warning(
            f"Permission denied: user={auth.user_id} permission={permission} roles={roles}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "insufficient_permission",
                "message": f"Permission denied: {permission}",
                "required_permission": permission,
            },
        )

    return rbac_context


def require_inventory_permission(permission: str):
    """
    Decorator factory for enforcing Inventory module permissions.

    Usage:
        @router.get("/items")
        async def list_items(
            rbac=Depends(require_inventory_permission("inventory:read_items")),
            ...
        ):
            ...
    """

    async def dependency(
        auth: AdaptixAuthContext = Depends(),
    ) -> RBACContext:
        return await require_permission(permission, compute_inventory_permissions, auth)

    return Depends(dependency)


def require_medications_permission(permission: str):
    """
    Decorator factory for enforcing Medications module permissions.

    Usage:
        @router.get("/medications")
        async def list_medications(
            rbac=Depends(require_medications_permission("medications:read")),
            ...
        ):
            ...
    """

    async def dependency(
        auth: AdaptixAuthContext = Depends(),
    ) -> RBACContext:
        return await require_permission(
            permission, compute_medications_permissions, auth
        )

    return Depends(dependency)


def require_narcotics_permission(permission: str):
    """
    Decorator factory for enforcing Narcotics module permissions.

    Usage:
        @router.get("/narcotics")
        async def list_narcotics(
            rbac=Depends(require_narcotics_permission("narcotics:read")),
            ...
        ):
            ...
    """

    async def dependency(
        auth: AdaptixAuthContext = Depends(),
    ) -> RBACContext:
        return await require_permission(permission, compute_narcotics_permissions, auth)

    return Depends(dependency)


async def require_module_entitlement(
    module: str,
    auth: AdaptixAuthContext = Depends(),
) -> RBACContext:
    """
    Verify tenant has purchased a module before allowing access.

    Args:
        module: Module name (e.g., "inventory", "medications", "narcotics")
        auth: Verified auth context

    Returns:
        RBACContext with verified entitlement

    Raises:
        HTTPException 403: If tenant lacks module entitlement
    """
    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "unauthorized", "message": "Authentication required"},
        )

    if not auth.tenant_context.has_module(module):
        logger.warning(
            f"Module entitlement denied: tenant={auth.tenant_id} module={module}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "module_not_entitled",
                "message": f"Module not enabled: {module}",
                "module": module,
            },
        )

    roles = [str(r) for r in auth.role_set.roles] if auth.role_set else []
    return RBACContext(
        user_id=auth.user_id,
        tenant_id=auth.tenant_id,
        roles=roles,
        modules_enabled=auth.tenant_context.modules_enabled,
    )


async def require_billing_access(
    auth: AdaptixAuthContext = Depends(),
) -> RBACContext:
    """
    Verify user has billing access (cost reports, attribution, etc).

    Only Founder, Agency Admin, and Billing Operator roles can access.

    Args:
        auth: Verified auth context

    Returns:
        RBACContext

    Raises:
        HTTPException 403: If user lacks billing access
    """
    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "unauthorized", "message": "Authentication required"},
        )

    # Check for billing-authorized roles
    allowed_roles = {"founder", "agency_admin", "billing_operator"}
    user_roles = {str(r) for r in auth.role_set.roles} if auth.role_set else set()

    if not user_roles.intersection(allowed_roles):
        logger.warning(f"Billing access denied: user={auth.user_id} roles={user_roles}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "billing_access_denied",
                "message": "Billing access requires Founder, Agency Admin, or Billing Operator role",
            },
        )

    return RBACContext(
        user_id=auth.user_id,
        tenant_id=auth.tenant_id,
        roles=list(user_roles),
        modules_enabled=auth.tenant_context.modules_enabled,
    )


async def verify_tenant_isolation(
    tenant_id: str,
    auth: AdaptixAuthContext = Depends(),
) -> None:
    """
    Verify user's auth context matches the requested tenant_id.

    This prevents cross-tenant data access even if URL is manipulated.

    Args:
        tenant_id: Requested tenant UUID
        auth: Verified auth context

    Raises:
        HTTPException 403: If tenant_id mismatch
    """
    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "unauthorized", "message": "Authentication required"},
        )

    if auth.tenant_id != tenant_id:
        logger.error(
            f"Tenant isolation violation: user={auth.user_id} "
            f"auth_tenant={auth.tenant_id} requested_tenant={tenant_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "tenant_mismatch",
                "message": "You do not have access to this tenant",
            },
        )


def rbac_decorator(
    permission: str,
    module: str = "inventory",
):
    """
    Decorator for route-level RBAC enforcement.

    Usage:
        @router.get("/items")
        @rbac_decorator("inventory:read_items", module="inventory")
        async def list_items(rbac: RBACContext, ...):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # rbac dependency will be injected by FastAPI
            # This decorator just marks the route as RBAC-protected
            return await func(*args, **kwargs)

        return wrapper

    return decorator
