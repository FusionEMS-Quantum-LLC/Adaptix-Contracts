"""Platform migration run, source, plan, and entity catalog.

This module extends the billing-vendor lifecycle in
``migration_contracts`` so Imports, Cortex, and domain ingest endpoints
share one run/source/plan vocabulary. It does not replace
:class:`~adaptix_contracts.schemas.migration_contracts.MigrationState`.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from .migration_contracts import (
    MIGRATION_CONTRACT_SCHEMA_VERSION,
    MigrationState,
    MigrationSourceVendor,
    VendorProfileRef,
)

PLATFORM_MIGRATION_CONTRACT_SCHEMA_VERSION = "3.0.0"


class MigrationDomain(str, Enum):
    """Service-registry slugs that can own a migrated entity.

    Values are the live ``SERVICE_BY_SLUG`` keys that persist domain records
    a migration can write. Unknown slugs fail closed at parse time.
    """

    BILLING = "billing"
    EPCR = "epcr"
    PATIENT_IDENTITY = "patient-identity"
    CAD = "cad"
    FIRE = "fire"
    NARCOTICS = "narcotics"
    MEDICATIONS = "medications"
    WORKFORCE = "workforce"
    TRANSPORT = "transport"
    AIR = "air"
    FINANCE = "finance"
    DOCUMENTS = "documents"
    COMPLIANCE = "compliance"
    POLICY = "policy"
    EXPORTS = "exports"
    IMPORTS = "imports"
    AUDIT = "audit"


class PlatformEntity(BaseModel):
    """One migratable entity owned by exactly one domain service."""

    domain: MigrationDomain
    entity: str
    always_deterministic: bool = False
    historical_import_path: str


PLATFORM_ENTITY_CATALOG: tuple[PlatformEntity, ...] = (
    PlatformEntity(
        domain=MigrationDomain.BILLING,
        entity="claim",
        always_deterministic=True,
        historical_import_path="/api/v1/billing/migration/import",
    ),
    PlatformEntity(
        domain=MigrationDomain.BILLING,
        entity="remittance",
        always_deterministic=True,
        historical_import_path="/api/v1/billing/migration/import",
    ),
    PlatformEntity(
        domain=MigrationDomain.BILLING,
        entity="payer",
        always_deterministic=True,
        historical_import_path="/api/v1/billing/migration/import",
    ),
    PlatformEntity(
        domain=MigrationDomain.BILLING,
        entity="encounter",
        always_deterministic=True,
        historical_import_path="/api/v1/billing/migration/import",
    ),
    PlatformEntity(
        domain=MigrationDomain.EPCR,
        entity="chart",
        always_deterministic=True,
        historical_import_path="/api/v1/epcr/migration/import",
    ),
    PlatformEntity(
        domain=MigrationDomain.PATIENT_IDENTITY,
        entity="patient",
        always_deterministic=True,
        historical_import_path="/api/v1/patient-identity/migration/import",
    ),
    PlatformEntity(
        domain=MigrationDomain.NARCOTICS,
        entity="controlled_substance_transaction",
        always_deterministic=True,
        historical_import_path="/api/v1/narcotics/migration/import",
    ),
    PlatformEntity(
        domain=MigrationDomain.MEDICATIONS,
        entity="administration",
        always_deterministic=True,
        historical_import_path="/api/v1/medications/migration/import",
    ),
    PlatformEntity(
        domain=MigrationDomain.CAD,
        entity="incident",
        always_deterministic=False,
        historical_import_path="/api/v1/cad/migration/import",
    ),
    PlatformEntity(
        domain=MigrationDomain.FIRE,
        entity="incident",
        always_deterministic=False,
        historical_import_path="/api/v1/fire/migration/import",
    ),
    PlatformEntity(
        domain=MigrationDomain.WORKFORCE,
        entity="shift",
        always_deterministic=False,
        historical_import_path="/api/v1/workforce/migration/import",
    ),
    PlatformEntity(
        domain=MigrationDomain.TRANSPORT,
        entity="request",
        always_deterministic=False,
        historical_import_path="/api/v1/transport/migration/import",
    ),
    PlatformEntity(
        domain=MigrationDomain.AIR,
        entity="mission",
        always_deterministic=False,
        historical_import_path="/api/v1/air/migration/import",
    ),
    PlatformEntity(
        domain=MigrationDomain.FINANCE,
        entity="invoice",
        always_deterministic=True,
        historical_import_path="/api/v1/finance/migration/import",
    ),
    PlatformEntity(
        domain=MigrationDomain.DOCUMENTS,
        entity="signature",
        always_deterministic=True,
        historical_import_path="/api/v1/documents/migration/import",
    ),
    PlatformEntity(
        domain=MigrationDomain.COMPLIANCE,
        entity="obligation",
        always_deterministic=False,
        historical_import_path="/api/v1/compliance/migration/import",
    ),
    PlatformEntity(
        domain=MigrationDomain.POLICY,
        entity="policy_document",
        always_deterministic=True,
        historical_import_path="/api/v1/policy/migration/import",
    ),
    PlatformEntity(
        domain=MigrationDomain.EXPORTS,
        entity="export_artifact",
        always_deterministic=False,
        historical_import_path="/api/v1/exports/migration/import",
    ),
    PlatformEntity(
        domain=MigrationDomain.AUDIT,
        entity="audit_event",
        always_deterministic=True,
        historical_import_path="/api/v1/audit/migration/import",
    ),
)


def catalog_entity(domain: MigrationDomain | str, entity: str) -> PlatformEntity | None:
    """Return the catalog row for ``domain`` × ``entity``, or ``None``.

    Fails closed: an unknown pair is not invented.
    """

    try:
        resolved = MigrationDomain(domain)
    except ValueError:
        return None
    needle = entity.strip().lower()
    for row in PLATFORM_ENTITY_CATALOG:
        if row.domain is resolved and row.entity == needle:
            return row
    return None


class MigrationRun(BaseModel):
    """One tenant migration execution. State uses the existing lifecycle."""

    tenant_id: str
    migration_run_id: str
    state: MigrationState = MigrationState.DRAFT
    source_vendor: Optional[MigrationSourceVendor] = None
    paused_from_state: Optional[MigrationState] = None
    created_by_user_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    schema_version: str = PLATFORM_MIGRATION_CONTRACT_SCHEMA_VERSION
    billing_schema_version: str = MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None
    record_version: Optional[int] = Field(default=None, ge=0)


class MigrationSource(BaseModel):
    """Registered legacy source for a run. Complements MigrationSourceFile."""

    tenant_id: str
    migration_run_id: str
    source_id: str
    vendor_profile: Optional[VendorProfileRef] = None
    connection_type: Optional[str] = None
    reachable: bool = False
    registered_at: Optional[datetime] = None
    schema_version: str = PLATFORM_MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None
    record_version: Optional[int] = Field(default=None, ge=0)


class MigrationEntityPlan(BaseModel):
    """Per-entity slice of a migration plan."""

    tenant_id: str
    migration_run_id: str
    domain: MigrationDomain
    entity: str
    included: bool = True
    historical: bool = True
    dry_run_required: bool = True
    schema_version: str = PLATFORM_MIGRATION_CONTRACT_SCHEMA_VERSION
    record_version: Optional[int] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _must_be_catalogued(self) -> "MigrationEntityPlan":
        if catalog_entity(self.domain, self.entity) is None:
            raise ValueError("entity is not in the platform migration catalog")
        return self


class MigrationPlan(BaseModel):
    """Ordered entity plans for one run. Unknown catalog pairs are refused."""

    tenant_id: str
    migration_run_id: str
    plan_id: str
    entity_plans: list[MigrationEntityPlan] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    schema_version: str = PLATFORM_MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None
    record_version: Optional[int] = Field(default=None, ge=0)
