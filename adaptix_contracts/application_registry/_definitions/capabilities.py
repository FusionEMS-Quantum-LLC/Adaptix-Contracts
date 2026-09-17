"""Shared capabilities — reusable platform functions that are NOT applications."""

from __future__ import annotations

from adaptix_contracts.application_registry._definitions.shorthand import _GW, _WEB
from adaptix_contracts.application_registry._model import (
    SharedCapabilityDefinition,
    _cap,
)

SHARED_CAPABILITIES: tuple[SharedCapabilityDefinition, ...] = (
    _cap(
        "search",
        "Search",
        "Tenant-scoped search across indexed records.",
        route="/workspace/search",
        services=("adaptix-search",),
        source=f"{_WEB}; {_GW} /api/v1/search -> adaptix-search",
    ),
    _cap(
        "notifications",
        "Notifications",
        "A person's own notifications and alerts.",
        route="/workspace/notifications",
        services=("adaptix-core",),
        source=f"{_WEB}; {_GW} /api/v1/notifications -> adaptix-core",
    ),
    _cap(
        "calendar",
        "Calendar",
        "Platform calendar events, reminders and booking.",
        route="/workspace/calendar",
        services=("adaptix-calendar",),
        source=f"{_WEB}; {_GW} /api/v1/calendar -> adaptix-calendar",
    ),
    _cap(
        "communications",
        "Communications",
        "Phone, SMS, email, fax, voicemail, templates and consent across applications.",
        route="/workspace/communications",
        modules=("communications",),
        services=("adaptix-communications", "adaptix-telephony"),
        source=(
            f"{_WEB} (reads /api/v1/communications x37, telephony x17, templates, "
            f"consent, communications-hub); {_GW} all -> adaptix-communications / "
            "adaptix-telephony"
        ),
    ),
    _cap(
        "telephony",
        "Telephony",
        "Call queues, presence, scripts and voicemail.",
        route="/workspace/telephony",
        modules=("telephony",),
        services=("adaptix-telephony",),
        source=f"{_WEB}; {_GW} /api/v1/telephony -> adaptix-telephony",
    ),
    _cap(
        "voice",
        "Voice",
        "Real-time voice rooms tied to incidents and cases.",
        route="/workspace/voice",
        modules=("communications",),
        services=("adaptix-voice",),
        source=(
            f"{_WEB}; routes registry gates /voice on the communications "
            f"entitlement; {_GW} /api/v1/voice -> adaptix-voice"
        ),
    ),
    _cap(
        "trustsign",
        "TrustSign",
        "AdaptixCore's signature authority: signing requests, verification and the signed archive.",
        route="/workspace/trustsign",
        services=("adaptix-trustsign",),
        source=f"{_WEB}; {_GW} /api/v1/trustsign AND /api/v1/verifications -> adaptix-trustsign",
    ),
    _cap(
        "nemsis",
        "NEMSIS",
        "NEMSIS dataset registry, validation and state submission plumbing.",
        route="/workspace/nemsis",
        modules=("nemsis",),
        services=("adaptix-nemsis",),
        source=f"{_WEB}; {_GW} /api/v1/nemsis AND /api/v1/wards -> adaptix-nemsis",
    ),
    _cap(
        "terminology",
        "Terminology",
        "Reference terminology, code sets and concept governance.",
        route="/workspace/terminology/concepts",
        services=("adaptix-terminology",),
        source=(
            f"{_WEB} (app/workspace/terminology has NO root page.tsx — only "
            "concepts, mappings, review and sources; concepts is the entry); "
            f"{_GW} /api/v1/terminology -> adaptix-terminology"
        ),
    ),
    _cap(
        "graph",
        "Graph",
        "Microsoft Graph integration surfaces (mail, calendar, files).",
        route="/workspace/graph",
        services=("adaptix-graph",),
        source=f"{_WEB}; {_GW} /api/v1/graph -> adaptix-graph",
    ),
    _cap(
        "cortex",
        "Cortex",
        "Cross-platform AI assistance consumed by every application; this is its own operator surface.",
        route="/workspace/cortex-ai",
        modules=("ai", "cortex"),
        services=("adaptix-ai", "adaptix-cortex", "adaptix-bedrock"),
        source=(
            f"{_WEB} (app/workspace/cortex-ai reads /api/v1/ai x38); {_GW} "
            "/api/v1/ai -> adaptix-ai, /api/v1/cortex -> adaptix-cortex + core; "
            "the pricing catalog sells Cortex as module 'cortex' and the runtime "
            "grant is 'ai', so either opens the surface. Cortex is an "
            "intelligence layer, never a business application; founder-only "
            "Cortex administration is Administration's workspace."
        ),
    ),
    _cap(
        "forms",
        "Forms",
        "Structured forms consumed by Documents, ePCR and TransportLink.",
        services=("adaptix-forms",),
        source=f"{_GW} /api/v1/forms -> adaptix-forms; surfaced inside Governance/Documents",
    ),
    _cap(
        "payments",
        "Payments",
        "Payment handling consumed by Billing, Finance, portals and subscriptions. Never a second money ledger.",
        services=("adaptix-payments",),
        source=f"{_GW} /api/v1/payments -> adaptix-payments",
    ),
    _cap(
        "audit",
        "Audit",
        "Immutable cross-service audit trails and the evidence graph.",
        services=("adaptix-audit",),
        source=f"{_GW} /api/v1/audit -> adaptix-audit + core",
    ),
    _cap(
        "patient_identity",
        "Patient Identity",
        "Master patient index and matching consumed by clinical applications.",
        services=("adaptix-patient-identity",),
        source="module_registry patient_identity (audience adaptix-patient-identity)",
    ),
)
