"""Canonical contracts for autonomous billing-vendor migration.

Scope
-----
These contracts are the single typed vocabulary for moving a customer's
revenue-cycle data OFF a legacy billing vendor and ONTO Adaptix. They cover the
migration lifecycle state machine, the source-file/lineage facts, the proposed
field mapping, financial reconciliation controls, exception grouping, cutover
sign-off, and the domain events the migration subsystem publishes.

Why this module exists
----------------------
The migration subsystem in ``Adaptix-Billing-Service`` is real and running, but
at ``origin/main`` (read 2026-08-16) it has **no shared typed vocabulary at
all**: it defines zero ``Enum`` classes, and its state words live as bare
strings in five mutually disjoint vocabularies —

* ``BillingMigrationJob.status`` — dict keys only, in
  ``backend/billing_app/services/migration/migration_service.py:31``
  (``pending``, ``running``, ``approval_pending``, ``committing``, ``rejected``,
  ``failed``, ``cancelled``, ``completed``)
* ``MigrationIntake.status`` — ``backend/billing_app/models/migration_imports.py:30``
* ``ImportBatch.status`` — ``backend/billing_app/models/migration_imports.py:48``
* ``CommercialInquiry`` "migration" status — declared nowhere, hardcoded in
  ``backend/billing_app/api/migration.py:150``
* ``CortexWhispererRun.status`` — ``backend/billing_app/models/migration_whisperer.py:29``

plus three orthogonal axes (``mapping_state``, ``commit_status``,
``cortex_status``). None of the legacy vocabularies is removed or renamed by
this module; they remain the persisted column values of their own tables. This
module adds the **canonical cross-service** vocabulary that those subsystems map
onto, so Billing, Imports, Cortex, and the operator UI stop inventing a private
state word per table.

Guarded transitions are a contract requirement
----------------------------------------------
:data:`MIGRATION_STATE_TRANSITIONS` and :func:`is_legal_migration_transition`
exist because the live code demonstrates the exact failure they prevent: at
``backend/billing_app/api/migration_intelligence_routes.py:715`` the commit
endpoint assigns ``job.status = "completed"`` directly on a job created at
``"pending"`` (``:192``) — an illegal jump under that service's own declared
``_VALID_TRANSITIONS`` map, whose guard function ``update_migration_status``
(``services/migration/migration_service.py:65``) has zero callers. A UI button
must never be able to advance migration state. Every state write MUST be
validated by the guard server-side; these contracts make the legal edge set
importable so no service has to re-derive it.

The edge set below is canonically DEFINED HERE. No prior machine-readable
definition of these 26 states existed in the workspace; the legacy 8-value
``_VALID_TRANSITIONS`` map covers a different, smaller vocabulary and is not a
subset of this one.

Money
-----
Every monetary field in this module is **signed integer cents**, declared
``strict`` so a float is REJECTED rather than silently truncated. This matches
the migration subsystem's persisted reality — every money column on the
migration path is ``BigInteger`` cents
(``models/migration_staging.py:80-82, 132-133, 189``;
``models/migration_imports.py:134``) with no ``Numeric`` and no ``Float``
anywhere — and it makes the contract layer refuse the float that a lax ``int``
field would round away.

PHI
---
No field, default, docstring, or example in this module carries PHI. Fields that
exist to show an operator what a mapping did are named ``*_masked_*`` and are
contractually required to be redacted BY THE PRODUCER before publication.

Producers and consumers
-----------------------
Producer: ``Adaptix-Billing-Service`` migration subsystem
(``backend/billing_app/api/migration_intelligence_routes.py``,
``backend/billing_app/services/migration/``) and ``Adaptix-Imports-Service``
for source ingest/profiling. Consumers: the Billing migration cockpit in
``Adaptix-Web-App``, ``Adaptix-Audit-Service`` for the evidence trail, and
``Adaptix-Finance-Service`` for AR continuity.

Event-bus status — READ THIS BEFORE PUBLISHING
----------------------------------------------
At ``origin/main`` the migration subsystem publishes **nothing** to the Adaptix
event bus: its ``event_type`` strings are written to
``billing_migration_audit_events.event_type`` rows through the local
``_audit_migration_event`` helper
(``api/migration_intelligence_routes.py:128``), and no migration module imports
``EventSchema``/``EventMetadata``. The event models below are therefore the
canonical SHAPES for that publication, but the event types are **not yet
registered** in ``adaptix_contracts.events.registry.ALL_EVENTS``. Publishing one
through the operational envelope will fail
``assert_event_type_registered`` until registration lands together with a real
producer file citation. Registration is deliberately not done here: the
registry requires evidence of a live publisher, and no migration publisher
exists yet.

``MigrationCreated.event_type`` reuses the live audit vocabulary value
``"migration.created"`` (emitted at
``api/migration_intelligence_routes.py:201``) because it marks the same act.
The remaining event types are new strings in the ``migration.*`` namespace
rather than being force-mapped onto differently-scoped legacy audit rows such as
``"migration.batch_uploaded"`` (``:300``) or ``"migration.field_mapped"``
(``:867``).
"""
# Pydantic schema DTOs intentionally expose fields, not behavior.
# pylint: disable=too-few-public-methods

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Optional

from pydantic import BaseModel, Field

# The migration source vendor vocabulary is already canonical in this package.
# It is reused rather than duplicated: Stedi is the only live clearinghouse, and
# every value below is a migration/import source only, never a submission target.
from .billing_contracts import MigrationSourceVendor

#: Contract revision that shipped this module. Stamped on records so a consumer
#: can tell which contract release produced a payload it is replaying.
MIGRATION_CONTRACT_SCHEMA_VERSION = "2.9.0"


# ---------------------------------------------------------------------------
# Shared field types
# ---------------------------------------------------------------------------

