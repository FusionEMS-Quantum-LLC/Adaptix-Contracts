"""
Adaptix Service Registry — canonical service names, route prefixes, and ports.

This is the single source of truth for all Adaptix platform services.
All services must be registered here before being used in contracts or clients.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceDefinition:
    """Canonical definition of an Adaptix platform service."""

    name: str
    slug: str
    route_prefix: str
    port: int
    description: str
    domain_owner: bool = True  # True = owns its domain data


# ============================================================================
# PLATFORM FOUNDATION SERVICES (Core-owned)
# ============================================================================

CORE_SERVICE = ServiceDefinition(
    name="Adaptix-Core-Service",
    slug="core",
    route_prefix="/api/core",
    port=8000,
    description="Authentication, tenant management, RBAC, audit framework, event bus",
    domain_owner=False,  # Core is infrastructure, not a domain owner
)

# ============================================================================
# EXISTING OPERATIONAL SERVICES
# ============================================================================

CAD_SERVICE = ServiceDefinition(
    name="Adaptix-CAD-Service",
    slug="cad",
    route_prefix="/api/v1/cad",
    port=8001,
    description="Computer-aided dispatch, incident management",
)

EPCR_SERVICE = ServiceDefinition(
    name="Adaptix-EPCR-Service",
    slug="epcr",
    route_prefix="/api/v1/epcr",
    port=8002,
    description="Electronic patient care reports, NEMSIS data collection",
)

FIRE_SERVICE = ServiceDefinition(
    name="Adaptix-Fire-Service",
    slug="fire",
    route_prefix="/api/v1/fire",
    port=8003,
    description="Fire incident reporting, NERIS data collection",
)

BILLING_SERVICE = ServiceDefinition(
    name="Adaptix-Billing-Service",
    slug="billing",
    route_prefix="/api/v1/billing",
    port=8004,
    description="Claims, payments, invoices, billing lifecycle",
)

CREW_SERVICE = ServiceDefinition(
    name="Adaptix-Crew-Service",
    slug="crew",
    route_prefix="/api/v1/crew",
    port=8005,
    description="Crew management, CrewLink mobile",
)

WORKFORCE_SERVICE = ServiceDefinition(
    name="Adaptix-Workforce-Service",
    slug="workforce",
    route_prefix="/api/v1/workforce",
    port=8006,
    description="Workforce scheduling, staffing",
)

TRANSPORT_SERVICE = ServiceDefinition(
    name="Adaptix-Transport-Service",
    slug="transport",
    route_prefix="/api/v1/transport",
    port=8007,
    description="Transport trips, MDT, TransportLink",
)

COMMUNICATIONS_SERVICE = ServiceDefinition(
    name="Adaptix-Communications-Service",
    slug="communications",
    route_prefix="/api/v1/communications",
    port=8008,
    description="SMS, email, push notifications",
)

TELEPHONY_SERVICE = ServiceDefinition(
    name="Adaptix-Telephony-Service",
    slug="telephony",
    route_prefix="/api/v1/telephony",
    port=8009,
    description="Voice, fax, Telnyx integration",
)

INVENTORY_SERVICE = ServiceDefinition(
    name="Adaptix-Inventory-Service",
    slug="inventory",
    route_prefix="/api/v1/inventory",
    port=8040,
    description="Inventory management",
)

MEDICATIONS_SERVICE = ServiceDefinition(
    name="Adaptix-Medications-Service",
    slug="medications",
    route_prefix="/api/v1/medications",
    port=8041,
    description="Medication management",
)

NARCOTICS_SERVICE = ServiceDefinition(
    name="Adaptix-Narcotics-Service",
    slug="narcotics",
    route_prefix="/api/v1/narcotics",
    port=8042,
    description="Narcotics tracking, DEA compliance",
)

LABOR_SERVICE = ServiceDefinition(
    name="Adaptix-Labor-Service",
    slug="labor",
    route_prefix="/api/v1/labor",
    port=8043,
    description="Labor tracking, timekeeping",
)

GRAPH_SERVICE = ServiceDefinition(
    name="Adaptix-Graph-Service",
    slug="graph",
    route_prefix="/api/v1/graph",
    port=8044,
    description="Graph relationships, Microsoft Graph integration",
)

AIR_SERVICE = ServiceDefinition(
    name="Adaptix-Air-Service",
    slug="air",
    route_prefix="/api/v1/air",
    port=8045,
    description="Air transport operations",
)

# Workforce scheduling domain. Registered here because 27 ``schedule.*`` events in
# ``adaptix_contracts.events.registry`` already declare
# ``source_service="adaptix-scheduling"``; without this entry those events name a
# service that does not resolve (see
# ``tests/test_scheduling_service_registration.py``).
#
# Runtime note (verified 2026-07-23 against
# Adaptix-Gateway/backend/app/config/routes.py:1830-1842): the ``/api/v1/scheduling``
# prefix is currently proxied to Labor-Service with audience ``adaptix-labor``. No
# standalone Adaptix-Scheduling-Service repository or ECS service exists yet. This
# definition declares the canonical contract-level owner of the scheduling domain
# per SCHEDULING_ARCHITECTURE_LOCK.md; it does not assert a deployed service.
SCHEDULING_SERVICE = ServiceDefinition(
    name="Adaptix-Scheduling-Service",
    slug="scheduling",
    route_prefix="/api/v1/scheduling",
    port=8046,
    description=(
        "Workforce scheduling: schedules, shift templates/instances, assignments, "
        "availability, time off, overtime, swaps, holdovers, coverage rules"
    ),
)

# ============================================================================
# NEW DOMAIN SERVICES (Option A expansion)
# ============================================================================

CRM_SERVICE = ServiceDefinition(
    name="Adaptix-CRM-Service",
    slug="crm",
    route_prefix="/api/v1/crm",
    port=8010,
    description="Contacts, accounts, leads, organizations, CRM activity timeline",
)

INVESTOR_SERVICE = ServiceDefinition(
    name="Adaptix-Investor-Service",
    slug="investor",
    route_prefix="/api/v1/investor",
    port=8011,
    description="Investors, funding rounds, commitments, investment pipeline",
)

PARTNER_SERVICE = ServiceDefinition(
    name="Adaptix-Partner-Service",
    slug="partner",
    route_prefix="/api/v1/partner",
    port=8012,
    description="Partner organizations, contacts, agreements, referrals",
)

FINANCE_SERVICE = ServiceDefinition(
    name="Adaptix-Finance-Service",
    slug="finance",
    route_prefix="/api/v1/finance",
    port=8013,
    description="Platform financial summaries, revenue, cost, financial dashboard APIs",
)

CALENDAR_SERVICE = ServiceDefinition(
    name="Adaptix-Calendar-Service",
    slug="calendar",
    route_prefix="/api/v1/calendar",
    port=8014,
    description="Platform calendar events, operational scheduling, reminders",
)

SEARCH_SERVICE = ServiceDefinition(
    name="Adaptix-Search-Service",
    slug="search",
    route_prefix="/api/v1/search",
    port=8015,
    description="Global search, indexed records, tenant-scoped search",
)

FOUNDER_SERVICE = ServiceDefinition(
    name="Adaptix-Founder-Service",
    slug="founder",
    route_prefix="/api/v1/founder-command",
    port=8016,
    description="Founder dashboard, command views, platform status summaries",
)

DOCUMENTS_SERVICE = ServiceDefinition(
    name="Adaptix-Documents-Service",
    slug="documents",
    route_prefix="/api/v1/documents",
    port=8017,
    description="File storage, attachments, document lifecycle, versioning",
)

OFFICE_SERVICE = ServiceDefinition(
    name="Adaptix-Office-Service",
    slug="office",
    route_prefix="/api/v1/office",
    port=8018,
    description="Internal operational tools, admin utilities, office management",
)

TRAINING_SERVICE = ServiceDefinition(
    name="Adaptix-Training-Service",
    slug="training",
    route_prefix="/api/v1/training",
    port=8019,
    description="Certifications, CE tracking, training records",
)

FLEET_SERVICE = ServiceDefinition(
    name="Adaptix-Fleet-Service",
    slug="fleet",
    route_prefix="/api/v1/fleet",
    port=8020,
    description="Vehicles, equipment assignment, fleet lifecycle, maintenance",
)

HR_SERVICE = ServiceDefinition(
    name="Adaptix-HR-Service",
    slug="hr",
    route_prefix="/api/v1/hr",
    port=8021,
    description="Personnel records, employment data, HR lifecycle",
)

ANALYTICS_SERVICE = ServiceDefinition(
    name="Adaptix-Analytics-Service",
    slug="analytics",
    route_prefix="/api/v1/analytics",
    port=8022,
    description="Metrics, dashboards, reporting pipelines",
)

COMPLIANCE_SERVICE = ServiceDefinition(
    name="Adaptix-Compliance-Service",
    slug="compliance",
    route_prefix="/api/v1/compliance",
    port=8023,
    description="Regulatory tracking, compliance workflows",
)

IMPORTS_SERVICE = ServiceDefinition(
    name="Adaptix-Imports-Service",
    slug="imports",
    route_prefix="/api/v1/imports",
    port=8024,
    description="Inbound data ingestion pipelines, import jobs",
)

EXPORTS_SERVICE = ServiceDefinition(
    name="Adaptix-Exports-Service",
    slug="exports",
    route_prefix="/api/v1/exports",
    port=8025,
    description="Outbound data export pipelines, export artifacts",
)

POLICY_SERVICE = ServiceDefinition(
    name="Adaptix-Policy-Service",
    slug="policy",
    route_prefix="/api/v1/policy",
    port=8026,
    description="Policy documents, enforcement, versioning",
)

DEVICE_SERVICE = ServiceDefinition(
    name="Adaptix-Device-Service",
    slug="device",
    route_prefix="/api/v1/device",
    port=8027,
    description="Device inventory, assignments, status, device lifecycle",
)

APP_MANAGEMENT_SERVICE = ServiceDefinition(
    name="Adaptix-App-Management-Service",
    slug="app-management",
    route_prefix="/api/v1/app-management",
    port=8028,
    description="App config, deployments, feature flags",
)

AI_SERVICE = ServiceDefinition(
    name="Adaptix-AI-Service",
    slug="ai",
    route_prefix="/api/v1/ai",
    port=8029,
    description="AI services, inference endpoints, automation logic",
)

PATIENT_IDENTITY_SERVICE = ServiceDefinition(
    name="Adaptix-Patient-Identity-Service",
    slug="patient-identity",
    route_prefix="/api/v1/patient-identity",
    port=8030,
    description="Patient identity management, MPI, patient matching",
)

LEGAL_SERVICE = ServiceDefinition(
    name="Adaptix-Legal-Service",
    slug="legal",
    route_prefix="/api/v1/legal",
    port=8031,
    description="Legal requests, contracts, legal document management",
)

INTEGRATIONS_SERVICE = ServiceDefinition(
    name="Adaptix-Integrations-Service",
    slug="integrations",
    route_prefix="/api/v1/integrations",
    port=8032,
    description="Third-party integrations, integration configs, webhook management",
)

TERMINOLOGY_SERVICE = ServiceDefinition(
    name="Adaptix-Terminology-Service",
    slug="terminology",
    route_prefix="/api/v1/terminology",
    port=8033,
    description="Reference data, terminology codes, code sets",
)

MARKETING_SERVICE = ServiceDefinition(
    name="Adaptix-Marketing-Service",
    slug="marketing",
    route_prefix="/api/v1/marketing",
    port=8034,
    description="Marketing campaigns, leads, marketing analytics",
)

CUSTOMER_SUCCESS_SERVICE = ServiceDefinition(
    name="Adaptix-Customer-Success-Service",
    slug="customer-success",
    route_prefix="/api/v1/customer-success",
    port=8035,
    description="Customer health scores, success plans, onboarding tracking",
)

PRICING_SERVICE = ServiceDefinition(
    name="Adaptix-Pricing-Service",
    slug="pricing",
    route_prefix="/api/v1/pricing",
    port=8036,
    description="Pricing plans, rate cards, pricing rules",
)

OPERATIONS_SERVICE = ServiceDefinition(
    name="Adaptix-Operations-Service",
    slug="operations",
    route_prefix="/api/v1/operations",
    port=8037,
    description="Operations command, operational workflows, ops status",
)

NEMSIS_SERVICE = ServiceDefinition(
    name="Adaptix-NEMSIS-Service",
    slug="nemsis",
    route_prefix="/api/v1/nemsis",
    port=8038,
    description="NEMSIS 3.5.1 export pipeline, XML generation, XSD/Schematron validation",
)

NERIS_SERVICE = ServiceDefinition(
    name="Adaptix-NERIS-Service",
    slug="neris",
    route_prefix="/api/v1/neris",
    port=8039,
    description="NERIS fire reporting, incident documentation, NERIS export",
)


# ============================================================================
# ALL SERVICES REGISTRY
# ============================================================================

ALL_SERVICES: list[ServiceDefinition] = [
    # Platform foundation
    CORE_SERVICE,
    # Existing operational
    CAD_SERVICE,
    EPCR_SERVICE,
    FIRE_SERVICE,
    BILLING_SERVICE,
    CREW_SERVICE,
    WORKFORCE_SERVICE,
    TRANSPORT_SERVICE,
    COMMUNICATIONS_SERVICE,
    TELEPHONY_SERVICE,
    INVENTORY_SERVICE,
    MEDICATIONS_SERVICE,
    NARCOTICS_SERVICE,
    LABOR_SERVICE,
    GRAPH_SERVICE,
    AIR_SERVICE,
    SCHEDULING_SERVICE,
    # New domain services
    CRM_SERVICE,
    INVESTOR_SERVICE,
    PARTNER_SERVICE,
    FINANCE_SERVICE,
    CALENDAR_SERVICE,
    SEARCH_SERVICE,
    FOUNDER_SERVICE,
    DOCUMENTS_SERVICE,
    OFFICE_SERVICE,
    TRAINING_SERVICE,
    FLEET_SERVICE,
    HR_SERVICE,
    ANALYTICS_SERVICE,
    COMPLIANCE_SERVICE,
    IMPORTS_SERVICE,
    EXPORTS_SERVICE,
    POLICY_SERVICE,
    DEVICE_SERVICE,
    APP_MANAGEMENT_SERVICE,
    AI_SERVICE,
    PATIENT_IDENTITY_SERVICE,
    LEGAL_SERVICE,
    INTEGRATIONS_SERVICE,
    TERMINOLOGY_SERVICE,
    MARKETING_SERVICE,
    CUSTOMER_SUCCESS_SERVICE,
    PRICING_SERVICE,
    OPERATIONS_SERVICE,
    NEMSIS_SERVICE,
    NERIS_SERVICE,
]

# Lookup by slug
SERVICE_BY_SLUG: dict[str, ServiceDefinition] = {s.slug: s for s in ALL_SERVICES}
