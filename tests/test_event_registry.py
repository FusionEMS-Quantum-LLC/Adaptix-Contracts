from __future__ import annotations

from adaptix_contracts.events import registry


def test_realtime_registry_includes_billing_claim_updated() -> None:
    assert registry.BILLING_CLAIM_UPDATED == "billing.claim.updated"
    assert registry.ALL_EVENTS[registry.BILLING_CLAIM_UPDATED] == {
        "version": "1.0",
        "source_service": "billing",
    }
    assert registry.is_registered("billing.claim.updated") is True


def test_realtime_registry_includes_epcr_chart_updated() -> None:
    assert registry.EPCR_CHART_UPDATED == "epcr.chart.updated"
    assert registry.ALL_EVENTS[registry.EPCR_CHART_UPDATED] == {
        "version": "1.0",
        "source_service": "epcr",
    }
    assert registry.is_registered("epcr.chart.updated") is True