#: Signed integer cents. ``strict`` so ``100.0`` (and every other float) is
#: REJECTED instead of being coerced. A lax ``int`` field accepts a float whose
#: fractional part is zero, which is exactly how a rounding defect enters a
#: financial migration unnoticed. Signed because reconciliation differences and
#: reversals are legitimately negative.
MigrationMoneyCents = Annotated[int, Field(strict=True)]

#: Integer cents constrained to be non-negative, for totals that cannot be
#: negative (charges, balances, file-level sums).
MigrationNonNegativeCents = Annotated[int, Field(strict=True, ge=0)]

#: Model/rule confidence, always normalized to 0.0-1.0 inclusive. The live
#: mapping path stores the raw Cortex value unbounded and lets it be ``None``
#: (``api/migration_intelligence_routes.py:835``); this bound is the contract
#: fix, and absence must be expressed as ``None``, never as ``0.0``.
MigrationConfidence = Annotated[float, Field(ge=0.0, le=1.0)]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MigrationState(str, Enum):
    """Canonical lifecycle state of a billing-vendor migration.

    This is the cross-service state a migration is IN. It is not a replacement
    for the per-table legacy status columns listed in the module docstring;
    services map their local column onto this value when they publish.
    """

    DRAFT = "draft"
    SOURCE_CONNECTING = "source_connecting"
    SOURCE_READY = "source_ready"
    INGESTING = "ingesting"
    QUARANTINED = "quarantined"
    PROFILING = "profiling"
    MAPPING_PROPOSED = "mapping_proposed"
    MAPPING_REVIEW = "mapping_review"
    DRY_RUN = "dry_run"
    RECONCILING = "reconciling"
    EXCEPTIONS_BLOCKING = "exceptions_blocking"
    READY_FOR_CUTOVER = "ready_for_cutover"
    CUTOVER_APPROVED = "cutover_approved"
    INITIAL_PROMOTION = "initial_promotion"
    DELTA_SYNC = "delta_sync"
    OPEN_AR_ACTIVE = "open_ar_active"
    HISTORY_BACKFILL = "history_backfill"
    POST_CUTOVER_MONITORING = "post_cutover_monitoring"
    FINAL_RECONCILIATION = "final_reconciliation"
    SIGNOFF_PENDING = "signoff_pending"
    COMPLETED = "completed"
    PAUSED = "paused"
    ROLLBACK_PENDING = "rollback_pending"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class MigrationEraState(str, Enum):
    """Lifecycle of a migrated ERA/835 remittance through matching and posting.

    Tracked separately from :class:`MigrationState` because remittance for
    pre-cutover dates of service keeps arriving from the legacy payer connection
    long after the migration itself reaches ``OPEN_AR_ACTIVE``. A migration is
    not finished because its ERAs are; an ERA is not unposted because the
    migration is still running.

    ``UNAPPLIED`` is cash received that could not be attached to a claim — it is
    money the agency holds, not money it earned, and it must never be reported
    as revenue. ``REVERSAL_PENDING``/``REVERSED`` exist because posted money is
    corrected by an offsetting entry, never by mutating the original.
    """

    ERA_DISCOVERED = "era_discovered"
    ERA_RETRIEVING = "era_retrieving"
    ERA_RECEIVED = "era_received"
    ERA_PARSED = "era_parsed"
    MATCHING = "matching"
    MATCHED = "matched"
    POSTING_READY = "posting_ready"
    POSTING = "posting"
    POSTED = "posted"
    PARTIALLY_POSTED = "partially_posted"
    UNAPPLIED = "unapplied"
    REVERSAL_PENDING = "reversal_pending"
    REVERSED = "reversed"
    RECONCILIATION_EXCEPTION = "reconciliation_exception"
    MANUAL_REVIEW = "manual_review"
    CLOSED = "closed"


class MappingDecisionLevel(str, Enum):
    """How much authority a proposed field mapping carries.

    Deterministic rules authorize; models only recommend. ``AUTO_DETERMINISTIC``
    is a mapping a rule proved (exact source/target agreement); it may apply
    without a human. ``AUTO_MODEL_PLUS_RULES`` is a model suggestion that passed
    deterministic guardrails and may auto-apply only when the proposal also sets
    ``auto_approve_allowed``. ``REVIEW_REQUIRED`` must be shown to an operator.
    ``BLOCKED`` must not be applied at all — it is evidence the migration cannot
    proceed on this field yet.

    The live subsystem has no equivalent: its ``mapping_state`` column
    (``models/migration_staging.py:36-41``) records ``unmapped`` /
    ``ai_suggested`` / ``operator_mapped`` / ``ready``, which is *who touched the
    field*, not *what authority the proposal has*.
    """

    AUTO_DETERMINISTIC = "auto_deterministic"
    AUTO_MODEL_PLUS_RULES = "auto_model_plus_rules"
    REVIEW_REQUIRED = "review_required"
    BLOCKED = "blocked"


class MigrationExceptionCategory(str, Enum):
    """Why a migration record could not be moved cleanly.

    Exceptions are grouped by category so an operator resolves a class of
    defects once rather than a row at a time. ``SOURCE_VENDOR_DEFECT`` records
    that the legacy export itself is wrong — the customer's data is not at
    fault and the fix is a re-export, not a mapping change.
    """

    SOURCE_FIELD_MISSING = "source_field_missing"
    MAPPING_MISMATCH = "mapping_mismatch"
    CODE_CROSSWALK_MISSING = "code_crosswalk_missing"
    IDENTIFIER_COLLISION = "identifier_collision"
    ORPHAN_RELATIONSHIP = "orphan_relationship"
    INVALID_DATE_OR_AMOUNT = "invalid_date_or_amount"
    FINANCIAL_IMBALANCE = "financial_imbalance"
    UNSUPPORTED_STATE = "unsupported_state"
    DUPLICATE = "duplicate"
    TRUNCATED_EXPORT = "truncated_export"
    SOURCE_VENDOR_DEFECT = "source_vendor_defect"


