"""Shared integration helpers for Inventory, Medications, and Narcotics services.

Provides canonical clients for publishing to Notifications, Analytics, and Audit
services. These are used by all three domain services to maintain consistency.

There is deliberately no SearchClient here. One existed and was removed because it
had never indexed a single row: its six call sites across the three domain services
were all unreachable, and the client itself was wrong on three axes at once against
Adaptix-Search-Service â€” it POSTed to /api/v1/search/index/{index} (not a route; the
real one is POST /api/v1/search/index), authenticated with `Authorization: Bearer`
instead of the required X-Internal-Service-Key, and sent a payload carrying none of
IndexEntityRequest's required entity_type/entity_id/title fields. `_index_document`
then caught the resulting exception and returned False, so none of it ever surfaced.

The role-gate question this docstring used to leave open is now CLOSED upstream.
Adaptix-Search-Service PR #118 (merge 63845f4, deployed as
adaptix-production-search:138) inverted the `GET /api/v1/search` entity_type gate
from a three-value deny-list ({patient, epcr_chart, billing_claim}, which returned
every OTHER entity_type to every role including `viewer` and `dispatch`) to a
positive allow-list in search_app/permissions.py. inventory_items /
medication_lots / narcotic_vials are now classified there with entitlements copied
from THIS module's sibling rbac_contracts matrix â€” narcotics:read,
medications:read, inventory:read_items respectively â€” and a Search test asserts
equality with those permission sets, so widening a read permission here widens
search only deliberately and visibly.

Consequences for a future supply SearchClient:

* Indexing narcotic_vials no longer exposes substance_name / vial_id / lot_id /
  unit_id / seal_status / chain_of_custody_status to `viewer` or `dispatch`.
* An entity_type that is NOT classified in search_app.permissions is rejected at
  the write path (IndexEntityRequest -> 422) and returns no rows to any
  non-founder role. Use exactly the three registered strings above, or register
  the new one in Search first.
* The client must still POST /api/v1/search/index with the
  X-Internal-Service-Key header and a full IndexEntityRequest body â€” the three
  defects that made the removed client a no-op are unchanged.

Usage:
    from adaptix_contracts.supply_integrations import NotificationClient, AnalyticsClient, AuditClient

    # Publish low-stock notification
    await NotificationClient.send_low_stock_alert(
        tenant_id=tenant_id,
        recipient_user_id=user_id,
        item_name="Saline 0.9%",
        current_stock=5,
        par_level=20,
    )

    # Publish analytics event
    await AnalyticsClient.publish_stock_adjustment(
        tenant_id=tenant_id,
        quantity=10,
        cost=50.00,
    )

    # Log audit event
    await AuditClient.log_mutation(
        tenant_id=tenant_id,
        entity_type="inventory_item",
        entity_id=item_id,
        action="stock_adjusted",
        before_state={"stock": 15},
        after_state={"stock": 5},
    )
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from decimal import Decimal
from typing import Optional, Any
from datetime import datetime, timezone
from uuid import UUID

import httpx

from adaptix_contracts.gateway_signing import (
    build_gateway_signed_headers,
    gateway_secret_env_name,
)
from adaptix_contracts.schemas.audit_contracts import (
    AuditActorType,
    AuditIngestRequest,
    AuditOutcome,
    AuditSeverity,
)

logger = logging.getLogger(__name__)

# --- Audit rail configuration ------------------------------------------------
# Resolved per call, never at import. Binding a destination at module import is
# the exact trap documented in Adaptix-Narcotics-Service
# docs/NARCOTIC_EVENT_PUBLISHING_STATUS.md: setting the variable on a running
# task then has no effect, and the miswiring is invisible until someone reads
# the task definition.
_AUDIT_URL_ENV = "AUDIT_SERVICE_URL"
_AUDIT_URL_DEFAULT = "http://audit.adaptix.internal:8000"
_AUDIT_INGEST_PATH = "/api/v1/audit/events"
_AUDIT_AUDIENCE = "adaptix-audit"
_AUDIT_SERVICE_PRINCIPAL = "00000000-0000-0000-0000-000000000000"
_AUDIT_DEFAULT_RETRIES = 2
_AUDIT_TIMEOUT_ENV = "AUDIT_TIMEOUT_SECONDS"
_AUDIT_SOURCE_SERVICE_ENV = "ADAPTIX_SERVICE_NAME"


class AuditPublisherError(RuntimeError):
    """Raised when an audit event ultimately fails to reach the Audit service."""


class NotificationClient:
    """Client for publishing notifications to the Notifications Service.

    Publishes alerts via HTTP to the Notifications Service internal API.
    Best-effort delivery with retries.
    """

    _BASE_URL = os.environ.get(
        "NOTIFICATIONS_SERVICE_URL", "http://notifications:8000"
    ).rstrip("/")
    _TOKEN = os.environ.get("NOTIFICATIONS_SERVICE_TOKEN", "")
    _TIMEOUT = float(os.environ.get("NOTIFICATIONS_TIMEOUT_SECONDS", "5"))

    @classmethod
    async def send_low_stock_alert(
        cls,
        *,
        tenant_id: UUID,
        recipient_user_id: str,
        item_name: str,
        current_stock: int,
        par_level: int,
        recommended_quantity: int,
        unit: str = "units",
        cost_estimate: Optional[float] = None,
    ) -> bool:
        """Send low-stock alert to Supply Officer.

        Args:
            tenant_id: Tenant context
            recipient_user_id: User to notify
            item_name: Item name
            current_stock: Current stock level
            par_level: Par/target level
            recommended_quantity: Recommended reorder amount
            unit: Unit of measure
            cost_estimate: Estimated reorder cost

        Returns:
            True if delivery succeeded, False otherwise.
        """
        payload = {
            "tenant_id": str(tenant_id),
            "recipient_user_id": recipient_user_id,
            "notification_type": "low_stock_alert",
            "title": f"Low Stock: {item_name}",
            "message": f"{item_name} is below par level ({current_stock}/{par_level} {unit})",
            "item_name": item_name,
            "current_stock": current_stock,
            "par_level": par_level,
            "recommended_quantity": recommended_quantity,
            "unit": unit,
            "cost_estimate": cost_estimate,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return await cls._post_notification(payload)

    @classmethod
    async def send_expiration_alert(
        cls,
        *,
        tenant_id: UUID,
        recipient_user_id: str,
        item_name: str,
        expiration_date: datetime,
        current_stock: int,
        waste_forecast: Decimal,
    ) -> bool:
        """Send expiration alert."""
        payload = {
            "tenant_id": str(tenant_id),
            "recipient_user_id": recipient_user_id,
            "notification_type": "expiration_alert",
            "title": f"Expiring Soon: {item_name}",
            "message": f"{item_name} expires on {expiration_date.strftime('%Y-%m-%d')}",
            "item_name": item_name,
            "expiration_date": expiration_date.isoformat(),
            "current_stock": current_stock,
            # str(), not the Decimal itself -- see the identical comment on
            # AnalyticsClient.publish_waste_event's `cost` field below in this
            # module for why an unconverted Decimal here silently drops the
            # alert instead of raising.
            "waste_forecast": str(waste_forecast),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return await cls._post_notification(payload)

    @classmethod
    async def send_recall_alert(
        cls,
        *,
        tenant_id: UUID,
        recipient_user_id: str,
        item_name: str,
        recall_id: str,
        affected_lots: list[str],
        recommended_action: str,
    ) -> bool:
        """Send medication/medication recall alert."""
        payload = {
            "tenant_id": str(tenant_id),
            "recipient_user_id": recipient_user_id,
            "notification_type": "recall_alert",
            "title": f"RECALL: {item_name}",
            "message": f"{item_name} has been recalled (ID: {recall_id})",
            "item_name": item_name,
            "recall_id": recall_id,
            "affected_lots": affected_lots,
            "recommended_action": recommended_action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return await cls._post_notification(payload)

    @classmethod
    async def send_discrepancy_alert(
        cls,
        *,
        tenant_id: UUID,
        recipient_user_id: str,
        substance_name: str,
        missing_quantity: int,
        unit: str,
        escalation_flag: bool = False,
    ) -> bool:
        """Send narcotics discrepancy alert."""
        severity = "CRITICAL" if escalation_flag else "WARNING"
        payload = {
            "tenant_id": str(tenant_id),
            "recipient_user_id": recipient_user_id,
            "notification_type": "discrepancy_alert",
            "title": f"{severity}: Narcotic Discrepancy - {substance_name}",
            "message": f"{substance_name} discrepancy: {missing_quantity} {unit} missing",
            "substance_name": substance_name,
            "missing_quantity": missing_quantity,
            "unit": unit,
            "escalation_flag": escalation_flag,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return await cls._post_notification(payload)

    @classmethod
    async def _post_notification(cls, payload: dict[str, Any]) -> bool:
        """POST notification to Notifications Service."""
        if not cls._BASE_URL:
            logger.warning("Notifications Service not configured")
            return False

        headers = {
            "Authorization": f"Bearer {cls._TOKEN}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=cls._TIMEOUT) as client:
                resp = await client.post(
                    f"{cls._BASE_URL}/api/v1/notifications/send",
                    json=payload,
                    headers=headers,
                )
            resp.raise_for_status()
            logger.info("Notification sent: %s", payload.get("notification_type"))
            return True
        except Exception as exc:
            logger.warning("Failed to send notification: %s", exc)
            return False


class AnalyticsClient:
    """Client for publishing analytics events to the Analytics Service."""

    _BASE_URL = os.environ.get("ANALYTICS_SERVICE_URL", "http://analytics:8000").rstrip(
        "/"
    )
    _TOKEN = os.environ.get("ANALYTICS_SERVICE_TOKEN", "")
    _TIMEOUT = float(os.environ.get("ANALYTICS_TIMEOUT_SECONDS", "5"))

    @classmethod
    async def publish_usage_event(
        cls,
        *,
        tenant_id: UUID,
        unit_id: Optional[str],
        event_type: str,
        quantity: int,
        cost: Optional[float] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Publish usage event to Analytics Service."""
        payload = {
            "tenant_id": str(tenant_id),
            "unit_id": unit_id,
            "event_type": event_type,
            "quantity": quantity,
            "cost": cost,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }
        return await cls._post_event(payload)

    @classmethod
    async def publish_waste_event(
        cls,
        *,
        tenant_id: UUID,
        unit_id: Optional[str],
        waste_reason: str,
        quantity: int,
        cost: Decimal,
    ) -> bool:
        """Publish waste event to Analytics Service."""
        payload = {
            "tenant_id": str(tenant_id),
            "unit_id": unit_id,
            "event_type": "waste_recorded",
            "waste_reason": waste_reason,
            "quantity": quantity,
            # str(), not the Decimal itself: this dict goes straight to
            # httpx's `json=`, which uses the stdlib json encoder and cannot
            # serialise Decimal (`TypeError: Object of type Decimal is not
            # JSON serializable`). `_post_event` catches that in a broad
            # `except Exception` and returns False, so an unconverted Decimal
            # here silently drops the waste event instead of raising. This
            # matches the wire convention every other exact quantity in this
            # package has used since 2.37.0: an exact value serialises as a
            # JSON string, not a JSON number.
            "cost": str(cost),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return await cls._post_event(payload)

    @classmethod
    async def publish_risk_event(
        cls,
        *,
        tenant_id: UUID,
        unit_id: str,
        risk_type: str,
        risk_score: float,
        risk_level: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Publish risk event (expiration risk, diversion risk, etc)."""
        payload = {
            "tenant_id": str(tenant_id),
            "unit_id": unit_id,
            "event_type": "risk_recorded",
            "risk_type": risk_type,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }
        return await cls._post_event(payload)

    @classmethod
    async def _post_event(cls, payload: dict[str, Any]) -> bool:
        """POST event to Analytics Service."""
        if not cls._BASE_URL:
            logger.warning("Analytics Service not configured")
            return False

        headers = {
            "Authorization": f"Bearer {cls._TOKEN}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=cls._TIMEOUT) as client:
                resp = await client.post(
                    f"{cls._BASE_URL}/api/v1/analytics/events",
                    json=payload,
                    headers=headers,
                )
            resp.raise_for_status()
            logger.info("Analytics event published: %s", payload.get("event_type"))
            return True
        except Exception as exc:
            logger.warning("Failed to publish analytics event: %s", exc)
            return False


class AuditClient:
    """Publisher of immutable audit events to the shared Audit service.

    REWRITTEN 2026-09-05. The previous implementation could not have written a
    single row, and had not. It was wrong on three independent axes at once,
    exactly like the SearchClient described at the top of this module:

    * **Wrong route.** It POSTed to ``/api/v1/audit/entries``. That path exists
      nowhere in the platform -- an org-wide code search returns zero hits
      outside this file. The real ingest surface is
      ``POST /api/v1/audit/events`` (Adaptix-Audit-Service
      ``backend/audit_app/api/audit.py``, router prefix ``/api/v1/audit``,
      responding ``201 CREATED``).
    * **Wrong host.** It defaulted to ``http://audit:8000``. Cloud Map publishes
      the service as ``audit.adaptix.internal`` in namespace ``adaptix.internal``
      (verified against the live namespace, 2026-09-05); the bare label does not
      resolve from an awsvpc task.
    * **Wrong auth.** It sent ``Authorization: Bearer`` built from
      ``AUDIT_SERVICE_TOKEN``, which is set on no consumer. The service requires
      a *signed gateway context* and pins the audience to ``adaptix-audit``
      (``backend/audit_app/api/gateway_auth.py``); it explicitly refuses to fall
      back to plain headers.

    ``_post_audit`` then caught the resulting exception in a bare
    ``except Exception`` and returned ``False``, and every caller wraps the call
    in its own ``except Exception`` as well. So the failure was swallowed twice
    and surfaced nowhere.

    Runtime evidence, captured 2026-09-05 against account 793439286972:
    ``adaptix-production-narcotics:437``, ``adaptix-production-medications:125``
    and ``adaptix-production-inventory:230`` set neither ``AUDIT_SERVICE_URL``
    nor ``AUDIT_SERVICE_TOKEN``, so all three took the broken defaults. All
    three DO carry ``ADAPTIX_GATEWAY_SHARED_SECRET``, which is why this
    correction needs no infrastructure change to start working.

    Scope note: the primary controlled-substance ledger is NOT this rail.
    Adaptix-Narcotics-Service maintains its own hash-chained chain-of-custody
    tables locally (migrations 005 / 009). What was lost here is the
    replication of those mutations into the shared, tenant-isolated Audit
    service -- not the DEA ledger itself.

    Delivery semantics: transient failures (network, timeout, 429, 5xx) are
    retried with exponential backoff. A non-429 4xx is a producer defect, is
    not retried, and is logged at ERROR with the response body. Give-up is
    logged at ERROR. Callers that require the audit write to be durable before
    reporting domain success pass ``raise_on_error=True``; the default remains
    ``False`` so existing callers keep their current control flow.
    """

    @staticmethod
    def _base_url() -> str:
        return os.environ.get(_AUDIT_URL_ENV, _AUDIT_URL_DEFAULT).rstrip("/")

    @staticmethod
    def _timeout() -> float:
        return float(os.environ.get(_AUDIT_TIMEOUT_ENV, "5"))

    @staticmethod
    def _source_service() -> Optional[str]:
        value = os.environ.get(_AUDIT_SOURCE_SERVICE_ENV, "").strip()
        return value or None

    @staticmethod
    def _coerce_actor(
        actor_user_id: Optional[str],
    ) -> tuple[Optional[UUID], AuditActorType, dict[str, Any]]:
        """Map a legacy string actor onto the typed contract without inventing one.

        ``AuditIngestRequest.actor_user_id`` is a UUID. Callers in this package
        have always passed a plain string. A value that does not parse is NOT
        discarded and NOT replaced with a fabricated UUID -- it is preserved
        verbatim in metadata and the record is classified as service-initiated,
        so the legal record never claims an actor it cannot identify.
        """
        if actor_user_id is None:
            return None, AuditActorType.SERVICE, {}
        try:
            return UUID(str(actor_user_id)), AuditActorType.USER, {}
        except (ValueError, AttributeError, TypeError):
            return (
                None,
                AuditActorType.SERVICE,
                {"actor_user_id_raw": str(actor_user_id)},
            )

    @classmethod
    async def log_mutation(
        cls,
        *,
        tenant_id: UUID,
        entity_type: str,
        entity_id: str,
        action: str,
        actor_user_id: Optional[str] = None,
        before_state: Optional[dict[str, Any]] = None,
        after_state: Optional[dict[str, Any]] = None,
        reason: Optional[str] = None,
        severity: AuditSeverity = AuditSeverity.LOW,
        outcome: AuditOutcome = AuditOutcome.SUCCESS,
        correlation_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        raise_on_error: bool = False,
    ) -> bool:
        """Append an immutable audit event for a domain mutation."""
        actor_uuid, actor_type, extra_metadata = cls._coerce_actor(actor_user_id)

        # ``changes`` is the structured before/after diff; ``metadata`` is
        # producer context. AuditIngestRequest documents that conflating them is
        # a defect, so ``reason`` goes to metadata and the states go to changes.
        changes: Optional[dict[str, Any]] = None
        if before_state is not None or after_state is not None:
            changes = {"before": before_state, "after": after_state}

        metadata: dict[str, Any] = dict(extra_metadata)
        if reason is not None:
            metadata["reason"] = reason

        request = AuditIngestRequest(
            tenant_id=tenant_id,
            actor_user_id=actor_uuid,
            actor_type=actor_type,
            action=action,
            resource_type=entity_type,
            resource_id=entity_id,
            severity=severity,
            outcome=outcome,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            metadata=metadata,
            changes=changes,
            occurred_at=datetime.now(timezone.utc),
            source_service=cls._source_service(),
        )
        return await cls._post_audit(request, raise_on_error=raise_on_error)

    @classmethod
    async def log_approval(
        cls,
        *,
        tenant_id: UUID,
        entity_type: str,
        entity_id: str,
        approver_user_id: str,
        approval_type: str,
        reason: Optional[str] = None,
        correlation_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        raise_on_error: bool = False,
    ) -> bool:
        """Append an immutable audit event for an approval/confirmation."""
        actor_uuid, actor_type, extra_metadata = cls._coerce_actor(approver_user_id)

        metadata: dict[str, Any] = dict(extra_metadata)
        metadata["approval_type"] = approval_type
        if reason is not None:
            metadata["reason"] = reason

        request = AuditIngestRequest(
            tenant_id=tenant_id,
            actor_user_id=actor_uuid,
            actor_type=actor_type,
            action=f"approval_{approval_type}",
            resource_type=entity_type,
            resource_id=entity_id,
            severity=AuditSeverity.MEDIUM,
            outcome=AuditOutcome.SUCCESS,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            metadata=metadata,
            occurred_at=datetime.now(timezone.utc),
            source_service=cls._source_service(),
        )
        return await cls._post_audit(request, raise_on_error=raise_on_error)

    @classmethod
    def _build_headers(cls, request: AuditIngestRequest) -> dict[str, str]:
        """Return signed-context headers the Audit service will actually accept.

        The audience MUST be ``adaptix-audit``: the service compares it against
        a hardcoded ``EXPECTED_AUDIENCE`` regardless of environment, so a
        context minted for another service is rejected 401.
        """
        secret_env = gateway_secret_env_name()
        secret = os.environ.get(secret_env, "").strip()
        if not secret:
            raise AuditPublisherError(
                f"{secret_env} is unset; the audit publisher cannot sign an "
                "outbound identity without it. Set the secret in the task "
                "definition."
            )

        tenant_id = str(request.tenant_id)
        # The signed identity is what the service trusts. Its tenant must equal
        # the body tenant or ingest_event returns 403 for a non-founder caller.
        user_id = (
            str(request.actor_user_id)
            if request.actor_user_id is not None
            else _AUDIT_SERVICE_PRINCIPAL
        )
        headers = build_gateway_signed_headers(
            shared_secret=secret,
            user_id=user_id,
            tenant_id=tenant_id,
            aud=_AUDIT_AUDIENCE,
            sub=user_id,
            email=None,
            roles=["service"],
        )
        headers.update(
            {
                "X-User-Id": user_id,
                "X-Tenant-Id": tenant_id,
                "X-User-Roles": "service",
                "Content-Type": "application/json",
            }
        )
        if request.correlation_id:
            headers["X-Request-Id"] = request.correlation_id
        return headers

    @classmethod
    async def _post_audit(
        cls,
        request: AuditIngestRequest,
        *,
        raise_on_error: bool = False,
        retries: int = _AUDIT_DEFAULT_RETRIES,
    ) -> bool:
        """POST one audit event, retrying only what is actually retryable."""
        base_url = cls._base_url()
        headers = cls._build_headers(request)
        body = json.loads(request.model_dump_json())

        for attempt in range(retries + 1):
            try:
                async with httpx.AsyncClient(timeout=cls._timeout()) as client:
                    resp = await client.post(
                        f"{base_url}{_AUDIT_INGEST_PATH}",
                        json=body,
                        headers=headers,
                    )
                if 200 <= resp.status_code < 300:
                    logger.info(
                        "audit.publisher: accepted action=%s resource=%s/%s tenant=%s",
                        request.action,
                        request.resource_type,
                        request.resource_id,
                        request.tenant_id,
                    )
                    return True
                if 400 <= resp.status_code < 500 and resp.status_code != 429:
                    # A producer defect. Retrying cannot fix it and would only
                    # hide it; surface the body so the mismatch is diagnosable.
                    logger.error(
                        "audit.publisher: non-retryable http=%s body=%s action=%s "
                        "resource=%s/%s tenant=%s",
                        resp.status_code,
                        resp.text[:400],
                        request.action,
                        request.resource_type,
                        request.resource_id,
                        request.tenant_id,
                    )
                    break
                logger.warning(
                    "audit.publisher: transient http=%s attempt=%d/%d action=%s",
                    resp.status_code,
                    attempt + 1,
                    retries + 1,
                    request.action,
                )
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                logger.warning(
                    "audit.publisher: %s attempt=%d/%d action=%s",
                    type(exc).__name__,
                    attempt + 1,
                    retries + 1,
                    request.action,
                )
            if attempt < retries:
                await asyncio.sleep(0.25 * (2**attempt))

        logger.error(
            "audit.publisher: GAVE UP action=%s resource=%s/%s tenant=%s -- "
            "this audit event was NOT recorded",
            request.action,
            request.resource_type,
            request.resource_id,
            request.tenant_id,
        )
        if raise_on_error:
            raise AuditPublisherError(
                f"audit event {request.action!r} for "
                f"{request.resource_type}/{request.resource_id} was not recorded"
            )
        return False


__all__ = [
    "AuditPublisherError",
    "NotificationClient",
    "AnalyticsClient",
    "AuditClient",
]
