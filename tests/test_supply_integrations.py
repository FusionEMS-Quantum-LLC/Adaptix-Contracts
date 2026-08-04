"""Integration tests for supply domain integrations.

Tests the shared NotificationClient, AnalyticsClient, and AuditClient with mock
services.

READ THIS BEFORE ADDING A TEST HERE. These tests patch httpx.AsyncClient, force a
success response, and assert `result is True`. They assert nothing about the URL,
the headers, or the request body. The deleted SearchClient tests were written the
same way, and that is exactly why a client wrong on all three at once — wrong path,
wrong auth header, wrong payload shape — passed this suite for its entire life
without ever indexing a row. A test that mocks the transport and asserts only the
return value measures nothing about the contract.

If you extend this file, assert on the call arguments: `mock_post.call_args` gives
you the URL, `headers=`, and `json=` actually sent. Compare them against the
receiving service's route, its auth dependency, and its request model.
"""

import pytest
import httpx
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock, Mock, patch

pytest_plugins = ("pytest_asyncio",)


def _mock_success_response(payload: dict | None = None) -> Mock:
    response = Mock()
    response.raise_for_status = Mock()
    response.json = Mock(return_value=payload or {})
    return response


@pytest.mark.asyncio
async def test_notification_client_low_stock_alert():
    """Test sending low-stock alert notification."""
    from adaptix_contracts.supply_integrations import NotificationClient

    tenant_id = uuid4()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = _mock_success_response({"id": "notif-123"})

        mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await NotificationClient.send_low_stock_alert(
            tenant_id=tenant_id,
            recipient_user_id="user-123",
            item_name="Saline 0.9%",
            current_stock=5,
            par_level=20,
            recommended_quantity=15,
            unit="boxes",
            cost_estimate=75.00,
        )

        assert result is True


@pytest.mark.asyncio
async def test_notification_client_expiration_alert():
    """Test sending expiration alert notification."""
    from adaptix_contracts.supply_integrations import NotificationClient

    tenant_id = uuid4()
    expiration_date = datetime.now(timezone.utc)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = _mock_success_response()

        mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await NotificationClient.send_expiration_alert(
            tenant_id=tenant_id,
            recipient_user_id="user-123",
            item_name="Saline 0.9%",
            expiration_date=expiration_date,
            current_stock=10,
            waste_forecast=50.00,
        )

        assert result is True


@pytest.mark.asyncio
async def test_notification_client_recall_alert():
    """Test sending medication recall alert."""
    from adaptix_contracts.supply_integrations import NotificationClient

    tenant_id = uuid4()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = _mock_success_response()

        mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await NotificationClient.send_recall_alert(
            tenant_id=tenant_id,
            recipient_user_id="user-123",
            item_name="Medication X",
            recall_id="FDA-2026-001",
            affected_lots=["LOT-001", "LOT-002"],
            recommended_action="Quarantine and return to vendor",
        )

        assert result is True


@pytest.mark.asyncio
async def test_notification_client_discrepancy_alert():
    """Test sending narcotics discrepancy alert."""
    from adaptix_contracts.supply_integrations import NotificationClient

    tenant_id = uuid4()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = _mock_success_response()

        mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await NotificationClient.send_discrepancy_alert(
            tenant_id=tenant_id,
            recipient_user_id="user-123",
            substance_name="Fentanyl",
            missing_quantity=5,
            unit="vials",
            escalation_flag=True,
        )

        assert result is True


@pytest.mark.asyncio
async def test_analytics_client_publish_usage_event():
    """Test publishing usage event to analytics."""
    from adaptix_contracts.supply_integrations import AnalyticsClient

    tenant_id = uuid4()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = _mock_success_response()

        mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await AnalyticsClient.publish_usage_event(
            tenant_id=tenant_id,
            unit_id="unit-123",
            event_type="stock_adjusted",
            quantity=10,
            cost=50.00,
            metadata={"reason": "restock"},
        )

        assert result is True


@pytest.mark.asyncio
async def test_analytics_client_publish_waste_event():
    """Test publishing waste event to analytics."""
    from adaptix_contracts.supply_integrations import AnalyticsClient

    tenant_id = uuid4()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = _mock_success_response()

        mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await AnalyticsClient.publish_waste_event(
            tenant_id=tenant_id,
            unit_id="unit-123",
            waste_reason="expired",
            quantity=5,
            cost=25.00,
        )

        assert result is True


@pytest.mark.asyncio
async def test_analytics_client_publish_risk_event():
    """Test publishing risk event to analytics."""
    from adaptix_contracts.supply_integrations import AnalyticsClient

    tenant_id = uuid4()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = _mock_success_response()

        mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await AnalyticsClient.publish_risk_event(
            tenant_id=tenant_id,
            unit_id="unit-123",
            risk_type="expiration_risk",
            risk_score=75.5,
            risk_level="yellow",
        )

        assert result is True


@pytest.mark.asyncio
async def test_audit_client_log_mutation():
    """Test logging a mutation to audit service."""
    from adaptix_contracts.supply_integrations import AuditClient

    tenant_id = uuid4()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = _mock_success_response()

        mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await AuditClient.log_mutation(
            tenant_id=tenant_id,
            entity_type="inventory_item",
            entity_id="item-123",
            action="stock_adjusted",
            actor_user_id="user-123",
            before_state={"stock": 15},
            after_state={"stock": 5},
            reason="usage",
        )

        assert result is True


@pytest.mark.asyncio
async def test_audit_client_log_approval():
    """Test logging an approval to audit service."""
    from adaptix_contracts.supply_integrations import AuditClient

    tenant_id = uuid4()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = _mock_success_response()

        mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await AuditClient.log_approval(
            tenant_id=tenant_id,
            entity_type="narcotic_discrepancy",
            entity_id="disc-123",
            approver_user_id="user-456",
            approval_type="supervisor_review",
            reason="Discrepancy resolved",
        )

        assert result is True


@pytest.mark.asyncio
async def test_integration_graceful_degradation_no_config():
    """Test that integrations degrade gracefully when not configured."""
    from adaptix_contracts.supply_integrations import NotificationClient

    tenant_id = uuid4()

    with patch.dict("os.environ", {}, clear=True):
        # Without configuration, should return False gracefully
        result = await NotificationClient.send_low_stock_alert(
            tenant_id=tenant_id,
            recipient_user_id="user-123",
            item_name="Item",
            current_stock=1,
            par_level=10,
            recommended_quantity=9,
        )

        assert result is False


@pytest.mark.asyncio
async def test_integration_handles_network_errors():
    """Test that integrations handle network errors gracefully."""
    from adaptix_contracts.supply_integrations import NotificationClient

    tenant_id = uuid4()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.ConnectError("Connection failed")
        )
        mock_client_class.return_value = mock_client

        result = await NotificationClient.send_low_stock_alert(
            tenant_id=tenant_id,
            recipient_user_id="user-123",
            item_name="Item",
            current_stock=1,
            par_level=10,
            recommended_quantity=9,
        )

        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
