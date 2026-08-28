"""Tests for the canonical service-audience registry.

These pin the registry's shape and its contract with the two consumers
(``Adaptix-Gateway``'s ``KNOWN_AUDIENCES`` and ``Adaptix-Core-Service``'s
``_LIVE_SERVICE_AUDIENCES``). They deliberately do NOT reach for a sibling
checkout: needing one is exactly why the previous drift guard skipped in CI and
never gated anything.
"""

from __future__ import annotations

import re

import pytest

from adaptix_contracts.service_audiences import (
    KNOWN_SERVICE_AUDIENCES,
    is_known_service_audience,
)

_AUDIENCE_RE = re.compile(r"^adaptix-[a-z0-9]+(-[a-z0-9]+)*$")


def test_registry_is_an_immutable_frozenset() -> None:
    """A mutable registry could be edited at runtime by any importer."""
    assert isinstance(KNOWN_SERVICE_AUDIENCES, frozenset)


def test_every_audience_matches_the_platform_naming_pattern() -> None:
    bad = sorted(a for a in KNOWN_SERVICE_AUDIENCES if not _AUDIENCE_RE.match(a))
    assert not bad, f"audiences violating the naming pattern: {bad}"


def test_core_audience_is_present() -> None:
    assert "adaptix-core" in KNOWN_SERVICE_AUDIENCES


def test_vision_audience_is_present() -> None:
    """Regression pin for the 2026-08-04 vision audience drift."""
    assert "adaptix-vision" in KNOWN_SERVICE_AUDIENCES


def test_audit_audience_is_present() -> None:
    """Audit is deployed and requires an explicit downstream identity."""
    assert "adaptix-audit" in KNOWN_SERVICE_AUDIENCES


def test_signal_bus_audience_is_present() -> None:
    """The cross-service signal bus owns a distinct service identity."""
    assert "adaptix-signal-bus" in KNOWN_SERVICE_AUDIENCES


def test_mih_audience_is_present() -> None:
    """MIH is an active clinical service with a dedicated production identity.

    The downstream service is configured to require
    ``ADAPTIX_GATEWAY_EXPECTED_AUDIENCE=adaptix-mih``. The gateway route may
    reference that audience only after this canonical registry recognizes it.
    """
    assert "adaptix-mih" in KNOWN_SERVICE_AUDIENCES


@pytest.mark.parametrize(
    "value",
    ["adaptix-core", "  adaptix-core  ", "ADAPTIX-CORE"],
    ids=["exact", "surrounding-whitespace", "uppercase"],
)
def test_is_known_service_audience_accepts_normalizable_forms(value: str) -> None:
    assert is_known_service_audience(value) is True


@pytest.mark.parametrize(
    "value",
    [None, "", "   ", "adaptix-does-not-exist", "core", "adaptix_core"],
    ids=["none", "empty", "blank", "unknown", "missing-prefix", "underscore"],
)
def test_is_known_service_audience_rejects_everything_else(value) -> None:
    assert is_known_service_audience(value) is False


def test_registry_has_no_duplicate_after_normalization() -> None:
    normalized = [a.strip().lower() for a in KNOWN_SERVICE_AUDIENCES]
    assert len(normalized) == len(set(normalized))
