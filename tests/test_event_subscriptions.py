"""Tests for adaptix_contracts.event_subscriptions (declared Core bus subscriptions).

Each negative test hands ``validate_declarations`` a deliberately broken copy of
the real declaration and asserts the exact problem it reports, so every rule
that guards the real declaration is shown to fail when that rule is broken.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Collection, Mapping, Sequence

import pytest

from adaptix_contracts.event_consumers import (
    BILLING_SERVICE_CONSUMER,
    HOSPITAL_SERVICE_CONSUMER,
    KNOWN_EVENT_BUS_CONSUMERS,
    TRANSPORT_SERVICE_CONSUMER,
)
from adaptix_contracts.event_subscriptions import (
    EVENT_BUS_CONSUMER_DECLARATIONS,
    EVENT_BUS_CONSUMER_SERVICE_SLUGS,
    EVENT_BUS_SUBSCRIPTIONS,
    UNPROVEN_EVENT_BUS_CONSUMERS,
    UNREGISTERED_SUBSCRIBED_TOPICS,
    CodeCitation,
    EventBusConsumerDeclaration,
    EventSubscription,
    EventSubscriptionDeclarationError,
    SubscriptionEdge,
    subscribers_of,
    subscription_edges,
    validate_declarations,
    validate_declared_subscriptions,
)
from adaptix_contracts.events.registry import ALL_EVENTS, producer_of
from adaptix_contracts.schemas.service_registry import ALL_SERVICES, SERVICE_BY_SLUG

_SERVICE_REPOSITORY_NAMES: dict[str, str] = {
    service.slug: service.name for service in ALL_SERVICES
}


def _declared_consumers() -> set[str]:
    return {declaration.consumer for declaration in EVENT_BUS_CONSUMER_DECLARATIONS}


def _declaration(consumer: str) -> EventBusConsumerDeclaration:
    for declaration in EVENT_BUS_CONSUMER_DECLARATIONS:
        if declaration.consumer == consumer:
            return declaration
    raise AssertionError(f"{consumer!r} is not declared")


def _replacing(
    replacement: EventBusConsumerDeclaration,
) -> tuple[EventBusConsumerDeclaration, ...]:
    return tuple(
        replacement if declaration.consumer == replacement.consumer else declaration
        for declaration in EVENT_BUS_CONSUMER_DECLARATIONS
    )


def _renamed_topic(
    declaration: EventBusConsumerDeclaration, old: str, new: str
) -> EventBusConsumerDeclaration:
    subscriptions: list[EventSubscription] = []
    for subscription in declaration.subscriptions:
        if subscription.topic == old:
            subscription = dataclasses.replace(subscription, topic=new)
        subscriptions.append(subscription)
    return dataclasses.replace(declaration, subscriptions=tuple(subscriptions))


def _validate(
    declarations: Sequence[EventBusConsumerDeclaration],
    *,
    known_consumers: Collection[str] = KNOWN_EVENT_BUS_CONSUMERS,
    registered_topics: Collection[str] = frozenset(ALL_EVENTS),
    unregistered_topics: Mapping[str, str] = UNREGISTERED_SUBSCRIBED_TOPICS,
) -> None:
    validate_declarations(
        declarations,
        known_consumers=known_consumers,
        registered_topics=registered_topics,
        unregistered_topics=unregistered_topics,
        unproven_consumers=UNPROVEN_EVENT_BUS_CONSUMERS,
        service_repository_names=_SERVICE_REPOSITORY_NAMES,
    )


def test_the_real_declaration_validates_against_the_live_registries() -> None:
    validate_declared_subscriptions()
    _validate(EVENT_BUS_CONSUMER_DECLARATIONS)


def test_every_declared_consumer_is_in_known_event_bus_consumers() -> None:
    assert _declared_consumers() <= KNOWN_EVENT_BUS_CONSUMERS


def test_every_known_consumer_is_declared_or_listed_as_unproven() -> None:
    declared = _declared_consumers()
    unproven = set(UNPROVEN_EVENT_BUS_CONSUMERS)
    assert declared | unproven == KNOWN_EVENT_BUS_CONSUMERS
    assert not declared & unproven


def test_every_subscribed_topic_is_registered_or_listed_with_a_reason() -> None:
    for consumer, topics in EVENT_BUS_SUBSCRIPTIONS.items():
        for topic in topics:
            registered = topic in ALL_EVENTS
            listed = topic in UNREGISTERED_SUBSCRIBED_TOPICS
            assert registered != listed, (consumer, topic)
            if listed:
                assert UNREGISTERED_SUBSCRIBED_TOPICS[topic].strip(), topic


def test_unregistered_entries_are_still_subscribed_and_still_unregistered() -> None:
    subscribed: set[str] = set()
    for topics in EVENT_BUS_SUBSCRIPTIONS.values():
        subscribed |= topics
    for topic in UNREGISTERED_SUBSCRIBED_TOPICS:
        assert topic in subscribed, topic
        assert topic not in ALL_EVENTS, topic


def test_mapped_slugs_exist_in_all_services_and_name_the_repository() -> None:
    for declaration in EVENT_BUS_CONSUMER_DECLARATIONS:
        if declaration.service_slug is None:
            continue
        service = SERVICE_BY_SLUG[declaration.service_slug]
        repository_name = declaration.repository.split("/")[1]
        assert service.name == repository_name, declaration.consumer


def test_consumer_to_service_slug_mapping() -> None:
    assert dict(EVENT_BUS_CONSUMER_SERVICE_SLUGS) == {
        "billing-service": "billing",
        "cad-service": "cad",
        "communications-service": "communications",
        "epcr-service": "epcr",
        "hospital-service": None,
        "transport-service": "transport",
    }


def test_hospital_is_unmapped_because_no_service_names_its_repository() -> None:
    hospital = _declaration(HOSPITAL_SERVICE_CONSUMER)
    assert hospital.service_slug is None
    assert hospital.unmapped_reason
    service_names = {service.name for service in ALL_SERVICES}
    assert hospital.repository.split("/")[1] not in service_names


def test_subscribers_of_returns_every_consumer_of_a_topic() -> None:
    assert subscribers_of("epcr.chart.finalized") == {
        BILLING_SERVICE_CONSUMER,
        HOSPITAL_SERVICE_CONSUMER,
    }
    assert subscribers_of("cad.case.created") == {TRANSPORT_SERVICE_CONSUMER}
    assert subscribers_of("not.a.subscribed.topic") == frozenset()


def test_subscription_edges_carry_the_registered_producer_or_none() -> None:
    edges = subscription_edges()
    declared_pairs = sum(
        len(declaration.subscriptions)
        for declaration in EVENT_BUS_CONSUMER_DECLARATIONS
    )
    assert len(edges) == declared_pairs
    expected = {
        SubscriptionEdge("epcr", "epcr.chart.finalized", "billing-service", "billing"),
        SubscriptionEdge("epcr", "epcr.chart.finalized", "hospital-service", None),
        SubscriptionEdge(None, "cad.case.created", "transport-service", "transport"),
    }
    assert expected <= set(edges)
    for edge in edges:
        if edge.topic in ALL_EVENTS:
            assert edge.producer_slug == producer_of(edge.topic).slug
        else:
            assert edge.producer_slug is None
            assert edge.topic in UNREGISTERED_SUBSCRIBED_TOPICS


def test_validation_fails_when_a_subscription_names_an_unknown_topic() -> None:
    billing = _declaration(BILLING_SERVICE_CONSUMER)
    broken = _renamed_topic(billing, "epcr.chart.finalized", "epcr.chart.finalised")
    message = "'billing-service' subscribes to unknown topic 'epcr.chart.finalised'"
    with pytest.raises(EventSubscriptionDeclarationError, match=re.escape(message)):
        _validate(_replacing(broken))


def test_validation_fails_for_a_consumer_that_is_not_known() -> None:
    ghost = dataclasses.replace(
        _declaration(TRANSPORT_SERVICE_CONSUMER), consumer="ghost-service"
    )
    message = "'ghost-service' is not in KNOWN_EVENT_BUS_CONSUMERS"
    with pytest.raises(EventSubscriptionDeclarationError, match=re.escape(message)):
        _validate((*EVENT_BUS_CONSUMER_DECLARATIONS, ghost))


def test_validation_fails_when_a_known_consumer_is_not_declared() -> None:
    known = KNOWN_EVENT_BUS_CONSUMERS | {"ghost-service"}
    message = "known consumer 'ghost-service' is neither declared nor listed"
    with pytest.raises(EventSubscriptionDeclarationError, match=re.escape(message)):
        _validate(EVENT_BUS_CONSUMER_DECLARATIONS, known_consumers=known)


def test_validation_fails_when_a_slug_names_a_different_repository() -> None:
    wrong = dataclasses.replace(
        _declaration(BILLING_SERVICE_CONSUMER), service_slug="cad"
    )
    message = "but slug 'cad' names Adaptix-CAD-Service"
    with pytest.raises(EventSubscriptionDeclarationError, match=re.escape(message)):
        _validate(_replacing(wrong))


def test_validation_fails_when_a_slug_is_not_in_all_services() -> None:
    wrong = dataclasses.replace(
        _declaration(BILLING_SERVICE_CONSUMER), service_slug="no-such-slug"
    )
    message = "maps to slug 'no-such-slug', which is not in ALL_SERVICES"
    with pytest.raises(EventSubscriptionDeclarationError, match=re.escape(message)):
        _validate(_replacing(wrong))


def test_validation_fails_when_an_unmapped_repository_has_a_service() -> None:
    unmapped = dataclasses.replace(
        _declaration(TRANSPORT_SERVICE_CONSUMER),
        service_slug=None,
        unmapped_reason="claimed to have no service",
    )
    message = "is unmapped, but ServiceDefinition slug(s) ['transport'] name"
    with pytest.raises(EventSubscriptionDeclarationError, match=re.escape(message)):
        _validate(_replacing(unmapped))


def test_validation_fails_when_an_unregistered_topic_becomes_registered() -> None:
    registered = frozenset(ALL_EVENTS) | {"cad.case.created"}
    message = "'cad.case.created' is registered in ALL_EVENTS; remove it"
    with pytest.raises(EventSubscriptionDeclarationError, match=re.escape(message)):
        _validate(EVENT_BUS_CONSUMER_DECLARATIONS, registered_topics=registered)


def test_validation_fails_for_a_citation_not_pinned_to_a_commit() -> None:
    transport = _declaration(TRANSPORT_SERVICE_CONSUMER)
    unpinned = dataclasses.replace(
        transport,
        consumer_name_evidence=dataclasses.replace(
            transport.consumer_name_evidence, commit="main"
        ),
    )
    message = "commit 'main' is not a full 40-character SHA"
    with pytest.raises(EventSubscriptionDeclarationError, match=re.escape(message)):
        _validate(_replacing(unpinned))


def test_validation_fails_when_a_pair_cites_only_another_repository() -> None:
    transport = _declaration(TRANSPORT_SERVICE_CONSUMER)
    elsewhere = CodeCitation(
        "FusionEMS-Quantum-LLC/Adaptix-CAD-Service",
        "0" * 40,
        "backend/cad_app/main.py",
        1,
    )
    broken = dataclasses.replace(
        transport,
        subscriptions=(EventSubscription("cad.case.created", (elsewhere,)),),
    )
    message = (
        "subscription 'cad.case.created' cites nothing in "
        "FusionEMS-Quantum-LLC/Adaptix-Transport-Service"
    )
    with pytest.raises(EventSubscriptionDeclarationError, match=re.escape(message)):
        _validate(_replacing(broken))


def test_validation_fails_for_a_stale_unregistered_entry() -> None:
    stale = {**UNREGISTERED_SUBSCRIBED_TOPICS, "retired.topic": "no longer used"}
    message = "lists 'retired.topic', which no declared consumer subscribes to"
    with pytest.raises(EventSubscriptionDeclarationError, match=re.escape(message)):
        _validate(EVENT_BUS_CONSUMER_DECLARATIONS, unregistered_topics=stale)
