"""Contract tests for versioned rule packs (shared platform primitive C)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from adaptix_contracts import schemas
from adaptix_contracts.schemas.rule_pack_contracts import (
    MUTABLE_RULE_PACK_STATES,
    RulePack,
    RulePackRule,
    RulePackState,
)
import pytest
from pydantic import ValidationError

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
EFFECTIVE_FROM = date(2026, 9, 1)


def _pack(**overrides: object) -> RulePack:
    payload: dict[str, object] = {
        "rule_pack_id": "pack-1",
        "global_scope": True,
        "authority": "CMS",
        "semantic_version": "2.1.0",
        "state": RulePackState.DRAFT,
        "created_at": NOW,
    }
    payload.update(overrides)
    return RulePack(**payload)  # type: ignore[arg-type]


def _effective(**overrides: object) -> RulePack:
    payload: dict[str, object] = {
        "state": RulePackState.EFFECTIVE,
        "approved_by": "user-1",
        "approval_receipt_id": "rcpt-1",
        "effective_from": EFFECTIVE_FROM,
    }
    payload.update(overrides)
    return _pack(**payload)


class TestScope:
    def test_a_global_pack_carries_no_tenant(self) -> None:
        assert _pack().tenant_id is None

    def test_a_tenant_pack_is_valid(self) -> None:
        pack = _pack(global_scope=False, tenant_id="tenant-a")
        assert pack.tenant_id == "tenant-a"

    def test_both_scopes_at_once_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="either tenant-scoped"):
            _pack(global_scope=True, tenant_id="tenant-a")

    def test_neither_scope_is_refused(self) -> None:
        """A pack nobody can be shown to be governed by is not evaluable."""

        with pytest.raises(ValidationError, match="either tenant-scoped"):
            _pack(global_scope=False)


class TestApproval:
    def test_effective_pack_requires_an_approver(self) -> None:
        with pytest.raises(ValidationError, match="approved_by"):
            _pack(state=RulePackState.EFFECTIVE, effective_from=EFFECTIVE_FROM)

    def test_effective_pack_requires_an_approval_receipt(self) -> None:
        with pytest.raises(ValidationError, match="approval_receipt_id"):
            _pack(
                state=RulePackState.EFFECTIVE,
                approved_by="user-1",
                effective_from=EFFECTIVE_FROM,
            )

    def test_effective_pack_requires_an_effective_date(self) -> None:
        with pytest.raises(ValidationError, match="effective_from"):
            _pack(
                state=RulePackState.EFFECTIVE,
                approved_by="user-1",
                approval_receipt_id="rcpt-1",
            )

    def test_fully_approved_effective_pack_is_valid(self) -> None:
        assert _effective().state is RulePackState.EFFECTIVE

    def test_approved_but_not_yet_effective_needs_no_date(self) -> None:
        """Approved today, live on the first of the month is the normal case."""

        pack = _pack(state=RulePackState.APPROVED, approved_by="user-1")
        assert pack.effective_from is None


class TestImmutability:
    @pytest.mark.parametrize("state", [RulePackState.DRAFT, RulePackState.PROPOSED])
    def test_draft_states_are_mutable(self, state: RulePackState) -> None:
        pack = _pack(state=state)
        assert pack.is_mutable()
        pack.assert_mutable()

    @pytest.mark.parametrize(
        "state",
        [
            RulePackState.APPROVED,
            RulePackState.SUPERSEDED,
            RulePackState.RETIRED,
        ],
    )
    def test_settled_states_are_frozen(self, state: RulePackState) -> None:
        pack = _pack(state=state, approved_by="user-1")
        assert not pack.is_mutable()
        with pytest.raises(ValueError, match="must not be edited in place"):
            pack.assert_mutable()

    def test_effective_pack_is_frozen(self) -> None:
        with pytest.raises(ValueError, match="create a superseding pack"):
            _effective().assert_mutable()

    def test_every_state_is_classified(self) -> None:
        for state in RulePackState:
            assert isinstance(state in MUTABLE_RULE_PACK_STATES, bool)


class TestEffectiveWindow:
    def test_a_draft_governs_nothing(self) -> None:
        assert not _pack().is_in_effect_on(date(2026, 12, 1))

    def test_a_date_before_the_start_is_not_governed(self) -> None:
        assert not _effective().is_in_effect_on(date(2026, 8, 31))

    def test_the_first_effective_day_is_governed(self) -> None:
        assert _effective().is_in_effect_on(EFFECTIVE_FROM)

    def test_an_open_ended_pack_governs_the_future(self) -> None:
        assert _effective().is_in_effect_on(date(2030, 1, 1))

    def test_the_last_day_is_inclusive(self) -> None:
        pack = _effective(effective_until=date(2026, 12, 31))
        assert pack.is_in_effect_on(date(2026, 12, 31))
        assert not pack.is_in_effect_on(date(2027, 1, 1))

    def test_reversed_window_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="effective_until precedes"):
            _effective(effective_until=date(2026, 1, 1))


def test_rules_carry_their_citation() -> None:
    pack = _pack(
        rules=[
            RulePackRule(
                rule_id="lcd-l35162-r1",
                description="Ambulance transport requires a documented reason",
                severity="block",
                source_reference="LCD L35162 §B.2",
            )
        ]
    )
    assert pack.rules[0].source_reference == "LCD L35162 §B.2"
    assert pack.rules[0].expression == {}


def test_surface_is_exported_from_the_package_root() -> None:
    for name in (
        "RulePack",
        "RulePackRule",
        "RulePackState",
        "MUTABLE_RULE_PACK_STATES",
    ):
        assert name in schemas.__all__
        assert hasattr(schemas, name)
