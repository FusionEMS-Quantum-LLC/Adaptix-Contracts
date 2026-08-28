"""Canonical public-safety incident model.

This is not NEMSIS, NERIS, FHIR, or a vendor CAD schema. Source records remain
independent members of the incident graph and are never overwritten.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .provenance import DataProvenance


# pylint too-few-public-methods (R0903) is disabled per class below. These are
# declarative Pydantic wire contracts whose entire contract IS their field set,
# exactly the shape pylint already exempts for @dataclass; the rule's intent (a
# class doing so little it should be a function or a tuple) cannot apply to a
# validated wire contract. Per class, never module-wide, so a future non-schema
# class added to this module is still checked.
class IncidentIdentity(BaseModel):  # pylint: disable=too-few-public-methods
    """The stable identity of one canonical incident.

    ``global_incident_id`` is what the incident graph is keyed on, while
    ``originating_agency_id`` and ``primary_incident_number`` preserve the
    identity the first-reporting agency already uses, so the canonical record
    can always be traced back to a number that agency recognises. Frozen: an
    incident's identity is not edited in place.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    global_incident_id: str = Field(..., min_length=1)
    originating_agency_id: str = Field(..., min_length=1)
    primary_incident_number: str = Field(..., min_length=1)
    incident_type: str = Field(..., min_length=1)
    incident_status: str = Field(..., min_length=1)


class IncidentLocation(BaseModel):  # pylint: disable=too-few-public-methods
    """Where the incident occurred, as reported by contributing agencies.

    ``extra="allow"`` is deliberate: agencies carry location detail this
    model does not enumerate, and silently discarding it would lose reported
    operational fact. Latitude and longitude are range-bounded so a
    transposed or unit-mangled coordinate fails validation instead of
    landing on a map.
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    address: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)


class AgencyParticipation(BaseModel):  # pylint: disable=too-few-public-methods
    """One agency's window of involvement in a multi-agency incident.

    Each agency's participation is recorded independently rather than
    collapsed into a single owning agency, which is what makes a mutual-aid
    incident reconstructable. ``joined_at`` and ``cleared_at`` bound the
    involvement in time; ``tenant_id`` is populated only where that agency is
    an Adaptix tenant.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    agency_id: str = Field(..., min_length=1)
    tenant_id: str | None = None
    role: str | None = None
    joined_at: datetime | None = None
    cleared_at: datetime | None = None


class UnitParticipation(BaseModel):  # pylint: disable=too-few-public-methods
    """One responding unit's assignment window on an incident.

    Scoped by ``agency_id`` as well as ``unit_id`` because unit designators
    are only unique within an agency and repeat freely across them.
    ``assigned_at`` and ``cleared_at`` bound the assignment; ``status`` is
    the unit's last reported state within it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    agency_id: str = Field(..., min_length=1)
    unit_id: str = Field(..., min_length=1)
    unit_type: str | None = None
    status: str | None = None
    assigned_at: datetime | None = None
    cleared_at: datetime | None = None


class SourceRecordReference(BaseModel):  # pylint: disable=too-few-public-methods
    """Citation of a source record that contributed to the canonical incident.

    A citation, not a copy: the referenced record stays authoritative in its
    own system, per this module's note that source records are never
    overwritten. ``source_record_version`` tells a consumer which revision
    was folded in, and ``source_standard`` / ``source_standard_version`` name
    the format it was expressed in without that format becoming canonical.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    source_agency_id: str = Field(..., min_length=1)
    source_tenant_id: str | None = None
    source_service: str = Field(..., min_length=1)
    source_record_id: str = Field(..., min_length=1)
    source_record_version: str | None = None
    source_standard: str | None = None
    source_standard_version: str | None = None


class PublicSafetyIncident(BaseModel):  # pylint: disable=too-few-public-methods
    """Versioned canonical incident spanning multiple agencies and source records."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    canonical_resource_version: str = Field(default="1.0", min_length=1)
    identity: IncidentIdentity
    location: IncidentLocation | None = None
    timestamps: dict[str, datetime] = Field(default_factory=dict)
    agency_participation: list[AgencyParticipation] = Field(default_factory=list)
    units: list[UnitParticipation] = Field(default_factory=list)
    personnel: list[dict[str, Any]] = Field(default_factory=list)
    dispatch: dict[str, Any] = Field(default_factory=dict)
    response: dict[str, Any] = Field(default_factory=dict)
    patient_encounters: list[str] = Field(default_factory=list)
    fire_activity: dict[str, Any] = Field(default_factory=dict)
    clinical_activity: dict[str, Any] = Field(default_factory=dict)
    transport: dict[str, Any] = Field(default_factory=dict)
    destination: dict[str, Any] = Field(default_factory=dict)
    communications: list[dict[str, Any]] = Field(default_factory=list)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    source_records: list[SourceRecordReference] = Field(default_factory=list)
    provenance: list[DataProvenance] = Field(default_factory=list)


__all__ = [
    "AgencyParticipation",
    "IncidentIdentity",
    "IncidentLocation",
    "PublicSafetyIncident",
    "SourceRecordReference",
    "UnitParticipation",
]
