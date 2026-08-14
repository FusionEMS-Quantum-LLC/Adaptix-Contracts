"""AdaptixCore Fire CAD Connect — shared contracts.

One normalized "AdaptixCore Standard CAD Incident" that every intake path
(uploaded file/paste today; secure feed / automatic inbox / vendor API / NENA
EIDO later) produces and the Fire domain consumes to populate a Fire incident +
NERIS. This subpackage defines only the shared, versioned DTOs, enums, and event
constants — no business logic, no ORM, no routes (those live in the Imports /
AI / Fire services).

Contract-enforced non-negotiables:
- Every normalized value is a ``FieldValue`` with its own confidence, review
  status (Confirmed/Review/Missing/Conflict), and source reference — never a
  bare value; ``MISSING`` never carries a value and ``CONFLICT`` lists >= 2
  candidates (no fabrication, no silent guessing).
- Provenance ties every value to where it came from and how it was derived
  (deterministic / agency profile / Cortex), with Cortex attribution.
- Agency mapping profiles are versioned + immutable-once-superseded (a
  correction creates a new version; Cortex proposes, never silently replaces).

Import example:
    from adaptix_contracts.cad_connect import CadConnectIncident, FieldStatus
"""

from .enums import (
    ConnectorSupportStatus,
    ExtractionMethod,
    FieldStatus,
    IngestionMethod,
    MappingProfileStatus,
)
from .events import (
    CAD_CONNECT_APPLIED,
    CAD_CONNECT_EVENT_TYPES,
    CAD_CONNECT_FAILED,
    CAD_CONNECT_MAPPING_PROFILE_ACTIVATED,
    CAD_CONNECT_NORMALIZED,
    CAD_CONNECT_PAYLOAD_RECEIVED,
    CAD_CONNECT_REVIEW_REQUIRED,
    CAD_CONNECT_SOURCE_CONNECTED,
)
from .profile import AgencyCadMappingProfile, CadFieldMappingRule
from .provenance import CadConnectProvenance, CadConnectSourceRef, FieldValue
from .record import (
    CadConnectAddress,
    CadConnectCaller,
    CadConnectIncident,
    CadConnectIncidentDetails,
    CadConnectIncidentTimes,
    CadConnectSource,
    CadConnectSummary,
    CadConnectUnit,
    CadConnectUnitTimes,
)

__all__ = [
    # enums
    "FieldStatus",
    "IngestionMethod",
    "ConnectorSupportStatus",
    "ExtractionMethod",
    "MappingProfileStatus",
    # provenance + field value
    "CadConnectSourceRef",
    "CadConnectProvenance",
    "FieldValue",
    # record
    "CadConnectAddress",
    "CadConnectCaller",
    "CadConnectIncidentDetails",
    "CadConnectIncidentTimes",
    "CadConnectUnitTimes",
    "CadConnectUnit",
    "CadConnectSource",
    "CadConnectSummary",
    "CadConnectIncident",
    # profile
    "CadFieldMappingRule",
    "AgencyCadMappingProfile",
    # events (defined; registered in producer PRs)
    "CAD_CONNECT_SOURCE_CONNECTED",
    "CAD_CONNECT_PAYLOAD_RECEIVED",
    "CAD_CONNECT_NORMALIZED",
    "CAD_CONNECT_REVIEW_REQUIRED",
    "CAD_CONNECT_APPLIED",
    "CAD_CONNECT_FAILED",
    "CAD_CONNECT_MAPPING_PROFILE_ACTIVATED",
    "CAD_CONNECT_EVENT_TYPES",
]
