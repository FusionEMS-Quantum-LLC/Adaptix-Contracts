"""Mapping decisions, confidence bands, and always-deterministic fields.

Does not replace :class:`~adaptix_contracts.schemas.migration_contracts.FieldMappingProposal`
or :class:`~adaptix_contracts.schemas.migration_contracts.MappingDecisionLevel`.
A decision wraps a proposal and states whether a human is required.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from .migration_contracts import (
    FieldMappingProposal,
    MappingDecisionLevel,
    MigrationConfidence,
)
from .migration_platform_run import PLATFORM_MIGRATION_CONTRACT_SCHEMA_VERSION


class DeterministicFieldClass(str, Enum):
    """Field classes that a model must never auto-apply."""

    MONEY = "money"
    PATIENT_IDENTITY = "patient_identity"
    CLAIM_ID = "claim_id"
    MEDICATION_QUANTITY = "medication_quantity"
    NARCOTICS_TRANSACTION = "narcotics_transaction"
    SIGNATURE = "signature"
    PAYER_ID = "payer_id"
    LEGAL_AUDIT = "legal_audit"


ALWAYS_DETERMINISTIC_FIELD_CLASSES: frozenset[DeterministicFieldClass] = frozenset(
    DeterministicFieldClass
)


class MappingConfidenceBand(str, Enum):
    """Deterministic bands. Confidence alone never authorizes a write."""

    ABSENT = "absent"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


def confidence_band_for(confidence: MigrationConfidence | float | None) -> MappingConfidenceBand:
    """Map a 0-1 score onto a band. ``None`` is ``ABSENT``, never ``LOW``."""

    if confidence is None:
        return MappingConfidenceBand.ABSENT
    if confidence < 0.80:
        return MappingConfidenceBand.LOW
    if confidence < 0.95:
        return MappingConfidenceBand.MEDIUM
    return MappingConfidenceBand.HIGH


def requires_human_review(
    decision_level: MappingDecisionLevel | str | None,
    field_class: DeterministicFieldClass | str | None,
    *,
    downstream_financial_impact: bool = False,
    auto_approve_allowed: bool = False,
) -> bool:
    """Return whether a human must decide before the mapping may apply.

    Always-deterministic classes, financial impact, and missing authority
    fail closed to review. ``AUTO_DETERMINISTIC`` on a non-restricted field
    may apply only when ``auto_approve_allowed`` is explicitly True.
    """

    try:
        level = MappingDecisionLevel(decision_level) if decision_level else None
    except ValueError:
        return True
    if level is None or level in {
        MappingDecisionLevel.REVIEW_REQUIRED,
        MappingDecisionLevel.BLOCKED,
    }:
        return True
    if field_class is not None:
        try:
            resolved_class = DeterministicFieldClass(field_class)
        except ValueError:
            return True
        if resolved_class in ALWAYS_DETERMINISTIC_FIELD_CLASSES:
            return True
    if downstream_financial_impact:
        return True
    if level is MappingDecisionLevel.AUTO_DETERMINISTIC:
        return not auto_approve_allowed
    return True


class MappingDecision(BaseModel):
    """Authority record for one field mapping proposal."""

    tenant_id: str
    migration_run_id: str
    decision_id: str
    proposal: FieldMappingProposal
    field_class: Optional[DeterministicFieldClass] = None
    confidence_band: MappingConfidenceBand = MappingConfidenceBand.ABSENT
    human_review_required: bool = True
    decided_by_user_id: Optional[str] = None
    decided_at: Optional[datetime] = None
    schema_version: str = PLATFORM_MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None
    record_version: Optional[int] = Field(default=None, ge=0)
