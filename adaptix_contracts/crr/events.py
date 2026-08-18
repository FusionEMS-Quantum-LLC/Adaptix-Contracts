"""Signal Bus event contracts for the Community Risk Reduction service.

Event names follow the platform ``<domain>.<entity>.<action>`` convention used
in ``adaptix_contracts.fire.events`` and ``adaptix_contracts.neris.events``.
Every wire payload is carried on the canonical envelope defined by
``adaptix_contracts.events.envelope.AdaptixEventEnvelope`` — the typed payload
models below describe the ``payload`` field of that envelope, not a replacement
for it.

The event-name string constants are exported so consumers can subscribe by
canonical name without hand-copying strings; the aggregate ``CRR_EVENTS`` set
matches the shape ``FIRE_EVENTS`` publishes for the Fire domain.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from adaptix_contracts.crr.enums import CrrOutcome, InterventionType

# ---------------------------------------------------------------------------
# Event-name string constants (subscribe by these on the Signal Bus)
# ---------------------------------------------------------------------------

CRR_CAMPAIGN_LAUNCHED: str = "crr.campaign.launched"
CRR_INTERVENTION_COMPLETED: str = "crr.intervention.completed"
CRR_OUTCOME_MEASURED: str = "crr.outcome.measured"
ISO_PACKAGE_GENERATED: str = "iso.package.generated"

CRR_EVENTS: frozenset[str] = frozenset(
    {
        CRR_CAMPAIGN_LAUNCHED,
        CRR_INTERVENTION_COMPLETED,
        CRR_OUTCOME_MEASURED,
        ISO_PACKAGE_GENERATED,
    }
)


# ---------------------------------------------------------------------------
# Typed payload contracts
# ---------------------------------------------------------------------------
#
# Each model below describes the JSON object placed in
# ``AdaptixEventEnvelope.payload`` for the matching event type. The
# ``event_type`` literal on each model matches the string constant above so a
# consumer can dispatch on payload identity as well as envelope identity —
# same pattern the Fire domain uses in
# ``adaptix_contracts.schemas.fire_contracts``.


class CrrCampaignLaunchedEvent(BaseModel):
    """Published when a CRR campaign transitions from ``planned`` to ``active``."""

    model_config = ConfigDict(extra="forbid")

    event_type: str = Field(default=CRR_CAMPAIGN_LAUNCHED, frozen=True)
    campaign_id: str
    tenant_id: str
    correlation_id: str

    name: str
    target_risks: list[str] = Field(default_factory=list)
    target_intervention_types: list[InterventionType] = Field(default_factory=list)
    start_date: date
    end_date: date | None = None
    launched_at: datetime
    launched_by_user_id: str | None = None


class CrrInterventionCompletedEvent(BaseModel):
    """Published when a single CRR intervention is delivered and recorded."""

    model_config = ConfigDict(extra="forbid")

    event_type: str = Field(default=CRR_INTERVENTION_COMPLETED, frozen=True)
    intervention_id: str
    tenant_id: str
    correlation_id: str

    campaign_id: str
    intervention_type: InterventionType
    household_id: str | None = None
    community_group_id: str | None = None

    delivered_at: datetime
    delivered_by_user_id: str | None = None
    materials_distributed: dict[str, int] = Field(default_factory=dict)


class CrrOutcomeMeasuredEvent(BaseModel):
    """Published when an outcome cohort is measured against its baseline."""

    model_config = ConfigDict(extra="forbid")

    event_type: str = Field(default=CRR_OUTCOME_MEASURED, frozen=True)
    cohort_id: str
    tenant_id: str
    correlation_id: str

    campaign_id: str
    intervention_type: InterventionType | None = None

    cohort_size: int = Field(..., ge=0)
    baseline_incident_count: int | None = Field(default=None, ge=0)
    measured_incident_count: int | None = Field(default=None, ge=0)

    outcome: CrrOutcome
    measured_at: datetime


class IsoPackageGeneratedEvent(BaseModel):
    """Published when an ISO Community Risk Reduction credit package is generated."""

    model_config = ConfigDict(extra="forbid")

    event_type: str = Field(default=ISO_PACKAGE_GENERATED, frozen=True)
    package_id: str
    tenant_id: str
    correlation_id: str

    campaign_ids: list[str] = Field(default_factory=list)
    cohort_ids: list[str] = Field(default_factory=list)
    reporting_period_start: date
    reporting_period_end: date

    total_interventions: int = Field(..., ge=0)
    total_households_reached: int = Field(..., ge=0)
    total_community_events: int = Field(default=0, ge=0)
    outcome_summary: dict[CrrOutcome, int] = Field(default_factory=dict)

    generated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "CRR_CAMPAIGN_LAUNCHED",
    "CRR_EVENTS",
    "CRR_INTERVENTION_COMPLETED",
    "CRR_OUTCOME_MEASURED",
    "CrrCampaignLaunchedEvent",
    "CrrInterventionCompletedEvent",
    "CrrOutcomeMeasuredEvent",
    "ISO_PACKAGE_GENERATED",
    "IsoPackageGeneratedEvent",
]
