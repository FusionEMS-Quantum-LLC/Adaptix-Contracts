"""Pydantic v2 models for the Critical Care Transport (CCT) service (Play P05).

Every top-level model carries ``tenant_id`` and ``correlation_id`` so
cross-service messages remain tenant-scoped and traceable, matching the
platform rule enforced by the shared event envelope
(``adaptix_contracts.events.envelope.AdaptixEventEnvelope``).

Shape convention follows the existing ``crr`` and ``mih`` subpackages:
``from __future__ import annotations``, Pydantic v2 ``BaseModel`` + ``Field``,
enums from the sibling ``enums`` module, and UTC-aware datetime boundaries.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from adaptix_contracts.cct.enums import CctType, CredentialLevel, VentMode


class CctEquipmentLoadout(BaseModel):
    """The equipment package a CCT mission is confirmed to be carrying.

    Modeled as a free-form ``items`` map (label -> quantity/serial string)
    rather than a fixed equipment enum because CAMTS-accredited programs
    carry program-specific device inventories (make/model of transport
    ventilator, ECMO console, IABP console, infusion pumps) that this
    shared contract should not attempt to standardize.
    """

    model_config = ConfigDict(extra="forbid")

    loadout_id: str
    tenant_id: str = Field(
        ..., description="Tenant scope — required for every CCT record"
    )
    correlation_id: str = Field(
        ...,
        description=(
            "Correlation ID used to trace this loadout across services (Signal Bus, "
            "audit, analytics). Must match the correlation ID stamped on the "
            "originating request/event."
        ),
    )

    mission_id: str
    cct_type: CctType

    items: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Equipment carried, keyed by item label with a free-text value for "
            "quantity/serial/lot, e.g. {'transport_ventilator': 'SN-4471', "
            "'iabp_console': 'SN-2201', 'infusion_pumps': '4'}."
        ),
    )
    ecmo_circuit_verified: bool = Field(
        default=False,
        description="True once an ECMO circuit pre-flight check has been recorded.",
    )
    blood_products_onboard: bool = False
    controlled_substances_manifest_id: str | None = None

    verified_at: datetime | None = None
    verified_by_user_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SendingPhysician(BaseModel):
    """The physician releasing the patient at the sending facility."""

    model_config = ConfigDict(extra="forbid")

    physician_id: str
    tenant_id: str
    correlation_id: str

    name: str
    npi: str | None = None
    facility_name: str
    facility_id: str | None = None
    phone: str | None = None
    report_given_at: datetime | None = None
    report_notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReceivingPhysician(BaseModel):
    """The physician accepting the patient at the receiving facility."""

    model_config = ConfigDict(extra="forbid")

    physician_id: str
    tenant_id: str
    correlation_id: str

    name: str
    npi: str | None = None
    facility_name: str
    facility_id: str | None = None
    phone: str | None = None
    accepted_at: datetime | None = None
    accepting_service: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtendedVital(BaseModel):
    """A single extended-critical-care vital-sign reading captured in transit.

    Extends beyond a standard ePCR vital set (which lives in the ePCR
    domain) with the ventilator/hemodynamic parameters a CCT crew must
    trend continuously. This model is intentionally a point-in-time
    reading rather than a rolling trend so the CCT service can persist
    a full time series.
    """

    model_config = ConfigDict(extra="forbid")

    vital_id: str
    tenant_id: str
    correlation_id: str

    mission_id: str
    recorded_at: datetime

    heart_rate: int | None = None
    systolic_bp: int | None = None
    diastolic_bp: int | None = None
    map_mmhg: float | None = Field(
        default=None, description="Mean arterial pressure (mmHg)"
    )
    spo2_pct: float | None = Field(default=None, ge=0, le=100)
    etco2_mmhg: float | None = None
    respiratory_rate: int | None = None

    vent_mode: VentMode | None = None
    vent_rate: int | None = None
    tidal_volume_ml: float | None = None
    peep_cmh2o: float | None = None
    fio2_pct: float | None = Field(default=None, ge=0, le=100)

    iabp_ratio: str | None = Field(
        default=None, description="IABP augmentation ratio, e.g. '1:1', '1:2'"
    )
    ecmo_flow_lpm: float | None = None
    ecmo_sweep_lpm: float | None = None

    vasopressor_infusions: dict[str, float] = Field(
        default_factory=dict,
        description="Active vasopressor/inotrope infusions keyed by drug label to rate.",
    )
    temperature_c: float | None = None
    glasgow_coma_score: int | None = Field(default=None, ge=3, le=15)

    notes: str | None = None
    recorded_by_user_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CamtsChecklistItem(BaseModel):
    """A single CAMTS accreditation checklist item recorded against a mission.

    CCT services must be able to reconstruct a CAMTS survey-ready audit
    trail per mission; each item is one standard/question with a pass/fail
    style outcome plus free-text evidence.
    """

    model_config = ConfigDict(extra="forbid")

    checklist_item_id: str
    tenant_id: str
    correlation_id: str

    mission_id: str
    standard_reference: str = Field(
        ..., description="CAMTS standard/section reference this item verifies."
    )
    description: str
    is_satisfied: bool | None = Field(
        default=None,
        description="None = not yet evaluated; True/False = evaluated outcome.",
    )
    evidence_notes: str | None = None

    evaluated_at: datetime | None = None
    evaluated_by_user_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class InterfacilityHandoff(BaseModel):
    """The sending/receiving handoff record for a CCT interfacility transport.

    Bundles both physician contacts and the report-given/accepted
    timestamps CAMTS auditors and receiving facilities expect to see
    reconciled against the mission's dispatch/arrival timestamps.
    """

    model_config = ConfigDict(extra="forbid")

    handoff_id: str
    tenant_id: str
    correlation_id: str

    mission_id: str
    sending_physician: SendingPhysician
    receiving_physician: ReceivingPhysician

    sending_facility_report_at: datetime | None = None
    receiving_facility_accepted_at: datetime | None = None
    patient_condition_at_handoff: str | None = None
    equipment_returned: bool = False
    handoff_notes: str | None = None

    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CctMission(BaseModel):
    """A tenant-scoped Critical Care Transport mission — the top-level record.

    ``cct_type`` drives the minimum ``required_credential_level`` and the
    equipment package expected on ``CctEquipmentLoadout``; the service
    layer enforces the actual staffing/equipment match, this contract just
    carries the declared requirement and the assigned crew's credentials.
    """

    model_config = ConfigDict(extra="forbid")

    mission_id: str = Field(..., description="Stable per-tenant CCT mission identifier")
    tenant_id: str = Field(
        ..., description="Tenant scope — required for every CCT record"
    )
    correlation_id: str = Field(
        ...,
        description=(
            "Correlation ID used to trace this mission across services (Signal Bus, "
            "audit, analytics). Must match the correlation ID stamped on the "
            "originating request/event."
        ),
    )

    cct_type: CctType
    required_credential_level: CredentialLevel
    patient_id: str | None = None

    sending_facility_name: str
    sending_facility_id: str | None = None
    receiving_facility_name: str
    receiving_facility_id: str | None = None

    assigned_crew_user_ids: list[str] = Field(default_factory=list)
    assigned_crew_credential_levels: dict[str, CredentialLevel] = Field(
        default_factory=dict,
        description="Crew user_id -> credential level held, for eligibility checks.",
    )

    loadout_id: str | None = None
    handoff_id: str | None = None

    status: str = Field(
        default="requested",
        description="requested|accepted|en_route_to_sending|at_sending|en_route_to_receiving|at_receiving|completed|cancelled",
    )

    linked_epcr_chart_id: str | None = None
    linked_cad_incident_id: str | None = None

    requested_at: datetime
    dispatched_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancellation_reason: str | None = None

    camts_reportable: bool = Field(
        default=True,
        description="Whether this mission falls under the program's CAMTS reporting scope.",
    )

    created_at: datetime
    updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "CamtsChecklistItem",
    "CctEquipmentLoadout",
    "CctMission",
    "ExtendedVital",
    "InterfacilityHandoff",
    "ReceivingPhysician",
    "SendingPhysician",
]
