"""Contracts supply_integrations reaches its peers at addresses that exist (ENDPOINTS-001).

Adaptix-Governance#313. NotificationClient and AnalyticsClient bound their base
URL, token and timeout at import time, defaulting to ``http://notifications:8000``
and ``http://analytics:8000``: single-label compose hosts with no DNS record in
the VPC. Both now resolve per call and default to the Cloud Map addresses.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import httpx
import pytest

import adaptix_contracts
from adaptix_contracts.supply_integrations import AnalyticsClient, NotificationClient

PACKAGE = Path(adaptix_contracts.__file__).resolve().parent
MODULE = PACKAGE / "supply_integrations.py"
NOTIFICATIONS = "http://notifications.adaptix.internal:8000"
ANALYTICS = "http://analytics.adaptix.internal:8022"
# A single-label host (no dot) after http(s):// is a docker-compose name; localhost is
# not one. The lookahead lets the pattern find a URL embedded in prose.
SINGLE_LABEL_HOST = re.compile(
    r"https?://(?!localhost)[A-Za-z0-9-]+(:[0-9]+)?(?![A-Za-z0-9.-])"
)


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


def test_the_guard_recognises_single_label_hosts() -> None:
    assert SINGLE_LABEL_HOST.search("http://notifications:8000")
    assert SINGLE_LABEL_HOST.search("http://adaptix-core:8000")
    assert SINGLE_LABEL_HOST.search("see http://analytics:8000 for details")
    assert not SINGLE_LABEL_HOST.search(NOTIFICATIONS)
    assert not SINGLE_LABEL_HOST.search("https://api.adaptixcore.com")
    assert not SINGLE_LABEL_HOST.search("http://localhost:8000")


def test_no_module_names_a_single_label_host() -> None:
    offenders = {
        str(path.relative_to(PACKAGE)): hits
        for path in sorted(PACKAGE.rglob("*.py"))
        if (hits := [v for v in _code_strings(path) if SINGLE_LABEL_HOST.search(v)])
    }
    assert not offenders, f"hosts with no DNS record in production: {offenders}"


@pytest.mark.parametrize("address", [NOTIFICATIONS, ANALYTICS])
def test_fallback_literal_is_the_cloud_map_address(address: str) -> None:
    assert any(value == address for value in _code_strings(MODULE))


class _Recorder:
    """Records every request and the client timeout the module asked for."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.timeouts: list[float] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(200, json={"ok": True})

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        real_client = httpx.AsyncClient

        def factory(*, timeout: float) -> httpx.AsyncClient:
            self.timeouts.append(timeout)
            return real_client(
                transport=httpx.MockTransport(self.handler), timeout=timeout
            )

        monkeypatch.setattr(httpx, "AsyncClient", factory)


ENV = (
    "NOTIFICATIONS_SERVICE_URL",
    "NOTIFICATIONS_SERVICE_TOKEN",
    "NOTIFICATIONS_TIMEOUT_SECONDS",
    "ANALYTICS_SERVICE_URL",
    "ANALYTICS_SERVICE_TOKEN",
    "ANALYTICS_TIMEOUT_SECONDS",
)


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    for name in ENV:
        monkeypatch.delenv(name, raising=False)
    rec = _Recorder()
    rec.install(monkeypatch)
    return rec


async def test_notifications_default_to_cloud_map_when_unset(
    recorder: _Recorder,
) -> None:
    assert await NotificationClient._post_notification(
        {"notification_type": "low_stock"}
    )
    assert [str(r.url) for r in recorder.requests] == [
        f"{NOTIFICATIONS}/api/v1/notifications/send"
    ]
    assert recorder.requests[0].headers["Authorization"] == "Bearer "
    assert recorder.timeouts == [5.0]


async def test_analytics_default_to_cloud_map_when_unset(recorder: _Recorder) -> None:
    assert await AnalyticsClient._post_event({"event_type": "usage"})
    assert [str(r.url) for r in recorder.requests] == [
        f"{ANALYTICS}/api/v1/analytics/events"
    ]
    assert recorder.timeouts == [5.0]


async def test_values_set_after_import_are_honoured(
    recorder: _Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NOTIFICATIONS_SERVICE_URL", "http://n.example.test/")
    monkeypatch.setenv("NOTIFICATIONS_SERVICE_TOKEN", "n-token")
    monkeypatch.setenv("NOTIFICATIONS_TIMEOUT_SECONDS", "7")
    monkeypatch.setenv("ANALYTICS_SERVICE_URL", "http://a.example.test")
    monkeypatch.setenv("ANALYTICS_SERVICE_TOKEN", "a-token")
    monkeypatch.setenv("ANALYTICS_TIMEOUT_SECONDS", "9")
    assert await NotificationClient._post_notification({"notification_type": "recall"})
    assert await AnalyticsClient._post_event({"event_type": "waste"})
    assert [str(r.url) for r in recorder.requests] == [
        "http://n.example.test/api/v1/notifications/send",
        "http://a.example.test/api/v1/analytics/events",
    ]
    assert [r.headers["Authorization"] for r in recorder.requests] == [
        "Bearer n-token",
        "Bearer a-token",
    ]
    assert recorder.timeouts == [7.0, 9.0]


async def test_blank_url_sends_nothing_and_reports_false(
    recorder: _Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NOTIFICATIONS_SERVICE_URL", "")
    monkeypatch.setenv("ANALYTICS_SERVICE_URL", "")
    assert (
        await NotificationClient._post_notification({"notification_type": "x"}) is False
    )
    assert await AnalyticsClient._post_event({"event_type": "x"}) is False
    assert recorder.requests == []
