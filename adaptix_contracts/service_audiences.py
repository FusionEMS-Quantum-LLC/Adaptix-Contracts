"""Canonical Adaptix service-audience registry.

SINGLE SOURCE OF TRUTH for "which JWT ``aud`` values name a live Adaptix
service" across the polyrepo.

Why this exists
---------------
Two repos independently maintained the same list and drifted:

* ``Adaptix-Gateway/backend/app/config/routes.py`` — ``KNOWN_AUDIENCES``.
  The gateway stamps this audience onto the signed context it forwards to each
  upstream, and refuses to route a prefix whose audience is not in the set.
* ``Adaptix-Core-Service/core/backend/core_app/auth.py`` —
  ``_LIVE_SERVICE_AUDIENCES``. Core issues the founder EVERY audience in its
  set, so an audience the gateway routes but Core does not know means the
  founder's session carries no such audience and every request to that surface
  returns **403 jwt_audience_mismatch**.

That failure has happened at least twice. The 2026-07-17 AI/Cortex panel
outage is recorded in ``auth.py``'s own comment, and on 2026-08-04
``adaptix-vision`` was found routed by the gateway (``/api/v1/vision``, with
``ADAPTIX_GATEWAY_EXPECTED_AUDIENCE=adaptix-vision`` live on
``adaptix-production-vision``) but absent from Core — so Vision 403'd for the
founder.

Why the previous guard did not catch it
---------------------------------------
Core carried a drift test, but it located the gateway's list by walking parent
directories for a sibling ``Adaptix-Gateway`` checkout and calling
``pytest.skip`` when it was not found. CodeBuild clones only the one repo, so
the test **skipped in CI on every run** and could only ever fail on a developer
machine that happened to have both repos. A guard that silently skips in the
only place it is meant to gate reports green while measuring nothing.

Importing this module removes the sibling-checkout dependency: both repos can
assert against it with nothing but their own tree, so the check runs in each
repo's own CI.

Adding a new service
--------------------
1. Add the audience here.
2. Add the ``RouteEntry`` in the gateway's ``routes.py``.
3. Install the verifier downstream — set ``ADAPTIX_GATEWAY_EXPECTED_AUDIENCE``
   on the service's task definition to the same string. Without it the service
   accepts a context minted for any audience; with a *wrong* value it rejects
   every real request. Both are 401/403 storms in production.

Removing a service is the same list in reverse, and the audience must leave the
gateway's route table in the same change — an audience removed here while a
route still references it makes that route unroutable.
"""

from __future__ import annotations

__all__ = ["KNOWN_SERVICE_AUDIENCES", "is_known_service_audience"]


# Kept sorted so a diff adding one service is a single line, and so the two
# consuming repos cannot disagree on ordering while agreeing on content.
KNOWN_SERVICE_AUDIENCES: frozenset[str] = frozenset(
    {
        "adaptix-ai",
        "adaptix-air",
        "adaptix-audit",
        "adaptix-analytics",
        "adaptix-app-management",
        "adaptix-assetops",
        "adaptix-bedrock",
        "adaptix-billing",
        "adaptix-cad",
        "adaptix-calendar",
        "adaptix-communications",
        "adaptix-compliance",
        "adaptix-core",
        "adaptix-cortex",
        "adaptix-crew",
        "adaptix-crewlink",
        "adaptix-crm",
        "adaptix-customer-success",
        "adaptix-device",
        "adaptix-documents",
        "adaptix-epcr",
        "adaptix-exports",
        "adaptix-facilities",
        "adaptix-field",
        "adaptix-finance",
        "adaptix-fire",
        "adaptix-fleet",
        "adaptix-forms",
        "adaptix-founder",
        "adaptix-geo",
        "adaptix-governance",
        "adaptix-graph",
        "adaptix-hl7",
        "adaptix-hospital",
        "adaptix-hr",
        "adaptix-imports",
        "adaptix-integrations",
        "adaptix-inventory",
        "adaptix-investor",
        "adaptix-labor",
        "adaptix-legal",
        "adaptix-mailroom",
        "adaptix-marketing",
        "adaptix-media",
        "adaptix-medications",
        "adaptix-narcotics",
        "adaptix-nemsis",
        "adaptix-neris",
        "adaptix-office",
        "adaptix-officeally",
        "adaptix-operations",
        "adaptix-partner",
        "adaptix-patient-identity",
        "adaptix-payments",
        "adaptix-policy",
        "adaptix-pricing",
        "adaptix-reference-data",
        "adaptix-rtc",
        "adaptix-search",
        "adaptix-social",
        "adaptix-telephony",
        "adaptix-telnyx",
        "adaptix-terminology",
        "adaptix-training",
        "adaptix-transport",
        "adaptix-transportlink",
        "adaptix-trustsign",
        "adaptix-vision",
        "adaptix-voice",
        "adaptix-workforce",
    }
)


def is_known_service_audience(audience: str | None) -> bool:
    """Return whether ``audience`` names a live Adaptix service.

    Exact match on the normalized string. Audience comparison is exact
    everywhere it matters — the gateway's route validator and the downstream
    ``ADAPTIX_GATEWAY_EXPECTED_AUDIENCE`` check both compare literally — so this
    only strips surrounding whitespace and lowercases; it never guesses at a
    near-miss. A caller that wants to be forgiving about an unknown audience
    must decide that itself rather than have this helper decide for it.
    """
    if not audience:
        return False
    return audience.strip().lower() in KNOWN_SERVICE_AUDIENCES
