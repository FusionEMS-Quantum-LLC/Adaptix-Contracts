"""Canonical encounter linkage contracts."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from .provenance import DataProvenance


class EncounterLinkStatus(str, Enum):
    """Adjudication state of an encounter's link to a canonical incident.

    ``SUGGESTED`` is a proposed link nothing has adjudicated yet,
    ``CONFIRMED`` one that was accepted, ``REJECTED`` one explicitly refused.
    The three stay distinct so a merely suggested link is never counted as
    established linkage; the ``interoperability.incident.link.*`` events
    mirror the same three outcomes.
    """

    SUGGESTED = "SUGGESTED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


# pylint too-few-public-methods (R0903) is disabled per class below. These are
# declarative Pydantic wire contracts whose entire contract IS their field set,
# exactly the shape pylint already exempts for @dataclass; the rule's intent (a
# class doing so little it should be a function or a tuple) cannot apply to a
# validated wire contract. Per class, never module-wide, so a future non-schema
# class added to this module is still checked.
class PublicSafetyEncounter(BaseModel):  # pylint: disable=too-few-public-methods
    """Canonical patient encounter joined to the cross-agency incident graph.

    Points at the source record rather than replacing it:
    ``source_agency_id``, ``source_service`` and ``source_encounter_id``
    identify the system that still owns the encounter.
    ``patient_identity_ref`` is a reference resolved by
    Adaptix-Patient-Identity-Service — this package carries the reference and
    implements none of the matching behind it. ``status`` records how the
    link to ``global_incident_id`` was established, and ``provenance`` the
    origin and transformation evidence for the values above.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    canonical_resource_version: str = "1.0"
    global_encounter_id: str = Field(..., min_length=1)
    global_incident_id: str | None = None
    source_agency_id: str = Field(..., min_length=1)
    source_tenant_id: str | None = None
    source_service: str = Field(..., min_length=1)
    source_encounter_id: str = Field(..., min_length=1)
    patient_identity_ref: str | None = None
    status: EncounterLinkStatus = EncounterLinkStatus.CONFIRMED
    occurred_at: datetime | None = None
    provenance: list[DataProvenance] = Field(default_factory=list)


__all__ = ["EncounterLinkStatus", "PublicSafetyEncounter"]
