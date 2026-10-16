"""Admin management contracts shared across Adaptix services."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AdminAction(str, enum.Enum):
    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DEACTIVATE = "user.deactivate"
    USER_REACTIVATE = "user.reactivate"
    ROLE_ASSIGN = "role.assign"
    ROLE_REVOKE = "role.revoke"
    TENANT_CONFIGURE = "tenant.configure"
    TENANT_SUSPEND = "tenant.suspend"
    API_KEY_CREATE = "api_key.create"
    API_KEY_REVOKE = "api_key.revoke"
    SERVICE_IDENTITY_CREATE = "service_identity.create"


class UserContract(BaseModel):
    id: UUID
    tenant_id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool = True
    is_founder: bool = False
    mfa_enabled: bool = False
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None


class UserCreateRequest(BaseModel):
    email: str
    full_name: str
    role: str
    password: str


class UserUpdateRequest(BaseModel):
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class RoleContract(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None = None
    permissions: list[str] = Field(default_factory=list)
    created_at: datetime


class PermissionContract(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    resource_type: str
    action: str


class ApiKeyContract(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    key_prefix: str
    is_active: bool = True
    expires_at: datetime | None = None
    created_at: datetime


class ServiceIdentityContract(BaseModel):
    id: UUID
    service_name: str
    description: str | None = None
    is_active: bool = True
    created_at: datetime


class PaginationContract(BaseModel):
    page: int = 1
    page_size: int = 50
    total_count: int = 0
    total_pages: int = 0


class PaginatedResponse(BaseModel):
    items: list[Any] = Field(default_factory=list)
    pagination: PaginationContract
