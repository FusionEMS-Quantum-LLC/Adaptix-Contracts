"""Tests for the canonical service-audience registry.

These pin the registry's shape and its contract with the two consumers
(``Adaptix-Gateway``'s ``KNOWN_AUDIENCES`` and ``Adaptix-Core-Service``'s
``_LIVE_SERVICE_AUDIENCES``). They deliberately do NOT reach for a sibling
checkout: needing one is exactly why the previous drift guard skipped in CI and
never gated anything.
"""

from __future__ import annotations

import re

import pytest

from adaptix_contracts.service_audiences import (
    KNOWN_SERVICE_AUDIENCES,
    is_known_service_audience,
)

_AUDIENCE_RE = re.compile(r"^adaptix-[a-z0-9]+(-[a-z0-9]+)*$")


def test_registry_is_an_immutable_frozenset() -> None:
    """A mutable registry could be edited at runtime by any importer."""
    assert isinstance(KNOWN_SERVICE_AUDIENCES, frozenset)


def test_every_audience_matches_the_platform_naming_pattern() -> None:
    """``adaptix-<lowercase-hyphenated>``. A stray capital or underscore is a
    silent 403: the gateway and the downstream verifier both compare literally,
    so a near-miss never matches and never warns."""
    bad = sorted(a for a in KNOWN_SERVICE_AUDIENCES if not _AUDIENCE_RE.match(a))
    assert not bad, f"audiences violating the naming pattern: {bad}"


def test_core_audience_is_present() -> None:
    """Core is the identity issuer; its own audience must be routable."""
    assert "adaptix-core" in KNOWN_SERVICE_AUDIENCES


def test_vision_audience_is_present() -> None:
    """Regression pin for the 2026-08-04 drift.

    ``adaptix-vision`` was routed by the gateway (``/api/v1/vision``) with the
    verifier live on ``adaptix-production-vision``
    (``ADAPTIX_GATEWAY_EXPECTED_AUDIENCE=adaptix-vision``) while Core's registry
    did not know it — so every Vision surface returned 403
    ``jwt_audience_mismatch`` for the founder.
    """
    assert "adaptix-vision" in KNOWN_SERVICE_AUDIENCES


def test_audit_audience_is_present() -> None:
    """Adaptix-Audit-Service is deployed and already expects this exact string.

    Verified 2026-08-19 against the live account (793439286972, us-east-1): ECS
    service ``adaptix-production-audit`` on cluster ``adaptix-production`` was
    ACTIVE at 1/1 running, task definition revision 11, rollout COMPLETED, and
    that task definition sets ``GATEWAY_AUDIENCE=adaptix-audit``.

    Step 3 of this module's own "Adding a new service" procedure (install the
    verifier downstream) was therefore already done in production while step 1
    was missing here. That is the inverse of the 2026-08-04 ``adaptix-vision``
    drift, with the same consequence: the gateway refuses to route any prefix
    whose audience is absent from this registry
    (``Adaptix-Gateway/backend/app/config/routes.py`` raises at
    ``entry.audience not in KNOWN_AUDIENCES``), so no ``RouteEntry`` could be
    written for the service at all, and its Evidence Graph surface
    (``/api/v1/audit/evidence/...``) was unreachable at the edge as a result.
    """
    assert "adaptix-audit" in KNOWN_SERVICE_AUDIENCES


def test_signal_bus_audience_is_present() -> None:
    """Adaptix-SignalCore-Service (the cross-service event bus) needs a DISTINCT
    audience (A012 SSRF/identity hardening).

    The service serves ``/api/v1/signal-bus`` — deliberately NOT ``/api/v1/signalcore``,
    which is Core's separate Founder investor-signal (Wefunder) stream routed to Core
    with ``audience="adaptix-core"`` (see ``Adaptix-Gateway`` routes.py). Its audience
    must therefore be distinct from ``adaptix-core`` so the gateway can route the
    event-bus prefix and stamp its own audience, and the downstream verifier
    (``ADAPTIX_GATEWAY_EXPECTED_AUDIENCE=adaptix-signal-bus``) can be installed without
    colliding with the fundraising stream. Registered here (step 1 of "Adding a new
    service") so the gateway route table can reference it without the "audience absent
    from the registry -> prefix unroutable" failure that hit ``adaptix-audit`` and
    ``adaptix-vision``.
    """
    assert "adaptix-signal-bus" in KNOWN_SERVICE_AUDIENCES


@pytest.mark.parametrize(
    "value",
    ["adaptix-core", "  adaptix-core  ", "ADAPTIX-CORE"],
    ids=["exact", "surrounding-whitespace", "uppercase"],
)
def test_is_known_service_audience_accepts_normalizable_forms(value: str) -> None:
    assert is_known_service_audience(value) is True


@pytest.mark.parametrize(
    "value",
    [None, "", "   ", "adaptix-does-not-exist", "core", "adaptix_core"],
    ids=["none", "empty", "blank", "unknown", "missing-prefix", "underscore"],
)
def test_is_known_service_audience_rejects_everything_else(value) -> None:
    """Notably ``adaptix_core``: underscore is NOT normalized to a hyphen. A
    helper that guessed at near-misses would let a typo'd audience pass here and
    then fail at the real comparison downstream, which is worse than failing
    here."""
    assert is_known_service_audience(value) is False


def test_registry_has_no_duplicate_after_normalization() -> None:
    """Two entries differing only by case or whitespace would both live in the
    frozenset while being the same audience to every consumer."""
    normalized = [a.strip().lower() for a in KNOWN_SERVICE_AUDIENCES]
    assert len(normalized) == len(set(normalized))


@pytest.mark.parametrize(
    "audience",
    [
        "adaptix-cct",
        "adaptix-edge",
        "adaptix-preplan",
        "adaptix-wildland",
        "adaptix-xr",
    ],
)
def test_undeployed_domain_service_audiences_are_registered(audience: str) -> None:
    """Step 1 of "Adding a new service" for the five domain services whose
    backends exist on ``main`` but which had no AWS footprint.

    Each of ``Adaptix-CCT-Service``, ``Adaptix-Edge-Service``,
    ``Adaptix-Preplan-Service``, ``Adaptix-Wildland-Service`` and
    ``Adaptix-XR-Service`` carries a real FastAPI application, Alembic
    migrations, and a ``backend/Dockerfile`` (Preplan: a root ``Dockerfile``
    over ``src/``), and each verifies a gateway-signed context through
    ``adaptix_contracts.auth_contracts``. Verified 2026-09-05 against the live
    account (793439286972, us-east-1): none of the five had an ECS service, a
    target group, an RDS instance, or a CodeBuild project, so none could be
    routed.

    Registering the audience here is deliberately the FIRST step and is inert on
    its own: the gateway refuses to start with a route whose audience is absent
    from this registry, and Core issues the founder every audience in this set,
    so both consumers must learn the string before either a ``RouteEntry`` or an
    ``ADAPTIX_GATEWAY_EXPECTED_AUDIENCE`` task-definition value can exist. An
    audience with no route resolves to a structured gateway 404, never a 403 --
    the reverse order is what produced the ``adaptix-audit`` and
    ``adaptix-vision`` outages this module was created to prevent.
    """
    assert audience in KNOWN_SERVICE_AUDIENCES
