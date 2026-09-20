"""Lineage, rollback, evidence, historical provenance, and domain import envelope.

Side-effect suppression is mandatory on historical import. A historical
record must not bill, notify, dispatch, or submit.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from .migration_platform_run import (
    MigrationDomain,
    PLATFORM_MIGRATION_CONTRACT_SCHEMA_VERSION,
)


class MigrationLineage(BaseModel):
    """Source record → transformed payload → destination record."""

    tenant_id: str
    migration_run_id: str
    lineage_id: str
    domain: MigrationDomain
    entity: str
    source_record_id: str
    transformed_hash_sha256: Optional[str] = Field(
        default=None, min_length=64, max_length=64
    )
    destination_record_id: Optional[str] = None
    recorded_at: Optional[datetime] = None
    schema_version: str = PLATFORM_MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None
    record_version: Optional[int] = Field(default=None, ge=0)


class RollbackPlan(BaseModel):
    """How a promoted run is reversed. Requires a recorded promotion watermark."""

    tenant_id: str
    migration_run_id: str
    plan_id: str
    watermark_id: str
    destination_record_ids: list[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    schema_version: str = PLATFORM_MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None
    record_version: Optional[int] = Field(default=None, ge=0)


class MigrationEvidence(BaseModel):
    """Operator-safe evidence pointer. No PHI in these fields."""

    tenant_id: str
    migration_run_id: str
    evidence_id: str
    kind: str
    object_store_key: Optional[str] = None
    content_hash_sha256: Optional[str] = Field(
        default=None, min_length=64, max_length=64
    )
    recorded_at: Optional[datetime] = None
    schema_version: str = PLATFORM_MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None
    record_version: Optional[int] = Field(default=None, ge=0)


class HistoricalRecordProvenance(BaseModel):
    """Provenance stamped on every historical import row."""

    source: str = "migration"
    migration_run_id: str
    source_vendor: str
    source_record_id: str
    source_timestamp: datetime
    imported_at: datetime
    historical: bool = True

    @model_validator(mode="after")
    def _historical_must_stay_true(self) -> "HistoricalRecordProvenance":
        if self.source != "migration":
            raise ValueError("historical provenance source must be migration")
        if not self.historical:
            raise ValueError("historical provenance cannot set historical=false")
        return self


class SideEffectName(str, Enum):
    """Live side effects a historical import must suppress."""

    BILLING_SUBMIT = "billing_submit"
    CLEARINGHOUSE_TRANSMIT = "clearinghouse_transmit"
    PATIENT_STATEMENT = "patient_statement"
    NOTIFICATION = "notification"
    DISPATCH = "dispatch"
    CAD_CREATE = "cad_create"
    SIGNATURE_REQUEST = "signature_request"
    NARCOTICS_LEDGER_LIVE = "narcotics_ledger_live"
    USAGE_INCREMENT = "usage_increment"


DEFAULT_SIDE_EFFECT_SUPPRESSION: frozenset[SideEffectName] = frozenset(SideEffectName)


class DomainMigrationImportRequest(BaseModel):
    """Envelope for POST /api/v1/<domain>/migration/import."""

    tenant_id: str
    migration_run_id: str
    domain: MigrationDomain
    entity: str
    provenance: HistoricalRecordProvenance
    suppress_side_effects: list[SideEffectName] = Field(
        default_factory=lambda: list(DEFAULT_SIDE_EFFECT_SUPPRESSION)
    )
    dry_run: bool = True
    payload_hash_sha256: Optional[str] = Field(
        default=None, min_length=64, max_length=64
    )
    schema_version: str = PLATFORM_MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None

    @model_validator(mode="after")
    def _historical_import_must_suppress(self) -> "DomainMigrationImportRequest":
        if self.provenance.migration_run_id != self.migration_run_id:
            raise ValueError("provenance run id mismatch")
        required = set(DEFAULT_SIDE_EFFECT_SUPPRESSION)
        present = set(self.suppress_side_effects)
        missing = required - present
        if missing:
            raise ValueError("historical import missing required side-effect suppression")
        return self


class DomainMigrationImportResponse(BaseModel):
    """Truthful result of one domain import attempt."""

    tenant_id: str
    migration_run_id: str
    accepted: bool
    dry_run: bool
    destination_record_id: Optional[str] = None
    lineage_id: Optional[str] = None
    rejected_reason: Optional[str] = None
    schema_version: str = PLATFORM_MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None
