"""Adaptix Wildland federal sync contracts (Play P10).

Public surface for the Adaptix Wildland-Service. Nothing in this
package runs Wildland behaviour — it defines the models, enums, events,
and error types that Adaptix services and clients share when talking
about wildland-fire resource assignments and federal system sync
(IROC resource ordering, IRWIN incident identity, WFDSS strategic
decisions, and ICS-209 status summaries).

Import from the subpackage root, not the leaf modules::

    from adaptix_contracts.wildland import WildlandAssignment, WILDLAND_ASSIGNMENT_CREATED
"""

from adaptix_contracts.wildland.enums import (
    Ics209Section,
    IrocResourceType,
    WfdssPhase,
)
from adaptix_contracts.wildland.errors import (
    WildlandAssignmentNotFoundError,
    WildlandAssignmentTenantMismatchError,
    WildlandDeploymentError,
    WildlandError,
    WildlandErrorCode,
    WildlandErrorEnvelope,
    WildlandIcs209Error,
    WildlandIrocSyncError,
    WildlandIrwinSyncError,
    WildlandWfdssSyncError,
)
from adaptix_contracts.wildland.events import (
    WILDLAND_ASSIGNMENT_CREATED,
    WILDLAND_DEPLOYMENT_REPORTED,
    WILDLAND_EVENTS,
    WILDLAND_ICS209_SUBMITTED,
    WILDLAND_IROC_ORDER_SYNCED,
    WILDLAND_SOURCE_SERVICE,
    WILDLAND_WFDSS_DECISION_SYNCED,
    WildlandAssignmentCreatedEvent,
    WildlandDeploymentReportedEvent,
    WildlandIcs209SubmittedEvent,
    WildlandIrocOrderSyncedEvent,
    WildlandWfdssDecisionSyncedEvent,
    build_wildland_assignment_created,
    build_wildland_deployment_reported,
    build_wildland_ics209_submitted,
    build_wildland_iroc_order_synced,
    build_wildland_wfdss_decision_synced,
)
from adaptix_contracts.wildland.models import (
    Ics209Report,
    IrocResourceOrder,
    WfdssDecision,
    WildlandAssignment,
    WildlandDeployment,
)

__all__ = [
    "Ics209Report",
    "Ics209Section",
    "IrocResourceOrder",
    "IrocResourceType",
    "WILDLAND_ASSIGNMENT_CREATED",
    "WILDLAND_DEPLOYMENT_REPORTED",
    "WILDLAND_EVENTS",
    "WILDLAND_ICS209_SUBMITTED",
    "WILDLAND_IROC_ORDER_SYNCED",
    "WILDLAND_SOURCE_SERVICE",
    "WILDLAND_WFDSS_DECISION_SYNCED",
    "WfdssDecision",
    "WfdssPhase",
    "WildlandAssignment",
    "WildlandAssignmentCreatedEvent",
    "WildlandAssignmentNotFoundError",
    "WildlandAssignmentTenantMismatchError",
    "WildlandDeployment",
    "WildlandDeploymentError",
    "WildlandDeploymentReportedEvent",
    "WildlandError",
    "WildlandErrorCode",
    "WildlandErrorEnvelope",
    "WildlandIcs209Error",
    "WildlandIcs209SubmittedEvent",
    "WildlandIrocOrderSyncedEvent",
    "WildlandIrocSyncError",
    "WildlandIrwinSyncError",
    "WildlandWfdssDecisionSyncedEvent",
    "WildlandWfdssSyncError",
    "build_wildland_assignment_created",
    "build_wildland_deployment_reported",
    "build_wildland_ics209_submitted",
    "build_wildland_iroc_order_synced",
    "build_wildland_wfdss_decision_synced",
]
