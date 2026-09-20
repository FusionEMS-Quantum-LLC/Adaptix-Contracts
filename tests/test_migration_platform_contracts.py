"""Regression tests for the platform migration contract layer.

Existing billing-vendor tests in test_migration_contracts.py stay authoritative
for MigrationState and the unpublished event shapes. These tests pin the
additive run/plan/authority/import envelope only.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from adaptix_contracts.schemas.migration_contracts import (
    CutoverWatermark,
    FieldMappingProposal,
    MappingDecisionLevel,
    MigrationExceptionCategory,
    MigrationReconciliationStatus,
    MigrationState,
    ReconciliationRunResult,
)
from adaptix_contracts.schemas.migration_cutover_authority import (
    CutoverApproval,
    evaluate_cutover_readiness,
)
from adaptix_contracts.schemas.migration_exception_actions import (
    EXCEPTION_CATEGORY_ACTIONS,
    MigrationExceptionAction,
    MigrationExceptionRecord,
    action_for_category,
)
from adaptix_contracts.schemas.migration_lineage_import import (
    DEFAULT_SIDE_EFFECT_SUPPRESSION,
    DomainMigrationImportRequest,
    HistoricalRecordProvenance,
    SideEffectName,
)
from adaptix_contracts.schemas.migration_mapping_authority import (
    ALWAYS_DETERMINISTIC_FIELD_CLASSES,
    DeterministicFieldClass,
    MappingConfidenceBand,
    confidence_band_for,
    requires_human_review,
)
from adaptix_contracts.schemas.migration_platform_run import (
    PLATFORM_ENTITY_CATALOG,
    MigrationDomain,
    MigrationEntityPlan,
    MigrationRun,
    catalog_entity,
)


def _ts() -> datetime:
    return datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def test_catalog_pairs_are_unique() -> None:
    pairs = [(row.domain, row.entity) for row in PLATFORM_ENTITY_CATALOG]
    assert len(pairs) == len(set(pairs))


def test_catalog_entity_fails_closed() -> None:
    assert catalog_entity("billing", "claim") is not None
    assert catalog_entity("not-a-service", "claim") is None
    assert catalog_entity(MigrationDomain.BILLING, "invented") is None


def test_entity_plan_rejects_unknown_catalog_pair() -> None:
    with pytest.raises(ValidationError):
        MigrationEntityPlan(
            tenant_id="t1",
            migration_run_id="r1",
            domain=MigrationDomain.BILLING,
            entity="invented",
        )


def test_migration_run_reuses_existing_lifecycle() -> None:
    run = MigrationRun(tenant_id="t1", migration_run_id="r1")
    assert run.state is MigrationState.DRAFT


@pytest.mark.parametrize("field_class", list(ALWAYS_DETERMINISTIC_FIELD_CLASSES))
def test_always_deterministic_fields_require_human(
    field_class: DeterministicFieldClass,
) -> None:
    assert requires_human_review(
        MappingDecisionLevel.AUTO_DETERMINISTIC,
        field_class,
        auto_approve_allowed=True,
    )


def test_non_restricted_deterministic_mapping_may_auto_apply() -> None:
    assert (
        requires_human_review(
            MappingDecisionLevel.AUTO_DETERMINISTIC,
            None,
            auto_approve_allowed=True,
        )
        is False
    )


def test_financial_impact_never_auto_applies() -> None:
    assert requires_human_review(
        MappingDecisionLevel.AUTO_DETERMINISTIC,
        None,
        downstream_financial_impact=True,
        auto_approve_allowed=True,
    )


def test_confidence_none_is_absent_not_low() -> None:
    assert confidence_band_for(None) is MappingConfidenceBand.ABSENT
    assert confidence_band_for(0.5) is MappingConfidenceBand.LOW
    assert confidence_band_for(0.9) is MappingConfidenceBand.MEDIUM
    assert confidence_band_for(0.95) is MappingConfidenceBand.HIGH


def test_exception_table_covers_every_existing_category() -> None:
    assert set(EXCEPTION_CATEGORY_ACTIONS) == set(MigrationExceptionCategory)
    assert (
        action_for_category("not-a-category") is MigrationExceptionAction.HUMAN_REVIEW
    )
    assert (
        action_for_category(MigrationExceptionCategory.FINANCIAL_IMBALANCE)
        is MigrationExceptionAction.BLOCK_CUTOVER
    )


def test_cutover_readiness_fails_closed_without_watermark() -> None:
    result = evaluate_cutover_readiness(
        tenant_id="t1",
        migration_run_id="r1",
        state=MigrationState.READY_FOR_CUTOVER,
        watermark=None,
        reconciliation=ReconciliationRunResult(
            tenant_id="t1",
            migration_id="r1",
            overall_status=MigrationReconciliationStatus.BALANCED,
        ),
        exceptions=[],
    )
    assert result.ready is False
    assert "watermark_missing" in result.blocking_reasons


def test_cutover_approval_requires_fresh_mfa() -> None:
    ready = evaluate_cutover_readiness(
        tenant_id="t1",
        migration_run_id="r1",
        state=MigrationState.READY_FOR_CUTOVER,
        watermark=CutoverWatermark(
            tenant_id="t1",
            migration_id="r1",
            watermark_at=_ts(),
        ),
        reconciliation=ReconciliationRunResult(
            tenant_id="t1",
            migration_id="r1",
            overall_status=MigrationReconciliationStatus.BALANCED,
        ),
        exceptions=[],
        evaluated_at=_ts(),
    )
    assert ready.ready is True
    with pytest.raises(ValidationError):
        CutoverApproval(
            tenant_id="t1",
            migration_run_id="r1",
            approval_id="a1",
            approved_by_user_id="u1",
            approved_at=_ts(),
            fresh_mfa_verified=False,
            readiness=ready,
        )


def test_historical_provenance_cannot_lie() -> None:
    with pytest.raises(ValidationError):
        HistoricalRecordProvenance(
            migration_run_id="r1",
            source_vendor="imagetrend",
            source_record_id="src-1",
            source_timestamp=_ts(),
            imported_at=_ts(),
            historical=False,
        )


def test_import_envelope_requires_full_suppression() -> None:
    provenance = HistoricalRecordProvenance(
        migration_run_id="r1",
        source_vendor="imagetrend",
        source_record_id="src-1",
        source_timestamp=_ts(),
        imported_at=_ts(),
    )
    with pytest.raises(ValidationError):
        DomainMigrationImportRequest(
            tenant_id="t1",
            migration_run_id="r1",
            domain=MigrationDomain.BILLING,
            entity="claim",
            provenance=provenance,
            suppress_side_effects=[SideEffectName.NOTIFICATION],
        )
    accepted = DomainMigrationImportRequest(
        tenant_id="t1",
        migration_run_id="r1",
        domain=MigrationDomain.BILLING,
        entity="claim",
        provenance=provenance,
        suppress_side_effects=list(DEFAULT_SIDE_EFFECT_SUPPRESSION),
    )
    assert accepted.dry_run is True


def test_blocking_exception_prevents_cutover() -> None:
    result = evaluate_cutover_readiness(
        tenant_id="t1",
        migration_run_id="r1",
        state=MigrationState.READY_FOR_CUTOVER,
        watermark=CutoverWatermark(
            tenant_id="t1",
            migration_id="r1",
            watermark_at=_ts(),
        ),
        reconciliation=ReconciliationRunResult(
            tenant_id="t1",
            migration_id="r1",
            overall_status=MigrationReconciliationStatus.BALANCED,
        ),
        exceptions=[
            MigrationExceptionRecord(
                tenant_id="t1",
                migration_run_id="r1",
                exception_id="e1",
                category=MigrationExceptionCategory.FINANCIAL_IMBALANCE,
                action=MigrationExceptionAction.BLOCK_CUTOVER,
            )
        ],
    )
    assert result.ready is False
    assert "blocking_exceptions" in result.blocking_reasons


def test_field_mapping_proposal_still_constructs() -> None:
    """Existing consumer shape must remain valid after the additive modules."""

    proposal = FieldMappingProposal(tenant_id="t1", source_field="acct")
    assert proposal.auto_approve_allowed is False
