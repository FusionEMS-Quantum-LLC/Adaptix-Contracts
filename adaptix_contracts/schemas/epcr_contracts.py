"""ePCR domain contract schemas for cross-domain communication."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EpcrChartCreatedEvent(BaseModel):
    """Published when an ePCR chart is created."""

    event_type: str = "epcr.chart.created"

    chart_id: str
    tenant_id: str
    call_number: str
    incident_type: str

    created_at: datetime


class EpcrChartAmendedEvent(BaseModel):
    """Published when a FINALIZED ePCR chart is amended.

    The producer is
    ``Adaptix-EPCR-Service/backend/epcr_app/chart_amendment_service.py``
    (``ChartEventOutbox`` row, event type ``epcr.chart.amended``), relayed by
    ``epcr_app/outbox_worker.py``. ``tenant_id`` is REQUIRED: the relay's
    generic publish path refuses tenant-less events, so a payload without it
    can never reach the bus at all — the field being mandatory here keeps the
    producer honest at validation time instead of at relay time.

    The intended consumer is Billing: a clinical amendment landing AFTER the
    chart was handed to billing must become visible against the claim that
    was built from the pre-amendment chart, never silently diverge from it.

    ``field`` is the chart attribute that was amended (e.g. ``"narrative"``);
    ``amendment_id`` is the append-only ``ChartAmendment`` row id so the
    consumer can fetch the full before/after detail through the authorized
    ePCR read path if it needs more than the notification.
    """

    event_type: str = "epcr.chart.amended"

    amendment_id: str
    chart_id: str
    tenant_id: str
    field: str

    actor_id: Optional[str] = None
    amended_at: Optional[datetime] = None


class EpcrChartFinalizedEvent(BaseModel):
    """Published when an ePCR chart is finalized.

    The authoritative producer is
    ``Adaptix-EPCR-Service/backend/epcr_app/chart_finalization_service.py:260``
    (origin/main, verified 2026-08-09), which writes a ``ChartEventOutbox`` row
    whose payload carries exactly::

        chart_id, tenant_id, call_number, finalized_at, billing_case_id,
        record_mode

    The row is republished onto the shared envelope by
    ``epcr_app/outbox_worker.py:78`` -> ``EpcrEventPublisher.publish_chart_finalized``.
    The sole consumer is
    ``Adaptix-Billing-Service/backend/billing_app/event_consumers.py:69``, which
    calls ``EpcrChartFinalizedEvent.model_validate(payload)`` before creating the
    claim-intake row, the patient financial account and the draft claim.

    Fields absent from that payload MUST therefore be optional. Requiring one
    makes every real finalization raise ``ValidationError`` inside the
    consumer's ``except`` block, which logs and returns ``False`` — so the chart
    finalizes, the crew sees success, and no billing record is ever created.
    """

    event_type: str = "epcr.chart.finalized"

    chart_id: str
    tenant_id: str
    call_number: str

    finalized_at: datetime

    # NEMSIS compliance as stated BY THE PRODUCER. ``None`` means the producer
    # did not report it — which is the live case: ``is_nemsis_compliant``
    # appears nowhere in Adaptix-EPCR-Service at origin/main, and the
    # finalization payload above does not carry it. This field was declared
    # required, so every production ``epcr.chart.finalized`` event failed
    # validation in the Billing consumer. (The same ValidationError is recorded
    # verbatim in the archived Phase 11 run,
    # ``Adaptix-Core-Service/PHASE_11_VALIDATION_RESULTS.json``.)
    #
    # It is deliberately tri-state rather than defaulting to a bool: absent is
    # NOT evidence of compliance, and it is not evidence of non-compliance
    # either. A consumer that gates on compliance must treat ``None`` as
    # "unknown — do not assume compliant" and obtain the status from the
    # authoritative compliance contract (``EpcrNemsissComplianceContract``)
    # rather than inferring it from this event.
    is_nemsis_compliant: Optional[bool] = None

    missing_fields: list[str] = Field(default_factory=list)

    # Test-record isolation. True for a non-production ePCR (e.g. a Founder
    # WARDS Lab record), which must never enter billing, patient-identity
    # matching, production NEMSIS/WARDS submission, notifications, or
    # analytics. EPCR is the authoritative chokepoint and does not emit this
    # event for test charts at all; the flag exists so every consumer can
    # additionally defend itself instead of trusting upstream filtering.
    #
    # Defaults to False so existing producers and persisted events remain
    # valid, and so an omitted value fails CLOSED toward production semantics
    # (a real encounter is never silently dropped from billing).
    is_test: bool = False

    # Claim-ready fact snapshot the producer collects at finalize time
    # (Adaptix-EPCR-Service ``ChartBillingReadinessExport``). OPTIONAL and
    # fully back-compatible: absent on legacy/persisted events, in which case
    # the Billing consumer falls back to its prior placeholder behaviour and
    # can call back for detail. When present it lets Billing mint a claim with
    # real demographics, primary impression + codes, transport reason, level
    # of service and attending crew instead of ``patient_name = call_number``.
    # Every field is optional — a finalized chart is a clinical/legal act and
    # must never be blocked by an incomplete billing fact set.
    billing_snapshot: Optional["EpcrBillingSnapshot"] = None


class EpcrNemsisSubmitSucceededEvent(BaseModel):  # pylint: disable=too-few-public-methods
    """Published when EPCR successfully submits a chart to NEMSIS.

    The authoritative producer is
    ``Adaptix-EPCR-Service/backend/epcr_app/chart_finalization_service.py``,
    whose success path writes an outbox payload carrying exactly::

        chart_id, tenant_id, state_code, submission_id,
        transmission_status, attempted_at

    Consumers that want typed dispatch for NEMSIS submission success must
    validate against that producer-owned shape instead of string-matching the
    event type alone.
    """

    event_type: str = "epcr.nemsis_submit.succeeded"

    chart_id: str
    tenant_id: str
    state_code: str
    submission_id: str
    transmission_status: str
    attempted_at: datetime


class EpcrBillingPatientDemographics(BaseModel):
    """Demographic block carried on the finalized event for billing."""

    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    age_years: Optional[int] = None
    sex: Optional[str] = None
    weight_kg: Optional[float] = None


class EpcrBillingCrewMember(BaseModel):
    """One attending crew member carried on the finalized event."""

    crew_member_id: str
    level_code: Optional[str] = None
    response_role_code: Optional[str] = None
    sequence_index: int = 0


class EpcrBillingTransportBlock(BaseModel):
    """Transport facts carried on the finalized event for billing.

    Mirrors EPCR's ``TransportBillingBlock`` (``chart_billing_readiness_export.py``),
    which the producer has ALWAYS serialized under the snapshot's ``"transport"``
    key — this model closes the gap where typed validation silently dropped it.
    Without these facts a ground transport claim cannot be priced or
    modifier-coded (origin/destination point-of-service modifiers, loaded miles).

    Values are the raw NEMSIS element strings exactly as documented by the crew
    (``origin_* <- eScene.21/.15/.11/.12``, ``destination_* <- eDisposition.02/.03``,
    ``transport_distance_miles <- eDisposition.17``, ``service_type_code <-
    eResponse.05``, ``unit_role_code <- eResponse.07``). The producer performs no
    parsing or unit coercion — ``transport_distance_miles`` is a string, not a
    number, and consumers must treat an unparseable value as absent, never guess.

    The block carried only flat street strings, so a consumer could not populate
    the point-of-pickup ZIP that CMS requires on every ambulance claim (CMS-1500
    Item 23; 837P loop 2310E ``N4``) nor the drop-off address in loop 2310F - it
    had to parse or geocode ``origin_address`` / ``destination_address``. The
    city/state/ZIP components are therefore carried explicitly, again as raw
    NEMSIS strings the producer does not parse:

    * ``origin_city`` <- eScene.17 Incident City
    * ``origin_state`` <- eScene.18 Incident State
    * ``origin_zip`` <- eScene.19 Incident ZIP Code
    * ``destination_city`` <- eDisposition.04 Destination City
    * ``destination_state`` <- eDisposition.05 Destination State
    * ``destination_zip`` <- eDisposition.07 Destination ZIP Code

    Element numbers verified against the NEMSIS 3.5 data dictionary
    (``Combined_ElementDetails.txt``): the city elements carry a
    ``CityGnisCode``, the state elements an ``ANSIStateCode`` (2 digits) - so
    neither is guaranteed to be a display name - and ZIP matches ``NNNNN``,
    ``NNNNN-NNNN`` or a Canadian postal code. Consumers must treat an
    unparseable or absent value as absent and must never geocode a substitute.
    """

    origin_name: Optional[str] = None
    origin_address: Optional[str] = None
    origin_latitude: Optional[str] = None
    origin_longitude: Optional[str] = None
    origin_city: Optional[str] = None  # eScene.17
    origin_state: Optional[str] = None  # eScene.18
    origin_zip: Optional[str] = None  # eScene.19
    destination_name: Optional[str] = None
    destination_address: Optional[str] = None
    destination_city: Optional[str] = None  # eDisposition.04
    destination_state: Optional[str] = None  # eDisposition.05
    destination_zip: Optional[str] = None  # eDisposition.07
    transport_distance_miles: Optional[str] = None
    service_type_code: Optional[str] = None
    unit_role_code: Optional[str] = None


class EpcrBillingInsuranceBlock(BaseModel):
    """Payer/subscriber facts carried on the finalized event for billing.

    Mirrors the NEMSIS ePayment insurance block persisted in EPCR's
    ``epcr_chart_payment`` (``ePayment.09–.22`` and ``.57–.60``). All values are
    the raw stored strings/codes; dates are ISO-8601 date strings. Absence of
    the whole block or any field means the crew did not document it — it is
    NOT evidence the patient is uninsured, and consumers must not treat it as
    verified coverage (verification belongs to the eligibility workflow).
    """

    insurance_company_id: Optional[str] = None  # ePayment.09
    insurance_company_name: Optional[str] = None  # ePayment.10
    insurance_billing_priority_code: Optional[str] = None  # ePayment.11
    insurance_company_address: Optional[str] = None  # ePayment.12
    insurance_company_city: Optional[str] = None  # ePayment.13
    insurance_company_state: Optional[str] = None  # ePayment.14
    insurance_company_zip: Optional[str] = None  # ePayment.15
    insurance_group_id: Optional[str] = None  # ePayment.17
    insurance_policy_id_number: Optional[str] = None  # ePayment.18
    insured_last_name: Optional[str] = None  # ePayment.19
    insured_first_name: Optional[str] = None  # ePayment.20
    insured_middle_name: Optional[str] = None  # ePayment.21
    relationship_to_insured_code: Optional[str] = None  # ePayment.22
    payer_type_code: Optional[str] = None  # ePayment.57
    insurance_group_name: Optional[str] = None  # ePayment.58
    insurance_company_phone: Optional[str] = None  # ePayment.59
    insured_date_of_birth: Optional[str] = None  # ePayment.60, ISO date string


class EpcrBillingCertificationBlock(BaseModel):
    """PCS / medical-necessity / authorization facts for billing.

    Mirrors the ambulance-specific NEMSIS ePayment elements persisted in
    EPCR's ``epcr_chart_payment``. These gate non-emergency claim submission
    (Physician Certification Statement, 42 CFR 410.40(e)) and carry the
    condition/indicator codes and prior-authorization identifiers a clean
    837P needs. Raw stored codes only — no inference, no invented values.
    """

    physician_certification_statement_code: Optional[str] = None  # ePayment.02
    pcs_signed_date: Optional[str] = None  # ePayment.03, ISO date string
    reason_for_pcs_codes: Optional[list[str]] = None  # ePayment.04 (1:M)
    pcs_provider_type_code: Optional[str] = None  # ePayment.05
    pcs_last_name: Optional[str] = None  # ePayment.06
    pcs_first_name: Optional[str] = None  # ePayment.07
    ambulance_transport_reason_code: Optional[str] = None  # ePayment.44
    ambulance_conditions_indicator_codes: Optional[list[str]] = None  # ePayment.47
    mileage_to_closest_hospital: Optional[float] = None  # ePayment.48
    cms_service_level_code: Optional[str] = None  # ePayment.50
    ems_condition_codes: Optional[list[str]] = None  # ePayment.51
    cms_transportation_indicator_codes: Optional[list[str]] = None  # ePayment.52
    transport_authorization_code: Optional[str] = None  # ePayment.53
    prior_authorization_code_payer: Optional[str] = None  # ePayment.54


class EpcrBillingProcedureItem(BaseModel):  # pylint: disable=too-few-public-methods
    """One performed-procedure fact carried on the finalized event.

    Mirrors a single structured ``Procedure`` row from EPCR's chart truth
    model at finalize time. ``code_system`` names the coding scheme the code
    was drawn from (e.g. ``"SNOMED"``) — required context because a bare code
    string is ambiguous across NEMSIS procedure-code sources. ``performed_count``
    and ``successful_count`` are raw counts as documented by the crew; a
    ``None`` ``successful_count`` means the crew did not separately record
    success/failure, not that the procedure failed.
    """

    procedure_code: str
    code_system: Optional[str] = None  # e.g. "SNOMED"
    performed_count: int = 1
    successful_count: Optional[int] = None


class EpcrBillingMedicationAdministrationItem(BaseModel):  # pylint: disable=too-few-public-methods
    """One medication-administration fact carried on the finalized event.

    Mirrors a single structured ``MedicationAdministration`` row from EPCR's
    chart truth model at finalize time. ``code_system`` names the coding
    scheme (e.g. ``"RxNorm"``). ``route_code`` is the NEMSIS eMedications.10
    route-of-administration code, carried raw and unparsed — it is what lets
    the Billing consumer distinguish an IV-push administration from a
    continuous infusion, which is the fact CMS ALS2 level-of-service
    determination turns on. ``administration_count`` is the raw count as
    documented by the crew.
    """

    medication_code: str
    code_system: Optional[str] = None  # e.g. "RxNorm"
    route_code: Optional[str] = None  # NEMSIS eMedications.10
    administration_count: int = 1


class EpcrBillingInterventionsBlock(BaseModel):  # pylint: disable=too-few-public-methods
    """Performed-intervention facts carried on the finalized event for billing.

    ``procedures`` and ``medication_administrations`` are RAW chart facts
    derived directly from EPCR's structured ``Procedure`` and
    ``MedicationAdministration`` rows at finalize time — NEVER parsed or
    inferred from narrative text. This block exists so Billing's ALS2/SCT
    undercoding detection can apply CMS level-of-service policy
    deterministically against real performed-intervention counts and route
    codes, instead of inferring level of service from ``level_of_service_code``
    alone. CMS ALS2/SCT policy determination is the Billing consumer's
    responsibility; this block supplies only the underlying facts.

    Absence of the whole block, or of either list, means the producer
    predates this block (or the chart carried no structured rows to export)
    — it is NOT evidence that no interventions were performed, and a consumer
    must not treat it as "zero interventions occurred."
    """

    procedures: list[EpcrBillingProcedureItem] = Field(default_factory=list)
    medication_administrations: list[EpcrBillingMedicationAdministrationItem] = Field(
        default_factory=list
    )
    procedure_total: Optional[int] = None
    medication_administration_total: Optional[int] = None


class EpcrBillingSnapshot(BaseModel):
    """Claim-ready fact set mirrored from EPCR's ChartBillingReadinessExport.

    The producer's ``BillingReadinessSnapshot.to_dict()`` is the source of
    truth for the shape. Every field is optional so a partial chart still
    produces a valid event; ``missing_fields`` and ``ready_for_billing`` let
    the consumer decide whether to open a claim or hold for documentation.
    """

    chart_status: Optional[str] = None
    primary_impression: Optional[str] = None
    primary_impression_icd10: Optional[str] = None
    primary_impression_snomed: Optional[str] = None
    transport_reason: Optional[str] = None
    transport_reason_source: Optional[str] = None
    level_of_service_code: Optional[str] = None
    level_of_service_label: Optional[str] = None
    patient_demographics: Optional[EpcrBillingPatientDemographics] = None
    attending_crew: list[EpcrBillingCrewMember] = Field(default_factory=list)
    # Transport facts the producer has always emitted under "transport"; typed
    # here (2.8.0) so validation stops discarding them. See the block docstring.
    transport: Optional[EpcrBillingTransportBlock] = None
    # ePayment insurance + PCS/authorization blocks, emitted by EPCR from
    # 2.8.0-aligned producers. Absent on older events — consumers fall back to
    # their prior behaviour.
    insurance: Optional[EpcrBillingInsuranceBlock] = None
    certification: Optional[EpcrBillingCertificationBlock] = None
    # Structured performed-procedure and medication-administration facts
    # (5.7.0) so Billing's ALS2/SCT undercoding detection can apply CMS
    # level-of-service policy deterministically. Absent on older events —
    # consumers fall back to their prior behaviour. See the block docstring.
    performed_interventions: Optional[EpcrBillingInterventionsBlock] = None
    missing_fields: list[str] = Field(default_factory=list)
    ready_for_billing: bool = False


class EpcrChartHospitalHandoffEvent(BaseModel):  # pylint: disable=too-few-public-methods
    """Published when ePCR emits a typed hospital handoff event.

    This contract captures the chart-to-hospital linkage and transfer-of-care
    facts shared across EPCR and hospital-facing consumers. ``tenant_id`` is
    REQUIRED so the generic EPCR outbox relay can publish it on the shared bus
    without failing closed on a tenant-less row.
    """

    event_type: str = "epcr.chart.hospital_handoff"

    chart_id: str
    tenant_id: str
    handoff_id: str
    call_number: str
    hospital_id: str
    handoff_status: str
    created_at: datetime

    hospital_name: Optional[str] = None
    incident_id: Optional[str] = None
    unit_id: Optional[str] = None
    bed_assignment: Optional[str] = None
    receiving_facility: Optional[str] = None
    receiving_clinician_name: Optional[str] = None
    receiving_role_title: Optional[str] = None
    transfer_of_care_time: Optional[datetime] = None
    hl7_message_id: Optional[str] = None
    is_test: bool = False
    chief_complaint: Optional[str] = None
    primary_impression: Optional[str] = None
    handoff_summary: Optional[str] = None
    patient_demographics: Optional[EpcrBillingPatientDemographics] = None
    transmitted_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None


class EpcrChartContract(BaseModel):
    """Read-only ePCR chart contract for cross-domain consumption."""

    id: str
    tenant_id: str

    call_number: str
    status: str
    incident_type: str

    created_at: datetime
    updated_at: Optional[datetime] = None
    finalized_at: Optional[datetime] = None


class EpcrPatientProfileContract(BaseModel):
    """Chart-scoped patient demographics owned by the ePCR domain."""

    chart_id: str
    tenant_id: str
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    age_years: Optional[int] = None
    sex: Optional[str] = None
    phone_number: Optional[str] = None
    weight_kg: Optional[float] = None
    allergies: list[str] = Field(default_factory=list)
    updated_at: datetime


class EpcrVitalSetContract(BaseModel):
    """Single chart-scoped vital set used for reassessment-aware workflows."""

    id: str
    chart_id: str
    tenant_id: str
    bp_sys: Optional[int] = None
    bp_dia: Optional[int] = None
    hr: Optional[int] = None
    rr: Optional[int] = None
    temp_f: Optional[float] = None
    spo2: Optional[int] = None
    glucose: Optional[int] = None
    recorded_at: datetime


class EpcrClinicalImpressionContract(BaseModel):
    """Structured impression contract for field and downstream read models."""

    chart_id: str
    tenant_id: str
    chief_complaint: Optional[str] = None
    field_diagnosis: Optional[str] = None
    primary_impression: Optional[str] = None
    secondary_impression: Optional[str] = None
    impression_notes: Optional[str] = None
    snomed_code: Optional[str] = None
    icd10_code: Optional[str] = None
    acuity: Optional[str] = None
    documented_at: datetime


class EpcrMedicationAdministrationContract(BaseModel):
    """Medication administration contract owned by the ePCR truth model."""

    id: str
    chart_id: str
    tenant_id: str
    medication_name: str
    rxnorm_code: Optional[str] = None
    dose_value: Optional[str] = None
    dose_unit: Optional[str] = None
    route: str
    indication: str
    response: Optional[str] = None
    export_state: str
    administered_at: datetime


class EpcrSignatureArtifactContract(BaseModel):
    """Authoritative signature artifact contract for chart completion workflows."""

    id: str
    chart_id: str
    tenant_id: str
    source_domain: str
    source_capture_id: str
    signature_class: str
    signature_method: str
    workflow_policy: str
    policy_pack_version: str
    payer_class: str
    signer_identity: Optional[str] = None
    signer_relationship: Optional[str] = None
    patient_capable_to_sign: Optional[bool] = None
    receiving_facility: Optional[str] = None
    transfer_of_care_time: Optional[datetime] = None
    signature_artifact_data_url: Optional[str] = None
    signature_on_file_reference: Optional[str] = None
    compliance_decision: str
    compliance_why: str
    chart_completion_effect: str
    billing_readiness_effect: str
    missing_requirements: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class EpcrNemsissComplianceContract(BaseModel):
    """NEMSIS 3.5.1 compliance status for a chart."""

    chart_id: str

    is_fully_compliant: bool
    compliance_percentage: float

    missing_mandatory_fields: list[str] = Field(default_factory=list)


class EpcrBillingHandoffPayload(BaseModel):
    """Authoritative payload for ePCR-to-Billing handoff on chart submission.

    Triggered when an ePCR chart is finalized and ready for billing.
    Contains all essential clinical data needed to auto-populate a billing claim.
    """

    chart_id: str
    tenant_id: str
    call_number: str

    # Test-record isolation. True for a non-production ePCR (e.g. a Founder
    # WARDS Lab record). A consumer MUST NOT create a Claim, ClaimIntakeRecord,
    # or any payer-facing artifact from a payload where this is True.
    #
    # Defaults to False so existing producers stay valid and an omitted value
    # fails CLOSED toward production (a real encounter is never silently
    # dropped from billing).
    is_test: bool = False

    # Patient demographics from ePCR
    patient_first_name: Optional[str] = None
    patient_last_name: Optional[str] = None
    patient_date_of_birth: Optional[str] = None
    patient_phone: Optional[str] = None

    # Clinical data for claim coding
    chief_complaint: Optional[str] = None
    primary_icd10_code: Optional[str] = None
    secondary_icd10_codes: list[str] = Field(default_factory=list)
    field_diagnosis: Optional[str] = None

    # Transport/Response info
    incident_type: str
    response_started_at: Optional[datetime] = None
    response_completed_at: Optional[datetime] = None

    # Service-level charge (configurable by org)
    base_charge_cents: int = Field(default=0, ge=0)
    mileage_km: Optional[float] = None
    mileage_charge_cents: int = Field(default=0, ge=0)

    # Compliance & readiness
    is_nemsis_compliant: bool
    missing_fields: list[str] = Field(default_factory=list)

    # Audit trail
    finalized_at: datetime
    created_at: datetime


class EpcrBillingHandoffResponse(BaseModel):
    """Response from Billing service after claim auto-population."""

    claim_id: str
    status: str
    total_charge_cents: int
    message: Optional[str] = None
    created_at: datetime
