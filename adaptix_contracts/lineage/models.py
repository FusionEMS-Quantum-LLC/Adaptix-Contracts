"""Canonical encounter lineage (5.27.0).

``EncounterLineage`` is the one cross-domain record that ties a patient
encounter back to the dispatch, transport request, trip, unit, vehicle and
crew that actually served it, and forward to the payer it bills. Before it,
vehicle and crew identifiers stopped at CAD (``CadTransportDispatch`` /
``CadUnitAssignment``) and TransportLink, so Billing could not ask Fleet,
Crew or Workforce about the resources actually used on a claim.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from adaptix_contracts.cad.models import LevelOfCare


class EncounterLineage(BaseModel):
    """Opaque identifiers that link one encounter across every owning domain.

    Every identifier is the owning service's opaque record id, never a display
    name, call sign or unit label. Each owner stays the source of truth for its
    record; this model only carries the references.

    Only ``tenant_id`` is required. Any other stage may not exist yet (a chart
    opened without a CAD dispatch, a trip not yet assigned a vehicle), so every
    other field is optional and ``None`` means "not known to the producer",
    never "did not happen".

    ``crew_member_ids`` is ordered as the producer lists the crew and is
    deduplicated preserving first occurrence.

    ``service_started_at`` / ``service_completed_at`` must be timezone-aware,
    and completion may not precede start. ``date_of_service`` is NOT derived
    from or checked against ``service_started_at``: the repository defines the
    date of service as the encounter's calendar date in the agency's local time
    zone (see ``EpcrBillingSnapshot.date_of_service``, 5.26.0), which can differ
    from the UTC date of any instant.

    The four level-of-care fields use the CAD vocabulary
    :class:`~adaptix_contracts.cad.models.LevelOfCare` and record the chain
    requested (intake) -> dispatched (CAD) -> documented (ePCR) -> billed
    (Billing), so a consumer can see where the level changed.
    """

    model_config = ConfigDict(extra="forbid")

    tenant_id: str = Field(..., min_length=1)

    dispatch_id: Optional[str] = Field(default=None, min_length=1)
    transport_request_id: Optional[str] = Field(default=None, min_length=1)
    trip_id: Optional[str] = Field(default=None, min_length=1)
    epcr_id: Optional[str] = Field(default=None, min_length=1)
    encounter_id: Optional[str] = Field(default=None, min_length=1)
    unit_id: Optional[str] = Field(default=None, min_length=1)
    vehicle_id: Optional[str] = Field(default=None, min_length=1)
    crew_member_ids: list[str] = Field(default_factory=list)
    patient_id: Optional[str] = Field(default=None, min_length=1)
    payer_id: Optional[str] = Field(default=None, min_length=1)

    service_started_at: Optional[AwareDatetime] = None
    service_completed_at: Optional[AwareDatetime] = None
    date_of_service: Optional[date] = None

    requested_level_of_care: Optional[LevelOfCare] = None
    dispatched_level_of_care: Optional[LevelOfCare] = None
    documented_level_of_care: Optional[LevelOfCare] = None
    billed_level_of_care: Optional[LevelOfCare] = None

    @field_validator("crew_member_ids")
    @classmethod
    def _dedupe_crew_member_ids(cls, value: list[str]) -> list[str]:
        if any(not member_id for member_id in value):
            raise ValueError("crew_member_ids must not contain empty identifiers")
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def _completed_not_before_started(self) -> EncounterLineage:
        if (
            self.service_started_at is not None
            and self.service_completed_at is not None
            and self.service_completed_at < self.service_started_at
        ):
            raise ValueError("service_completed_at must not precede service_started_at")
        return self