class MigrationReconciliationStatus(str, Enum):
    """Outcome of a single reconciliation control.

    Named with the ``Migration`` prefix because ``ReconciliationStatus`` is
    already taken by the finance domain in this package and the two are not the
    same vocabulary.

    ``NOT_RUN`` is distinct from ``BALANCED``: a control that never executed has
    proven nothing, and must never be rendered as a pass.
    """

    NOT_RUN = "not_run"
    BALANCED = "balanced"
    WITHIN_TOLERANCE = "within_tolerance"
    OUT_OF_BALANCE = "out_of_balance"
    BLOCKED = "blocked"


class MigrationErrorCode(str, Enum):
    """Machine-readable failure taxonomy for the migration subsystem.

    The migration path currently has no taxonomy at all: per-row failures are
    persisted as free text
    (``row.commit_error = f"{type(exc).__name__}: {exc}"`` at
    ``api/migration_intelligence_routes.py:621, 664, 709``), which cannot be
    counted, alerted on, or retried by class. These codes are the replacement.

    Values are lowercase snake_case, matching the domain enums in this package
    (``ClaimStatus``, ``SubmissionStatus``). They are deliberately NOT merged
    into ``adaptix_contracts.error_contracts.ErrorCode``, whose eight
    UPPERCASE values are the HTTP-envelope vocabulary for every Adaptix API;
    this enum is the migration-domain diagnosis carried INSIDE that envelope.
    """

    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    TENANT_MISMATCH = "tenant_mismatch"
    INVALID_STATE_TRANSITION = "invalid_state_transition"
    OPTIMISTIC_CONFLICT = "optimistic_conflict"
    DUPLICATE_IDEMPOTENT_REPLAY = "duplicate_idempotent_replay"
    VALIDATION = "validation"
    SOURCE_CORRUPTION = "source_corruption"
    UNSUPPORTED_FORMAT = "unsupported_format"
    MAPPING_AMBIGUITY = "mapping_ambiguity"
    FINANCIAL_IMBALANCE = "financial_imbalance"
    STEDI_AUTH = "stedi_auth"
    STEDI_RATE_LIMIT = "stedi_rate_limit"
    STEDI_VALIDATION = "stedi_validation"
    STEDI_UNAVAILABLE = "stedi_unavailable"
    SAGEMAKER_UNAVAILABLE = "sagemaker_unavailable"
    MODEL_GUARDRAIL = "model_guardrail"
    TEMPORAL_DELAYED = "temporal_delayed"
    DATABASE_TRANSIENT = "database_transient"
    DATABASE_PERMANENT = "database_permanent"
    OBJECT_STORE = "object_store"
    QUEUE_DLQ = "queue_dlq"
    INTERNAL_INVARIANT = "internal_invariant"


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

