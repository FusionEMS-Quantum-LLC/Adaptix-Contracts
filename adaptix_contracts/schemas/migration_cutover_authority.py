"""Cutover readiness hard gates and human-plus-fresh-MFA approval.

Does not replace :class:`~adaptix_contracts.schemas.migration_contracts.CutoverWatermark`
or the ``CutoverApproved`` event shape. Those remain the watermark and the
unpublished event. This module is the gate that must pass before either.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from .migration_contracts import (
    CutoverWatermark,
    MigrationReconciliationStatus,
    MigrationState,
    ReconciliationRunResult,
)
from .migration_exception_actions import (
    MigrationExceptionAction,
    MigrationExceptionRecord,
    action_blocks_cutover,
)
from .migration_platform_run import PLATFORM_MIGRATION_CONTRACT_SCHEMA_VERSION


class CutoverReadiness(BaseModel):
    """Hard-gate result. ``ready`` is True only when every gate passed."""

    tenant_id: str
    migration_run_id: str
    state: MigrationState
    ready: bool = False
    blocking_reasons: list[str] = Field(default_factory=list)
    watermark_present: bool = False
    reconciliation_status: Optional[MigrationReconciliationStatus] = None
    blocking_exception_count: int = Field(default=0, ge=0)
    evaluated_at: Optional[datetime] = None
    schema_version: str = PLATFORM_MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None


def evaluate_cutover_readiness(
    *,
    tenant_id: str,
    migration_run_id: str,
    state: MigrationState,
    watermark: CutoverWatermark | None,
    reconciliation: ReconciliationRunResult | None,
    exceptions: list[MigrationExceptionRecord],
    evaluated_at: datetime | None = None,
) -> CutoverReadiness:
    """Fail closed. Ready only from READY_FOR_CUTOVER with a watermark and balance."""

    reasons: list[str] = []
    if state is not MigrationState.READY_FOR_CUTOVER:
        reasons.append("state_not_ready_for_cutover")
    watermark_present = bool(
        watermark is not None
        and watermark.watermark_at is not None
        and watermark.tenant_id == tenant_id
        and (watermark.migration_id in {None, migration_run_id})
    )
    if not watermark_present:
        reasons.append("watermark_missing")
    recon_status = reconciliation.overall_status if reconciliation else None
    if recon_status is None or recon_status in {
        MigrationReconciliationStatus.NOT_RUN,
        MigrationReconciliationStatus.OUT_OF_BALANCE,
        MigrationReconciliationStatus.BLOCKED,
    }:
        reasons.append("reconciliation_not_balanced")
    blocking = [
        row for row in exceptions if row.blocking or action_blocks_cutover(row.action)
    ]
    if blocking:
        reasons.append("blocking_exceptions")
    if any(
        row.action is MigrationExceptionAction.BLOCK_MIGRATION for row in exceptions
    ):
        reasons.append("migration_blocked")
    return CutoverReadiness(
        tenant_id=tenant_id,
        migration_run_id=migration_run_id,
        state=state,
        ready=not reasons,
        blocking_reasons=reasons,
        watermark_present=watermark_present,
        reconciliation_status=recon_status,
        blocking_exception_count=len(blocking),
        evaluated_at=evaluated_at,
    )


class CutoverApproval(BaseModel):
    """Human cutover approval. Invalid unless fresh MFA is recorded."""

    tenant_id: str
    migration_run_id: str
    approval_id: str
    approved_by_user_id: str
    approved_at: datetime
    fresh_mfa_verified: bool = False
    fresh_mfa_at: Optional[datetime] = None
    readiness: CutoverReadiness
    schema_version: str = PLATFORM_MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None
    record_version: Optional[int] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _require_fresh_mfa_and_readiness(self) -> "CutoverApproval":
        if not self.fresh_mfa_verified or self.fresh_mfa_at is None:
            raise ValueError("cutover approval requires verified fresh MFA")
        if self.fresh_mfa_at > self.approved_at:
            raise ValueError("fresh MFA cannot occur after approval")
        if not self.readiness.ready:
            raise ValueError("cutover approval requires a ready gate")
        if self.readiness.tenant_id != self.tenant_id:
            raise ValueError("readiness tenant mismatch")
        if self.readiness.migration_run_id != self.migration_run_id:
            raise ValueError("readiness run mismatch")
        return self
