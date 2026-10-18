"""Device registration contracts shared across Adaptix services.

Canonical device registration record, platform, and status enums for the
AdaptixCore Device shared service (mobile/tablet device inventory and MDM).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DevicePlatform(str, Enum):
    """Operating platform of a registered device."""

    IOS = "ios"
    ANDROID = "android"
    WEB = "web"
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"


class DeviceStatus(str, Enum):
    """Lifecycle state of a registered device."""

    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    LOST = "lost"
    RETIRED = "retired"


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class DeviceRegistration(BaseModel):
    """A device registered to a tenant (and optionally a user)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    user_id: UUID | None = None
    device_identifier: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Stable hardware/install identifier.",
    )
    platform: DevicePlatform
    status: DeviceStatus = DeviceStatus.PENDING
    name: str | None = Field(default=None, max_length=200)
    os_version: str | None = Field(default=None, max_length=64)
    app_version: str | None = Field(default=None, max_length=64)
    push_token: str | None = Field(default=None, max_length=512)
    mdm_managed: bool = False
    last_seen_at: datetime | None = None
    registered_at: datetime
    updated_at: datetime