#: Legal next states for every :class:`MigrationState`.
#:
#: Reading the graph:
#:
#: * The happy path is DRAFT -> SOURCE_CONNECTING -> SOURCE_READY -> INGESTING
#:   -> PROFILING -> MAPPING_PROPOSED -> MAPPING_REVIEW -> DRY_RUN ->
#:   RECONCILING -> READY_FOR_CUTOVER -> CUTOVER_APPROVED -> INITIAL_PROMOTION
#:   -> DELTA_SYNC -> OPEN_AR_ACTIVE -> HISTORY_BACKFILL ->
#:   POST_CUTOVER_MONITORING -> FINAL_RECONCILIATION -> SIGNOFF_PENDING ->
#:   COMPLETED.
#: * ``EXCEPTIONS_BLOCKING`` is entered whenever a dry run, a reconciliation, or
#:   a post-cutover check finds blocking defects, and exits BACKWARD into
#:   remapping — never forward into cutover.
#: * No pre-cutover PIPELINE state has a direct edge to ``ROLLBACK_PENDING``:
#:   rolling back before anything was promoted is meaningless, and that case
#:   fails or returns to mapping instead. This is NOT the same as saying
#:   rollback is unreachable before cutover. ``EXCEPTIONS_BLOCKING`` and
#:   ``PAUSED`` both carry a rollback edge and both can be entered before OR
#:   after cutover, so ``DRY_RUN -> EXCEPTIONS_BLOCKING -> ROLLBACK_PENDING``
#:   is a legal walk. Those edges are deliberate — post-cutover exceptions must
#:   be able to roll back, and removing ``PAUSED -> ROLLBACK_PENDING`` would
#:   strand any rollback that gets paused.
#:
#:   A pairwise guard cannot see history, so it cannot enforce "something was
#:   actually promoted". Services MUST gate rollback on a recorded promotion
#:   fact — an established :class:`CutoverWatermark` — and treat this edge set
#:   as necessary but not sufficient.
#: * ``PAUSED`` is reachable from every interruptible state and returns to the
#:   same set. The record's own ``paused_from_state`` carries the resume target;
#:   the guard only proves the target is a legal place to be.
#: * ``COMPLETED`` and ``ROLLED_BACK`` are terminal (empty frozensets).
#: * ``FAILED`` retains a single retry edge back to ``DRAFT``, mirroring the
#:   live subsystem's ``"failed": ["pending"]`` edge
#:   (``services/migration/migration_service.py:38``).
#:
#: A state is never its own legal successor: re-writing the current state is a
#: no-op, not an advance, and must not pass the guard.
MIGRATION_STATE_TRANSITIONS: dict[MigrationState, frozenset[MigrationState]] = {
    MigrationState.DRAFT: frozenset(
        {
            MigrationState.SOURCE_CONNECTING,
            MigrationState.PAUSED,
            MigrationState.FAILED,
        }
    ),
    MigrationState.SOURCE_CONNECTING: frozenset(
        {
            MigrationState.SOURCE_READY,
            MigrationState.PAUSED,
            MigrationState.FAILED,
        }
    ),
    MigrationState.SOURCE_READY: frozenset(
        {
            MigrationState.INGESTING,
            MigrationState.PAUSED,
            MigrationState.FAILED,
        }
    ),
    MigrationState.INGESTING: frozenset(
        {
            MigrationState.PROFILING,
            MigrationState.QUARANTINED,
            MigrationState.PAUSED,
            MigrationState.FAILED,
        }
    ),
    MigrationState.QUARANTINED: frozenset(
        {
            MigrationState.INGESTING,
            MigrationState.PAUSED,
            MigrationState.FAILED,
        }
    ),
    MigrationState.PROFILING: frozenset(
        {
            MigrationState.MAPPING_PROPOSED,
            MigrationState.PAUSED,
            MigrationState.FAILED,
        }
    ),
    MigrationState.MAPPING_PROPOSED: frozenset(
        {
            MigrationState.MAPPING_REVIEW,
            MigrationState.PAUSED,
            MigrationState.FAILED,
        }
    ),
    MigrationState.MAPPING_REVIEW: frozenset(
        {
            MigrationState.MAPPING_PROPOSED,
            MigrationState.DRY_RUN,
            MigrationState.PAUSED,
            MigrationState.FAILED,
        }
    ),
    MigrationState.DRY_RUN: frozenset(
        {
            MigrationState.RECONCILING,
            MigrationState.EXCEPTIONS_BLOCKING,
            MigrationState.PAUSED,
            MigrationState.FAILED,
        }
    ),
    MigrationState.RECONCILING: frozenset(
        {
            MigrationState.READY_FOR_CUTOVER,
            MigrationState.EXCEPTIONS_BLOCKING,
            MigrationState.PAUSED,
            MigrationState.FAILED,
        }
    ),
    MigrationState.EXCEPTIONS_BLOCKING: frozenset(
        {
            MigrationState.MAPPING_REVIEW,
            MigrationState.DRY_RUN,
            MigrationState.ROLLBACK_PENDING,
            MigrationState.PAUSED,
            MigrationState.FAILED,
        }
    ),
    MigrationState.READY_FOR_CUTOVER: frozenset(
        {
            MigrationState.CUTOVER_APPROVED,
            MigrationState.EXCEPTIONS_BLOCKING,
            MigrationState.PAUSED,
            MigrationState.FAILED,
        }
    ),
    MigrationState.CUTOVER_APPROVED: frozenset(
        {
            MigrationState.INITIAL_PROMOTION,
            MigrationState.ROLLBACK_PENDING,
            MigrationState.PAUSED,
            MigrationState.FAILED,
        }
    ),
    MigrationState.INITIAL_PROMOTION: frozenset(
        {
            MigrationState.DELTA_SYNC,
            MigrationState.ROLLBACK_PENDING,
            MigrationState.PAUSED,
            MigrationState.FAILED,
        }
    ),
    MigrationState.DELTA_SYNC: frozenset(
        {
            MigrationState.OPEN_AR_ACTIVE,
            MigrationState.ROLLBACK_PENDING,
            MigrationState.PAUSED,
            MigrationState.FAILED,
        }
    ),
    MigrationState.OPEN_AR_ACTIVE: frozenset(
        {
            MigrationState.HISTORY_BACKFILL,
            MigrationState.POST_CUTOVER_MONITORING,
            MigrationState.ROLLBACK_PENDING,
            MigrationState.PAUSED,
            MigrationState.FAILED,
        }
    ),
    MigrationState.HISTORY_BACKFILL: frozenset(
        {
            MigrationState.POST_CUTOVER_MONITORING,
            MigrationState.ROLLBACK_PENDING,
            MigrationState.PAUSED,
            MigrationState.FAILED,
        }
    ),
    MigrationState.POST_CUTOVER_MONITORING: frozenset(
        {
            MigrationState.FINAL_RECONCILIATION,
            MigrationState.EXCEPTIONS_BLOCKING,
            MigrationState.ROLLBACK_PENDING,
            MigrationState.PAUSED,
            MigrationState.FAILED,
        }
    ),
    MigrationState.FINAL_RECONCILIATION: frozenset(
        {
            MigrationState.SIGNOFF_PENDING,
            MigrationState.EXCEPTIONS_BLOCKING,
            MigrationState.ROLLBACK_PENDING,
            MigrationState.PAUSED,
            MigrationState.FAILED,
        }
    ),
    MigrationState.SIGNOFF_PENDING: frozenset(
        {
            MigrationState.COMPLETED,
            MigrationState.EXCEPTIONS_BLOCKING,
            MigrationState.ROLLBACK_PENDING,
            MigrationState.PAUSED,
            MigrationState.FAILED,
        }
    ),
    MigrationState.COMPLETED: frozenset(),
    MigrationState.PAUSED: frozenset(
        {
            MigrationState.DRAFT,
            MigrationState.SOURCE_CONNECTING,
            MigrationState.SOURCE_READY,
            MigrationState.INGESTING,
            MigrationState.QUARANTINED,
            MigrationState.PROFILING,
            MigrationState.MAPPING_PROPOSED,
            MigrationState.MAPPING_REVIEW,
            MigrationState.DRY_RUN,
            MigrationState.RECONCILING,
            MigrationState.EXCEPTIONS_BLOCKING,
            MigrationState.READY_FOR_CUTOVER,
            MigrationState.CUTOVER_APPROVED,
            MigrationState.INITIAL_PROMOTION,
            MigrationState.DELTA_SYNC,
            MigrationState.OPEN_AR_ACTIVE,
            MigrationState.HISTORY_BACKFILL,
            MigrationState.POST_CUTOVER_MONITORING,
            MigrationState.FINAL_RECONCILIATION,
            MigrationState.SIGNOFF_PENDING,
            MigrationState.ROLLBACK_PENDING,
            MigrationState.FAILED,
        }
    ),
    MigrationState.ROLLBACK_PENDING: frozenset(
        {
            MigrationState.ROLLING_BACK,
            MigrationState.PAUSED,
            MigrationState.FAILED,
        }
    ),
    MigrationState.ROLLING_BACK: frozenset(
        {
            MigrationState.ROLLED_BACK,
            MigrationState.FAILED,
        }
    ),
    MigrationState.ROLLED_BACK: frozenset(),
    MigrationState.FAILED: frozenset({MigrationState.DRAFT}),
}

