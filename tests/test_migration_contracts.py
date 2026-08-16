"""Regression tests for the billing-vendor migration contracts.

These tests pin the four properties the migration contract cannot ship without:

1. every state vocabulary round-trips through its wire value,
2. the transition guard accepts only legal edges and fails closed otherwise,
3. money is integer cents and a float is REJECTED, not rounded,
4. every domain event carries ``tenant_id`` and every model validates from a
   minimal payload.

No fixture value in this file is PHI or resembles it. Masked examples are
deliberately obvious placeholders.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

import pytest
from pydantic import BaseModel, ValidationError

from adaptix_contracts.schemas import (
    MIGRATION_CONTRACT_SCHEMA_VERSION,
    MIGRATION_STATE_TRANSITIONS,
    MIGRATION_TERMINAL_STATES,
    CutoverApproved,
    CutoverWatermark,
    DryRunCompleted,
    FieldMappingProposal,
    MappingApproved,
    MappingDecisionLevel,
    MappingProposed,
    MigrationCompleted,
    MigrationCreated,
    MigrationEraState,
    MigrationError,
    MigrationErrorCode,
    MigrationExceptionCategory,
    MigrationExceptionGroup,
    MigrationExceptionRaised,
    MigrationReconciliationStatus,
    MigrationRolledBack,
    MigrationSignoff,
    MigrationSourceFile,
    MigrationSourceVendor,
    MigrationState,
    OpenARActivated,
    ReconciliationCompleted,
    ReconciliationControl,
    ReconciliationRunResult,
    SourceFileLanded,
    SourceProfiled,
    SourceRegistered,
    SourceSchemaFingerprint,
    VendorProfileRef,
    is_legal_migration_transition,
)


def _timestamp() -> datetime:
    """Return a deterministic UTC timestamp for regression tests."""

    return datetime(2026, 8, 16, 12, 0, tzinfo=UTC)


#: Every domain event in the migration contract.
MIGRATION_EVENTS: tuple[tuple[type[BaseModel], str], ...] = (
    (MigrationCreated, "migration.created"),
    (SourceRegistered, "migration.source.registered"),
    (SourceFileLanded, "migration.source.file_landed"),
    (SourceProfiled, "migration.source.profiled"),
    (MappingProposed, "migration.mapping.proposed"),
    (MappingApproved, "migration.mapping.approved"),
    (DryRunCompleted, "migration.dry_run.completed"),
    (MigrationExceptionRaised, "migration.exception.raised"),
    (ReconciliationCompleted, "migration.reconciliation.completed"),
    (CutoverApproved, "migration.cutover.approved"),
    (OpenARActivated, "migration.open_ar.activated"),
    (MigrationCompleted, "migration.completed"),
    (MigrationRolledBack, "migration.rolled_back"),
)

#: Every tenant-scoped record model in the migration contract.
MIGRATION_RECORD_MODELS: tuple[type[BaseModel], ...] = (
    MigrationSourceFile,
    SourceSchemaFingerprint,
    VendorProfileRef,
    FieldMappingProposal,
    ReconciliationControl,
    ReconciliationRunResult,
    MigrationExceptionGroup,
    CutoverWatermark,
    MigrationSignoff,
)

#: Every migration enum, with the vocabulary size the contract fixes.
MIGRATION_ENUMS: tuple[tuple[type[Enum], int], ...] = (
    (MigrationState, 26),
    (MigrationEraState, 16),
    (MappingDecisionLevel, 4),
    (MigrationExceptionCategory, 11),
    (MigrationReconciliationStatus, 5),
    (MigrationErrorCode, 23),
)


# ---------------------------------------------------------------------------
# Enum round-trips
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("enum_type", "expected_size"), MIGRATION_ENUMS)
def test_every_state_enum_round_trips(
    enum_type: type[Enum], expected_size: int
) -> None:
    """Each enum member must survive a value -> member -> value round-trip."""

    assert len(list(enum_type)) == expected_size
    for member in enum_type:
        assert isinstance(member.value, str)
        assert enum_type(member.value) is member
        assert str(member.value) == member.value


@pytest.mark.parametrize(("enum_type", "_expected_size"), MIGRATION_ENUMS)
def test_enum_values_are_unique_and_snake_case(
    enum_type: type[Enum], _expected_size: int
) -> None:
    """Ambiguous or shouty wire values break cross-service consumers."""

    values = [member.value for member in enum_type]
    assert len(values) == len(set(values))
    for value in values:
        assert value == value.lower(), f"{enum_type.__name__} value {value!r} not lower"
        assert " " not in value


def test_migration_state_covers_the_contract_vocabulary() -> None:
    """Pin the exact 26 canonical migration states."""

    assert {state.value for state in MigrationState} == {
        "draft",
        "source_connecting",
        "source_ready",
        "ingesting",
        "quarantined",
        "profiling",
        "mapping_proposed",
        "mapping_review",
        "dry_run",
        "reconciling",
        "exceptions_blocking",
        "ready_for_cutover",
        "cutover_approved",
        "initial_promotion",
        "delta_sync",
        "open_ar_active",
        "history_backfill",
        "post_cutover_monitoring",
        "final_reconciliation",
        "signoff_pending",
        "completed",
        "paused",
        "rollback_pending",
        "rolling_back",
        "rolled_back",
        "failed",
    }


def test_migration_era_state_covers_the_posting_lifecycle() -> None:
    """ERA posting states must include unapplied cash and reversal."""

    values = {state.value for state in MigrationEraState}
    assert {"unapplied", "reversal_pending", "reversed", "partially_posted"} <= values


# ---------------------------------------------------------------------------
# Transition map integrity
# ---------------------------------------------------------------------------


def test_transition_map_declares_every_state() -> None:
    """A state missing from the map would silently deny every transition."""

    assert set(MIGRATION_STATE_TRANSITIONS) == set(MigrationState)


def test_every_transition_target_is_a_real_state() -> None:
    """Guards against a typo producing an unreachable or bogus edge."""

    for source, targets in MIGRATION_STATE_TRANSITIONS.items():
        assert isinstance(targets, frozenset), f"{source} targets must be a frozenset"
        for target in targets:
            assert isinstance(target, MigrationState)
            assert target in MIGRATION_STATE_TRANSITIONS


def test_no_state_is_its_own_successor() -> None:
    """Re-writing the current state is a no-op, never an advance."""

    for source, targets in MIGRATION_STATE_TRANSITIONS.items():
        assert source not in targets


def test_terminal_states_have_no_outgoing_edges() -> None:
    """COMPLETED and ROLLED_BACK must be dead ends."""

    assert MIGRATION_TERMINAL_STATES == {
        MigrationState.COMPLETED,
        MigrationState.ROLLED_BACK,
    }
    for state in MIGRATION_TERMINAL_STATES:
        assert MIGRATION_STATE_TRANSITIONS[state] == frozenset()
        assert not is_legal_migration_transition(state, MigrationState.DRAFT)


def test_every_non_terminal_state_can_still_move() -> None:
    """A non-terminal state with no edges would strand a live migration."""

    for state in MigrationState:
        if state in MIGRATION_TERMINAL_STATES:
            continue
        assert MIGRATION_STATE_TRANSITIONS[state], f"{state} is stranded"


def test_every_state_is_reachable_from_draft() -> None:
    """An unreachable state is a contract that lies about the lifecycle."""

    seen = {MigrationState.DRAFT}
    frontier = [MigrationState.DRAFT]
    while frontier:
        for target in MIGRATION_STATE_TRANSITIONS[frontier.pop()]:
            if target not in seen:
                seen.add(target)
                frontier.append(target)

    assert seen == set(MigrationState)


def test_no_pre_cutover_pipeline_state_has_a_direct_rollback_edge() -> None:
    """Rolling back before anything was promoted is meaningless.

    Scoped to the linear PIPELINE states on purpose. ``EXCEPTIONS_BLOCKING`` and
    ``PAUSED`` are excluded because they legitimately carry a rollback edge and
    can be entered before or after cutover — see
    :func:`test_rollback_is_reachable_pre_cutover_through_exceptions`.
    """

    pre_promotion_pipeline = {
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
        MigrationState.READY_FOR_CUTOVER,
    }
    for state in pre_promotion_pipeline:
        assert not is_legal_migration_transition(
            state, MigrationState.ROLLBACK_PENDING
        ), f"{state} must not reach ROLLBACK_PENDING directly"


def test_rollback_is_reachable_pre_cutover_through_exceptions() -> None:
    """Pin the honest truth: a pairwise guard cannot enforce "was promoted".

    ``DRY_RUN -> EXCEPTIONS_BLOCKING -> ROLLBACK_PENDING`` is a legal walk, and
    ``PAUSED`` carries a rollback edge from anywhere. Both edges are deliberate:
    post-cutover exceptions must be able to roll back, and removing
    ``PAUSED -> ROLLBACK_PENDING`` would strand a paused rollback.

    This test exists so the contract states the property it actually has.
    Services MUST gate rollback on a recorded promotion fact (an established
    ``CutoverWatermark``), not on the state machine alone.
    """

    assert is_legal_migration_transition(
        MigrationState.DRY_RUN, MigrationState.EXCEPTIONS_BLOCKING
    )
    assert is_legal_migration_transition(
        MigrationState.EXCEPTIONS_BLOCKING, MigrationState.ROLLBACK_PENDING
    )
    assert is_legal_migration_transition(MigrationState.DRAFT, MigrationState.PAUSED)
    assert is_legal_migration_transition(
        MigrationState.PAUSED, MigrationState.ROLLBACK_PENDING
    )


# ---------------------------------------------------------------------------
# Transition guard
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (MigrationState.DRAFT, MigrationState.SOURCE_CONNECTING),
        (MigrationState.SOURCE_READY, MigrationState.INGESTING),
        (MigrationState.INGESTING, MigrationState.QUARANTINED),
        (MigrationState.QUARANTINED, MigrationState.INGESTING),
        (MigrationState.DRY_RUN, MigrationState.EXCEPTIONS_BLOCKING),
        (MigrationState.EXCEPTIONS_BLOCKING, MigrationState.MAPPING_REVIEW),
        (MigrationState.RECONCILING, MigrationState.READY_FOR_CUTOVER),
        (MigrationState.READY_FOR_CUTOVER, MigrationState.CUTOVER_APPROVED),
        (MigrationState.CUTOVER_APPROVED, MigrationState.INITIAL_PROMOTION),
        (MigrationState.DELTA_SYNC, MigrationState.OPEN_AR_ACTIVE),
        (MigrationState.SIGNOFF_PENDING, MigrationState.COMPLETED),
        (MigrationState.ROLLBACK_PENDING, MigrationState.ROLLING_BACK),
        (MigrationState.ROLLING_BACK, MigrationState.ROLLED_BACK),
        (MigrationState.FAILED, MigrationState.DRAFT),
    ],
)
def test_legal_transitions_are_accepted(
    current: MigrationState, target: MigrationState
) -> None:
    """The documented happy path and its branches must pass the guard."""

    assert is_legal_migration_transition(current, target) is True


@pytest.mark.parametrize(
    ("current", "target"),
    [
        # The exact defect the live commit endpoint performs today: a job
        # created at the first state jumped straight to a finished one.
        (MigrationState.DRAFT, MigrationState.COMPLETED),
        (MigrationState.DRAFT, MigrationState.CUTOVER_APPROVED),
        (MigrationState.DRAFT, MigrationState.OPEN_AR_ACTIVE),
        # Exceptions must never advance forward into cutover.
        (MigrationState.EXCEPTIONS_BLOCKING, MigrationState.READY_FOR_CUTOVER),
        (MigrationState.EXCEPTIONS_BLOCKING, MigrationState.COMPLETED),
        # Skipping human approval.
        (MigrationState.READY_FOR_CUTOVER, MigrationState.INITIAL_PROMOTION),
        (MigrationState.RECONCILING, MigrationState.COMPLETED),
        # Skipping sign-off.
        (MigrationState.FINAL_RECONCILIATION, MigrationState.COMPLETED),
        # Terminal states never move.
        (MigrationState.COMPLETED, MigrationState.DRAFT),
        (MigrationState.ROLLED_BACK, MigrationState.DRAFT),
        # Rollback cannot be short-circuited.
        (MigrationState.ROLLBACK_PENDING, MigrationState.ROLLED_BACK),
        (MigrationState.OPEN_AR_ACTIVE, MigrationState.ROLLED_BACK),
    ],
)
def test_illegal_transitions_are_rejected(
    current: MigrationState, target: MigrationState
) -> None:
    """A UI button must never be able to advance migration state."""

    assert is_legal_migration_transition(current, target) is False


def test_guard_accepts_wire_strings() -> None:
    """API boundaries check the raw body before parsing it into a model."""

    assert is_legal_migration_transition("draft", "source_connecting") is True
    assert is_legal_migration_transition("draft", "completed") is False


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("not_a_state", "draft"),
        ("draft", "not_a_state"),
        ("", "draft"),
        ("DRAFT", "source_connecting"),
        ("pending", "running"),
    ],
)
def test_unknown_states_fail_closed(current: str, target: str) -> None:
    """An unrecognized state must deny, never fall through to allowed."""

    assert is_legal_migration_transition(current, target) is False


def test_guard_rejects_self_transition() -> None:
    """Re-writing the same state is not an advance."""

    for state in MigrationState:
        assert is_legal_migration_transition(state, state) is False


def test_guard_is_pure() -> None:
    """The guard must not mutate the transition map it reads."""

    before = {
        state: frozenset(targets)
        for state, targets in MIGRATION_STATE_TRANSITIONS.items()
    }
    is_legal_migration_transition("nope", "also_nope")
    is_legal_migration_transition(MigrationState.DRAFT, MigrationState.COMPLETED)
    assert MIGRATION_STATE_TRANSITIONS == before


# ---------------------------------------------------------------------------
# Money is integer cents
# ---------------------------------------------------------------------------

#: (model, field) pairs carrying integer cents.
MONEY_FIELDS: tuple[tuple[type[BaseModel], str], ...] = (
    (ReconciliationControl, "source_value_cents"),
    (ReconciliationControl, "canonical_value_cents"),
    (ReconciliationControl, "production_value_cents"),
    (ReconciliationControl, "difference_cents"),
    (ReconciliationControl, "tolerance_cents"),
    (ReconciliationRunResult, "total_absolute_difference_cents"),
    (MigrationExceptionGroup, "affected_dollar_cents"),
    (CutoverWatermark, "open_ar_balance_cents"),
    (MigrationSignoff, "accepted_variance_cents"),
    (DryRunCompleted, "would_commit_total_cents"),
    (OpenARActivated, "open_ar_total_cents"),
    (MigrationCompleted, "migrated_total_cents"),
    (MigrationRolledBack, "reversed_total_cents"),
    (ReconciliationCompleted, "total_absolute_difference_cents"),
)


@pytest.mark.parametrize(("model", "field"), MONEY_FIELDS)
@pytest.mark.parametrize("bad_value", [100.0, 100.5, -0.5, 1e3, "100"])
def test_money_fields_reject_non_integers(
    model: type[BaseModel], field: str, bad_value: object
) -> None:
    """A float must be REJECTED, never silently coerced or rounded.

    ``100.0`` matters as much as ``100.5``: a lax ``int`` field accepts a float
    whose fractional part is zero, which is exactly how a rounding defect
    enters a financial migration unnoticed.
    """

    with pytest.raises(ValidationError):
        model(tenant_id="tenant-test", **{field: bad_value})


@pytest.mark.parametrize(("model", "field"), MONEY_FIELDS)
def test_money_fields_accept_integer_cents(model: type[BaseModel], field: str) -> None:
    """The happy path must still work for a plain integer."""

    instance = model(tenant_id="tenant-test", **{field: 12_345})
    assert getattr(instance, field) == 12_345


def test_signed_money_allows_negative_variance() -> None:
    """Production below source is the direction that loses money."""

    control = ReconciliationControl(
        tenant_id="tenant-test",
        control_name="open_ar_total",
        source_value_cents=1_000_000,
        production_value_cents=940_000,
        difference_cents=-60_000,
        status=MigrationReconciliationStatus.OUT_OF_BALANCE,
    )
    assert control.difference_cents == -60_000


@pytest.mark.parametrize(
    ("model", "field"),
    [
        (ReconciliationControl, "tolerance_cents"),
        (ReconciliationRunResult, "total_absolute_difference_cents"),
    ],
)
def test_non_negative_money_fields_reject_negatives(
    model: type[BaseModel], field: str
) -> None:
    """A tolerance or an absolute total can never be negative."""

    with pytest.raises(ValidationError):
        model(tenant_id="tenant-test", **{field: -1})


def test_confidence_is_bounded_to_zero_one() -> None:
    """The live mapping path stores confidence unbounded; the contract bounds it."""

    assert FieldMappingProposal(tenant_id="t", confidence=0.0).confidence == 0.0
    assert FieldMappingProposal(tenant_id="t", confidence=1.0).confidence == 1.0
    for bad in (-0.01, 1.01, 42.0):
        with pytest.raises(ValidationError):
            FieldMappingProposal(tenant_id="t", confidence=bad)


def test_absent_confidence_is_none_not_zero() -> None:
    """Absence of a score is unknown, never a score of zero."""

    assert FieldMappingProposal(tenant_id="t").confidence is None


# ---------------------------------------------------------------------------
# Minimal payloads and tenant scoping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("model", MIGRATION_RECORD_MODELS)
def test_record_models_validate_from_a_minimal_payload(
    model: type[BaseModel],
) -> None:
    """Only ``tenant_id`` is required; every other field is back-compat optional."""

    instance = model.model_validate({"tenant_id": "tenant-test"})
    assert instance.tenant_id == "tenant-test"
    assert instance.schema_version == MIGRATION_CONTRACT_SCHEMA_VERSION

    restored = model.model_validate(instance.model_dump())
    assert restored == instance


@pytest.mark.parametrize("model", MIGRATION_RECORD_MODELS)
def test_record_models_require_tenant_id(model: type[BaseModel]) -> None:
    """A tenant-scoped contract without a tenant is an isolation hole."""

    with pytest.raises(ValidationError):
        model.model_validate({})


@pytest.mark.parametrize(("event", "expected_type"), MIGRATION_EVENTS)
def test_events_carry_tenant_id(event: type[BaseModel], expected_type: str) -> None:
    """The Core relay refuses tenant-less events; the contract enforces it early."""

    with pytest.raises(ValidationError):
        event.model_validate({})

    instance = event.model_validate({"tenant_id": "tenant-test"})
    assert instance.tenant_id == "tenant-test"
    assert instance.event_type == expected_type


@pytest.mark.parametrize(("event", "expected_type"), MIGRATION_EVENTS)
def test_events_round_trip_through_a_dict(
    event: type[BaseModel], expected_type: str
) -> None:
    """Events are serialized onto a bus and rebuilt by a consumer."""

    instance = event.model_validate({"tenant_id": "tenant-test"})
    payload = instance.model_dump()
    assert payload["event_type"] == expected_type
    assert event.model_validate(payload) == instance


def test_event_types_are_unique_and_namespaced() -> None:
    """Two events sharing a type would be indistinguishable on the bus."""

    types = [expected for _event, expected in MIGRATION_EVENTS]
    assert len(types) == len(set(types))
    for event_type in types:
        assert event_type.startswith("migration.")


def test_migration_created_matches_the_live_audit_vocabulary() -> None:
    """The bus event and the live audit row must share one event type.

    The live writer persists ``"migration.created"`` at
    ``Adaptix-Billing-Service/backend/billing_app/api/migration_intelligence_routes.py:201``.
    """

    assert MigrationCreated(tenant_id="t").event_type == "migration.created"


# ---------------------------------------------------------------------------
# Representative payloads
# ---------------------------------------------------------------------------


def test_source_file_hash_must_be_a_sha256_digest() -> None:
    """A short or long digest is a lineage defect, not a cosmetic one."""

    digest = "a" * 64
    landed = MigrationSourceFile(
        tenant_id="tenant-test",
        original_filename="export.csv",
        content_type="text/csv",
        file_hash_sha256=digest,
        byte_size=2048,
        received_at=_timestamp(),
    )
    assert landed.file_hash_sha256 == digest
    assert landed.quarantine_reason is None

    for bad_digest in ("a" * 63, "a" * 65, ""):
        with pytest.raises(ValidationError):
            MigrationSourceFile(tenant_id="tenant-test", file_hash_sha256=bad_digest)


def test_quarantined_file_carries_its_reason() -> None:
    """Quarantine must state why, or an operator cannot remediate it."""

    quarantined = MigrationSourceFile(
        tenant_id="tenant-test",
        original_filename="truncated_export.csv",
        quarantine_reason="row count below declared control total",
        quarantined_at=_timestamp(),
    )
    assert quarantined.quarantine_reason
    assert is_legal_migration_transition(
        MigrationState.INGESTING, MigrationState.QUARANTINED
    )


def test_mapping_proposal_defaults_fail_closed() -> None:
    """An omitted authority flag must mean review, never auto-apply."""

    proposal = FieldMappingProposal(tenant_id="tenant-test")
    assert proposal.auto_approve_allowed is False
    assert proposal.downstream_financial_impact is False
    assert proposal.decision_level is None
    assert proposal.reason_codes == []
    assert proposal.evidence_masked_examples == []


def test_mapping_proposal_carries_masked_evidence_only() -> None:
    """Evidence samples leave the migration boundary and must be redacted."""

    proposal = FieldMappingProposal(
        tenant_id="tenant-test",
        source_field="COL_A",
        canonical_entity="claim",
        canonical_field="total_charge_cents",
        transform="currency_to_cents",
        confidence=0.97,
        reason_codes=["exact_header_match", "type_compatible"],
        decision_level=MappingDecisionLevel.AUTO_DETERMINISTIC,
        evidence_masked_examples=["<masked>", "<masked>"],
        downstream_financial_impact=True,
        vendor_profile=VendorProfileRef(
            tenant_id="tenant-test",
            vendor=MigrationSourceVendor.OFFICE_ALLY,
            product="legacy_export",
            export_version="v1",
            profile_version="2026.08.1",
        ),
    )
    assert proposal.vendor_profile is not None
    assert proposal.vendor_profile.vendor is MigrationSourceVendor.OFFICE_ALLY
    assert all("<masked>" == sample for sample in proposal.evidence_masked_examples)


def test_reconciliation_run_aggregates_controls() -> None:
    """A run carries its controls so a consumer never re-derives balance."""

    run = ReconciliationRunResult(
        tenant_id="tenant-test",
        run_id="run-001",
        controls=[
            ReconciliationControl(
                tenant_id="tenant-test",
                control_name="claim_count",
                source_value_count=1200,
                production_value_count=1200,
                difference_count=0,
                status=MigrationReconciliationStatus.BALANCED,
            ),
            ReconciliationControl(
                tenant_id="tenant-test",
                control_name="open_ar_total",
                source_value_cents=98_765_400,
                production_value_cents=98_765_000,
                difference_cents=-400,
                status=MigrationReconciliationStatus.OUT_OF_BALANCE,
            ),
        ],
        overall_status=MigrationReconciliationStatus.OUT_OF_BALANCE,
        controls_evaluated=2,
        controls_out_of_balance=1,
        total_absolute_difference_cents=400,
        started_at=_timestamp(),
        completed_at=_timestamp(),
    )
    assert len(run.controls) == 2
    assert run.overall_status is MigrationReconciliationStatus.OUT_OF_BALANCE
    assert ReconciliationRunResult.model_validate(run.model_dump()) == run


def test_not_run_is_not_a_pass() -> None:
    """A control that never executed has proven nothing."""

    assert MigrationReconciliationStatus.NOT_RUN.value == "not_run"
    assert (
        MigrationReconciliationStatus.NOT_RUN
        is not MigrationReconciliationStatus.BALANCED
    )


def test_exception_group_is_rankable_by_dollars() -> None:
    """Few rows worth a lot must be able to outrank many rows worth little."""

    big = MigrationExceptionGroup(
        tenant_id="tenant-test",
        category=MigrationExceptionCategory.FINANCIAL_IMBALANCE,
        affected_record_count=3,
        affected_dollar_cents=18_000_000,
        representative_masked_examples=["<masked>"],
        proposed_correction="Re-request the source export with full balances.",
        confidence=0.62,
        revalidation_impact="Requires a new dry run and reconciliation pass.",
    )
    small = MigrationExceptionGroup(
        tenant_id="tenant-test",
        category=MigrationExceptionCategory.TRUNCATED_EXPORT,
        affected_record_count=40_000,
        affected_dollar_cents=1_200,
    )
    assert big.affected_dollar_cents is not None
    assert small.affected_dollar_cents is not None
    assert big.affected_dollar_cents > small.affected_dollar_cents
    assert big.blocking is True


# ---------------------------------------------------------------------------
# Error taxonomy
# ---------------------------------------------------------------------------


def test_migration_error_requires_a_code_and_defaults_to_not_retryable() -> None:
    """An unclassified failure must never be retried by default."""

    with pytest.raises(ValidationError):
        MigrationError.model_validate({})

    error = MigrationError(code=MigrationErrorCode.FINANCIAL_IMBALANCE)
    assert error.retryable is False
    assert error.user_safe_message is None
    assert error.operator_diagnostic is None


def test_migration_error_carries_correlation_id() -> None:
    """Every failure must be traceable to the request that caused it."""

    error = MigrationError(
        code=MigrationErrorCode.STEDI_RATE_LIMIT,
        retryable=True,
        user_safe_message="The clearinghouse is throttling requests. Retrying.",
        operator_diagnostic="stedi 429 on batch submit; backoff scheduled",
        correlation_id="corr-0001",
        tenant_id="tenant-test",
        migration_id="mig-001",
        occurred_at=_timestamp(),
    )
    assert error.correlation_id == "corr-0001"
    assert error.retryable is True
    assert MigrationError.model_validate(error.model_dump()) == error


def test_error_taxonomy_covers_every_required_category() -> None:
    """Pin the taxonomy so a category cannot be dropped without a test failure."""

    assert {code.value for code in MigrationErrorCode} == {
        "authentication",
        "authorization",
        "tenant_mismatch",
        "invalid_state_transition",
        "optimistic_conflict",
        "duplicate_idempotent_replay",
        "validation",
        "source_corruption",
        "unsupported_format",
        "mapping_ambiguity",
        "financial_imbalance",
        "stedi_auth",
        "stedi_rate_limit",
        "stedi_validation",
        "stedi_unavailable",
        "sagemaker_unavailable",
        "model_guardrail",
        "temporal_delayed",
        "database_transient",
        "database_permanent",
        "object_store",
        "queue_dlq",
        "internal_invariant",
    }


def test_invalid_state_transition_has_an_error_code() -> None:
    """The guard's rejection must be reportable as a typed error."""

    assert (
        MigrationErrorCode.INVALID_STATE_TRANSITION.value == "invalid_state_transition"
    )
    assert MigrationErrorCode.OPTIMISTIC_CONFLICT.value == "optimistic_conflict"


def test_record_version_supports_optimistic_concurrency() -> None:
    """``optimistic_conflict`` needs a row version to conflict on."""

    control = ReconciliationControl(tenant_id="tenant-test", record_version=7)
    assert control.record_version == 7
    with pytest.raises(ValidationError):
        ReconciliationControl(tenant_id="tenant-test", record_version=-1)
