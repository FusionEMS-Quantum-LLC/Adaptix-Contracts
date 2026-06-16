"""ePCR CAD handoff ingest contract.

Defines the contract for ePCR consuming a CAD-to-ePCR handoff payload.
ePCR owns final NEMSIS mapping, XML generation, XSD validation, and Schematron validation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field


class EpcrCadHandoffIngestRequest(BaseModel):
    """Request to ingest a CAD handoff payload into an ePCR chart draft.

    ePCR must:
    - Preserve CAD source attribution on every mapped field
    - Not overwrite clinician-entered data without explicit review
    - Mark missing required NEMSIS elements clearly
    - Return validation warnings to ePCR UI
    - Store handoff mapping audit
    """

    handoff_id: str
    cad_dispatch_id: str
    tenant_id: str
    epcr_chart_id: str | None = Field(
        default=None,
        description="If provided, ingest into existing chart. If None, create new draft.",
    )
    handoff_payload: dict[str, Any] = Field(
        description="Full CadNemsisHandoffPayload as dict"
    )
    ingest_requested_by: str | None = None
    ingest_requested_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class EpcrCadHandoffFieldMapping(BaseModel):
    """Single field mapping result from CAD handoff to NEMSIS element."""

    nemsis_element: str = Field(description="e.g. eTimes.05, eResponse.05")
    nemsis_label: str
    cad_source_field: str
    cad_value: Any | None = None
    mapped: bool
    mapping_note: str | None = None
    requires_clinician_review: bool = False
    missing_required: bool = False


class EpcrCadHandoffIngestResult(BaseModel):
    """Result of ingesting a CAD handoff into an ePCR chart draft."""

    handoff_id: str
    cad_dispatch_id: str
    epcr_chart_id: str
    tenant_id: str
    ingest_status: str = Field(description="success|partial|failed")
    fields_mapped: int
    fields_missing: int
    fields_requiring_review: int
    field_mappings: list[EpcrCadHandoffFieldMapping] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)
    missing_required_nemsis_elements: list[str] = Field(default_factory=list)
    audit_id: str | None = None
    ingested_at: datetime


class EpcrCadHandoffIngestedEvent(BaseModel):
    """Event emitted when ePCR ingests a CAD handoff."""

    event_type: str = "epcr.cad_handoff.ingested"
    handoff_id: str
    cad_dispatch_id: str
    epcr_chart_id: str
    tenant_id: str
    ingest_status: str
    fields_mapped: int
    emitted_at: datetime


class EpcrNemsisCadFieldsMappedEvent(BaseModel):
    """Event emitted when ePCR maps CAD fields to NEMSIS elements."""

    event_type: str = "epcr.nemsis.cad_fields.mapped"
    handoff_id: str
    epcr_chart_id: str
    tenant_id: str
    fields_mapped: int
    missing_required_elements: list[str] = Field(default_factory=list)
    emitted_at: datetime


class EpcrNemsisValidationCompletedEvent(BaseModel):
    """Event emitted when ePCR completes NEMSIS validation after CAD handoff mapping."""

    event_type: str = "epcr.nemsis.validation.completed"
    epcr_chart_id: str
    tenant_id: str
    xsd_valid: bool
    schematron_valid: bool
    validation_errors: list[str] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)
    emitted_at: datetime
