"""ePCR transport-lifecycle event contracts (producer: Adaptix-EPCR-Service).

Why these exist
---------------
``epcr.chart.updated`` is a generic catch-all whose payload is an unbounded
spread of chart data. A downstream consumer that has to answer "where is this
patient being taken, and have they arrived yet?" cannot rely on it without
also receiving whatever else happens to be on the chart — which for ePCR means
clinical narrative, vitals and patient identity.

These two events publish exactly those two transport facts, and nothing else,
so a consumer outside the clinical boundary (Family Bridge is the first) can
follow the transport without ever being handed PHI it must not hold.

Field provenance — every field below maps to a column that already exists in
Adaptix-EPCR-Service, so nothing here invents a data source:

* ``destination_name``/``destination_code``/``type_of_destination_code`` ->
  ``epcr_app.models_chart_disposition.ChartDisposition`` (NEMSIS
  eDisposition.01, .02, .11).
* ``arrived_at`` -> ``ChartTimes.patient_arrived_at_destination_at``
  (NEMSIS eTimes.11).
* ``transfer_of_care_at`` -> ``ChartTimes.destination_transfer_of_care_at``
  (NEMSIS eTimes.12).

PHI boundary
------------
No patient name, date of birth, chief complaint, impression, narrative,
vitals, medications or crew notes appear in any payload in this module, and
``extra="forbid"`` makes adding one a validation error rather than a silent
leak. Opaque identifiers (``chart_id``, ``patient_id``, ``tenant_id``) are
carried because the consuming service needs to key on them; a *display*
surface must still not render them (see the Family-Bridge portal contract,
``adaptix_contracts.family_bridge.models.FamilyPortalView``).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Event name constants
# ---------------------------------------------------------------------------

#: The chart's transport destination was set or changed. Fires on the first
#: destination selection as well as on every diversion afterwards, so a
#: consumer that told a family "you are going to St. Mary's" learns when that
#: stops being true.
EPCR_TRANSPORT_DESTINATION_UPDATED: Final[str] = "epcr.transport.destination.updated"

#: The patient physically arrived at the destination facility
#: (``eTimes.11``). Distinct from ``epcr.chart.hospital_handoff``, which is
#: the clinical handoff packet, and from transfer of care (``eTimes.12``),
#: which may follow minutes later.
EPCR_TRANSPORT_ARRIVED_DESTINATION: Final[str] = "epcr.transport.arrived_destination"

EPCR_TRANSPORT_EVENTS: frozenset[str] = frozenset(
    {
        EPCR_TRANSPORT_DESTINATION_UPDATED,
        EPCR_TRANSPORT_ARRIVED_DESTINATION,
    }
)

EPCR_TRANSPORT_SOURCE_SERVICE: Final[str] = "epcr"
"""Service-registry slug of the producing service."""


# ---------------------------------------------------------------------------
# Payloads
# ---------------------------------------------------------------------------


class _EpcrTransportEventPayload(BaseModel):
    """Base for the transport-lifecycle payloads.

    ``extra="forbid"`` is the PHI guard: a producer that tries to attach a
    complaint, a narrative or a patient name fails validation at the publish
    site instead of leaking it to every subscriber.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    tenant_id: str = Field(..., description="Tenant scope.")
    chart_id: str = Field(..., description="Opaque ePCR chart identifier.")
    patient_id: str | None = Field(
        default=None,
        description=(
            "Opaque patient identifier when the chart has one. Absent for a "
            "chart documented before identity resolution."
        ),
    )
    incident_number: str | None = Field(
        default=None,
        description="Agency incident number, for operator cross-reference.",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Correlation id for tracing (mirrors envelope.correlation_id).",
    )
    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description=(
            "When the documented fact occurred. For crew-entered times this "
            "is the clinical time, which may pre-date publication by hours."
        ),
    )


class EpcrTransportDestinationUpdatedPayload(_EpcrTransportEventPayload):
    """Payload for ``epcr.transport.destination.updated``."""

    destination_name: str | None = Field(
        default=None,
        max_length=255,
        description=(
            "Facility name as documented (eDisposition.01). None while the "
            "crew has recorded a destination code but no name — a consumer "
            "must render that as unknown, never as an empty facility."
        ),
    )
    destination_code: str | None = Field(
        default=None,
        max_length=64,
        description="Facility code (eDisposition.02).",
    )
    type_of_destination_code: str | None = Field(
        default=None,
        max_length=16,
        description="NEMSIS type-of-destination code (eDisposition.11).",
    )
    previous_destination_name: str | None = Field(
        default=None,
        max_length=255,
        description=(
            "Destination this replaced, when the update is a diversion. None "
            "on the first destination selection."
        ),
    )
    eta_at: datetime | None = Field(
        default=None,
        description=(
            "Estimated arrival, only when the producer holds a real estimate. "
            "Never a fabricated or defaulted value."
        ),
    )


class EpcrTransportArrivedDestinationPayload(_EpcrTransportEventPayload):
    """Payload for ``epcr.transport.arrived_destination``."""

    destination_name: str | None = Field(
        default=None,
        max_length=255,
        description="Facility arrived at (eDisposition.01).",
    )
    destination_code: str | None = Field(
        default=None,
        max_length=64,
        description="Facility code (eDisposition.02).",
    )
    arrived_at: datetime = Field(
        ...,
        description="Patient arrived at destination (eTimes.11).",
    )
    transfer_of_care_at: datetime | None = Field(
        default=None,
        description=(
            "Transfer of care at destination (eTimes.12), when already "
            "documented. Arrival and transfer of care are separate facts; "
            "absent here means not yet documented, never 'same as arrival'."
        ),
    )


__all__ = [
    "EPCR_TRANSPORT_ARRIVED_DESTINATION",
    "EPCR_TRANSPORT_DESTINATION_UPDATED",
    "EPCR_TRANSPORT_EVENTS",
    "EPCR_TRANSPORT_SOURCE_SERVICE",
    "EpcrTransportArrivedDestinationPayload",
    "EpcrTransportDestinationUpdatedPayload",
]
