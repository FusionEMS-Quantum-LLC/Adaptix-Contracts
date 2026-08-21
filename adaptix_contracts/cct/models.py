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


class BloodProduct(BaseModel):
    """A single blood-product unit issued for a CCT mission, tracked end to end.

    Chain-of-custody spans issuing facility through transport to infusion
    (or waste/return). Every custody transition is captured as an ordered
    entry in ``witness_chain`` so a transfusion-safety or CAMTS audit can
    reconstruct exactly who held custody and when.

    Deliberately does NOT carry donor-identifying information. Only the
    platform unit identifier, product type, and the ABO/Rh label needed for
    a bedside compatibility check are modeled here; the issuing blood bank
    remains the system of record for donor traceability and is referenced
    only by ``issuing_blood_bank_unit_id``. Consumers (services, logs,
    audit trails) MUST treat every field on this model as protected data —
    never log raw field values, only ``blood_product_id`` / ``status``.
    """

    model_config = ConfigDict(extra="forbid")

    blood_product_id: str
    tenant_id: str = Field(
        ..., description="Tenant scope — required for every CCT record"
    )
    correlation_id: str = Field(
        ...,
        description=(
            "Correlation ID used to trace this record across services (Signal Bus, "
            "audit, analytics). Must match the correlation ID stamped on the "
            "originating request/event."
        ),
    )

    mission_id: str
    product_type: str = Field(
        ...,
        description=(
            "e.g. 'prbc', 'ffp', 'platelets', 'cryoprecipitate', 'whole_blood'"
        ),
    )
    abo_rh: str | None = Field(
        default=None, description="e.g. 'O_NEG', 'A_POS' — bedside compatibility label."
    )
    issuing_blood_bank_unit_id: str = Field(
        ...,
        description=(
            "The issuing blood bank's own unit identifier. No donor PII is "
            "carried on this contract — donor traceability stays in the "
            "blood bank's system of record."
        ),
    )
    issuing_facility_name: str
    issued_at: datetime | None = None
    expiration_at: datetime | None = None

    status: str = Field(
        default="issued",
        description="issued|in_transit|infused|wasted|returned",
    )

    cold_chain_log: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Ordered cold-chain telemetry/checks, each entry shaped like "
            "{'recorded_at': iso8601, 'temperature_c': float, "
            "'recorded_by_user_id': str}."
        ),
    )
    witness_chain: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Ordered custody/witness attestations, each entry shaped like "
            "{'action': 'issued'|'received'|'infused'|'wasted'|'returned', "
            "'user_id': str, 'witness_user_id': str | None, "
            "'occurred_at': iso8601}."
        ),
    )

    linked_infusion_run_id: str | None = None
    wasted_reason: str | None = None
    returned_reason: str | None = None

    created_at: datetime
    updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class InfusionRun(BaseModel):
    """A single infusion-pump run during a CCT mission.

    Covers vasopressor / inotrope / analgesic / sedation / blood-product
    infusions as the start-to-stop pump record (rate changes, volume to be
    infused, line, pump identity) — distinct from the point-in-time
    snapshot captured on :class:`ExtendedVital`, which only carries the
    currently-active rate at the moment a vital set was recorded.
    """

    model_config = ConfigDict(extra="forbid")

    infusion_run_id: str
    tenant_id: str = Field(
        ..., description="Tenant scope — required for every CCT record"
    )
    correlation_id: str = Field(
        ...,
        description=(
            "Correlation ID used to trace this record across services (Signal Bus, "
            "audit, analytics). Must match the correlation ID stamped on the "
            "originating request/event."
        ),
    )

    mission_id: str
    drug_label: str
    concentration: str | None = Field(default=None, description="e.g. '4mg/250mL'")
    rate_value: float | None = None
    rate_unit: str | None = Field(
        default=None, description="e.g. 'mcg/kg/min', 'mL/hr'"
    )
    vtbi_ml: float | None = Field(
        default=None, description="Volume to be infused, mL"
    )
    line: str | None = Field(
        default=None, description="e.g. 'peripheral_iv_left', 'central_line'"
    )
    pump_identity: str | None = None

    linked_blood_product_id: str | None = None

    started_at: datetime
    stopped_at: datetime | None = None
    rate_changes: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Ordered rate-change log, each entry shaped like "
            "{'changed_at': iso8601, 'new_rate_value': float, "
            "'changed_by_user_id': str}."
        ),
    )

    started_by_user_id: str | None = None
    stopped_by_user_id: str | None = None
    stop_reason: str | None = None

    created_at: datetime
    updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "BloodProduct",
    "CamtsChecklistItem",
    "CctEquipmentLoadout",
    "CctMission",
    "ExtendedVital",
    "InfusionRun",
    "InterfacilityHandoff",
    "ReceivingPhysician",
    "SendingPhysician",
]