#: States from which no further transition is legal.
MIGRATION_TERMINAL_STATES: frozenset[MigrationState] = frozenset(
    {MigrationState.COMPLETED, MigrationState.ROLLED_BACK}
)


def is_legal_migration_transition(
    current: MigrationState | str,
    target: MigrationState | str,
) -> bool:
    """Return whether ``current`` -> ``target`` is a legal migration transition.

    Pure: no I/O, no clock, no tenant lookup. The caller still owns
    authorization and tenant scoping — a legal edge is not permission to take
    it.

    Accepts enum members or their wire strings so an API boundary can check a
    request body before parsing it into a model. Anything that is not a known
    :class:`MigrationState` value returns ``False`` rather than raising: an
    unrecognized state must fail CLOSED, never fall through to "allowed".

    Self-transitions return ``False``. Re-writing the state a record already
    holds is a no-op, not an advance.
    """

    try:
        current_state = MigrationState(current)
        target_state = MigrationState(target)
    except ValueError:
        return False

    return target_state in MIGRATION_STATE_TRANSITIONS.get(current_state, frozenset())


# ---------------------------------------------------------------------------
# Source and lineage contracts
# ---------------------------------------------------------------------------


class MigrationSourceFile(BaseModel):
    """One physical file received from the legacy vendor.

    This is the lineage root. The ranked #1 migration-capability gap recorded in
    the 2026-08-16 discovery evidence is that raw vendor files are not archived
    with a hash for format jobs (``FormatImportJob.source_s3_key`` is always
    ``None``), so a migrated balance cannot be traced back to the bytes it came
    from. ``file_hash_sha256`` plus ``object_store_key`` close that gap: the
    hash proves WHICH bytes were parsed, and the key proves they were kept.

    ``quarantine_reason`` being set is what puts a migration into
    ``MigrationState.QUARANTINED``. A quarantined file has NOT been rejected
    forever — the state machine allows re-ingest after remediation.

    ``original_filename`` is vendor-supplied text and must be treated as
    untrusted: never render it as HTML, never use it as a filesystem path.
    """

    tenant_id: str
    source_file_id: Optional[str] = None
    migration_id: Optional[str] = None

    original_filename: Optional[str] = None
    content_type: Optional[str] = None

    # Lowercase hex SHA-256 of the exact bytes received. The live subsystem
    # already carries this as ``file_checksum_sha256``
    # (``models/migration_imports.py:167``); typing it here makes it a contract
    # rather than an optional convention.
    file_hash_sha256: Optional[str] = Field(default=None, min_length=64, max_length=64)
    byte_size: Optional[int] = Field(default=None, ge=0)

    object_store_key: Optional[str] = None
    received_at: Optional[datetime] = None

    quarantine_reason: Optional[str] = None
    quarantined_at: Optional[datetime] = None

    schema_version: str = MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None
    record_version: Optional[int] = Field(default=None, ge=0)


class SourceSchemaFingerprint(BaseModel):
    """Structural identity of a source export, independent of its contents.

    Two exports with the same fingerprint can reuse the same mapping; a changed
    fingerprint mid-migration means the vendor altered the export and every
    prior mapping decision must be revalidated. ``column_names`` is structure,
    not data — it must never be populated with row values.

    ``fingerprint_sha256`` is computed over the ordered column names and the
    declared delimiter/encoding, so it is stable across row counts.
    """

    tenant_id: str
    fingerprint_id: Optional[str] = None
    migration_id: Optional[str] = None
    source_file_id: Optional[str] = None

    entity_hint: Optional[str] = None
    fingerprint_sha256: Optional[str] = Field(
        default=None, min_length=64, max_length=64
    )

    column_names: list[str] = Field(default_factory=list)
    column_count: Optional[int] = Field(default=None, ge=0)
    row_count: Optional[int] = Field(default=None, ge=0)

    delimiter: Optional[str] = None
    encoding: Optional[str] = None
    detected_at: Optional[datetime] = None

    schema_version: str = MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None
    record_version: Optional[int] = Field(default=None, ge=0)


class VendorProfileRef(BaseModel):
    """Pointer to the versioned vendor export profile used for a migration.

    Vendor profiles do not exist as data in the live system — the discovery
    evidence records three hardcoded CSV column maps and a dead
    ``import_field_mappings`` table, with no mapping-version-per-job. That means
    a mapping cannot be reproduced after the code changes. ``profile_version``
    is the fix: it pins WHICH profile revision produced a mapping, so a
    reconciliation run months later can be explained.

    ``vendor`` reuses the canonical :class:`MigrationSourceVendor` vocabulary.
    Every member of that enum is an import/source system only. Nothing here
    authorizes claim submission through a legacy vendor; Stedi is the sole live
    clearinghouse.
    """

    tenant_id: str
    vendor: Optional[MigrationSourceVendor] = None
    product: Optional[str] = None
    export_version: Optional[str] = None
    profile_version: Optional[str] = None

    profile_id: Optional[str] = None
    resolved_at: Optional[datetime] = None

    schema_version: str = MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None
    record_version: Optional[int] = Field(default=None, ge=0)


# ---------------------------------------------------------------------------
# Mapping contracts
# ---------------------------------------------------------------------------


