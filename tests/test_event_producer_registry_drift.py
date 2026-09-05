"""Producer/registry drift guards for cross-service Adaptix events.

Context
-------
``events/registry.ALL_EVENTS`` is an allow-list: ``is_registered`` gates it and
``events/operational_envelope.assert_event_type_registered`` raises on anything
absent. Until this module landed, 18 event types that Adaptix domain services
publish TODAY through the shared envelope
(``adaptix_contracts.event_contracts.EventSchema``) were not in that allow-list,
and 64 of the 67 registered entries stamped a ``source_service`` that resolved
to no ``ServiceDefinition`` without an undocumented ``adaptix-`` strip that only
a test knew about.

Both classes are locked down here:

* :data:`LIVE_ENVELOPE_PRODUCERS` is the inventory of every literally-typed
  production emission found in the polyrepo workspace, each with the exact
  producing file and line at origin/main (audited 2026-08-09 by
  ``scripts/audit_event_producer_drift.py``). Every entry must stay registered,
  with the ``source_service`` the producer actually stamps.
* Every registry entry's ``source_service`` must be a direct
  ``SERVICE_BY_SLUG`` key — no prefix-stripping heuristic.

What these tests do NOT prove: nothing here validates event PAYLOAD shape. Both
envelopes carry ``payload: dict[str, Any]``, so payload compatibility between a
producer and a consumer is still unguarded by contract.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from adaptix_contracts.events.operational_envelope import (
    OperationalEventEnvelope,
    assert_event_type_registered,
)
from adaptix_contracts.events.registry import (
    ALL_EVENTS,
    LEGACY_SOURCE_SERVICE_ALIASES,
    PRODUCER_SOURCE_SERVICE_ALIASES,
    is_registered,
    producer_of,
    resolve_source_service,
)
from adaptix_contracts.schemas.service_registry import (
    BILLING_SERVICE,
    EPCR_SERVICE,
    FIRE_SERVICE,
    SERVICE_BY_SLUG,
)

#: (event_type, producer service-registry slug, producing file:line at
#: origin/main on 2026-08-09). Every one of these is constructed with
#: ``EventSchema(event_type=<literal>, metadata=EventMetadata(source_service=...))``
#: in live service code, i.e. it can arrive at a consumer in production.
LIVE_ENVELOPE_PRODUCERS: tuple[tuple[str, str, str], ...] = (
    # Adaptix-Billing-Service
    (
        "billing.claim.created",
        "billing",
        "Adaptix-Billing-Service/backend/billing_app/services/event_publisher.py:34",
    ),
    (
        "billing.claim.updated",
        "billing",
        "Adaptix-Billing-Service/backend/billing_app/services/event_publisher.py:93",
    ),
    (
        "billing.claim.status_changed",
        "billing",
        "Adaptix-Billing-Service/backend/billing_app/services/event_publisher.py:130",
    ),
    (
        "billing.payment.received",
        "billing",
        "Adaptix-Billing-Service/backend/billing_app/services/event_publisher.py:166",
    ),
    (
        "billing.invoice.created",
        "billing",
        "Adaptix-Billing-Service/backend/billing_app/services/event_publisher.py:201",
    ),
    (
        "billing.invoice.paid",
        "billing",
        "Adaptix-Billing-Service/backend/billing_app/services/event_publisher.py:238",
    ),
    (
        "billing.call_context.assembled",
        "billing",
        "Adaptix-Billing-Service/backend/billing_app/event_consumers_calls.py:103",
    ),
    (
        "trustsign.document.signed",
        "billing",
        "Adaptix-Billing-Service/backend/billing_app/api/trustsign_routes.py:892",
    ),
    # Adaptix-EPCR-Service
    (
        "epcr.chart.created",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services/chart_publisher.py:62",
    ),
    (
        "epcr.chart.updated",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services/chart_publisher.py:97",
    ),
    (
        "epcr.chart.finalized",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services/chart_publisher.py:27",
    ),
    (
        "epcr.chart.signed",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services/chart_publisher.py:165",
    ),
    (
        "epcr.chart.locked",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services/chart_publisher.py:203",
    ),
    (
        "epcr.chart.unlocked",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services/chart_publisher.py:239",
    ),
    (
        "epcr.chart.nemsis_validation_completed",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services/chart_publisher.py:277",
    ),
    (
        "epcr.chart.nemsis_export_completed",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services/chart_publisher.py:318",
    ),
    # Adaptix-Fire-Service
    (
        "fire.incident.created",
        "fire",
        "Adaptix-Fire-Service/backend/fire_app/services/event_publisher.py:37",
    ),
    (
        "fire.incident.updated",
        "fire",
        "Adaptix-Fire-Service/backend/fire_app/services/event_publisher.py:73",
    ),
    (
        "fire.incident.completed",
        "fire",
        "Adaptix-Fire-Service/backend/fire_app/services/event_publisher.py:110",
    ),
    (
        "fire.incident.closed",
        "fire",
        "Adaptix-Fire-Service/backend/fire_app/services/event_publisher.py:148",
    ),
    (
        "fire.unit.dispatched",
        "fire",
        "Adaptix-Fire-Service/backend/fire_app/services/event_publisher.py:186",
    ),
    (
        "fire.incident.status_changed",
        "fire",
        "Adaptix-Fire-Service/backend/fire_app/models/incident.py:420",
    ),
)

#: (event_type, registry source_service slug, producing file:line at
#: origin/main on 2026-08-09) for producers that reach a shared envelope
#: INDIRECTLY, and are therefore invisible to a scanner that only reads a
#: literal ``event_type=`` on the envelope construction itself:
#:
#: * ``ChartEventOutbox`` rows are republished with the row's OWN event_type by
#:   ``Adaptix-EPCR-Service/backend/epcr_app/outbox_worker.py:99``
#:   (``source_service="epcr"``).
#: * ``epcr.vision.*`` / ``hospital.cath_lab.*`` go through the thin wrapper
#:   ``chart_vision_capture_service.py:728`` (``source_service="epcr"``).
#: * ``patient.identity.merged`` is an ``OutboxEvent`` row republished by
#:   ``Adaptix-Patient-Identity-Service/.../outbox_worker.py:88``.
#:
#: Every one of these was unregistered until this inventory landed, so
#: ``is_registered()`` returned False for real production traffic.
INDIRECT_ENVELOPE_PRODUCERS: tuple[tuple[str, str, str], ...] = (
    # --- Adaptix-CAD-Service, via CadOutboxEvent -> cad_app/outbox.py
    # (event_type is a caller-supplied parameter, so the literal never
    # appears at the publish_outbox() call site itself -- it appears one
    # hop up, either as a named module-level constant or a direct string
    # literal at the call). Audited 2026-09-05: adaptix_contracts.cad.events
    # claimed universal CAD coverage while ALL_EVENTS held zero cad.* keys;
    # these seven are the events a real producer emits today. ---
    (
        "cad.incident.created",
        "cad",
        "Adaptix-CAD-Service/backend/cad_app/cad_event_publisher.py:62",
    ),
    (
        "cad.unit.dispatched",
        "cad",
        "Adaptix-CAD-Service/backend/cad_app/cad_event_publisher.py:99",
    ),
    (
        "cad.incident.closed",
        "cad",
        "Adaptix-CAD-Service/backend/cad_app/cad_event_publisher.py:134",
    ),
    (
        "cad.unit.status_changed",
        "cad",
        "Adaptix-CAD-Service/backend/cad_app/cad_event_publisher.py:169",
    ),
    (
        "cad.intake.created",
        "cad",
        "Adaptix-CAD-Service/backend/cad_app/services/intake_repository.py:307",
    ),
    (
        "cad.intake.updated",
        "cad",
        "Adaptix-CAD-Service/backend/cad_app/services/intake_repository.py:463",
    ),
    (
        "cad.intake.cancelled",
        "cad",
        "Adaptix-CAD-Service/backend/cad_app/services/intake_repository.py:539",
    ),
    # --- Adaptix-Audit-Service Evidence Graph, via the publication models in
    # audit_app/schemas/evidence.py (event_type is a field default, so the
    # string never appears at the AdaptixEventEnvelope construction site in
    # audit_app/events/publisher.py) ---
    (
        "evidence.node.created",
        "audit",
        "Adaptix-Audit-Service/backend/audit_app/services/evidence_service.py:180",
    ),
    (
        "evidence.edge.created",
        "audit",
        "Adaptix-Audit-Service/backend/audit_app/services/evidence_service.py:309",
    ),
    (
        "evidence.decision_receipt.created",
        "audit",
        "Adaptix-Audit-Service/backend/audit_app/services/evidence_service.py:411",
    ),
    # --- Adaptix-EPCR-Service, via ChartEventOutbox -> outbox_worker.py:99 ---
    (
        "epcr.chart.amended",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/chart_amendment_service.py:92",
    ),
    (
        "epcr.chart.billing_handoff",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/api_chart_cortex_lifecycle.py:102",
    ),
    (
        "epcr.nemsis_submit.failed",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/chart_finalization_service.py:57",
    ),
    (
        "epcr.nemsis_submit.succeeded",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/chart_finalization_service.py:58",
    ),
    (
        "caregraph.node.created",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services_caregraph.py:57",
    ),
    (
        "caregraph.node.amended",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services_caregraph.py:58",
    ),
    (
        "caregraph.node.reviewed",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services_caregraph.py:59",
    ),
    (
        "caregraph.node.ruled_out",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services_caregraph.py:60",
    ),
    (
        "caregraph.edge.created",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services_caregraph.py:61",
    ),
    (
        "caregraph.edge.removed",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services_caregraph.py:62",
    ),
    (
        "cpae.finding.created",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services_cpae.py:55",
    ),
    (
        "cpae.finding.proposed",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services_cpae.py:56",
    ),
    (
        "cpae.finding.accepted",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services_cpae.py:57",
    ),
    (
        "cpae.finding.amended",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services_cpae.py:58",
    ),
    (
        "cpae.finding.rejected",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services_cpae.py:59",
    ),
    (
        "cpae.finding.contradiction_detected",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services_cpae.py:60",
    ),
    (
        "vas.overlay.created",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services_vas.py:47",
    ),
    (
        "vas.overlay.accepted",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services_vas.py:49",
    ),
    (
        "vas.overlay.rejected",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services_vas.py:50",
    ),
    (
        "vas.overlay.amended",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services_vas.py:51",
    ),
    (
        "vas.overlay.removed",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services_vas.py:52",
    ),
    (
        "vas.projection.proposed",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services_vas.py:53",
    ),
    (
        "vas.projection.reviewed",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services_vas.py:54",
    ),
    # --- Adaptix-EPCR-Service, via the chart_vision_capture publish wrapper ---
    (
        "epcr.vision.capture_created",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services/"
        "chart_vision_capture_service.py:905",
    ),
    (
        "epcr.vision.capture_accepted",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services/"
        "chart_vision_capture_service.py:1119",
    ),
    (
        "epcr.vision.vital_signs_accepted",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services/"
        "chart_vision_capture_service.py:1132",
    ),
    (
        "epcr.vision.twelve_lead_accepted",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services/"
        "chart_vision_capture_service.py:1147",
    ),
    (
        "epcr.vision.capture_rejected",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services/"
        "chart_vision_capture_service.py:1201",
    ),
    (
        "hospital.cath_lab.activate_recommended",
        "epcr",
        "Adaptix-EPCR-Service/backend/epcr_app/services/"
        "chart_vision_capture_service.py:1155",
    ),
    # --- Adaptix-Patient-Identity-Service, via OutboxEvent -> worker:88 ---
    (
        "patient.identity.merged",
        "patient-identity",
        "Adaptix-Patient-Identity-Service/backend/patient_identity_app/outbox.py:173",
    ),
)

_EXPECTED_PRODUCER_SERVICE = {
    "billing": BILLING_SERVICE,
    "epcr": EPCR_SERVICE,
    "fire": FIRE_SERVICE,
}


# ---------------------------------------------------------------------------
# Every live producer is registered, with the producer's own source_service
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("event_type", "slug", "site"),
    LIVE_ENVELOPE_PRODUCERS,
    ids=[entry[0] for entry in LIVE_ENVELOPE_PRODUCERS],
)
def test_live_producer_event_is_registered(
    event_type: str, slug: str, site: str
) -> None:
    assert is_registered(event_type), (
        f"{event_type!r} is published in production at {site} but is absent from "
        "ALL_EVENTS. is_registered() returns False for it, and "
        "assert_event_type_registered() would reject it on the operational "
        "backbone. Register it — do not delete this row."
    )
    declared = ALL_EVENTS[event_type]["source_service"]
    assert declared == slug, (
        f"{event_type!r} is stamped source_service={slug!r} by its producer at "
        f"{site}, but the registry declares {declared!r}."
    )
    assert producer_of(event_type) is _EXPECTED_PRODUCER_SERVICE[slug]


def test_live_producer_inventory_has_no_duplicate_rows() -> None:
    event_types = [entry[0] for entry in LIVE_ENVELOPE_PRODUCERS]
    assert len(set(event_types)) == len(event_types)


# ---------------------------------------------------------------------------
# Indirect producers: outbox relays and thin publish wrappers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("event_type", "slug", "site"),
    INDIRECT_ENVELOPE_PRODUCERS,
    ids=[entry[0] for entry in INDIRECT_ENVELOPE_PRODUCERS],
)
def test_indirect_producer_event_is_registered(
    event_type: str, slug: str, site: str
) -> None:
    assert is_registered(event_type), (
        f"{event_type!r} reaches the shared contract envelope from {site} but is "
        "absent from ALL_EVENTS. It never appears as a literal at the envelope "
        "construction site, so only the relay/wrapper-aware audit sees it. "
        "Register it — do not delete this row."
    )
    declared = ALL_EVENTS[event_type]["source_service"]
    assert declared == slug, (
        f"{event_type!r} is produced by {site} and must declare "
        f"source_service={slug!r}, but the registry declares {declared!r}."
    )
    assert producer_of(event_type) is SERVICE_BY_SLUG[slug]


def test_indirect_producer_inventory_has_no_duplicate_rows() -> None:
    event_types = [entry[0] for entry in INDIRECT_ENVELOPE_PRODUCERS]
    assert len(set(event_types)) == len(event_types)


def test_indirect_and_direct_inventories_do_not_overlap() -> None:
    direct = {entry[0] for entry in LIVE_ENVELOPE_PRODUCERS}
    indirect = {entry[0] for entry in INDIRECT_ENVELOPE_PRODUCERS}
    assert direct & indirect == set()


@pytest.mark.parametrize(
    ("event_type", "slug", "site"),
    INDIRECT_ENVELOPE_PRODUCERS,
    ids=[entry[0] for entry in INDIRECT_ENVELOPE_PRODUCERS],
)
def test_indirect_producer_event_passes_operational_backbone_gate(
    event_type: str, slug: str, site: str
) -> None:
    """Proves the allow-list gate now ACCEPTS each indirectly-produced event.

    Does NOT prove the event is actually delivered on EventBridge, nor that any
    consumer subscribes to it, nor anything about its payload shape.
    """
    envelope = _operational_envelope(event_type, slug)
    assert_event_type_registered(envelope)


def test_registry_cites_a_producer_file_for_each_indirect_event() -> None:
    """No indirect event may be registered without in-source producer evidence."""
    registry_source = (
        Path(__file__).resolve().parents[1]
        / "adaptix_contracts"
        / "events"
        / "registry.py"
    ).read_text(encoding="utf-8")
    for event_type, _slug, site in INDIRECT_ENVELOPE_PRODUCERS:
        producer_file = site.rsplit("/", 1)[-1].split(":")[0]
        assert event_type in registry_source, (
            f"registry.py does not contain the event type {event_type!r}"
        )
        assert producer_file in registry_source, (
            f"registry.py has no citation for the producer of {event_type!r} ({site})"
        )


# ---------------------------------------------------------------------------
# Live-producer source_service aliases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("stamped", "slug"), sorted(PRODUCER_SOURCE_SERVICE_ALIASES.items())
)
def test_live_producer_source_service_alias_resolves(stamped: str, slug: str) -> None:
    """The string a RUNNING producer stamps must identify its service."""
    assert stamped not in SERVICE_BY_SLUG, (
        f"{stamped!r} is a real registry slug; it does not need an alias"
    )
    service = resolve_source_service(stamped)
    assert service is not None
    assert service is SERVICE_BY_SLUG[slug]


def test_producer_and_legacy_alias_maps_are_disjoint() -> None:
    """A string is either historical drift or a live spelling, never both."""
    overlap = set(PRODUCER_SOURCE_SERVICE_ALIASES) & set(LEGACY_SOURCE_SERVICE_ALIASES)
    assert overlap == set()


def test_patient_identity_producer_alias_matches_the_registered_declaration() -> None:
    """The underscore form the worker stamps resolves to the declared slug."""
    declared = str(ALL_EVENTS["patient.identity.merged"]["source_service"])
    assert declared == "patient-identity"
    assert resolve_source_service("patient_identity") is SERVICE_BY_SLUG[declared]


# ---------------------------------------------------------------------------
# source_service is one vocabulary: the service-registry slug
# ---------------------------------------------------------------------------


def test_every_registered_source_service_is_a_direct_registry_slug() -> None:
    """No prefix-stripping heuristic. A raw dict lookup must succeed."""
    offenders = {
        event_type: meta["source_service"]
        for event_type, meta in ALL_EVENTS.items()
        if meta["source_service"] not in SERVICE_BY_SLUG
    }
    assert not offenders, (
        "these events stamp a source_service that is not a SERVICE_BY_SLUG key: "
        f"{offenders}. source_service is the service-registry slug — not the JWT "
        "audience (service_audiences) and not the ECS service_name "
        "(platform/ownership_manifest.json)."
    )


def test_every_registered_event_has_a_resolvable_producer() -> None:
    for event_type in ALL_EVENTS:
        assert producer_of(event_type) is not None


def test_every_registered_event_declares_a_version() -> None:
    missing = [
        event_type
        for event_type, meta in ALL_EVENTS.items()
        if not str(meta.get("version", "")).strip()
    ]
    assert not missing, f"events registered without a version: {missing}"


# ---------------------------------------------------------------------------
# Backward compatibility for the previously-published source_service strings
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("legacy", "slug"), sorted(LEGACY_SOURCE_SERVICE_ALIASES.items())
)
def test_legacy_source_service_string_still_resolves(legacy: str, slug: str) -> None:
    """A persisted event row or replayed archive may carry the old string."""
    service = resolve_source_service(legacy)
    assert service is not None
    assert service is SERVICE_BY_SLUG[slug]


def test_legacy_alias_targets_all_exist() -> None:
    for slug in LEGACY_SOURCE_SERVICE_ALIASES.values():
        assert slug in SERVICE_BY_SLUG


def test_unknown_source_service_resolves_to_none_not_a_guess() -> None:
    assert resolve_source_service("adaptix-does-not-exist") is None
    assert resolve_source_service("") is None


def test_producer_of_rejects_an_unregistered_event_type() -> None:
    with pytest.raises(KeyError, match="not registered"):
        producer_of("totally.unregistered.event")


# ---------------------------------------------------------------------------
# The registration actually unblocks the operational backbone
# ---------------------------------------------------------------------------


def _operational_envelope(event_type: str, slug: str) -> OperationalEventEnvelope:
    return OperationalEventEnvelope(
        event_type=event_type,
        tenant_id="tenant-drift-guard",
        source_service=slug,
        source_record_id="record-1",
        source_version=1,
        observed_at="2026-08-09T00:00:00Z",
        effective_at="2026-08-09T00:00:00Z",
    )


@pytest.mark.parametrize(
    ("event_type", "slug"),
    [(entry[0], entry[1]) for entry in LIVE_ENVELOPE_PRODUCERS],
    ids=[entry[0] for entry in LIVE_ENVELOPE_PRODUCERS],
)
def test_live_producer_event_passes_operational_backbone_gate(
    event_type: str, slug: str
) -> None:
    """Proves the allow-list gate now ACCEPTS each real production event.

    Does NOT prove the event is actually published on EventBridge, nor that any
    consumer subscribes to it.
    """
    envelope = _operational_envelope(event_type, slug)
    assert_event_type_registered(envelope)
    assert envelope.source_service in SERVICE_BY_SLUG


def test_operational_backbone_gate_still_rejects_an_unregistered_type() -> None:
    """Control: the gate is not vacuously passing everything."""
    envelope = _operational_envelope("fire.incident.not_a_real_event", "fire")
    with pytest.raises(ValueError, match="not registered"):
        assert_event_type_registered(envelope)


# ---------------------------------------------------------------------------
# The inventory above is derived from source, not from memory
# ---------------------------------------------------------------------------


def test_registry_module_cites_a_producer_for_each_newly_registered_event() -> None:
    """Each newly registered event must carry a producer citation in-source.

    Guards against a future edit adding an event to ALL_EVENTS with no evidence
    of who publishes it — the exact failure mode that produced 64 entries whose
    source_service resolved to nothing.
    """
    registry_source = (
        Path(__file__).resolve().parents[1]
        / "adaptix_contracts"
        / "events"
        / "registry.py"
    ).read_text(encoding="utf-8")
    for event_type, _slug, site in LIVE_ENVELOPE_PRODUCERS:
        producer_file = site.rsplit("/", 1)[-1].split(":")[0]
        assert event_type in registry_source
        assert producer_file in registry_source, (
            f"registry.py has no citation for the producer of {event_type!r} ({site})"
        )


def test_registry_module_parses_and_exports_the_new_public_api() -> None:
    registry_path = (
        Path(__file__).resolve().parents[1]
        / "adaptix_contracts"
        / "events"
        / "registry.py"
    )
    tree = ast.parse(registry_path.read_text(encoding="utf-8"))
    exported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    exported = {
                        element.value
                        for element in node.value.elts  # type: ignore[attr-defined]
                        if isinstance(element, ast.Constant)
                    }
    for name in (
        "producer_of",
        "resolve_source_service",
        "LEGACY_SOURCE_SERVICE_ALIASES",
    ):
        assert name in exported, f"{name} is missing from registry.__all__"
