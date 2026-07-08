"""Application access-control contracts shared across Adaptix services.

Canonical app-access policy and evaluated-decision shapes for the AdaptixCore
App Management shared service (which application surfaces a user/device may
open, given roles, entitlements, platform, and app version).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AppAccessEffect(str, Enum):
    """Effect of an app-access evaluation."""

    ALLOW = "allow"
    DENY = "deny"


# ---------------------------------------------------------------------------
# Policy & Decision
# ---------------------------------------------------------------------------


class AppAccessPolicy(BaseModel):
    """Access policy governing who may open an application surface."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    app_key: str = Field(..., min_length=1, max_length=160)
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    required_roles: list[str] = Field(default_factory=list)
    required_module_entitlements: list[str] = Field(default_factory=list)
    allowed_platforms: list[str] = Field(default_factory=list)
    min_app_version: Optional[str] = Field(None, max_length=64)
    mfa_required: bool = False
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class AppAccessDecision(BaseModel):
    """The evaluated access decision for a user/device against a policy."""

    tenant_id: UUID
    user_id: UUID
    app_key: str = Field(..., min_length=1, max_length=160)
    effect: AppAccessEffect
    allowed: bool
    correlation_id: Optional[str] = None
    matched_policy_id: Optional[UUID] = None
    device_id: Optional[UUID] = None
    reasons: list[str] = Field(default_factory=list)
    evaluated_at: datetime