class FieldMappingProposal(BaseModel):
    """A proposed mapping of one source field onto one canonical field.

    This is the typed replacement for the untyped JSON blob the live system
    writes at ``api/migration_intelligence_routes.py:847-853``, where
    ``confidence`` is stored raw from the Cortex response
    (``data.get("confidence")``, ``:835``), unbounded and nullable, inside
    ``mapped_fields_json``. Untyped, it cannot be sorted, thresholded, or
    audited.

    Authority rules the consumer MUST enforce:

    * ``decision_level`` is the authority; ``confidence`` alone never authorizes
      anything. A high score on a ``REVIEW_REQUIRED`` proposal is still review.
    * ``auto_approve_allowed`` defaults to ``False`` so an omitted value fails
      CLOSED toward human review.
    * ``downstream_financial_impact`` marks a field that changes money or payer
      routing. A proposal with financial impact must not auto-apply regardless
      of confidence.

    ``evidence_masked_examples`` exists so an operator can see WHY a mapping was
    proposed. The producer MUST redact before publishing — values are masked
    source samples, never live patient or subscriber data.
    """

    tenant_id: str
    proposal_id: Optional[str] = None
    migration_id: Optional[str] = None

    source_field: Optional[str] = None
    canonical_entity: Optional[str] = None
    canonical_field: Optional[str] = None

    # Declarative transform identifier (e.g. a named normalizer), not code.
    transform: Optional[str] = None

    confidence: Optional[MigrationConfidence] = None
    reason_codes: list[str] = Field(default_factory=list)
    decision_level: Optional[MappingDecisionLevel] = None

    evidence_masked_examples: list[str] = Field(default_factory=list)

    downstream_financial_impact: bool = False
    auto_approve_allowed: bool = False

    proposed_at: Optional[datetime] = None
    vendor_profile: Optional[VendorProfileRef] = None

    schema_version: str = MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None
    record_version: Optional[int] = Field(default=None, ge=0)


# ---------------------------------------------------------------------------
# Reconciliation contracts
# ---------------------------------------------------------------------------


class ReconciliationControl(BaseModel):
    """One financial or volumetric control comparing source to production.

    No reconciliation control exists in the live migration subsystem. The
    discovery evidence is explicit: reconciliation there is self-referential
    (job metadata against itself), with no source-vs-target comparison and no
    financial balancing anywhere. A migration that cannot prove the money
    arrived is not a migration; it is a data copy.

    Three-way by design: ``source_value_cents`` is what the legacy vendor said,
    ``canonical_value_cents`` is what Adaptix parsed and staged, and
    ``production_value_cents`` is what actually landed in live billing tables.
    Comparing only source to production hides a staging defect that a later
    re-run would silently repeat.

    ``difference_cents`` is SIGNED and deliberately carries no ``ge``
    constraint: a negative variance (production below source) is the direction
    that loses an agency money and must be representable.

    Count controls use the ``*_count`` fields; money controls use the
    ``*_cents`` fields. A control may populate either or both.
    """

    tenant_id: str
    control_id: Optional[str] = None
    migration_id: Optional[str] = None

    control_name: Optional[str] = None

    source_value_cents: Optional[MigrationMoneyCents] = None
    canonical_value_cents: Optional[MigrationMoneyCents] = None
    production_value_cents: Optional[MigrationMoneyCents] = None
    difference_cents: Optional[MigrationMoneyCents] = None

    source_value_count: Optional[int] = Field(default=None, ge=0)
    canonical_value_count: Optional[int] = Field(default=None, ge=0)
    production_value_count: Optional[int] = Field(default=None, ge=0)
    difference_count: Optional[int] = None

    tolerance_cents: Optional[MigrationNonNegativeCents] = None
    status: Optional[MigrationReconciliationStatus] = None

    evaluated_at: Optional[datetime] = None

    schema_version: str = MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None
    record_version: Optional[int] = Field(default=None, ge=0)


class ReconciliationRunResult(BaseModel):
    """Outcome of one reconciliation pass over a migration.

    ``overall_status`` is the WORST control status in ``controls``, not an
    average: one out-of-balance control fails the run. A run whose
    ``overall_status`` is ``OUT_OF_BALANCE`` is what drives a migration into
    ``MigrationState.EXCEPTIONS_BLOCKING``; it must never be summarized as a
    pass because most controls balanced.
    """

    tenant_id: str
    run_id: Optional[str] = None
    migration_id: Optional[str] = None

    controls: list[ReconciliationControl] = Field(default_factory=list)
    overall_status: Optional[MigrationReconciliationStatus] = None

    controls_evaluated: Optional[int] = Field(default=None, ge=0)
    controls_out_of_balance: Optional[int] = Field(default=None, ge=0)
    total_absolute_difference_cents: Optional[MigrationNonNegativeCents] = None

    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    schema_version: str = MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None
    record_version: Optional[int] = Field(default=None, ge=0)


# ---------------------------------------------------------------------------
# Exception contracts
# ---------------------------------------------------------------------------


class MigrationExceptionGroup(BaseModel):
    """A class of migration defects, grouped so it is resolved once.

    ``affected_dollar_cents`` is what makes an exception rankable: 40,000 rows
    worth $12 do not outrank 3 rows worth $180,000. It is signed integer cents
    for the same reason as :class:`ReconciliationControl` — an exception can
    represent money missing in either direction.

    ``proposed_correction`` is a description of the fix, never an instruction
    that a consumer executes automatically. ``revalidation_impact`` states what
    must be re-run if the correction is applied, so an operator is not surprised
    by a second dry run.

    ``representative_masked_examples`` MUST be redacted by the producer. These
    are illustrative samples for an operator, and they leave the migration
    boundary — no PHI, no subscriber identifiers, no account numbers.
    """

    tenant_id: str
    group_id: Optional[str] = None
    migration_id: Optional[str] = None

    category: Optional[MigrationExceptionCategory] = None

    affected_record_count: Optional[int] = Field(default=None, ge=0)
    affected_dollar_cents: Optional[MigrationMoneyCents] = None

    representative_masked_examples: list[str] = Field(default_factory=list)

    proposed_correction: Optional[str] = None
    confidence: Optional[MigrationConfidence] = None
    revalidation_impact: Optional[str] = None

    blocking: bool = True
    first_seen_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    schema_version: str = MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None
    record_version: Optional[int] = Field(default=None, ge=0)


