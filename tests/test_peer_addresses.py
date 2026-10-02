"""Contracts supply_integrations reaches its peers at addresses that exist (ENDPOINTS-001).

Adaptix-Governance#313.
NotificationClient and AnalyticsClient bound their base URL, token and timeout
at import time from NOTIFICATIONS_SERVICE_URL and ANALYTICS_SERVICE_URL,
defaulting to http://notifications:8000 and http://analytics:8000, compose
names with no DNS record in the VPC. None of the three consumers (Inventory,
Medications, Narcotics) sets those variables on its production task definition,
so every low-stock, expiration, recall and discrepancy alert and every
analytics event failed to resolve and was dropped with a warning. Import-time
binding is the trap the module's own audit-rail note documents: a value set on
a running task has no effect. Both clients now resolve per call and default to
the Cloud Map addresses, notifications.adaptix.internal:8000 and
analytics.adaptix.internal:8022.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import adaptix_contracts

PACKAGE = Path(adaptix_contracts.__file__).resolve().parent
# A single-label host right after http(s)://adaptix- is a docker-compose name.
COMPOSE_HOST = re.compile(r"https?://adaptix-[a-z0-9-]+(?::\d+)?(?:/|$)")
EXPECTED: dict[str, list[str]] = {
    "supply_integrations.py": [
        "http://notifications.adaptix.internal:8000",
        "http://analytics.adaptix.internal:8022",
    ]
}


def _code_strings(path: Path) -> list[str]:
    """String constants in code; docstrings and other bare string statements are prose."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    prose = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
    }
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in prose
    ]


def test_the_guard_recognises_a_compose_hostname() -> None:
    assert COMPOSE_HOST.search("http://adaptix-ai:8000")
    assert not COMPOSE_HOST.search("http://ai.adaptix.internal:8029")


def test_no_module_names_a_compose_hostname() -> None:
    offenders = {
        str(path.relative_to(PACKAGE)): hits
        for path in sorted(PACKAGE.rglob("*.py"))
        if (
            hits := [
                value for value in _code_strings(path) if COMPOSE_HOST.search(value)
            ]
        )
    }
    assert not offenders, f"hosts with no DNS record in production: {offenders}"


@pytest.mark.parametrize(
    ("relative", "address"),
    [
        (relative, address)
        for relative, addresses in EXPECTED.items()
        for address in addresses
    ],
)
def test_fallback_names_the_cloud_map_address(relative: str, address: str) -> None:
    # Equality on each literal, not ``address in <list>``: CodeQL reads a URL
    # literal on the left of ``in`` as an incomplete URL-substring check.
    assert any(value == address for value in _code_strings(PACKAGE / relative))
