"""Drift guards for service registration and platform ownership.

Phase 1 of the Workforce Scheduling directive (SCHEDULING_ARCHITECTURE_LOCK.md
section 3.3). Covers:

* every ``source_service`` stamped on a registered event resolves to a real
  ``ServiceDefinition``;
* ``service_registry`` route prefixes agree with ``ownership_manifest.json``;
* the deprecated scheduling-domain names in the duplicate contract modules point
  at canonical replacements that actually exist;
* the legacy enum value sets that block the full consolidation stay frozen, so a
  destructive collapse cannot land silently.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

import adaptix_contracts
from adaptix_contracts.events.registry import ALL_EVENTS
from adaptix_contracts.scheduling.events import ALL_SCHEDULING_EVENTS
from adaptix_contracts.schemas.service_registry import (
    ALL_SERVICES,
    SCHEDULING_SERVICE,
    SERVICE_BY_SLUG,
    ServiceDefinition,
)

_MANIFEST_PATH = (
    Path(adaptix_contracts.__file__).resolve().parent
    / "platform"
    / "ownership_manifest.json"
)

#: Top-level keys in ownership_manifest.json that are metadata, not service entries.
_MANIFEST_METADATA_KEYS = frozenset({"manifest_version", "generated"})


def _load_manifest() -> dict[str, dict]:
    with _MANIFEST_PATH.open(encoding="utf-8") as handle:
        raw = json.load(handle)
    return {k: v for k, v in raw.items() if k not in _MANIFEST_METADATA_KEYS}


def _resolve_source_service(source_service: str) -> ServiceDefinition | None:
    """Resolve an event ``source_service`` string to a registered service.

    ``events/registry.py`` stamps two conventions today: the bare slug
    (``"billing"``, ``"epcr"``) and the ``adaptix-``-prefixed service name
    (``"adaptix-fire"``, ``"adaptix-neris"``, ``"adaptix-scheduling"``). Both
    forms must land on the same registry.
    """
    if source_service in SERVICE_BY_SLUG:
        return SERVICE_BY_SLUG[source_service]
    if source_service.startswith("adaptix-"):
        return SERVICE_BY_SLUG.get(source_service.removeprefix("adaptix-"))
    return None


# ---------------------------------------------------------------------------
# SCHEDULING_SERVICE registration
# ---------------------------------------------------------------------------


def test_scheduling_service_is_registered() -> None:
    assert SCHEDULING_SERVICE in ALL_SERVICES
    assert SERVICE_BY_SLUG["scheduling"] is SCHEDULING_SERVICE
    assert SCHEDULING_SERVICE.slug == "scheduling"
    assert SCHEDULING_SERVICE.route_prefix == "/api/v1/scheduling"
    assert SCHEDULING_SERVICE.domain_owner is True


def test_service_registry_slugs_and_ports_are_unique() -> None:
    slugs = [service.slug for service in ALL_SERVICES]
    ports = [service.port for service in ALL_SERVICES]
    assert len(set(slugs)) == len(slugs), "duplicate slug in ALL_SERVICES"
    assert len(set(ports)) == len(ports), "duplicate port in ALL_SERVICES"


# ---------------------------------------------------------------------------
# Event source_service resolution
# ---------------------------------------------------------------------------


def test_every_event_source_service_resolves_to_registered_service() -> None:
    """Every source_service in ALL_EVENTS must name a registered service."""
    unresolved: dict[str, str] = {}
    for event_type, meta in ALL_EVENTS.items():
        source_service = meta["source_service"]
        assert isinstance(source_service, str) and source_service, (
            f"{event_type} has an empty source_service"
        )
        if _resolve_source_service(source_service) is None:
            unresolved[event_type] = source_service

    assert not unresolved, (
        "events name a source_service with no ServiceDefinition in "
        f"adaptix_contracts.schemas.service_registry: {unresolved}"
    )


def test_scheduling_events_resolve_to_scheduling_service() -> None:
    assert ALL_SCHEDULING_EVENTS, "ALL_SCHEDULING_EVENTS is empty"
    for event_type in ALL_SCHEDULING_EVENTS:
        meta = ALL_EVENTS[event_type]
        assert meta["source_service"] == "adaptix-scheduling"
        assert _resolve_source_service(meta["source_service"]) is SCHEDULING_SERVICE


# ---------------------------------------------------------------------------
# service_registry <-> ownership_manifest agreement
# ---------------------------------------------------------------------------


def test_ownership_manifest_is_valid_json_with_service_entries() -> None:
    manifest = _load_manifest()
    assert manifest, "ownership_manifest.json contains no service entries"
    for slug, entry in manifest.items():
        assert isinstance(entry, dict), f"manifest entry {slug!r} is not an object"
        assert "api_prefixes" in entry, f"manifest entry {slug!r} has no api_prefixes"
        assert isinstance(entry["api_prefixes"], list)


def test_service_registry_route_prefix_matches_ownership_manifest() -> None:
    """For every slug present in both sources, the route prefix must agree.

    Checked by exact slug/key match. Slugs with no manifest key are covered by
    ``test_registry_slugs_absent_from_ownership_manifest_is_frozen`` below.
    """
    manifest = _load_manifest()
    mismatches: dict[str, tuple[str, list[str]]] = {}
    checked = 0
    for service in ALL_SERVICES:
        entry = manifest.get(service.slug)
        if entry is None:
            continue
        checked += 1
        prefixes = entry["api_prefixes"]
        if service.route_prefix not in prefixes:
            mismatches[service.slug] = (service.route_prefix, prefixes)

    assert checked >= 14, f"expected at least 14 overlapping slugs, checked {checked}"
    assert not mismatches, (
        "service_registry route_prefix disagrees with ownership_manifest "
        f"api_prefixes: {mismatches}"
    )


def test_ownership_manifest_scheduling_entry_owns_all_scheduling_events() -> None:
    manifest = _load_manifest()
    entry = manifest["scheduling"]
    assert entry["api_prefixes"] == [SCHEDULING_SERVICE.route_prefix]
    assert entry["service_name"] == "adaptix-scheduling"
    assert sorted(entry["owned_events"]) == sorted(ALL_SCHEDULING_EVENTS)


# ---------------------------------------------------------------------------
# Known drift: registry slugs with no ownership_manifest entry
# ---------------------------------------------------------------------------

#: Registry slugs that have NO ownership_manifest.json entry as of 2026-07-23.
#: Frozen deliberately: this test passes today and starts failing the moment a
#: new unmapped service is registered, so the gap cannot grow silently. Shrink
#: this set as manifest entries are added; do not extend it without a reason.
_SLUGS_WITHOUT_MANIFEST_ENTRY = frozenset(
    {
        # Registered service whose manifest entry exists under a DIFFERENT key
        # with a DIFFERENT prefix — see test_crew_service_has_ownership_manifest_entry.
        "crew",
        # Registered services whose manifest entry exists under a different key
        # but whose prefix agrees, so nothing is silently wrong:
        #   transport  -> manifest key "transportlink" (api_prefixes /api/v1/transport)
        #   telephony  -> manifest key "voice"         (api_prefixes /api/v1/voice)
        "transport",
        "telephony",
        # Registered services with no manifest entry under any key.
        "labor",
        "crm",
        "investor",
        "partner",
        "finance",
        "calendar",
        "search",
        "founder",
        "documents",
        "office",
        "training",
        "fleet",
        "hr",
        "analytics",
        "compliance",
        "imports",
        "exports",
        "policy",
        "device",
        "app-management",
        "patient-identity",
        "legal",
        "integrations",
        "terminology",
        "marketing",
        "customer-success",
        "pricing",
        "operations",
        "nemsis",
        "neris",
    }
)


def test_registry_slugs_absent_from_ownership_manifest_is_frozen() -> None:
    manifest = _load_manifest()
    absent = {s.slug for s in ALL_SERVICES if s.slug not in manifest}

    new_drift = absent - _SLUGS_WITHOUT_MANIFEST_ENTRY
    assert not new_drift, (
        "new service slugs registered without an ownership_manifest.json entry: "
        f"{sorted(new_drift)}. Add the manifest entry, or add the slug to "
        "_SLUGS_WITHOUT_MANIFEST_ENTRY with a reason."
    )

    resolved = _SLUGS_WITHOUT_MANIFEST_ENTRY - absent
    assert not resolved, (
        "these slugs now HAVE an ownership_manifest.json entry and must be "
        f"removed from _SLUGS_WITHOUT_MANIFEST_ENTRY: {sorted(resolved)}"
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "KNOWN PLATFORM DRIFT — not papered over. service_registry.CREW_SERVICE "
        "declares slug 'crew' with route_prefix '/api/v1/crew', but "
        "ownership_manifest.json has NO 'crew' key. Its nearest entry, 'crewlink', "
        "declares api_prefixes ['/api/v1/crewlink'] and canonical_repo "
        "Adaptix-Crew-Service. Both prefixes are live and DISTINCT in the gateway "
        "(Adaptix-Gateway/backend/app/config/routes.py:1788-1793 routes /api/v1/crew "
        "to crew_service_url; :1438-1460 routes /api/v1/crewlink to cad_service_url "
        "and comments that the adaptix-crewlink upstream 'has no ECS service backing "
        "it'). So the manifest attributes crewlink to the wrong repo AND omits crew "
        "entirely. The correct canonical_repo / ecs_service / database_schema for a "
        "'crew' entry, and the resolution of the crewlink ownership contradiction, "
        "are not derivable from Adaptix-Contracts and require a governance decision. "
        "Fix the manifest, then delete this marker."
    ),
)
def test_crew_service_has_ownership_manifest_entry() -> None:
    manifest = _load_manifest()
    entry = manifest.get("crew")
    assert entry is not None, "ownership_manifest.json has no 'crew' entry"
    assert SERVICE_BY_SLUG["crew"].route_prefix in entry["api_prefixes"]


def test_narcotics_manifest_prefix_matches_gateway_routable_plural() -> None:
    """Regression guard for the fixed narcotics prefix.

    ownership_manifest.json previously listed only the singular
    '/api/v1/narcotic'. The gateway boundary-matches the PLURAL prefix
    (Adaptix-Gateway/backend/app/config/routes.py:1849), which is why
    Adaptix-Narcotics-Service/backend/core_app/main.py:40-62 aliases every
    singular router onto the plural namespace. The plural must stay listed and
    must stay first.
    """
    manifest = _load_manifest()
    prefixes = manifest["narcotics"]["api_prefixes"]
    assert prefixes[0] == "/api/v1/narcotics"
    assert prefixes[0] == SERVICE_BY_SLUG["narcotics"].route_prefix
    assert "/api/v1/narcotic" in prefixes, (
        "the singular native prefix is still served in-service and must remain "
        "documented"
    )


# ---------------------------------------------------------------------------
# Deprecated-name pointers resolve to real canonical symbols
# ---------------------------------------------------------------------------

_DEPRECATION_MAPS = [
    ("adaptix_contracts.schemas.workforce_contracts", "DEPRECATED_MODEL_REPLACEMENTS"),
    ("adaptix_contracts.schemas.workforce_contracts", "DEPRECATED_ENUM_REPLACEMENTS"),
    ("adaptix_contracts.schemas.labor_contracts", "DEPRECATED_MODEL_REPLACEMENTS"),
    ("adaptix_contracts.schemas.labor_contracts", "DEPRECATED_ENUM_REPLACEMENTS"),
    ("adaptix_contracts.workforce.models", "DEPRECATED_REPLACEMENTS"),
]


@pytest.mark.parametrize(("module_path", "map_name"), _DEPRECATION_MAPS)
def test_deprecated_names_and_replacements_both_resolve(
    module_path: str, map_name: str
) -> None:
    module = importlib.import_module(module_path)
    replacements: dict[str, str] = getattr(module, map_name)
    assert replacements, f"{module_path}.{map_name} is empty"

    for legacy_name, canonical_path in replacements.items():
        # The legacy name must still exist — backward compatibility is mandatory.
        assert hasattr(module, legacy_name), (
            f"{module_path}.{legacy_name} was removed; downstream imports break"
        )
        # The canonical replacement must be importable.
        canonical_module_path, _, symbol = canonical_path.rpartition(".")
        canonical_module = importlib.import_module(canonical_module_path)
        assert hasattr(canonical_module, symbol), (
            f"{canonical_path} does not exist (referenced by "
            f"{module_path}.{map_name}[{legacy_name!r}])"
        )


def test_canonical_scheduling_models_are_reexported_from_legacy_modules() -> None:
    """Callers may adopt the canonical names from the legacy module paths."""
    from adaptix_contracts.scheduling import models as canonical
    from adaptix_contracts.schemas import labor_contracts, workforce_contracts
    from adaptix_contracts.workforce import models as workforce_models

    assert workforce_contracts.ShiftInstance is canonical.ShiftInstance
    assert workforce_contracts.ShiftAssignment is canonical.ShiftAssignment
    assert workforce_contracts.AvailabilityWindow is canonical.AvailabilityWindow
    assert workforce_contracts.TimeOffRequest is canonical.TimeOffRequest
    assert workforce_contracts.RiskLevel is canonical.RiskLevel

    assert labor_contracts.ShiftInstance is canonical.ShiftInstance
    assert labor_contracts.ShiftAssignment is canonical.ShiftAssignment
    assert labor_contracts.ShiftSwapRequest is canonical.ShiftSwapRequest
    assert labor_contracts.TimeOffRequest is canonical.TimeOffRequest

    assert workforce_models.RiskLevel is canonical.RiskLevel


# ---------------------------------------------------------------------------
# Frozen legacy enum value sets — the blocker on the full consolidation
# ---------------------------------------------------------------------------


def test_legacy_enum_value_sets_are_unchanged() -> None:
    """The three fatigue enums and the duplicate status enums stay as-is.

    Collapsing any of these onto the canonical enum deletes members and narrows
    accepted values, which DEPRECATION_POLICY.md classifies as a major-version
    change. This test fails loudly if that collapse is attempted in a minor
    release.
    """
    from adaptix_contracts.scheduling.models import (
        AssignmentStatus as CanonicalAssignmentStatus,
        RiskLevel,
        ShiftStatus as CanonicalShiftStatus,
        SwapStatus as CanonicalSwapStatus,
        TimeOffStatus as CanonicalTimeOffStatus,
    )
    from adaptix_contracts.schemas import labor_contracts, workforce_contracts
    from adaptix_contracts.workforce import models as workforce_models

    def values(enum_cls) -> set[str]:
        return {member.value for member in enum_cls}

    # Canonical.
    assert values(RiskLevel) == {"low", "medium", "high", "critical"}
    assert values(CanonicalShiftStatus) == {
        "open",
        "assigned",
        "cancelled",
        "completed",
    }
    assert values(CanonicalAssignmentStatus) == {"pending", "confirmed", "cancelled"}
    assert values(CanonicalSwapStatus) == {
        "requested",
        "approved",
        "denied",
        "cancelled",
    }
    assert values(CanonicalTimeOffStatus) == {
        "pending",
        "approved",
        "denied",
        "cancelled",
    }

    # Three fatigue severity enums — NOT interchangeable.
    assert values(workforce_contracts.FatigueLevel) == {
        "none",
        "low",
        "moderate",
        "high",
        "critical",
    }
    assert values(workforce_models.FatigueRiskLevel) == {
        "low",
        "moderate",
        "high",
        "critical",
    }
    assert values(workforce_contracts.FatigueLevel) != values(RiskLevel)
    assert values(workforce_models.FatigueRiskLevel) != values(RiskLevel)

    # Duplicate status enums — NOT interchangeable.
    assert values(workforce_contracts.ShiftStatus) == {
        "draft",
        "published",
        "in_progress",
        "completed",
        "cancelled",
    }
    assert values(labor_contracts.ShiftStatus) == {
        "draft",
        "published",
        "locked",
        "open",
        "in_progress",
        "completed",
        "cancelled",
    }
    assert values(labor_contracts.AssignmentStatus) == {
        "pending",
        "confirmed",
        "overridden",
        "cancelled",
    }
    assert values(labor_contracts.TradeStatus) == {
        "proposed",
        "accepted",
        "denied",
        "cancelled",
        "completed",
    }

    # The two that ARE value-compatible with the canonical enum.
    assert values(workforce_contracts.TimeOffStatus) == values(CanonicalTimeOffStatus)
    assert values(labor_contracts.LeaveStatus) == values(CanonicalTimeOffStatus)


def test_payroll_only_surface_stays_in_labor_contracts() -> None:
    from adaptix_contracts.schemas import labor_contracts

    for name in labor_contracts.PAYROLL_ONLY_SURFACE:
        assert hasattr(labor_contracts, name), (
            f"payroll-only symbol {name} was removed from labor_contracts"
        )


def test_fatigue_risk_score_carries_folded_assessment_fields() -> None:
    """FatigueRiskScore is the canonical fatigue model and must be a superset."""
    from adaptix_contracts.scheduling.ai import FatigueRiskScore
    from adaptix_contracts.workforce.models import FatigueAssessment

    for field in ("risk_factors", "ai_generated", "supervisor_review_flag"):
        assert field in FatigueRiskScore.model_fields, (
            f"{field} was not carried over from FatigueAssessment"
        )
        assert field in FatigueAssessment.model_fields

    # Carried-over fields are optional, so existing producers are unaffected.
    score = FatigueRiskScore(
        person_id="00000000-0000-0000-0000-000000000001",
        shift_id="00000000-0000-0000-0000-000000000002",
        hours_worked_last_24h=12.0,
        hours_worked_last_48h=20.0,
        hours_worked_last_7d=48.0,
        consecutive_shifts=3,
        fatigue_score=0.75,
        risk_level="high",
        explanation="48h worked in the last 7 days.",
    )
    assert score.risk_factors == []
    assert score.ai_generated is False
    assert score.supervisor_review_flag is False
