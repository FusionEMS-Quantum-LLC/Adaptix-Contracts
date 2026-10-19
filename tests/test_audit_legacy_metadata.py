from __future__ import annotations

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from adaptix_contracts.audit_contracts import AuditServiceClient


@pytest.mark.parametrize(
    ("ip_address", "user_agent"),
    [
        ("192.0.2.1", None),
        (None, "test-client/1.0"),
        ("192.0.2.1", "test-client/1.0"),
    ],
)
async def test_legacy_request_metadata_is_reported_without_logging_values(
    caplog: pytest.LogCaptureFixture,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    session = Mock()
    session.flush = AsyncMock()

    with caplog.at_level("WARNING", logger="adaptix_contracts.audit_contracts"):
        await AuditServiceClient.log_action(
            tenant_id=uuid4(),
            action="test.action",
            resource_type="test",
            session=session,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    assert "does not persist ip_address or user_agent" in caplog.text
    assert ip_address is None or ip_address not in caplog.text
    assert user_agent is None or user_agent not in caplog.text
    session.add.assert_called_once()
    session.flush.assert_awaited_once()
