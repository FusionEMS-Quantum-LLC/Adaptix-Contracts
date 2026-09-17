"""OPERATIONS domain applications.

See ``_definitions/__init__.py`` for the evidence rules every entry obeys.
"""

from __future__ import annotations

from adaptix_contracts.application_registry._definitions.shorthand import _GW, _WEB
from adaptix_contracts.application_registry._model import (
    ApplicationDefinition,
    ApplicationDomain,
    PortalDefinition,
    _app,
    _ws,
)

OPERATIONS_APPLICATIONS: tuple[ApplicationDefinition, ...] = (
    _app(
        "cad",
        "CAD",
        "Receive work, assign units and follow every response through to close.",
        domain=ApplicationDomain.OPERATIONS,
        canonical_route="/workspace/cad",
        modules=("cad",),
        primary_services=("adaptix-cad",),
        workspaces=(
            _ws("dispatch", "Dispatch Board", "/workspace/cad/dispatch"),
            _ws("incidents", "Incidents", "/workspace/cad/incidents"),
            _ws("intake", "Intake", "/workspace/cad/intake"),
            _ws("units", "Units", "/workspace/cad/units"),
            _ws("map", "Map", "/workspace/cad/map"),
            _ws("tracking", "Tracking", "/workspace/cad/tracking"),
            _ws("communications", "Communications", "/workspace/cad/comms"),
            _ws("facilities", "Facilities", "/workspace/cad/facilities"),
            _ws("hospitals", "Hospitals", "/workspace/cad/hospitals"),
            _ws("premise_hazards", "Premise Hazards", "/workspace/cad/premise-hazards"),
            _ws("transports", "Transports", "/workspace/cad/transports"),
            _ws("analytics", "Analytics", "/workspace/cad/analytics"),
            _ws("settings", "Settings", "/workspace/cad/settings"),
        ),
        source=f"{_WEB}; {_GW} /api/v1/cad -> adaptix-cad; module_registry cad",
    ),
    _app(
        "field_operations",
        "Field Operations",
        "What the crew works from in the unit: status, assignment, navigation, paging and messages.",
        domain=ApplicationDomain.OPERATIONS,
        canonical_route="/workspace/mdt",
        modules=("mdt", "crewlink", "crew"),
        primary_services=("adaptix-cad", "adaptix-crew"),
        supporting_services=("adaptix-field",),
        clients=("Adaptix-Android-MDT", "Adaptix-Android-CrewLink"),
        workspaces=(
            _ws("mdt", "MDT", "/workspace/mdt", modules=("mdt",)),
            _ws("mdt_status", "Unit Status", "/workspace/mdt/status", modules=("mdt",)),
            _ws("mdt_map", "Navigation", "/workspace/mdt/map", modules=("mdt",)),
            _ws(
                "mdt_messages", "Messages", "/workspace/mdt/messages", modules=("mdt",)
            ),
            _ws("crewlink", "CrewLink", "/workspace/crewlink", modules=("crewlink",)),
            _ws(
                "crewlink_roster",
                "Roster",
                "/workspace/crewlink/roster",
                modules=("crewlink",),
            ),
            _ws(
                "crewlink_shifts",
                "Shifts",
                "/workspace/crewlink/shifts",
                modules=("crewlink",),
            ),
            _ws(
                "crewlink_ptt",
                "Push-to-Talk",
                "/workspace/crewlink/ptt",
                modules=("crewlink",),
            ),
            _ws(
                "crewlink_devices",
                "Devices",
                "/workspace/crewlink/devices",
                modules=("crewlink",),
            ),
            _ws("crew", "Crew", "/workspace/crew", modules=("crew",)),
        ),
        source=(
            f"{_WEB}; {_GW} /api/v1/mdt -> adaptix-cad, /api/v1/crewlink -> "
            "adaptix-cad + adaptix-crew, /api/v1/crew -> adaptix-crew, "
            "/api/v1/field -> adaptix-field. The umbrella shell route is the MDT "
            "surface until a dedicated field shell exists; CrewLink and Crew are "
            "workspaces with their own module gates, so consolidation widens no "
            "entitlement."
        ),
    ),
    _app(
        "transportlink",
        "TransportLink",
        "Schedule and run interfacility and non-emergency transports end to end.",
        domain=ApplicationDomain.OPERATIONS,
        canonical_route="/transportlink",
        modules=("transportlink",),
        primary_services=("adaptix-transport",),
        clients=("Adaptix-Transport-Request-App",),
        portals=(
            PortalDefinition(
                portal_id="transport_status_portal",
                display_name="Transport Status Portal",
                entry_route="/transportlink/portal",
                audience="transport_requester",
            ),
        ),
        workspaces=(
            _ws("new_request", "New Request", "/transportlink/requests/new"),
            _ws("forms", "Forms", "/transportlink/forms"),
            _ws("intelligence", "Intelligence", "/transportlink/intelligence"),
            _ws("schedule", "Daily Schedule", "/workspace/transport/schedule"),
            _ws("hazards", "Hazard Reports", "/workspace/transport/hazards"),
            _ws("mci", "MCI Incidents", "/workspace/transport/mci"),
            _ws("rollups", "Status Rollups", "/workspace/transport/analytics"),
        ),
        source=(
            f"{_WEB} (app/transportlink/page.tsx is the navigated root on main; "
            "routes registry PUBLIC product entry); "
            f"{_GW} /api/v1/transport AND /api/v1/transportlink -> adaptix-transport "
            "(module_registry records adaptix-transportlink for the module; the "
            "gateway is the routing truth and is what is recorded here). The "
            "external requester/status portal stays a separate audience surface."
        ),
    ),
    _app(
        "air_operations",
        "Air Operations",
        "Air-medical missions from request through flight following and post-flight.",
        domain=ApplicationDomain.OPERATIONS,
        canonical_route="/workspace/air",
        modules=("air",),
        primary_services=("adaptix-air",),
        clients=("Adaptix-Android-Air", "Adaptix-Android-AirPilot"),
        workspaces=(
            _ws("missions", "Missions", "/workspace/air/missions"),
            _ws("aircraft", "Aircraft", "/workspace/air/aircraft"),
            _ws("weather", "Weather", "/workspace/air/weather"),
            _ws("weight_balance", "Weight & Balance", "/workspace/air/weight-balance"),
            _ws("helipads", "Helipads", "/workspace/air/helipads"),
            _ws(
                "landing_requests",
                "Landing Requests",
                "/workspace/air/landing-requests",
            ),
            _ws("tracking", "Flight Following", "/workspace/air/tracking"),
            _ws("duty_rest", "Duty & Rest", "/workspace/air/duty-rest"),
            _ws("risk", "Risk (FRAT)", "/workspace/air/risk"),
            _ws("maintenance", "Maintenance", "/workspace/air/maintenance"),
            _ws("airworthiness", "Airworthiness", "/workspace/air/airworthiness"),
            _ws("inspections", "Inspections", "/workspace/air/inspections"),
            _ws("post_flight", "Post-Flight", "/workspace/air/post-flight"),
            _ws("pilot_operations", "Pilot Operations", "/workspace/air-pilot"),
        ),
        source=(
            f"{_WEB}; {_GW} /api/v1/air AND /api/v1/air-pilot -> adaptix-air. "
            "Adaptix-Air-Service-Pilot has no gateway audience of its own, so the "
            "pilot surface is a workspace of this application, never a second app."
        ),
    ),
    _app(
        "hospital_facility_operations",
        "Hospital / Facility Operations",
        "Destination capacity, diversion, bed reservations, transfers and patient handoff.",
        domain=ApplicationDomain.OPERATIONS,
        canonical_route="/workspace/hospital",
        modules=("hospital",),
        primary_services=("adaptix-hospital",),
        supporting_services=("adaptix-facilities",),
        portals=(
            PortalDefinition(
                portal_id="hospital_portal",
                display_name="Hospital Portal",
                entry_route="/hospital/login",
                audience="hospital_staff",
            ),
        ),
        workspaces=(
            _ws("handoffs", "Handoffs", "/workspace/hospital/handoffs"),
            _ws("incoming", "Incoming", "/workspace/hospital/incoming"),
            _ws("transfers", "Transfers", "/workspace/hospital/transfers"),
            _ws("capacity", "Capacity", "/workspace/hospital/capacity"),
            _ws(
                "bed_reservations",
                "Bed Reservations",
                "/workspace/hospital/bed-reservations",
            ),
            _ws(
                "facility_registry",
                "Facility Registry",
                "/workspace/hospital/facility-registry",
            ),
            _ws("hie", "HIE", "/workspace/hospital/hie"),
            _ws("analytics", "Analytics", "/workspace/hospital/analytics"),
            _ws("integrations", "Integrations", "/workspace/hospital/integrations"),
            _ws("audit", "Audit", "/workspace/hospital/audit"),
        ),
        source=(
            f"{_WEB} (layout gates module 'hospital'); {_GW} /api/v1/hospital -> "
            "adaptix-hospital, /api/v1/facilities -> adaptix-facilities. "
            "Facility-Registry-Service owns facility data; this is the human "
            "workspace. Hospital staff authenticate through their own portal "
            "session, not the agency JWT."
        ),
    ),
)