# ---------------------------------------------------------------------------
# Cutover contracts
# ---------------------------------------------------------------------------


class CutoverWatermark(BaseModel):
    """The boundary that decides which system owns a record.

    Everything at or before ``watermark_at`` belongs to the legacy vendor's
    reporting; everything after belongs to Adaptix. Without a recorded
    watermark, delta sync either double-counts the overlap or drops it, and
    neither is detectable afterward.

    ``last_source_record_id`` pins the exact final record consumed from the
    source so a resumed delta sync restarts from a row, not from a timestamp
    that ties.
    """

    tenant_id: str
    watermark_id: Optional[str] = None
    migration_id: Optional[str] = None

    entity: Optional[str] = None
    watermark_at: Optional[datetime] = None
    last_source_record_id: Optional[str] = None

    records_before_watermark: Optional[int] = Field(default=None, ge=0)
    open_ar_balance_cents: Optional[MigrationMoneyCents] = None

    established_at: Optional[datetime] = None

    schema_version: str = MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None
    record_version: Optional[int] = Field(default=None, ge=0)


class MigrationSignoff(BaseModel):
    """Named human acceptance of a migration outcome.

    A migration is complete when a person accepts it, not when a job finishes.
    ``signed_by_user_id`` is required in practice for a valid sign-off; it is
    Optional here only so a partially-built record round-trips through the
    contract layer, and a consumer MUST reject a sign-off without it.

    ``accepted_variance_cents`` records that the signer knowingly accepted a
    residual difference. Its presence is the audit answer to "who agreed the
    books were off by this much".
    """

    tenant_id: str
    signoff_id: Optional[str] = None
    migration_id: Optional[str] = None

    signed_by_user_id: Optional[str] = None
    signed_by_role: Optional[str] = None
    signed_at: Optional[datetime] = None

    reconciliation_run_id: Optional[str] = None
    accepted_variance_cents: Optional[MigrationMoneyCents] = None
    outstanding_exception_group_ids: list[str] = Field(default_factory=list)

    statement: Optional[str] = None

    schema_version: str = MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None
    record_version: Optional[int] = Field(default=None, ge=0)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MigrationError(BaseModel):
    """A typed migration failure, safe to show and useful to diagnose.

    Two message fields on purpose. ``user_safe_message`` is what an operator
    reads and MUST contain no PHI, no credentials, and no stack content.
    ``operator_diagnostic`` carries the technical detail for the engineer and
    still must not carry PHI or secrets — it is persisted and exported.

    ``retryable`` defaults to ``False`` so an unclassified failure is never
    retried by default. Retrying a non-idempotent financial operation because a
    field was omitted is worse than stopping.
    """

    code: MigrationErrorCode
    retryable: bool = False

    user_safe_message: Optional[str] = None
    operator_diagnostic: Optional[str] = None

    correlation_id: Optional[str] = None

    # Optional here alone among these contracts, deliberately: an
    # ``AUTHENTICATION`` or ``TENANT_MISMATCH`` failure occurs BEFORE a tenant
    # is resolved, and a model that demanded the tenant would be unable to
    # describe the two failures that matter most for tenant isolation.
    tenant_id: Optional[str] = None

    migration_id: Optional[str] = None
    occurred_at: Optional[datetime] = None

    schema_version: str = MIGRATION_CONTRACT_SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------
#
# ``tenant_id`` is REQUIRED on every event below. The Core relay refuses
# tenant-less events, so a payload without it can never reach the bus; making
# the field mandatory here keeps the producer honest at validation time instead
# of at relay time. Every other field is optional so a producer that has not yet
# collected a fact emits a valid event rather than raising inside a consumer's
# ``except`` block — the exact defect recorded for ``epcr.chart.finalized`` in
# CHANGELOG 2.5.0.
#
# None of these event types is registered in
# ``adaptix_contracts.events.registry.ALL_EVENTS`` yet. See the module docstring.


class MigrationCreated(BaseModel):
    """Published when a migration record is created.

    ``event_type`` matches the value the live audit writer already persists at
    ``api/migration_intelligence_routes.py:201`` for the same act, so the bus
    event and the audit row share one vocabulary.
    """

    event_type: str = "migration.created"

    tenant_id: str
    migration_id: Optional[str] = None
    agency_id: Optional[str] = None

    vendor: Optional[MigrationSourceVendor] = None
    legacy_vendor_name: Optional[str] = None
    connection_type: Optional[str] = None

    state: Optional[MigrationState] = None
    initiated_by: Optional[str] = None
    created_at: Optional[datetime] = None

    schema_version: str = MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None


class SourceRegistered(BaseModel):
    """Published when a legacy source connection is registered and reachable."""

    event_type: str = "migration.source.registered"

    tenant_id: str
    migration_id: Optional[str] = None

    vendor_profile: Optional[VendorProfileRef] = None
    connection_type: Optional[str] = None
    state: Optional[MigrationState] = None
    registered_at: Optional[datetime] = None

    schema_version: str = MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None


class SourceFileLanded(BaseModel):
    """Published when a source file is received and hashed.

    Distinct from the legacy ``"migration.batch_uploaded"`` audit row
    (``api/migration_intelligence_routes.py:300``), which records an operator
    upload action against a batch. This event records that specific BYTES
    arrived and were fingerprinted, which is the lineage fact.
    """

    event_type: str = "migration.source.file_landed"

    tenant_id: str
    migration_id: Optional[str] = None

    source_file: Optional[MigrationSourceFile] = None
    quarantined: bool = False
    landed_at: Optional[datetime] = None

    schema_version: str = MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None


class SourceProfiled(BaseModel):
    """Published when a source export has been structurally profiled."""

    event_type: str = "migration.source.profiled"

    tenant_id: str
    migration_id: Optional[str] = None

    fingerprint: Optional[SourceSchemaFingerprint] = None
    entities_detected: list[str] = Field(default_factory=list)
    profiled_at: Optional[datetime] = None

    schema_version: str = MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None


