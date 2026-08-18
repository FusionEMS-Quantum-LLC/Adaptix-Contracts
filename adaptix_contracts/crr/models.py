"""Pydantic v2 models for the Community Risk Reduction (CRR) service (Play P08).

Every top-level model carries ``tenant_id`` and ``correlation_id`` so cross-
service messages remain tenant-scoped and traceable, matching the platform
rule enforced by the shared event envelope
(``adaptix_contracts.events.envelope.AdaptixEventEnvelope``).

Shape convention follows the existing ``fire`` and ``neris`` subpackages:
``from __future__ import annotations``, Pydantic v2 ``BaseModel`` + ``Field``,
enums from the sibling ``enums`` module, and datetimes on UTC-aware boundaries.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from adaptix_contracts.crr.enums import CrrOutcome, InterventionType


class CrrCampaign(BaseModel):
    """A tenant-scoped CRR campaign — the top-level plan-of-work for a risk.

    A campaign groups the target households, scheduled interventions, and the
    outcome cohort measured against it. ``target_risks`` is a free-form list of
    NFPA / Vision 20/20 risk labels (e.g. ``"residential_fire"``,
    ``"cooking_fire"``) rather than an enum, because agencies build campaigns
    around locally-identified risks; forcing an enum would strand
    community-specific programs the model has never seen.
    """

    model_config = ConfigDict(extra="forbid")

    campaign_id: str = Field(..., description="Stable per-tenant campaign identifier")
    tenant_id: str = Field(..., description="Tenant scope — required for every CRR record")
    correlation_id: str = Field(
        ...,
        description=(
            "Correlation ID used to trace this campaign across services (Signal Bus, "
            "audit, analytics). Must match the correlation ID stamped on the "
            "originating request/event."
        ),
    )

    name: str
    description: str | None = None
    target_risks: list[str] = Field(default_factory=list)
    target_intervention_types: list[InterventionType] = Field(default_factory=list)

    start_date: date
    end_date: date | None = None

    status: str = Field(default="planned", description="planned|active|paused|completed|cancelled")
    owner_user_id: str | None = None

    created_at: datetime
    updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TargetHousehold(BaseModel):
    """A household selected as a CRR intervention target.

    The address is captured as a single string plus optional coordinates rather
    than a full USPS-normalised address model because CRR data is often sourced
    from tax rolls, GIS parcels, and door-knock lists whose normalisation
    quality varies wildly across agencies.
    """

    model_config = ConfigDict(extra="forbid")

    household_id: str
    tenant_id: str
    correlation_id: str

    campaign_id: str
    address: str
    unit: str | None = None
    jurisdiction: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    risk_score: float | None = Field(
        default=None,
        description=(
            "Optional tenant-calculated risk score (higher = higher risk). "
            "Scale is tenant-defined; consumers must not assume a fixed range."
        ),
    )
    risk_factors: list[str] = Field(default_factory=list)
    occupant_count: int | None = None
    contact_name: str | None = None
    contact_phone: str | None = None

    identified_at: datetime
    last_contacted_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Intervention(BaseModel):
    """A single CRR intervention event — the delivered unit of prevention work.

    Both ``household_id`` and ``community_group_id`` are optional so the same
    contract can carry a household smoke-alarm install and a classroom fire-
    safety session; at least one of them is expected in practice, but the
    service layer enforces that rule so this contract stays permissive.
    """

    model_config = ConfigDict(extra="forbid")

    intervention_id: str
    tenant_id: str
    correlation_id: str

    campaign_id: str
    intervention_type: InterventionType

    household_id: str | None = None
    community_group_id: str | None = None

    delivered_at: datetime
    delivered_by_user_id: str | None = None
    delivered_by_agency: str | None = None

    materials_distributed: dict[str, int] = Field(
        default_factory=dict,
        description=(
            "Materials handed out by SKU/label, e.g. "
            "``{'smoke_alarm_10yr': 2, 'battery_9v': 4}``."
        ),
    )
    notes: str | None = None

    outcome: CrrOutcome | None = None
    outcome_recorded_at: datetime | None = None

    metadata: dict[str, Any] = Field(default_factory=dict)


class OutcomeCohort(BaseModel):
    """A measured outcome cohort — the population an outcome claim covers.

    Cohorts are the unit of evidence for both internal effectiveness reporting
    and ISO Community Risk Reduction credit packages (see
    ``IsoCreditPackage``).
    """

    model_config = ConfigDict(extra="forbid")

    cohort_id: str
    tenant_id: str
    correlation_id: str

    campaign_id: str
    intervention_type: InterventionType | None = None

    cohort_size: int = Field(..., ge=0)
    baseline_period_start: date
    baseline_period_end: date
    measurement_period_start: date
    measurement_period_end: date

    baseline_incident_count: int | None = Field(default=None, ge=0)
    measured_incident_count: int | None = Field(default=None, ge=0)

    outcome: CrrOutcome
    outcome_value: Decimal | None = Field(
        default=None,
        description=(
            "Optional quantitative outcome measurement — e.g. incident-rate delta "
            "expressed as a Decimal to avoid float rounding in reporting."
        ),
    )
    outcome_notes: str | None = None

    measured_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class IsoCreditPackage(BaseModel):
    """Evidence bundle submitted for ISO Community Risk Reduction credit.

    Wraps the campaign + cohort references and the totals ISO reviewers look
    for. This model is the contract shipped downstream to the ISO integration;
    the actual ISO submission format lives in the CRR service itself.
    """

    model_config = ConfigDict(extra="forbid")

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

    intervention_type_breakdown: dict[InterventionType, int] = Field(
        default_factory=dict,
        description="Count of delivered interventions grouped by ``InterventionType``.",
    )

    outcome_summary: dict[CrrOutcome, int] = Field(
        default_factory=dict,
        description="Cohort count grouped by ``CrrOutcome`` value.",
    )

    narrative: str | None = None
    supporting_artifact_urls: list[str] = Field(default_factory=list)

    generated_at: datetime
    generated_by_service: str = Field(default="crr")
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "CrrCampaign",
    "Intervention",
    "IsoCreditPackage",
    "OutcomeCohort",
    "TargetHousehold",
]
