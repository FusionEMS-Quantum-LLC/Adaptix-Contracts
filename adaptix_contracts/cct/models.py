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

from adaptix_contracts.cct.enums import (
    AboGroup,
    BloodProductStatus,
    BloodProductType,
    CctType,
    CredentialLevel,
    InfusionRunStatus,
    RhFactor,
    VentMode,
)


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


class ColdChainReading(BaseModel):
    """A single temperature reading in a blood-product cold-chain log.

    Blood products have narrow acceptable-temperature windows during
    transport (RBC 1–6 °C, platelets 20–24 °C, FFP frozen ≤ -18 °C). A
    sequence of these readings, timestamped, is what makes a unit
    transfusable at the receiving facility.
    """

    model_config = ConfigDict(extra="forbid")

    recorded_at: datetime
    temperature_c: float = Field(
        ..., description="Storage-container temperature at reading (Celsius)."
    )
    reader_device_id: str | None = Field(
        default=None,
        description="Telemetry device / cooler probe identifier, if applicable.",
    )
    recorded_by_user_id: str | None = None
    within_tolerance: bool = Field(
        default=True,
        description=(
            "Whether this reading is within the product's acceptable temperature "
            "window. Service layer classifies against the product's storage spec; "
            "this field carries the classified outcome for downstream consumers."
        ),
    )
    notes: str | None = None


class CustodyEvent(BaseModel):
    """One transfer of custody for a blood-product unit.

    Two named parties per event: the party releasing custody (``from_party``)
    and the party accepting it (``to_party``). Both are typically clinicians
    with a printed name + signature timestamp; a witness is required per
    AABB standards on issuance and on infusion.
    """

    model_config = ConfigDict(extra="forbid")

    recorded_at: datetime
    from_party_user_id: str | None = None
    from_party_name: str = Field(
        ...,
        description=(
            "Free-text printed name of the releasing party (e.g. blood-bank "
            "technologist at the sending facility)."
        ),
    )
    to_party_user_id: str | None = None
    to_party_name: str = Field(
        ..., description="Printed name of the accepting party (typically the CCT crew)."
    )
    witness_user_id: str | None = None
    witness_name: str | None = Field(
        default=None,
        description=(
            "Printed name of a second clinician who verified the transfer. "
            "AABB standards require a two-person witness at issue and infusion."
        ),
    )
    from_location: str | None = Field(
        default=None,
        description="Physical location of the releasing party (e.g. 'Regional Med Ctr Blood Bank').",
    )
    to_location: str | None = Field(
        default=None,
        description="Physical location of the accepting party (e.g. 'CCT Unit N4271').",
    )
    notes: str | None = None


