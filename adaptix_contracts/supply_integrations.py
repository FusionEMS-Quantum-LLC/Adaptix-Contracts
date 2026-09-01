"""Shared integration helpers for Inventory, Medications, and Narcotics services.

Provides canonical clients for publishing to Notifications, Analytics, and Audit
services. These are used by all three domain services to maintain consistency.

There is deliberately no SearchClient here. One existed and was removed because it
had never indexed a single row: its six call sites across the three domain services
were all unreachable, and the client itself was wrong on three axes at once against
Adaptix-Search-Service — it POSTed to /api/v1/search/index/{index} (not a route; the
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
from THIS module's sibling rbac_contracts matrix — narcotics:read,
medications:read, inventory:read_items respectively — and a Search test asserts
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
  X-Internal-Service-Key header and a full IndexEntityRequest body — the three
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

import logging
import os
from decimal import Decimal
from typing import Optional, Any
from datetime import datetime, timezone
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)


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
    """Client for publishing immutable audit entries to the Audit Service."""

    _BASE_URL = os.environ.get("AUDIT_SERVICE_URL", "http://audit:8000").rstrip("/")
    _TOKEN = os.environ.get("AUDIT_SERVICE_TOKEN", "")
    _TIMEOUT = float(os.environ.get("AUDIT_TIMEOUT_SECONDS", "5"))

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
    ) -> bool:
        """Log an immutable audit entry for a mutation."""
        payload = {
            "tenant_id": str(tenant_id),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": action,
            "actor_user_id": actor_user_id,
            "before_state": before_state,
            "after_state": after_state,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return await cls._post_audit(payload)

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
    ) -> bool:
        """Log an approval/confirmation action."""
        payload = {
            "tenant_id": str(tenant_id),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": f"approval_{approval_type}",
            "actor_user_id": approver_user_id,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return await cls._post_audit(payload)

    @classmethod
    async def _post_audit(cls, payload: dict[str, Any]) -> bool:
        """POST audit entry to Audit Service."""
        if not cls._BASE_URL:
            logger.warning("Audit Service not configured")
            return False

        headers = {
            "Authorization": f"Bearer {cls._TOKEN}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=cls._TIMEOUT) as client:
                resp = await client.post(
                    f"{cls._BASE_URL}/api/v1/audit/entries",
                    json=payload,
                    headers=headers,
                )
            resp.raise_for_status()
            logger.info(
                "Audit entry logged: %s/%s %s",
                payload.get("entity_type"),
                payload.get("entity_id"),
                payload.get("action"),
            )
            return True
        except Exception as exc:
            logger.warning("Failed to log audit entry: %s", exc)
            return False


__all__ = [
    "NotificationClient",
    "AnalyticsClient",
    "AuditClient",
]
