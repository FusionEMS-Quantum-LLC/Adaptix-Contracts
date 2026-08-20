"""Tests for the Cortex Live demo side-effect classification contract."""

from __future__ import annotations

import pytest

from adaptix_contracts.demo_contracts import (
    DemoSideEffectClass,
    demo_side_effect_allowed,
)


def test_non_demo_requests_are_never_blocked_by_this_gate() -> None:
    """is_demo=False -> the gate imposes nothing, regardless of class."""
    for side_effect in DemoSideEffectClass:
        assert demo_side_effect_allowed(is_demo=False, side_effect=side_effect) is True


def test_demo_read_and_local_write_are_allowed() -> None:
    assert (
        demo_side_effect_allowed(is_demo=True, side_effect=DemoSideEffectClass.READ)
        is True
    )
    assert (
        demo_side_effect_allowed(
            is_demo=True, side_effect=DemoSideEffectClass.LOCAL_DEMO_WRITE
        )
        is True
    )


def test_demo_sandbox_external_requires_explicit_sandbox_configuration() -> None:
    """SANDBOX_EXTERNAL fails closed unless the sandbox path is configured."""
    assert (
        demo_side_effect_allowed(
            is_demo=True, side_effect=DemoSideEffectClass.SANDBOX_EXTERNAL
        )
        is False
    )
    assert (
        demo_side_effect_allowed(
            is_demo=True,
            side_effect=DemoSideEffectClass.SANDBOX_EXTERNAL,
            sandbox_configured=True,
        )
        is True
    )


def test_demo_production_external_is_always_denied() -> None:
    """PRODUCTION_EXTERNAL is denied for demo even if sandbox_configured=True."""
    assert (
        demo_side_effect_allowed(
            is_demo=True, side_effect=DemoSideEffectClass.PRODUCTION_EXTERNAL
        )
        is False
    )
    assert (
        demo_side_effect_allowed(
            is_demo=True,
            side_effect=DemoSideEffectClass.PRODUCTION_EXTERNAL,
            sandbox_configured=True,
        )
        is False
    )


def test_side_effect_values_are_stable_wire_strings() -> None:
    """The enum values are a wire contract shared across services."""
    assert DemoSideEffectClass.READ.value == "read"
    assert DemoSideEffectClass.LOCAL_DEMO_WRITE.value == "local_demo_write"
    assert DemoSideEffectClass.SANDBOX_EXTERNAL.value == "sandbox_external"
    assert DemoSideEffectClass.PRODUCTION_EXTERNAL.value == "production_external"


def test_unknown_classification_would_fail_closed_for_demo() -> None:
    """Non-member input is a type error at the boundary, not a silent allow."""
    with pytest.raises(ValueError):
        DemoSideEffectClass("real_payer_submission")
