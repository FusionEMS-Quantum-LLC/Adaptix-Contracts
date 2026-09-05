"""Tests for the canonical ENVIRONMENT-detection module.

Proves the single-source predicate this module replaces four independent
in-package copies of (``gateway_signature.is_production``,
``auth_contracts._is_production``,
``auth.module_entitlement_gate._is_production``,
``security.temporal_payload_codec.is_production_environment``), and the
opt-in startup assertion that closes the "forgotten task-definition
variable silently disables every production guard" failure class.
"""

from __future__ import annotations

import pytest

from adaptix_contracts.environment import (
    ENVIRONMENT_ENV,
    PRODUCTION_ENVIRONMENTS,
    assert_environment_configured,
    is_production,
    is_production_environment,
)


def test_environment_env_is_the_expected_name() -> None:
    assert ENVIRONMENT_ENV == "ENVIRONMENT"


@pytest.mark.parametrize(
    "value",
    ["production", "prod", "PRODUCTION", "Prod", "  production  ", "PROD"],
)
def test_is_production_environment_accepts_known_spellings(value: str) -> None:
    assert is_production_environment(value) is True


@pytest.mark.parametrize(
    "value",
    ["staging", "development", "test", "local", "productions", " prods "],
)
def test_is_production_environment_rejects_everything_else(value: str) -> None:
    assert is_production_environment(value) is False


def test_is_production_environment_treats_none_and_empty_as_not_production() -> None:
    assert is_production_environment(None) is False
    assert is_production_environment("") is False
    assert is_production_environment("   ") is False


def test_production_environments_set_matches_the_pure_predicate() -> None:
    """PRODUCTION_ENVIRONMENTS is public precisely so callers can build their
    own membership checks; it must actually be what the predicate uses."""
    for value in PRODUCTION_ENVIRONMENTS:
        assert is_production_environment(value) is True
    assert is_production_environment("not-a-production-value") is False


def test_is_production_reads_live_environment_variable(monkeypatch) -> None:
    monkeypatch.setenv(ENVIRONMENT_ENV, "production")
    assert is_production() is True
    monkeypatch.setenv(ENVIRONMENT_ENV, "staging")
    assert is_production() is False


def test_is_production_defaults_to_false_when_unset(monkeypatch) -> None:
    """Unset must mean 'not production,' not an error -- local dev, this
    package's own test suite, and one-off scripts legitimately never set
    ENVIRONMENT and must not be forced to. See assert_environment_configured
    for the opt-in check that catches a REAL deployment forgetting to set it."""
    monkeypatch.delenv(ENVIRONMENT_ENV, raising=False)
    assert is_production() is False


def test_assert_environment_configured_raises_when_unset(monkeypatch) -> None:
    monkeypatch.delenv(ENVIRONMENT_ENV, raising=False)
    with pytest.raises(RuntimeError, match=ENVIRONMENT_ENV):
        assert_environment_configured()


def test_assert_environment_configured_raises_when_blank(monkeypatch) -> None:
    monkeypatch.setenv(ENVIRONMENT_ENV, "   ")
    with pytest.raises(RuntimeError, match=ENVIRONMENT_ENV):
        assert_environment_configured()


@pytest.mark.parametrize("value", ["production", "staging", "development", "local"])
def test_assert_environment_configured_passes_for_any_non_blank_value(
    monkeypatch, value: str
) -> None:
    """Deliberately does not validate against a 'known good' allow-list --
    only that some value was configured at all (see module docstring)."""
    monkeypatch.setenv(ENVIRONMENT_ENV, value)
    assert_environment_configured()  # must not raise
