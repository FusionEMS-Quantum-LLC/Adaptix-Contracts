"""Declared Core event-bus subscriptions: which consumer listens to which topic.

``events.registry.ALL_EVENTS`` records the PRODUCER of every registered event
type and ``event_consumers.KNOWN_EVENT_BUS_CONSUMERS`` records the consumer
names, but until this module nothing in the contract said who listens to what.
A question such as "if Billing stops, which services stop receiving work?"
could not be answered from this package.

How a subscription is chosen (read from Core, not assumed)
----------------------------------------------------------
Core's per-consumer fan-out (``EventBusService.get_pending_events_for_consumer``
in Adaptix-Core-Service ``core/backend/core_app/events/service.py``, lines
333-370 at ``c485b0155a837da8298f302ee0907bf15f0d4e85``) offers EVERY event
published after a consumer's first poll to that consumer. Core has no
per-consumer topic filter. Each consumer picks its topics with its own handler
map and acknowledges everything else unprocessed. So a subscription is proven
here by the line, in the consumer's own repository, that registers or
dispatches the topic inside a poll worker that the service's startup code
launches.

What this declaration claims, and what it does not
--------------------------------------------------
* Every (consumer, topic) pair cites the repository, commit, file and line
  that prove it. Nothing was added from a comment, a name or a guess.
* Topics are the literal strings the consumer code subscribes to, not
  ``events.registry`` constants. If a registry constant is ever renamed, the
  consumer still listens on the old string; a literal keeps the tests red until
  the pair is re-audited instead of silently following the rename.
* A topic a consumer handles that is not a key of ``ALL_EVENTS`` is listed in
  :data:`UNREGISTERED_SUBSCRIBED_TOPICS` with the reason. It is declared
  because the consumer really listens for it; it is not registered because no
  producer is recorded for it in this contract.
* Each worker's start is gated by its own service's configuration (Core
  event-bus settings, and for some services an enable flag). Whether a given
  environment satisfies that gate is runtime state and is NOT claimed here.
* Payload compatibility between producer and consumer is NOT covered.
* Consumer names and service-registry slugs are separate identifier namespaces
  (``"billing-service"`` versus ``"billing"``). Each declaration maps one to the
  other explicitly, and only when a ``ServiceDefinition`` in
  ``schemas.service_registry`` names the consumer's repository.

Audited 2026-09-10 against each repository's ``main`` at the commit recorded in
every citation. Core's push-delivery registry (``EVENT_BUS_SERVICE_REGISTRY_JSON``
in ``core_app/event_bus.py``) is a runtime environment value, not code, so
nothing is declared from it.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from adaptix_contracts.event_consumers import (
    BILLING_SERVICE_CONSUMER,
    CAD_SERVICE_CONSUMER,
    COMMUNICATIONS_SERVICE_CONSUMER,
    EPCR_SERVICE_CONSUMER,
    HOSPITAL_SERVICE_CONSUMER,
    KNOWN_EVENT_BUS_CONSUMERS,
    TRANSPORT_SERVICE_CONSUMER,
)
from adaptix_contracts.events.registry import ALL_EVENTS, producer_of
from adaptix_contracts.schemas.service_registry import ALL_SERVICES

__all__ = [
    "EVENT_BUS_CONSUMER_DECLARATIONS",
    "EVENT_BUS_CONSUMER_SERVICE_SLUGS",
    "EVENT_BUS_SUBSCRIPTIONS",
    "UNPROVEN_EVENT_BUS_CONSUMERS",
    "UNREGISTERED_SUBSCRIBED_TOPICS",
    "CodeCitation",
    "EventBusConsumerDeclaration",
    "EventSubscription",
    "EventSubscriptionDeclarationError",
    "SubscriptionEdge",
    "subscribers_of",
    "subscription_edges",
    "validate_declarations",
    "validate_declared_subscriptions",
]

_FULL_COMMIT_SHA: Final[re.Pattern[str]] = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True)
class CodeCitation:
    """One line of code, at one commit, in one GitHub repository."""

    repository: str
    """``owner/name`` on GitHub."""
    commit: str
    """Full 40-character commit SHA the line was read at."""
    path: str
    """Repository-relative file path."""
    line: int
    """1-based line number at ``commit``."""


@dataclass(frozen=True)
class EventSubscription:
    """One topic a consumer handles, with the code that proves it."""

    topic: str
    evidence: tuple[CodeCitation, ...]


@dataclass(frozen=True)
class EventBusConsumerDeclaration:
    """Everything proven about one Core event-bus consumer."""

    consumer: str
    """Name the service passes as ``consumer=`` when it polls Core."""
    repository: str
    """``owner/name`` of the repository that polls under ``consumer``."""
    service_slug: str | None
    """``ServiceDefinition.slug`` whose ``name`` is that repository, or None."""
    unmapped_reason: str | None
    """Why ``service_slug`` is None; must be None when a slug is mapped."""
    consumer_name_evidence: CodeCitation
    """Where the repository sets the consumer name it polls under."""
    dispatch_evidence: CodeCitation
    """Where the poll worker routes a delivered event by its type."""
    worker_start_evidence: tuple[CodeCitation, ...]
    """Startup code that hands the handler map to the worker and launches it."""
    subscriptions: tuple[EventSubscription, ...]


@dataclass(frozen=True)
class SubscriptionEdge:
    """One producer -> topic -> consumer link derived from the declarations."""

    producer_slug: str | None
    """Registered producer slug, or None when the topic is not in ALL_EVENTS."""
    topic: str
    consumer: str
    consumer_slug: str | None


class EventSubscriptionDeclarationError(ValueError):
    """A declaration names a consumer, topic, slug or citation the contract rejects."""


@dataclass(frozen=True)
class _AuditedCheckout:
    """A repository at the exact commit its citations were read at."""

    repository: str
    commit: str

    def cite(self, path: str, line: int) -> CodeCitation:
        return CodeCitation(self.repository, self.commit, path, line)


def _subscription(topic: str, *evidence: CodeCitation) -> EventSubscription:
    return EventSubscription(topic, evidence)


# ---------------------------------------------------------------------------
# Audited checkouts. Every citation below was read at exactly these commits.
# ---------------------------------------------------------------------------
_BILLING: Final[_AuditedCheckout] = _AuditedCheckout(
    "FusionEMS-Quantum-LLC/Adaptix-Billing-Service",
    "3683e08d190abd255b12ce664ac02c16d5070dab",
)
_CAD: Final[_AuditedCheckout] = _AuditedCheckout(
    "FusionEMS-Quantum-LLC/Adaptix-CAD-Service",
    "be8db83a3000062a68cc5485e6970bd1a08facb0",
)
_COMMUNICATIONS: Final[_AuditedCheckout] = _AuditedCheckout(
    "FusionEMS-Quantum-LLC/Adaptix-Communications-Service",
    "afea394a679c5058b983547c1eb36671e582db10",
)
_EPCR: Final[_AuditedCheckout] = _AuditedCheckout(
    "FusionEMS-Quantum-LLC/Adaptix-EPCR-Service",
    "658bfda8cf84fde11d2401c330d5f233d819cca5",
)
_HOSPITAL: Final[_AuditedCheckout] = _AuditedCheckout(
    "FusionEMS-Quantum-LLC/Adaptix-Hospital-Service",
    "1a802bc1a585c429b954077335d45a3016ba04ae",
)
_TRANSPORT: Final[_AuditedCheckout] = _AuditedCheckout(
    "FusionEMS-Quantum-LLC/Adaptix-Transport-Service",
    "bf98ccbc88738f28473eaca6892dfdc758bd1408",
)
# Communications compares against three topic constants imported from this
# package, so they are cited at the Contracts commit Communications installs
# (its backend/pyproject.toml line 32 at the Communications commit above).
_CONTRACTS_AT_COMMUNICATIONS_PIN: Final[_AuditedCheckout] = _AuditedCheckout(
    "FusionEMS-Quantum-LLC/Adaptix-Contracts",
    "637c8c3d09b40874dd22ebc73e0b38ce9d9f33b2",
)

# ---------------------------------------------------------------------------
# Billing: handler map built and started in main.py lifespan.
# ---------------------------------------------------------------------------
_BILLING_MAIN: Final[str] = "backend/billing_app/main.py"
_BILLING_WORKER: Final[str] = "backend/billing_app/background_worker.py"

_BILLING_DECLARATION: Final[EventBusConsumerDeclaration] = EventBusConsumerDeclaration(
    consumer=BILLING_SERVICE_CONSUMER,
    repository=_BILLING.repository,
    service_slug="billing",
    unmapped_reason=None,
    consumer_name_evidence=_BILLING.cite(_BILLING_WORKER, 85),
    dispatch_evidence=_BILLING.cite(_BILLING_WORKER, 300),
    worker_start_evidence=(
        _BILLING.cite(_BILLING_MAIN, 1003),
        _BILLING.cite(_BILLING_MAIN, 1004),
    ),
    subscriptions=(
        _subscription("epcr.chart.finalized", _BILLING.cite(_BILLING_MAIN, 992)),
        _subscription("epcr.chart.billing_handoff", _BILLING.cite(_BILLING_MAIN, 994)),
        _subscription("epcr.chart.amended", _BILLING.cite(_BILLING_MAIN, 997)),
        _subscription("call.received", _BILLING.cite(_BILLING_MAIN, 998)),
        _subscription(
            "cad.dispatch.billing_handoff_ready", _BILLING.cite(_BILLING_MAIN, 1000)
        ),
    ),
)

# ---------------------------------------------------------------------------
# CAD: handler map built by event_worker_bootstrap.build_cad_event_registry.
# ---------------------------------------------------------------------------
_CAD_BOOTSTRAP: Final[str] = "backend/cad_app/event_worker_bootstrap.py"
_CAD_WORKER: Final[str] = "backend/cad_app/background_worker.py"
_CAD_AIR: Final[str] = "backend/cad_app/air_event_consumer.py"


def _cad_registered(topic: str, line: int) -> EventSubscription:
    """A topic registered by a literal in ``build_cad_event_registry``."""
    return _subscription(topic, _CAD.cite(_CAD_BOOTSTRAP, line))


def _cad_air_mission(topic: str, line: int) -> EventSubscription:
    """An ``AIR_MISSION_EVENT_TYPES`` key, registered by the loop at line 130."""
    return _subscription(
        topic, _CAD.cite(_CAD_AIR, line), _CAD.cite(_CAD_BOOTSTRAP, 130)
    )


_CAD_DECLARATION: Final[EventBusConsumerDeclaration] = EventBusConsumerDeclaration(
    consumer=CAD_SERVICE_CONSUMER,
    repository=_CAD.repository,
    service_slug="cad",
    unmapped_reason=None,
    consumer_name_evidence=_CAD.cite(_CAD_WORKER, 42),
    dispatch_evidence=_CAD.cite(_CAD_WORKER, 610),
    worker_start_evidence=(
        _CAD.cite("backend/cad_app/main.py", 234),
        _CAD.cite(_CAD_BOOTSTRAP, 209),
        _CAD.cite("backend/cad_app/main.py", 238),
    ),
    subscriptions=(
        _cad_registered("crewlink.page.acknowledged", 83),
        _cad_registered("crewlink.cad.page_escalated", 88),
        _cad_registered("workforce.shift.created", 94),
        _cad_registered("workforce.shift.cancelled", 97),
        _cad_registered("workforce.ot.filled", 99),
        _cad_registered("workforce.vacancy.created", 101),
        _cad_registered("workforce.schedule.change", 104),
        _cad_registered("fleet.unit.status_changed", 110),
        _cad_registered("fleet.vehicle.out_of_service", 115),
        _subscription(
            "flow_guard.incident_created",
            _CAD.cite("backend/cad_app/flow_guard_consumer.py", 40),
            _CAD.cite(_CAD_BOOTSTRAP, 120),
        ),
        _cad_air_mission("air.mission.accepted", 100),
        _cad_air_mission("air.mission.declined", 101),
        _cad_air_mission("air.mission.launched", 104),
        _cad_air_mission("air.mission.arrived", 105),
        _cad_air_mission("air.mission.cancelled", 106),
        _cad_air_mission("air.mission.aborted", 107),
        _cad_air_mission("air.mission.ground_fallback", 108),
        _cad_air_mission("air.mission.hold", 111),
        _cad_air_mission("air.mission.completed", 113),
        _cad_registered("hospital.incoming.acknowledged", 136),
        _cad_registered("hospital.incoming.diverted", 141),
        _cad_registered("hospital.incoming_patient.arrived", 146),
        _cad_registered("hospital.incoming_patient.cancelled", 151),
    ),
)

# ---------------------------------------------------------------------------
# Communications: Core poll worker feeds the push receiver's dispatcher.
# ---------------------------------------------------------------------------
_COMMS_POLLER: Final[str] = "backend/communications_app/core_event_poll_worker.py"
_COMMS_ROUTER: Final[str] = "backend/communications_app/api/internal_events_router.py"
_COMMS_ACTIVATION: Final[str] = (
    "backend/communications_app/services/family_bridge_activation.py"
)
_CONTRACTS_TRANSPORT_EVENTS: Final[str] = "adaptix_contracts/epcr/transport_events.py"
_CONTRACTS_PATIENT_EVENTS: Final[str] = "adaptix_contracts/patient_identity/events.py"

_COMMUNICATIONS_DECLARATION: Final[EventBusConsumerDeclaration] = (
    EventBusConsumerDeclaration(
        consumer=COMMUNICATIONS_SERVICE_CONSUMER,
        repository=_COMMUNICATIONS.repository,
        service_slug="communications",
        unmapped_reason=None,
        consumer_name_evidence=_COMMUNICATIONS.cite(_COMMS_POLLER, 68),
        dispatch_evidence=_COMMUNICATIONS.cite(_COMMS_POLLER, 306),
        worker_start_evidence=(
            _COMMUNICATIONS.cite("backend/communications_app/main.py", 236),
        ),
        subscriptions=(
            _subscription(
                "epcr.chart.created",
                _COMMUNICATIONS.cite(_COMMS_ROUTER, 311),
                _COMMUNICATIONS.cite(_COMMS_ACTIVATION, 110),
            ),
            _subscription(
                "epcr.chart.patient_identified",
                _COMMUNICATIONS.cite(_COMMS_ROUTER, 328),
                _COMMUNICATIONS.cite(_COMMS_ACTIVATION, 111),
            ),
            _subscription(
                "epcr.transport.destination.updated",
                _COMMUNICATIONS.cite(_COMMS_ROUTER, 347),
                _CONTRACTS_AT_COMMUNICATIONS_PIN.cite(_CONTRACTS_TRANSPORT_EVENTS, 52),
            ),
            _subscription(
                "epcr.transport.arrived_destination",
                _COMMUNICATIONS.cite(_COMMS_ROUTER, 364),
                _CONTRACTS_AT_COMMUNICATIONS_PIN.cite(_CONTRACTS_TRANSPORT_EVENTS, 58),
            ),
            _subscription(
                "patient.nok.consent.changed",
                _COMMUNICATIONS.cite(_COMMS_ROUTER, 383),
                _CONTRACTS_AT_COMMUNICATIONS_PIN.cite(_CONTRACTS_PATIENT_EVENTS, 60),
            ),
        ),
    )
)

# ---------------------------------------------------------------------------
# ePCR: handler map built and started in main.py lifespan.
# ---------------------------------------------------------------------------
_EPCR_MAIN: Final[str] = "backend/epcr_app/main.py"
_EPCR_WORKER: Final[str] = "backend/epcr_app/background_worker.py"

_EPCR_DECLARATION: Final[EventBusConsumerDeclaration] = EventBusConsumerDeclaration(
    consumer=EPCR_SERVICE_CONSUMER,
    repository=_EPCR.repository,
    service_slug="epcr",
    unmapped_reason=None,
    consumer_name_evidence=_EPCR.cite(_EPCR_WORKER, 90),
    dispatch_evidence=_EPCR.cite(_EPCR_WORKER, 271),
    worker_start_evidence=(_EPCR.cite(_EPCR_MAIN, 352), _EPCR.cite(_EPCR_MAIN, 354)),
    subscriptions=(
        _subscription("fire.incident.created", _EPCR.cite(_EPCR_MAIN, 342)),
        _subscription("billing.claim.status_updated", _EPCR.cite(_EPCR_MAIN, 349)),
    ),
)

# ---------------------------------------------------------------------------
# Hospital: SUBSCRIBED_EVENTS + OBSERVED_EVENTS gate, _dispatch_strict routes.
# Its poll loop (``event_loop`` in event_bus.py) returns at once unless
# EVENT_BUS_POLL_ENABLED is "true" and the Core event-bus settings are present.
# ---------------------------------------------------------------------------
_HOSPITAL_BUS: Final[str] = "backend/hospital_app/services/event_bus.py"

_HOSPITAL_DECLARATION: Final[EventBusConsumerDeclaration] = EventBusConsumerDeclaration(
    consumer=HOSPITAL_SERVICE_CONSUMER,
    repository=_HOSPITAL.repository,
    service_slug=None,
    unmapped_reason=(
        "schemas.service_registry.ALL_SERVICES has no ServiceDefinition named "
        "Adaptix-Hospital-Service, so there is no slug to map this consumer to."
    ),
    consumer_name_evidence=_HOSPITAL.cite(_HOSPITAL_BUS, 61),
    dispatch_evidence=_HOSPITAL.cite(_HOSPITAL_BUS, 511),
    worker_start_evidence=(_HOSPITAL.cite("backend/hospital_app/main.py", 44),),
    subscriptions=(
        _subscription(
            "epcr.chart.finalized",
            _HOSPITAL.cite(_HOSPITAL_BUS, 68),
            _HOSPITAL.cite(_HOSPITAL_BUS, 80),
            _HOSPITAL.cite(_HOSPITAL_BUS, 453),
        ),
        _subscription(
            "epcr.completed",
            _HOSPITAL.cite(_HOSPITAL_BUS, 69),
            _HOSPITAL.cite(_HOSPITAL_BUS, 83),
            _HOSPITAL.cite(_HOSPITAL_BUS, 453),
        ),
        _subscription(
            "flow_guard.incident_created",
            _HOSPITAL.cite(_HOSPITAL_BUS, 84),
            _HOSPITAL.cite(_HOSPITAL_BUS, 455),
        ),
        _subscription(
            "hospital.cath_lab.activate_recommended",
            _HOSPITAL.cite(_HOSPITAL_BUS, 92),
            _HOSPITAL.cite(_HOSPITAL_BUS, 457),
        ),
    ),
)

# ---------------------------------------------------------------------------
# Transport: background_worker.build_event_registry, started in main.py.
# ---------------------------------------------------------------------------
_TRANSPORT_WORKER: Final[str] = "backend/transportlink_app/background_worker.py"
_TRANSPORT_MAIN: Final[str] = "backend/transportlink_app/main.py"

_TRANSPORT_DECLARATION: Final[EventBusConsumerDeclaration] = (
    EventBusConsumerDeclaration(
        consumer=TRANSPORT_SERVICE_CONSUMER,
        repository=_TRANSPORT.repository,
        service_slug="transport",
        unmapped_reason=None,
        consumer_name_evidence=_TRANSPORT.cite(_TRANSPORT_WORKER, 100),
        dispatch_evidence=_TRANSPORT.cite(_TRANSPORT_WORKER, 291),
        worker_start_evidence=(
            _TRANSPORT.cite(_TRANSPORT_MAIN, 377),
            _TRANSPORT.cite(_TRANSPORT_MAIN, 380),
        ),
        subscriptions=(
            _subscription("cad.case.created", _TRANSPORT.cite(_TRANSPORT_WORKER, 147)),
        ),
    )
)

EVENT_BUS_CONSUMER_DECLARATIONS: Final[tuple[EventBusConsumerDeclaration, ...]] = (
    _BILLING_DECLARATION,
    _CAD_DECLARATION,
    _COMMUNICATIONS_DECLARATION,
    _EPCR_DECLARATION,
    _HOSPITAL_DECLARATION,
    _TRANSPORT_DECLARATION,
)
"""Every Core event-bus consumer whose subscriptions are proven from code."""

#: Known consumers whose subscriptions could not be proven from code, with why.
#: Empty: every name in ``KNOWN_EVENT_BUS_CONSUMERS`` is declared above. A
#: consumer whose topics come only from runtime configuration belongs here, not
#: in :data:`EVENT_BUS_CONSUMER_DECLARATIONS`.
UNPROVEN_EVENT_BUS_CONSUMERS: Final[Mapping[str, str]] = MappingProxyType[str, str]({})

_NOT_IN_REGISTRY: Final[str] = (
    "Not a key of events.registry.ALL_EVENTS, so this contract records no "
    "producer for it."
)

#: Topics a declared consumer subscribes to that ``ALL_EVENTS`` does not
#: register, each with the reason. Registering one means proving its producer
#: (``events/registry.py`` cites a producer file and line for its entries); once
#: a topic is registered the tests require its entry here to be removed.
UNREGISTERED_SUBSCRIBED_TOPICS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "air.mission.aborted": _NOT_IN_REGISTRY,
        "air.mission.accepted": _NOT_IN_REGISTRY,
        "air.mission.arrived": _NOT_IN_REGISTRY,
        "air.mission.cancelled": _NOT_IN_REGISTRY,
        "air.mission.completed": _NOT_IN_REGISTRY,
        "air.mission.declined": _NOT_IN_REGISTRY,
        "air.mission.ground_fallback": _NOT_IN_REGISTRY,
        "air.mission.hold": _NOT_IN_REGISTRY,
        "air.mission.launched": _NOT_IN_REGISTRY,
        "billing.claim.status_updated": (
            "Not a key of events.registry.ALL_EVENTS, so this contract records no "
            "producer for it. ALL_EVENTS registers billing.claim.status_changed "
            "(source 'billing') under a different name; which name reaches the "
            "ePCR subscriber was not proven by this audit."
        ),
        "cad.case.created": _NOT_IN_REGISTRY,
        "cad.dispatch.billing_handoff_ready": _NOT_IN_REGISTRY,
        "call.received": _NOT_IN_REGISTRY,
        "crewlink.cad.page_escalated": _NOT_IN_REGISTRY,
        "crewlink.page.acknowledged": _NOT_IN_REGISTRY,
        "epcr.chart.patient_identified": _NOT_IN_REGISTRY,
        "epcr.completed": (
            "Not a key of events.registry.ALL_EVENTS, so this contract records no "
            "producer for it. Hospital routes it to the same handler as "
            "epcr.chart.finalized."
        ),
        "flow_guard.incident_created": _NOT_IN_REGISTRY,
        "hospital.incoming.acknowledged": _NOT_IN_REGISTRY,
        "hospital.incoming.diverted": _NOT_IN_REGISTRY,
        "hospital.incoming_patient.arrived": _NOT_IN_REGISTRY,
        "hospital.incoming_patient.cancelled": _NOT_IN_REGISTRY,
        "workforce.ot.filled": _NOT_IN_REGISTRY,
        "workforce.schedule.change": _NOT_IN_REGISTRY,
        "workforce.shift.created": _NOT_IN_REGISTRY,
        "workforce.vacancy.created": _NOT_IN_REGISTRY,
    }
)

EVENT_BUS_SUBSCRIPTIONS: Final[Mapping[str, frozenset[str]]] = MappingProxyType(
    {
        declaration.consumer: frozenset(
            subscription.topic for subscription in declaration.subscriptions
        )
        for declaration in EVENT_BUS_CONSUMER_DECLARATIONS
    }
)
"""Consumer name -> the topics its code subscribes to."""

EVENT_BUS_CONSUMER_SERVICE_SLUGS: Final[Mapping[str, str | None]] = MappingProxyType(
    {
        declaration.consumer: declaration.service_slug
        for declaration in EVENT_BUS_CONSUMER_DECLARATIONS
    }
)
"""Consumer name -> service-registry slug, or None when no slug names its repo."""


def subscribers_of(topic: str) -> frozenset[str]:
    """Return the names of the consumers whose code subscribes to ``topic``."""
    return frozenset(
        consumer
        for consumer, topics in EVENT_BUS_SUBSCRIPTIONS.items()
        if topic in topics
    )


def subscription_edges() -> tuple[SubscriptionEdge, ...]:
    """Return every declared producer -> topic -> consumer link.

    ``producer_slug`` comes from ``events.registry.producer_of`` and is None for
    a topic in :data:`UNREGISTERED_SUBSCRIBED_TOPICS`: this contract records no
    producer for it, and nothing here guesses one.
    """
    return tuple(
        SubscriptionEdge(
            producer_slug=(
                producer_of(subscription.topic).slug
                if subscription.topic in ALL_EVENTS
                else None
            ),
            topic=subscription.topic,
            consumer=declaration.consumer,
            consumer_slug=declaration.service_slug,
        )
        for declaration in EVENT_BUS_CONSUMER_DECLARATIONS
        for subscription in declaration.subscriptions
    )


def _citation_problems(citation: CodeCitation, where: str) -> list[str]:
    problems: list[str] = []
    if citation.repository.count("/") != 1:
        problems.append(
            f"{where}: repository {citation.repository!r} is not owner/name"
        )
    if _FULL_COMMIT_SHA.fullmatch(citation.commit) is None:
        problems.append(
            f"{where}: commit {citation.commit!r} is not a full 40-character SHA"
        )
    if not citation.path or citation.path.startswith("/"):
        problems.append(f"{where}: path {citation.path!r} is not repository-relative")
    if citation.line < 1:
        problems.append(f"{where}: line {citation.line} is not a 1-based line number")
    return problems


def _repository_name(repository: str) -> str:
    return repository.rsplit("/", 1)[-1]


def _slug_problems(
    declaration: EventBusConsumerDeclaration,
    service_repository_names: Mapping[str, str],
) -> list[str]:
    consumer = declaration.consumer
    slug = declaration.service_slug
    repository_name = _repository_name(declaration.repository)
    problems: list[str] = []
    if slug is None:
        if not (declaration.unmapped_reason or "").strip():
            problems.append(f"{consumer!r} has no service slug and no unmapped_reason")
        owners = sorted(
            candidate
            for candidate, name in service_repository_names.items()
            if name == repository_name
        )
        if owners:
            problems.append(
                f"{consumer!r} is unmapped, but ServiceDefinition slug(s) {owners} "
                f"name {repository_name}; map it"
            )
        return problems
    if declaration.unmapped_reason is not None:
        problems.append(
            f"{consumer!r} maps to {slug!r} but also has an unmapped_reason"
        )
    owner = service_repository_names.get(slug)
    if owner is None:
        problems.append(
            f"{consumer!r} maps to slug {slug!r}, which is not in ALL_SERVICES"
        )
    elif owner != repository_name:
        problems.append(
            f"{consumer!r} polls from {repository_name}, but slug {slug!r} "
            f"names {owner}"
        )
    return problems


def _consumer_citation_problems(declaration: EventBusConsumerDeclaration) -> list[str]:
    consumer = declaration.consumer
    problems: list[str] = []
    if not declaration.worker_start_evidence:
        problems.append(f"{consumer!r} has no worker_start_evidence")
    labelled: list[tuple[str, CodeCitation]] = [
        ("consumer_name_evidence", declaration.consumer_name_evidence),
        ("dispatch_evidence", declaration.dispatch_evidence),
    ]
    labelled.extend(
        ("worker_start_evidence", citation)
        for citation in declaration.worker_start_evidence
    )
    for label, citation in labelled:
        where = f"{consumer!r} {label}"
        problems.extend(_citation_problems(citation, where))
        if citation.repository != declaration.repository:
            problems.append(
                f"{where} cites {citation.repository}, not {declaration.repository}"
            )
    return problems


def _subscription_problems(
    declaration: EventBusConsumerDeclaration,
    registered_topics: Collection[str],
    unregistered_topics: Mapping[str, str],
) -> list[str]:
    consumer = declaration.consumer
    problems: list[str] = []
    if not declaration.subscriptions:
        problems.append(f"{consumer!r} declares no subscriptions")
    seen: set[str] = set()
    for subscription in declaration.subscriptions:
        topic = subscription.topic
        where = f"{consumer!r} subscription {topic!r}"
        if topic in seen:
            problems.append(f"{where} is declared more than once")
        seen.add(topic)
        registered = topic in registered_topics
        explained = topic in unregistered_topics
        if not registered and not explained:
            problems.append(
                f"{consumer!r} subscribes to unknown topic {topic!r}: not in "
                "ALL_EVENTS and not in UNREGISTERED_SUBSCRIBED_TOPICS"
            )
        elif registered and explained:
            problems.append(
                f"{topic!r} is registered in ALL_EVENTS; remove it from "
                "UNREGISTERED_SUBSCRIBED_TOPICS"
            )
        if not subscription.evidence:
            problems.append(f"{where} has no evidence")
        elif all(
            citation.repository != declaration.repository
            for citation in subscription.evidence
        ):
            problems.append(f"{where} cites nothing in {declaration.repository}")
        for citation in subscription.evidence:
            problems.extend(_citation_problems(citation, where))
    return problems


def validate_declarations(
    declarations: Sequence[EventBusConsumerDeclaration],
    *,
    known_consumers: Collection[str],
    registered_topics: Collection[str],
    unregistered_topics: Mapping[str, str],
    unproven_consumers: Mapping[str, str],
    service_repository_names: Mapping[str, str],
) -> None:
    """Raise :class:`EventSubscriptionDeclarationError` naming every problem.

    ``service_repository_names`` maps each service-registry slug to its
    ``ServiceDefinition.name`` (the repository name). Every input is a parameter
    rather than a module global, so a test can hand in a deliberately broken
    declaration and watch this fail.
    """
    problems: list[str] = []
    declared: set[str] = set()
    subscribed: set[str] = set()
    for declaration in declarations:
        consumer = declaration.consumer
        if consumer in declared:
            problems.append(f"{consumer!r} is declared more than once")
        declared.add(consumer)
        if consumer not in known_consumers:
            problems.append(f"{consumer!r} is not in KNOWN_EVENT_BUS_CONSUMERS")
        if consumer in unproven_consumers:
            problems.append(f"{consumer!r} is declared and also listed as unproven")
        problems.extend(_slug_problems(declaration, service_repository_names))
        problems.extend(_consumer_citation_problems(declaration))
        problems.extend(
            _subscription_problems(declaration, registered_topics, unregistered_topics)
        )
        subscribed.update(
            subscription.topic for subscription in declaration.subscriptions
        )
    for consumer, reason in unproven_consumers.items():
        if consumer not in known_consumers:
            problems.append(f"unproven consumer {consumer!r} is not a known consumer")
        if not reason.strip():
            problems.append(f"unproven consumer {consumer!r} has no reason")
    for consumer in sorted(known_consumers):
        if consumer not in declared and consumer not in unproven_consumers:
            problems.append(
                f"known consumer {consumer!r} is neither declared nor listed as "
                "unproven"
            )
    for topic, reason in unregistered_topics.items():
        if topic not in subscribed:
            problems.append(
                f"UNREGISTERED_SUBSCRIBED_TOPICS lists {topic!r}, which no declared "
                "consumer subscribes to"
            )
        if not reason.strip():
            problems.append(f"UNREGISTERED_SUBSCRIBED_TOPICS[{topic!r}] has no reason")
    if problems:
        raise EventSubscriptionDeclarationError("; ".join(problems))


def validate_declared_subscriptions() -> None:
    """Validate this module's declarations against the live registries."""
    validate_declarations(
        EVENT_BUS_CONSUMER_DECLARATIONS,
        known_consumers=KNOWN_EVENT_BUS_CONSUMERS,
        registered_topics=ALL_EVENTS.keys(),
        unregistered_topics=UNREGISTERED_SUBSCRIBED_TOPICS,
        unproven_consumers=UNPROVEN_EVENT_BUS_CONSUMERS,
        service_repository_names={
            service.slug: service.name for service in ALL_SERVICES
        },
    )
