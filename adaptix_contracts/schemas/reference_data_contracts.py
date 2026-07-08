"""Reference-data contracts shared across Adaptix services.

Canonical code-list container and item shapes for the AdaptixCore Reference
Data shared service (lookups, enumerated code sets, and controlled vocabularies).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------


class ReferenceDataItem(BaseModel):
    """A single entry within a reference-data list."""

    code: str = Field(..., min_length=1, max_length=160)
    label: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=2000)
    parent_code: Optional[str] = Field(None, max_length=160)
    sort_order: int = Field(0, ge=0)
    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------


class ReferenceDataList(BaseModel):
    """A named, versioned set of reference-data items."""

    model_config = ConfigDict(from_attributes=True)

    list_key: str = Field(..., min_length=1, max_length=160)
    name: str = Field(..., min_length=1, max_length=255)
    tenant_id: Optional[UUID] = Field(
        None, description="None for platform-shared reference lists."
    )
    description: Optional[str] = Field(None, max_length=2000)
    version: int = Field(1, ge=1)
    items: list[ReferenceDataItem] = Field(default_factory=list)
    updated_at: datetime