class BloodProduct(BaseModel):
    """A single unit of blood/blood product carried on a CCT mission.

    The unit's chain of custody is reconstructed from ``custody_events``
    (each successful sign-over) and the temperature record is
    reconstructed from ``cold_chain_log`` (each recorded temperature).
    Both are append-only from the service's perspective — no update path
    rewrites prior entries, so the audit history remains defensible for
    AABB / blood-bank auditors and for the receiving facility.
    """

    model_config = ConfigDict(extra="forbid")

    blood_product_id: str = Field(
        ..., description="Internal CCT record id for this carried unit."
    )
    tenant_id: str
    correlation_id: str

    mission_id: str
    patient_id: str | None = Field(
        default=None,
        description=(
            "Patient the unit is intended for. Null while a unit is still "
            "unmatched / general-stock on the truck."
        ),
    )

    unit_id: str = Field(
        ...,
        description=(
            "Sending blood bank's Unit ID / DIN (Donation Identification "
            "Number) — the primary human-readable identifier on the label."
        ),
    )
    isbt128_code: str | None = Field(
        default=None,
        description="Full ISBT 128 identifier if the sending facility issues one.",
    )
    product_code: str | None = Field(
        default=None,
        description=(
            "Specific product code from the sending blood bank (e.g. AABB "
            "'E0139', 'E0141'). Kept alongside ``product_type`` because the "
            "type is the broad category and the code is the specific SKU."
        ),
    )
    product_type: BloodProductType

    abo_group: AboGroup
    rh_factor: RhFactor

    volume_ml: float | None = Field(
        default=None, ge=0, description="Nominal volume of the unit (mL)."
    )
    collected_at: datetime | None = Field(
        default=None, description="When the unit was collected from the donor."
    )
    expires_at: datetime = Field(
        ...,
        description=(
            "Expiration timestamp printed on the label. Required — a unit "
            "with no expiration cannot legitimately be transported."
        ),
    )

    issuing_facility_name: str = Field(
        ..., description="Sending / issuing blood bank / hospital name."
    )
    issuing_facility_id: str | None = None
    issued_at: datetime = Field(..., description="When the unit was issued to CCT.")

    status: BloodProductStatus = Field(
        default=BloodProductStatus.ISSUED,
        description="Current chain-of-custody status of this unit.",
    )
    infused_at: datetime | None = Field(
        default=None,
        description="Set when status transitions to INFUSED.",
    )
    returned_to_facility_name: str | None = Field(
        default=None,
        description="Facility a returned/wasted unit was handed back to.",
    )
    waste_reason: str | None = Field(
        default=None,
        description=(
            "Required when status is WASTED — free-text reason (e.g. "
            "'cold-chain breach 2026-08-21T05:12Z', 'discoloration on "
            "inspection at arrival')."
        ),
    )

    cold_chain_log: list[ColdChainReading] = Field(
        default_factory=list,
        description="Append-only temperature history for this unit.",
    )
    custody_events: list[CustodyEvent] = Field(
        default_factory=list,
        description=(
            "Append-only chain of custody transfers. Consumers should not "
            "assume ordering beyond ``recorded_at``."
        ),
    )

    created_at: datetime
    updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class InfusionRun(BaseModel):
    """A single medication infusion running on a CCT patient during transport.

    Captures the pump's programmed parameters at the moment the infusion
    was started or a rate change was made. The service persists a new
    ``InfusionRun`` row on start and on each rate/concentration change so
    the mission record preserves a defensible timeline rather than
    mutating the running values in place.
    """

    model_config = ConfigDict(extra="forbid")

    infusion_run_id: str
    tenant_id: str
    correlation_id: str

    mission_id: str
    patient_id: str | None = None

    drug_name: str = Field(
        ..., description="Human-readable drug name (e.g. 'Norepinephrine')."
    )
    rxnorm_code: str | None = Field(
        default=None,
        description=(
            "RxNorm RXCUI for the drug/formulation, when known. Kept "
            "optional because in-transit drugs are frequently drawn from "
            "the sending facility's pharmacy and the RxNorm mapping is "
            "resolved during ePCR closeout, not at start-of-infusion."
        ),
    )

    concentration_amount: float = Field(
        ..., gt=0, description="Numerator of the concentration (e.g. 4 for 4 mg / 250 mL)."
    )
    concentration_amount_unit: str = Field(
        ...,
        description="Unit for ``concentration_amount`` (e.g. 'mg', 'mcg', 'units').",
    )
    concentration_volume_ml: float = Field(
        ..., gt=0, description="Denominator of the concentration in mL (e.g. 250)."
    )
    diluent: str | None = Field(
        default=None, description="Diluent (e.g. '0.9% NaCl', 'D5W')."
    )

    rate_amount: float = Field(
        ...,
        ge=0,
        description=(
            "Programmed rate at the pump (e.g. 5). ``rate_amount_unit`` "
            "carries the units."
        ),
    )
    rate_amount_unit: str = Field(
        ...,
        description=(
            "Rate unit as programmed on the pump. Examples: 'mcg/kg/min', "
            "'units/hr', 'mL/hr'. Kept as a string because CCT-relevant "
            "vasoactive infusions span weight-normalized and non-weight-"
            "normalized rates and a fixed enum would drop pump-programmed "
            "units the crew must be able to reproduce."
        ),
    )
    volume_to_be_infused_ml: float | None = Field(
        default=None,
        ge=0,
        description=(
            "Pump VTBI setting in mL, when the pump is programmed with a "
            "volume ceiling (bolus, transfusion, limited-run infusion)."
        ),
    )
    dose_weight_kg: float | None = Field(
        default=None,
        gt=0,
        description=(
            "Dosing weight programmed into the pump for weight-normalized "
            "rates. May differ from patient's actual weight if a rounded "
            "or dry weight is used."
        ),
    )

    line_label: str | None = Field(
        default=None,
        description=(
            "Free-text vascular access label used at the bedside (e.g. "
            "'Right IJ Central Line - Lumen 1', 'Left AC 20g PIV')."
        ),
    )
    pump_channel: str | None = Field(
        default=None,
        description="Pump channel identifier (e.g. 'A', 'B', 'Channel 3').",
    )
    pump_device_id: str | None = Field(
        default=None,
        description="Serial or asset ID of the physical pump running this infusion.",
    )

    status: InfusionRunStatus = InfusionRunStatus.RUNNING
    started_at: datetime
    stopped_at: datetime | None = None
    stop_reason: str | None = None

    ordered_by_user_id: str | None = None
    programmed_by_user_id: str | None = Field(
        default=None,
        description="User who programmed the pump for this run/rate change.",
    )
    witness_user_id: str | None = Field(
        default=None,
        description=(
            "Second clinician who verified programming for high-alert "
            "infusions (vasopressors, insulin, heparin, blood products, "
            "chemotherapy)."
        ),
    )

    notes: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
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
    "BloodProduct",
    "CamtsChecklistItem",
    "CctEquipmentLoadout",
    "CctMission",
    "ColdChainReading",
    "CustodyEvent",
    "ExtendedVital",
    "InfusionRun",
    "InterfacilityHandoff",
    "ReceivingPhysician",
    "SendingPhysician",
]