class MappingProposed(BaseModel):
    """Published when a mapping proposal set is ready for review.

    ``review_required_count`` and ``blocked_count`` are carried on the event so
    a cockpit can show the review burden without fetching every proposal.
    """

    event_type: str = "migration.mapping.proposed"

    tenant_id: str
    migration_id: Optional[str] = None

    proposal_count: Optional[int] = Field(default=None, ge=0)
    review_required_count: Optional[int] = Field(default=None, ge=0)
    blocked_count: Optional[int] = Field(default=None, ge=0)
    financial_impact_count: Optional[int] = Field(default=None, ge=0)

    vendor_profile: Optional[VendorProfileRef] = None
    proposed_at: Optional[datetime] = None

    schema_version: str = MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None


class MappingApproved(BaseModel):
    """Published when a mapping set is approved for a dry run.

    ``approved_by_user_id`` is the accountable human. An approval event without
    it must be treated by consumers as unattributed and not used as evidence of
    review.
    """

    event_type: str = "migration.mapping.approved"

    tenant_id: str
    migration_id: Optional[str] = None

    approved_by_user_id: Optional[str] = None
    approved_proposal_count: Optional[int] = Field(default=None, ge=0)
    auto_applied_count: Optional[int] = Field(default=None, ge=0)
    approved_at: Optional[datetime] = None

    schema_version: str = MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None


class DryRunCompleted(BaseModel):
    """Published when a non-committing rehearsal of the migration finishes.

    A dry run writes nothing to live billing tables. ``would_commit_count`` is
    what WOULD have been written, which is the number an operator approves
    against.
    """

    event_type: str = "migration.dry_run.completed"

    tenant_id: str
    migration_id: Optional[str] = None

    would_commit_count: Optional[int] = Field(default=None, ge=0)
    would_commit_total_cents: Optional[MigrationMoneyCents] = None
    exception_group_count: Optional[int] = Field(default=None, ge=0)
    blocking_exception_count: Optional[int] = Field(default=None, ge=0)

    state: Optional[MigrationState] = None
    completed_at: Optional[datetime] = None

    schema_version: str = MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None


class MigrationExceptionRaised(BaseModel):
    """Published when a blocking or notable exception group is raised."""

    event_type: str = "migration.exception.raised"

    tenant_id: str
    migration_id: Optional[str] = None

    exception_group: Optional[MigrationExceptionGroup] = None
    category: Optional[MigrationExceptionCategory] = None
    blocking: bool = True
    raised_at: Optional[datetime] = None

    schema_version: str = MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None


class ReconciliationCompleted(BaseModel):
    """Published when a reconciliation pass finishes.

    Carries ``overall_status`` so a consumer never has to infer balance from a
    count of controls.
    """

    event_type: str = "migration.reconciliation.completed"

    tenant_id: str
    migration_id: Optional[str] = None

    run: Optional[ReconciliationRunResult] = None
    overall_status: Optional[MigrationReconciliationStatus] = None
    total_absolute_difference_cents: Optional[MigrationNonNegativeCents] = None
    completed_at: Optional[datetime] = None

    schema_version: str = MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None


class CutoverApproved(BaseModel):
    """Published when a human authorizes cutover.

    This is the last reversible-by-default moment. After it the migration may
    promote data, and recovery is a rollback rather than an edit.
    """

    event_type: str = "migration.cutover.approved"

    tenant_id: str
    migration_id: Optional[str] = None

    approved_by_user_id: Optional[str] = None
    approved_by_role: Optional[str] = None
    reconciliation_run_id: Optional[str] = None
    watermark: Optional[CutoverWatermark] = None
    approved_at: Optional[datetime] = None

    schema_version: str = MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None


class OpenARActivated(BaseModel):
    """Published when migrated open accounts receivable becomes live in Adaptix.

    This is the moment the agency's collectable money starts being worked in
    Adaptix rather than the legacy vendor. ``open_ar_total_cents`` is the
    balance handed over, and it is the figure every later reconciliation is
    measured against.
    """

    event_type: str = "migration.open_ar.activated"

    tenant_id: str
    migration_id: Optional[str] = None

    open_ar_total_cents: Optional[MigrationMoneyCents] = None
    open_ar_claim_count: Optional[int] = Field(default=None, ge=0)
    watermark: Optional[CutoverWatermark] = None
    activated_at: Optional[datetime] = None

    schema_version: str = MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None


class MigrationCompleted(BaseModel):
    """Published when a migration reaches ``MigrationState.COMPLETED``.

    Emitted only after sign-off. A job finishing is not a migration completing.
    """

    event_type: str = "migration.completed"

    tenant_id: str
    migration_id: Optional[str] = None

    signoff: Optional[MigrationSignoff] = None
    final_reconciliation_run_id: Optional[str] = None
    migrated_claim_count: Optional[int] = Field(default=None, ge=0)
    migrated_total_cents: Optional[MigrationMoneyCents] = None
    completed_at: Optional[datetime] = None

    schema_version: str = MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None


class MigrationRolledBack(BaseModel):
    """Published when a migration has been rolled back.

    ``reversed_total_cents`` is what was withdrawn from live billing. Consumers
    that reported migrated revenue MUST reconcile against this figure; a
    rollback that is not propagated leaves overstated AR in every downstream
    report.
    """

    event_type: str = "migration.rolled_back"

    tenant_id: str
    migration_id: Optional[str] = None

    rolled_back_by_user_id: Optional[str] = None
    reason: Optional[str] = None
    reversed_record_count: Optional[int] = Field(default=None, ge=0)
    reversed_total_cents: Optional[MigrationMoneyCents] = None
    rolled_back_at: Optional[datetime] = None

    schema_version: str = MIGRATION_CONTRACT_SCHEMA_VERSION
    correlation_id: Optional[str] = None
