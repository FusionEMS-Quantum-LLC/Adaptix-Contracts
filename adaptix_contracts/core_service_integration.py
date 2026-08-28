"""
Core Service Integration
========================
Middleware and utilities for integrating with Adaptix-Core-Service for auth,
RBAC, tenant resolution, and entitlement checks.

All Inventory/Medications/Narcotics services must use these utilities to
verify tenant isolation and enforce role-based access control.
"""

from __future__ import annotations

import logging
import os
from typing import Any
from datetime import datetime, timedelta, timezone
import httpx

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CoreServiceConfig(BaseModel):
    """Configuration for Core Service integration."""

    base_url: str = Field(
        ..., description="Core Service base URL (e.g., https://core.adaptixcore.com)"
    )
    api_key: str | None = None
    timeout_seconds: int = 10
    cache_ttl_seconds: int = 300


class TenantLookupRequest(BaseModel):
    """Request to Core Service for tenant lookup."""

    tenant_slug: str


class TenantLookupResponse(BaseModel):
    """Response from Core Service tenant lookup."""

    tenant_id: str
    tenant_slug: str
    agency_name: str
    agency_slug: str
    is_active: bool
    modules_enabled: list[str] = Field(default_factory=list)


class RBACVerifyRequest(BaseModel):
    """Request to Core Service for RBAC verification."""

    user_id: str
    tenant_id: str
    permission: str


class RBACVerifyResponse(BaseModel):
    """Response from Core Service RBAC verification."""

    has_permission: bool
    reason: str | None = None


class EntitlementCheckRequest(BaseModel):
    """Request to Core Service for entitlement check."""

    tenant_id: str
    module: str


class EntitlementCheckResponse(BaseModel):
    """Response from Core Service entitlement check."""

    has_entitlement: bool
    module: str
    reason: str | None = None


