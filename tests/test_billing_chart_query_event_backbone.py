"""Every existing crew-query wire event has its producer and consumer declared."""

import pytest

from adaptix_contracts.event_subscriptions import (
    UNREGISTERED_SUBSCRIBED_TOPICS,
    subscribers_of,
    subscription_edges,
    validate_declared_subscriptions,
)
from adaptix_contracts.events.operational_envelope import (
    OperationalEventEnvelope,
    assert_event_type_registered,
)
from adaptix_contracts.events.registry import producer_of


@pytest.mark.parametrize(
    ("topic", "producer", "consumer", "consumer_slug"),
    [
        ("billing.chart.query_opened", "billing", "epcr-service", "epcr"),
        ("billing.chart.query_withdrawn", "billing", "epcr-service", "epcr"),
        ("billing.chart.query_resolved", "billing", "epcr-service", "epcr"),
        ("epcr.chart.query_answered", "epcr", "billing-service", "billing"),
    ],
)
def test_crew_query_wire_names_reach_the_opposite_service(
    topic: str, producer: str, consumer: str, consumer_slug: str
) -> None:
    envelope = OperationalEventEnvelope(
        tenant_id="tenant-query-contract-test",
        source_service=producer,
        source_record_id="query-contract-test",
        source_version=1,
        observed_at="2026-10-26T00:00:00Z",
        effective_at="2026-10-26T00:00:00Z",
        event_type=topic,
    )
    assert_event_type_registered(envelope)
    assert producer_of(topic).slug == producer
    assert subscribers_of(topic) == {consumer}
    assert topic not in UNREGISTERED_SUBSCRIBED_TOPICS
    edges = [edge for edge in subscription_edges() if edge.topic == topic]
    assert len(edges) == 1
    assert edges[0].producer_slug == producer
    assert edges[0].consumer_slug == consumer_slug


def test_refreshed_billing_and_epcr_declarations_remain_consistent() -> None:
    validate_declared_subscriptions()


def test_epcr_also_declares_its_existing_billing_eligibility_handler() -> None:
    assert subscribers_of("billing.eligibility.result.v1") == {"epcr-service"}
