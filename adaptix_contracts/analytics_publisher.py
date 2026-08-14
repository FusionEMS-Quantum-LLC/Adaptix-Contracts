"""In-VPC publisher for Analytics KPI source events.

Every domain service that owns a KPI's source data calls
``AnalyticsPublisher.publish(event_type, tenant_id, payload)`` from its
workflow-completed hook. The publisher:

* validates ``event_type`` against the authoritative catalog in
  :mod:`adaptix_contracts.analytics_events` — an unknown or typo'd event
  raises at publish time, never lands silently as noise;
* signs the outbound identity with ``ADAPTIX_GATEWAY_SHARED_SECRET`` via
  :func:`adaptix_contracts.gateway_signing.build_gateway_signed_headers`,
  so Analytics can enforce ``ADAPTIX_GATEWAY_HMAC_ENFORCE=true``;
* POSTs to ``$ANALYTICS_URL/api/v1/analytics/events`` in-VPC (default
  ``http://analytics.adaptix.internal:8022``), so the call never transits
  the public gateway and no audience/entitlement gate is in the path;
* retries transient failures with exponential backoff and lets the caller
  decide whether to raise or swallow on give-up (``raise_on_error``).

Publisher failures MUST NOT break the domain workflow that emitted them.
Callers wrap in ``try/except AnalyticsPublisherError`` when domain success
must not depend on Analytics availability.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from adaptix_contracts.analytics_events import ALL_EVENT_TYPES, payload_contract
from adaptix_contracts.gateway_signing import (
    build_gateway_signed_headers,
    gateway_secret_env_name,
)

logger = logging.getLogger(__name__)

_ANALYTICS_URL_ENV = "ANALYTICS_URL"
_ANALYTICS_URL_DEFAULT = "http://analytics.adaptix.internal:8022"
_ANALYTICS_AUDIENCE = "adaptix-analytics"
_INGEST_PATH = "/api/v1/analytics/events"
_MAX_EVENTS_PER_CALL = 500
_DEFAULT_TIMEOUT_SECONDS = 5.0
_DEFAULT_RETRIES = 2  # 3 attempts total


class AnalyticsPublisherError(RuntimeError):
    """Raised when publication ultimately fails after retries."""


@dataclass(frozen=True)
class AnalyticsEvent:
    """One KPI source event ready to publish."""

    event_type: str
    tenant_id: str
    payload: Mapping[str, Any]
    occurred_at: datetime
    source_record_id: str | None = None

    def to_wire(self, source_service: str) -> dict[str, Any]:
        # The Analytics ingest schema is
        # KPIIngestEventRequest{event_type, source_service, source_record_id,
        # payload, occurred_at}. tenant_id is set from the signed identity
        # server-side — never trusted from the request body.
        occurred = self.occurred_at
        if occurred.tzinfo is None:
            occurred = occurred.replace(tzinfo=UTC)
        return {
            "event_type": self.event_type,
            "source_service": source_service,
            "source_record_id": self.source_record_id,
            "payload": dict(self.payload),
            "occurred_at": occurred.isoformat(),
        }


def _resolve_base_url() -> str:
    return os.environ.get(_ANALYTICS_URL_ENV, _ANALYTICS_URL_DEFAULT)


def _require_secret() -> str:
    name = gateway_secret_env_name()
    secret = os.environ.get(name, "").strip()
    if not secret:
        raise AnalyticsPublisherError(
            f"{name} is unset; the analytics publisher cannot sign an outbound "
            "identity without it. Set the secret in the task definition."
        )
    return secret


def _validate_event(event: AnalyticsEvent) -> None:
    if event.event_type not in ALL_EVENT_TYPES:
        raise ValueError(
            f"Unknown analytics event_type {event.event_type!r}. Add it to "
            "adaptix_contracts.analytics_events before publishing."
        )
    contract = payload_contract(event.event_type)
    if contract.value_field not in event.payload:
        raise ValueError(
            f"Analytics event {event.event_type!r} requires payload field "
            f"{contract.value_field!r} (the KPI engine reads it); got "
            f"keys={sorted(event.payload)}"
        )


class AnalyticsPublisher:
    """Signed, retrying, batched publisher of KPI source events.

    Not tied to a single tenant — the tenant_id per event is what identifies
    the row. The signed outbound identity uses the acting user's id when the
    caller supplies it (from the request context), else a synthetic service
    principal so audit records still resolve.
    """

    def __init__(
        self,
        source_service: str,
        *,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
        service_user_id: str = "00000000-0000-0000-0000-000000000000",
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = _DEFAULT_RETRIES,
    ) -> None:
        self._source_service = source_service
        self._base_url = base_url or _resolve_base_url()
        self._client = client
        self._service_user_id = service_user_id
        self._timeout = timeout_seconds
        self._retries = max_retries

    async def publish(
        self,
        event_type: str,
        *,
        tenant_id: str,
        payload: Mapping[str, Any],
        occurred_at: datetime | None = None,
        source_record_id: str | None = None,
        actor_user_id: str | None = None,
        raise_on_error: bool = False,
    ) -> bool:
        """Publish a single event. Returns True on success, False on give-up."""
        event = AnalyticsEvent(
            event_type=event_type,
            tenant_id=tenant_id,
            payload=payload,
            occurred_at=occurred_at or datetime.now(UTC),
            source_record_id=source_record_id,
        )
        return await self.publish_batch(
            [event], actor_user_id=actor_user_id, raise_on_error=raise_on_error
        )

    async def publish_batch(
        self,
        events: Iterable[AnalyticsEvent],
        *,
        actor_user_id: str | None = None,
        raise_on_error: bool = False,
    ) -> bool:
        """Publish a batch, chunked at 500 events per POST (the ingest limit).

        All events in one POST MUST share a tenant — the signed identity
        binds the tenant server-side. Batches spanning tenants are split.
        """
        by_tenant: dict[str, list[AnalyticsEvent]] = {}
        for ev in events:
            _validate_event(ev)
            by_tenant.setdefault(ev.tenant_id, []).append(ev)

        overall_ok = True
        for tenant_id, tenant_events in by_tenant.items():
            for start in range(0, len(tenant_events), _MAX_EVENTS_PER_CALL):
                chunk = tenant_events[start : start + _MAX_EVENTS_PER_CALL]
                ok = await self._post_chunk(
                    tenant_id=tenant_id,
                    events=chunk,
                    actor_user_id=actor_user_id,
                )
                overall_ok = overall_ok and ok
        if not overall_ok and raise_on_error:
            raise AnalyticsPublisherError(
                "Analytics publisher failed to POST at least one chunk; "
                "see prior ERROR logs for details."
            )
        return overall_ok

    async def _post_chunk(
        self,
        *,
        tenant_id: str,
        events: list[AnalyticsEvent],
        actor_user_id: str | None,
    ) -> bool:
        body = {"events": [e.to_wire(self._source_service) for e in events]}
        headers = self._build_headers(tenant_id=tenant_id, actor_user_id=actor_user_id)

        for attempt in range(self._retries + 1):
            try:
                async with self._acquire_client() as client:
                    resp = await client.post(
                        _INGEST_PATH,
                        json=body,
                        headers=headers,
                    )
                if resp.status_code == 202:
                    return True
                # 4xx (except 429) is a producer defect — not retryable.
                if 400 <= resp.status_code < 500 and resp.status_code != 429:
                    logger.error(
                        "analytics.publisher: non-retryable http=%s body=%s "
                        "source=%s events=%d",
                        resp.status_code,
                        resp.text[:200],
                        self._source_service,
                        len(events),
                    )
                    return False
                logger.warning(
                    "analytics.publisher: transient http=%s attempt=%d/%d source=%s",
                    resp.status_code,
                    attempt + 1,
                    self._retries + 1,
                    self._source_service,
                )
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                logger.warning(
                    "analytics.publisher: %s attempt=%d/%d source=%s",
                    type(exc).__name__,
                    attempt + 1,
                    self._retries + 1,
                    self._source_service,
                )
            if attempt < self._retries:
                await asyncio.sleep(0.25 * (2**attempt))

        logger.error(
            "analytics.publisher: give-up after %d attempts source=%s events=%d",
            self._retries + 1,
            self._source_service,
            len(events),
        )
        return False

    def _build_headers(
        self, *, tenant_id: str, actor_user_id: str | None
    ) -> dict[str, str]:
        secret = _require_secret()
        user_id = actor_user_id or self._service_user_id
        signed = build_gateway_signed_headers(
            shared_secret=secret,
            user_id=user_id,
            tenant_id=tenant_id,
            aud=_ANALYTICS_AUDIENCE,
            sub=user_id,
            email=None,
            roles=["service"],
        )
        signed.update(
            {
                "X-User-Id": user_id,
                "X-Tenant-Id": tenant_id,
                "X-User-Roles": "service",
            }
        )
        return signed

    def _acquire_client(self) -> _ClientCtx:
        return _ClientCtx(self._client, self._base_url, self._timeout)


class _ClientCtx:
    """Async context manager that yields the injected client if any,
    else builds a fresh short-lived one."""

    def __init__(
        self,
        client: httpx.AsyncClient | None,
        base_url: str,
        timeout: float,
    ) -> None:
        self._client = client
        self._base_url = base_url
        self._timeout = timeout
        self._owned: httpx.AsyncClient | None = None

    async def __aenter__(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        self._owned = httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout)
        return self._owned

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._owned is not None:
            await self._owned.aclose()
            self._owned = None


__all__ = [
    "AnalyticsEvent",
    "AnalyticsPublisher",
    "AnalyticsPublisherError",
]
