"""The AdaptixCore Standard CAD Incident — the ONE normalized record.

Every CAD Connect input path (uploaded PDF/image/CSV/XLSX/XML/JSON/text, pasted
text, or — later — a direct feed/EIDO) is translated into this single shape,
which the Fire domain consumes to populate a Fire incident + NERIS. Vendor field
names (``dispatch_time`` / ``DSP_TIME`` / ``DTDISP`` / "Time Dispatched") all
normalize to the same AdaptixCore meaning here.

Each captured value is a :class:`FieldValue` carrying its own confidence,
review status, and source reference — the contract never stores a bare value,
so the firefighter can always review every imported value against its source.
A field that the extractor did not address is ``None`` (the consumer treats an
absent field as :class:`FieldStatus.MISSING`).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import IngestionMethod
from .provenance import CadConnectProvenance, FieldValue


class CadConnectAddress(BaseModel):
    """Normalized incident location. Each part is an independently reviewable value."""

    full: Optional[FieldValue] = None
    street: Optional[FieldValue] = None
    apt_unit: Optional[FieldValue] = None
    municipality: Optional[FieldValue] = None
    county: Optional[FieldValue] = None
    postal_code: Optional[FieldValue] = None
    cross_streets: Optional[FieldValue] = None
    business_or_location_name: Optional[FieldValue] = None
    latitude: Optional[FieldValue] = None
    longitude: Optional[FieldValue] = None

    model_config = ConfigDict(from_attributes=True)


class CadConnectCaller(BaseModel):
    """Caller information, captured only when present/appropriate."""

    name: Optional[FieldValue] = None
    phone: Optional[FieldValue] = None
    notes: Optional[FieldValue] = None

    model_config = ConfigDict(from_attributes=True)


class CadConnectIncidentDetails(BaseModel):
    """Incident identity + description + location + caller."""

    cad_incident_number: Optional[FieldValue] = None
    incident_number: Optional[FieldValue] = None
    call_type: Optional[FieldValue] = None
    dispatch_description: Optional[FieldValue] = None
    dispatch_determinant_code: Optional[FieldValue] = None
    dispatch_notes: Optional[FieldValue] = None
    address: CadConnectAddress = Field(default_factory=CadConnectAddress)
    caller: CadConnectCaller = Field(default_factory=CadConnectCaller)

    model_config = ConfigDict(from_attributes=True)


class CadConnectIncidentTimes(BaseModel):
    """The 14 incident-level time points, each normalized to ISO-8601 in FieldValue.value."""

    call_received: Optional[FieldValue] = None
    call_entered: Optional[FieldValue] = None
    dispatch: Optional[FieldValue] = None
    station_alert: Optional[FieldValue] = None
    unit_notified: Optional[FieldValue] = None
    unit_acknowledged: Optional[FieldValue] = None
    en_route: Optional[FieldValue] = None
    arrived_on_scene: Optional[FieldValue] = None
    patient_contact: Optional[FieldValue] = None
    transport: Optional[FieldValue] = None
    destination_arrival: Optional[FieldValue] = None
    available: Optional[FieldValue] = None
    cleared: Optional[FieldValue] = None
    back_in_service: Optional[FieldValue] = None

    model_config = ConfigDict(from_attributes=True)


class CadConnectUnitTimes(BaseModel):
    """Per-unit response timeline. Kept distinct from incident-level first-unit times."""

    dispatched: Optional[FieldValue] = None
    en_route: Optional[FieldValue] = None
    arrived: Optional[FieldValue] = None
    at_patient: Optional[FieldValue] = None
    transport: Optional[FieldValue] = None
    at_destination: Optional[FieldValue] = None
    cleared: Optional[FieldValue] = None
    available: Optional[FieldValue] = None
    back_in_service: Optional[FieldValue] = None

    model_config = ConfigDict(from_attributes=True)


class CadConnectUnit(BaseModel):
    """A single responding unit/apparatus with its own timeline.

    ``E1`` normalizes to ``designation='Engine 1'`` while ``designation_raw``
    preserves the source token. An unknown or mutual-aid unit is represented as
    an external responding resource — the consumer must NOT auto-create an owned
    fleet asset from it.
    """

    designation_raw: str = Field(
        ..., description="The unit token exactly as in the source (e.g. 'E1')."
    )
    designation: Optional[FieldValue] = Field(
        default=None, description="Normalized display designation (e.g. 'Engine 1')."
    )
    unit_type: Optional[FieldValue] = Field(
        default=None,
        description="engine|medic|truck|battalion|rescue|... (best effort).",
    )
    times: CadConnectUnitTimes = Field(default_factory=CadConnectUnitTimes)

    model_config = ConfigDict(from_attributes=True)


class CadConnectSource(BaseModel):
    """Where the payload came from + its provenance."""

    input_format: str = Field(
        ..., description="pdf|image|csv|xlsx|xml|json|txt|nfirs|eido|eidd|..."
    )
    original_filename: Optional[str] = None
    byte_sha256: Optional[str] = Field(
        default=None, description="SHA-256 of the raw artifact (dedup/idempotency)."
    )
    layout_signature: Optional[str] = Field(
        default=None,
        description="Fingerprint of the source layout (matches an agency mapping profile).",
    )
    provenance: CadConnectProvenance

    model_config = ConfigDict(from_attributes=True)


class CadConnectSummary(BaseModel):
    """Roll-up of review state across the record (drives the review-screen counts)."""

    overall_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    confirmed_count: int = 0
    review_count: int = 0
    missing_count: int = 0
    conflict_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class CadConnectIncident(BaseModel):
    """The single normalized CAD incident produced by the Universal CAD Gateway."""

    source: CadConnectSource
    incident: CadConnectIncidentDetails = Field(
        default_factory=CadConnectIncidentDetails
    )
    times: CadConnectIncidentTimes = Field(default_factory=CadConnectIncidentTimes)
    units: list[CadConnectUnit] = Field(default_factory=list)
    summary: CadConnectSummary = Field(default_factory=CadConnectSummary)

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def empty(
        cls, input_format: str, ingestion_method: IngestionMethod
    ) -> "CadConnectIncident":
        """Construct a minimal record shell (a payload received but not yet extracted)."""
        return cls(
            source=CadConnectSource(
                input_format=input_format,
                provenance=CadConnectProvenance(ingestion_method=ingestion_method),
            )
        )


__all__ = [
    "CadConnectAddress",
    "CadConnectCaller",
    "CadConnectIncidentDetails",
    "CadConnectIncidentTimes",
    "CadConnectUnitTimes",
    "CadConnectUnit",
    "CadConnectSource",
    "CadConnectSummary",
    "CadConnectIncident",
]
