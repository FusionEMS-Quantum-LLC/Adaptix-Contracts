"""Tenant management contracts shared across Adaptix services."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


class TenantStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"
    PENDING_SETUP = "pending_setup"


class TenantType(str, enum.Enum):
    """The governed classification of a tenant, fixed when it is created.

    ``customer`` is an agency that uses Adaptix. ``production_certification``
    is an Adaptix-owned tenant in the real production stack (same auth,
    isolation, RBAC, APIs, database, events, workers, UI, audit and
    deployment as a customer) that holds only clearly named certification
    records and exists to runtime-prove the platform (the Adaptix
    Certification Fabric). Its records are never real PHI, never reported as
    patient care, never transmitted to a real external payer, clearinghouse
    or partner, and never counted in customer aggregates.

    The classification is immutable: converting either way would move real
    records out of, or certification records into, customer reporting.
    Adaptix-Core-Service owns it. Its CERT-CORE change (branch
    ``feat/core-production-certification-tenant``, not yet on Core main when
    this vocabulary was published) adds the immutable
    ``core_tenants.tenant_type`` column and the ``tenant_type`` access-token
    claim with exactly these two values. This enum is the wire vocabulary
    every other service reads it with.
    """

    CUSTOMER = "customer"
    PRODUCTION_CERTIFICATION = "production_certification"


class TenantScopedModel(BaseModel):
    """Base contract for any tenant-scoped entity."""

    tenant_id: UUID


class TenantContract(BaseModel):
    id: UUID
    name: str
    slug: str
    status: TenantStatus = TenantStatus.ACTIVE
    plan_tier: Optional[str] = None
    metadata_json: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class TenantCreateRequest(BaseModel):
    name: str
    slug: str
    plan_tier: Optional[str] = None
    metadata_json: Optional[dict[str, Any]] = None


class TenantUpdateRequest(BaseModel):
    name: Optional[str] = None
    plan_tier: Optional[str] = None
    status: Optional[TenantStatus] = None
    metadata_json: Optional[dict[str, Any]] = None


class TenantResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    status: TenantStatus
    plan_tier: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class TenantCreatedEvent(BaseModel):
    tenant_id: UUID
    name: str
    slug: str
    created_at: datetime


class TenantSuspendedEvent(BaseModel):
    tenant_id: UUID
    reason: Optional[str] = None
    suspended_at: datetime
