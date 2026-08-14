"""Agency CAD import mapping profile — how AdaptixCore learns a department's format.

When an agency first imports a dispatch report, the Universal CAD Gateway (with
the Cortex CAD Mapper) proposes a mapping from that source's layout to the
normalized AdaptixCore CAD Incident. The administrator confirms it once and the
profile is saved. Subsequent imports of the same layout are recognized and
mapped automatically.

Contract rules (mirrors the way ACIN records version):
- A profile is tenant-scoped and versioned.
- A confirmed profile is immutable: a correction produces a NEW version; the old
  version is retained (``SUPERSEDED``) for audit and reversal.
- Cortex may PROPOSE a mapping; it never silently replaces an approved profile.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import IngestionMethod, MappingProfileStatus


class CadFieldMappingRule(BaseModel):
    """One learned mapping: a source locator -> a canonical AdaptixCore field."""

    canonical_field: str = Field(
        ...,
        description="Dotted canonical target, e.g. 'times.dispatch' or 'incident.incident_number'.",
    )
    source_locator: str = Field(
        ...,
        description="How to find it in this layout (column header, label, cell, or region key).",
    )
    transform: Optional[str] = Field(
        default=None,
        description="Optional normalization hint (e.g. 'time:12h', 'date_from_context').",
    )
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class AgencyCadMappingProfile(BaseModel):
    """A versioned, auditable, reversible per-agency import mapping profile."""

    tenant_id: str = Field(..., description="Owning tenant.")
    display_name: str = Field(
        ..., description="Human label, e.g. 'Jefferson County CAD run sheet'."
    )
    connector_key: Optional[str] = Field(
        default=None,
        description="Connector this profile binds to (None for generic manual/upload).",
    )
    input_type: IngestionMethod = Field(
        ..., description="The intake method this profile applies to."
    )
    layout_signature: str = Field(
        ..., description="Fingerprint that matches incoming source layouts."
    )
    version: int = Field(
        ..., ge=1, description="Monotonic version; a correction creates a new version."
    )
    active: bool = Field(
        default=False, description="True only for the current confirmed version."
    )
    status: MappingProfileStatus = Field(default=MappingProfileStatus.DRAFT)
    field_map: list[CadFieldMappingRule] = Field(default_factory=list)
    code_map: dict[str, str] = Field(
        default_factory=dict,
        description="Local dispatch/determinant code -> NERIS incident type (seeded from the NERIS template).",
    )

    model_config = ConfigDict(from_attributes=True)


__all__ = [
    "CadFieldMappingRule",
    "AgencyCadMappingProfile",
]