class CoreServiceClient:
    """
    Client for Core Service API integration.

    Caches responses to reduce load on Core Service.
    All calls require valid authentication from verified JWT.
    """

    def __init__(self, config: CoreServiceConfig):
        self.config = config
        self._client = httpx.AsyncClient(timeout=config.timeout_seconds)
        self._cache: dict[str, tuple] = {}  # (response, expiration_time)

    async def close(self):
        """Close HTTP client."""
        await self._client.aclose()

    def _get_cached(self, key: str) -> Any | None:
        """Get cached value if not expired."""
        if key in self._cache:
            value, expiration = self._cache[key]
            if datetime.now(timezone.utc) < expiration:
                logger.debug(f"Cache hit: {key}")
                return value
            else:
                del self._cache[key]
        return None

    def _set_cached(self, key: str, value: Any) -> None:
        """Cache value with TTL."""
        expiration = datetime.now(timezone.utc) + timedelta(
            seconds=self.config.cache_ttl_seconds
        )
        self._cache[key] = (value, expiration)

    async def lookup_tenant(self, tenant_slug: str) -> TenantLookupResponse:
        """
        Resolve tenant_slug to tenant_id via Core Service.

        Args:
            tenant_slug: Agency slug (e.g., "my-agency")

        Returns:
            TenantLookupResponse with tenant_id, modules_enabled, etc.

        Raises:
            httpx.HTTPError: If Core Service is unreachable.
            ValueError: If tenant not found.
        """
        cache_key = f"tenant_lookup:{tenant_slug}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        url = f"{self.config.base_url}/api/v1/core/tenant/lookup"
        req = TenantLookupRequest(tenant_slug=tenant_slug)

        headers = self._build_headers()
        try:
            resp = await self._client.post(url, json=req.dict(), headers=headers)
            resp.raise_for_status()
            result = TenantLookupResponse(**resp.json())
            self._set_cached(cache_key, result)
            logger.info(f"Tenant lookup: slug={tenant_slug} → id={result.tenant_id}")
            return result
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Tenant not found: {tenant_slug}") from e
            raise
        except Exception as e:
            logger.error(f"Tenant lookup failed: {tenant_slug} - {e}")
            raise

    async def verify_rbac(
        self,
        user_id: str,
        tenant_id: str,
        permission: str,
    ) -> RBACVerifyResponse:
        """
        Verify RBAC permission via Core Service.

        Args:
            user_id: User UUID
            tenant_id: Tenant UUID
            permission: Permission string (e.g., "inventory:read_items")

        Returns:
            RBACVerifyResponse with has_permission flag.

        Raises:
            httpx.HTTPError: If Core Service is unreachable.
        """
        cache_key = f"rbac:{user_id}:{tenant_id}:{permission}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        url = f"{self.config.base_url}/api/v1/core/rbac/verify"
        req = RBACVerifyRequest(
            user_id=user_id, tenant_id=tenant_id, permission=permission
        )

        headers = self._build_headers()
        try:
            resp = await self._client.post(url, json=req.dict(), headers=headers)
            resp.raise_for_status()
            result = RBACVerifyResponse(**resp.json())
            self._set_cached(cache_key, result)
            logger.debug(
                f"RBAC check: user={user_id} permission={permission} → {result.has_permission}"
            )
            return result
        except Exception as e:
            logger.error(f"RBAC verification failed: {permission} - {e}")
            raise

    async def check_entitlement(
        self,
        tenant_id: str,
        module: str,
    ) -> EntitlementCheckResponse:
        """
        Check if tenant has purchased a module via Core Service.

        Args:
            tenant_id: Tenant UUID
            module: Module name (e.g., "inventory", "medications", "narcotics")

        Returns:
            EntitlementCheckResponse with has_entitlement flag.

        Raises:
            httpx.HTTPError: If Core Service is unreachable.
        """
        cache_key = f"entitlement:{tenant_id}:{module}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        url = f"{self.config.base_url}/api/v1/core/entitlements/check"
        req = EntitlementCheckRequest(tenant_id=tenant_id, module=module)

        headers = self._build_headers()
        try:
            resp = await self._client.post(url, json=req.dict(), headers=headers)
            resp.raise_for_status()
            result = EntitlementCheckResponse(**resp.json())
            self._set_cached(cache_key, result)
            logger.info(
                f"Entitlement check: tenant={tenant_id} module={module} → {result.has_entitlement}"
            )
            return result
        except Exception as e:
            logger.error(f"Entitlement check failed: {module} - {e}")
            raise

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers with API key if configured."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Adaptix-Service-Client/1.0",
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers


def get_core_service_config() -> CoreServiceConfig:
    """Load Core Service configuration from environment."""
    base_url = os.environ.get("CORE_SERVICE_URL", "https://core.adaptixcore.com")
    api_key = os.environ.get("CORE_SERVICE_API_KEY")
    timeout = int(os.environ.get("CORE_SERVICE_TIMEOUT_SECONDS", "10"))
    cache_ttl = int(os.environ.get("CORE_SERVICE_CACHE_TTL_SECONDS", "300"))

    return CoreServiceConfig(
        base_url=base_url,
        api_key=api_key,
        timeout_seconds=timeout,
        cache_ttl_seconds=cache_ttl,
    )


# Global client instance (will be initialized on app startup)
_core_service_client: CoreServiceClient | None = None


async def init_core_service_client():
    """Initialize global Core Service client."""
    global _core_service_client
    config = get_core_service_config()
    _core_service_client = CoreServiceClient(config)
    logger.info(f"Core Service client initialized: {config.base_url}")


async def close_core_service_client():
    """Close global Core Service client."""
    global _core_service_client
    if _core_service_client:
        await _core_service_client.close()
        _core_service_client = None
        logger.info("Core Service client closed")


def get_core_service_client() -> CoreServiceClient:
    """Get global Core Service client instance."""
    if _core_service_client is None:
        raise RuntimeError(
            "Core Service client not initialized. Call init_core_service_client() on startup."
        )
    return _core_service_client
