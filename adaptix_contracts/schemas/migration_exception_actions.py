"""Per-record migration exception plus category-to-action table.

Complements :class:`~adaptix_contracts.schemas.migration_contracts.MigrationExceptionGroup`.
A group ranks a class of defects; this record names one row and the only
legal next action for its category.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from .migration_contracts import MigrationExceptionCategory
from .migration_platform_run import (
    MigrationDomain,
    PLATFORM_MIGRATION_CONTRACT_SCHEMA_VERSION,
)


class MigrationExceptionAction(str, Enum):
    """What the authority may do with one classified exception."""

    AUTO_FIX = "auto_fix"
    KNOWN_VENDOR_QUIRK = "known_vendor_quirk"
    DETERMINISTIC_DUPLICATE_WINNER = "deterministic_duplicate_winner"
    DOCUMENTED_OPTIONAL_GAP = "documented_optional_gap"
    HUMAN_REVIEW = "human_review"
    BLOCK_RECORD = "block_record"
    BLOCK_CUTOVER = "block_cutover"
    BLOCK_MIGRATION = "block_migration"
    BLOCK_GROUP = "block_group"


EXCEPTION_CATEGORY_ACTIONS: dict[MigrationExceptionCategory, MigrationExceptionAction] = {
    MigrationExceptionCategory.SOURCE_FIELD_MISSING: MigrationExceptionAction.HUMAN_REVIEW,
    MigrationExceptionCategory.MAPPING_MISMATCH: MigrationExceptionAction.HUMAN_REVIEW,
    MigrationExceptionCategory.CODE_CROSSWALK_MISSING: MigrationExceptionAction.BLOCK_RECORD,
    MigrationExceptionCategory.IDENTIFIER_COLLISION: (
        MigrationExceptionAction.DETERMINISTIC_DUPLICATE_WINNER
    ),
    MigrationExceptionCategory.ORPHAN_RELATIONSHIP: MigrationExceptionAction.BLOCK_RECORD,
    MigrationExceptionCategory.INVALID_DATE_OR_AMOUNT: MigrationExceptionAction.BLOCK_RECORD,
    MigrationExceptionCategory.FINANCIAL_IMBALANCE: MigrationExceptionAction.BLOCK_CUTOVER,
    MigrationExceptionCategory.UNSUPPORTED_STATE: MigrationExceptionAction.BLOCK_GROUP,
    MigrationExceptionCategory.DUPLICATE: (
        MigrationExceptionAction.DETERMINISTIC_DUPLICATE_WINNER
    ),
    MigrationExceptionCategory.TRUNCATED_EXPORT: MigrationExceptionAction.BLOCK_MIGRATION,
    MigrationExceptionCategory.SOURCE_VENDOR_DEFECT: (
        MigrationExceptionAction.KNOWN_VENDOR_QUIRK
    ),
}


def action_for_category(
    category: MigrationExceptionCategory | str,
) -> MigrationExceptionAction:
    """Return the only legal action for a category. Unknown fails to review."""

    try:
        resolved = MigrationExceptionCategory(category)
    except ValueError:
        return MigrationExceptionAction.HUMAN_REVIEW
    return EXCEPTION_CATEGORY_ACTIONS.get(
        resolved, MigrationExceptionAction.HUMAN_REVIEW
    )


def action_blocks_cutover(action: MigrationExceptionAction | str) -> bool:
    """Whether the action forbids advancing into cutover."""

    try:
        resolved = MigrationExceptionAction(action)
    except ValueError:
        return True
    return resolved in {
        MigrationExceptionAction.BLOCK_CUTOVER,
        MigrationExceptionAction.BLOCK_MIGRATION,
        MigrationExceptionAction.BLOCK_GROUP,
        MigrationExceptionAction.HUMAN_REVIEW,
        MigrationExceptionAction.BLOCK_RECORD,
    }


class MigrationExceptionRecord(BaseModel):
    """One classified exception row. Not the bus event MigrationExceptionRaised."""

    tenant_id: str
    migration_run_id: str
    exception_id: str
    domain: Optional[MigrationDomain] = None
    entity: Optional[str] = None
    source_record_id: Optional[str] = None
    category: MigrationExceptionCategory
    action: MigrationExceptionAction
    blocking: bool = True
    opened_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    schema_version: str = PLATFORM_MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None
    record_version: Optional[int] = Field(default=None, ge=0)
