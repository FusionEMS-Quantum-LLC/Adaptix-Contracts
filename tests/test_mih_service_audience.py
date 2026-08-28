"""MIH service-identity regression contract."""

from adaptix_contracts.service_audiences import (
    KNOWN_SERVICE_AUDIENCES,
    is_known_service_audience,
)


def test_mih_audience_is_registered_exactly() -> None:
    assert "adaptix-mih" in KNOWN_SERVICE_AUDIENCES
    assert is_known_service_audience("adaptix-mih") is True
    assert is_known_service_audience("adaptix_mih") is False
