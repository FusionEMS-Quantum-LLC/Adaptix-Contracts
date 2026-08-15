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
    missing_fields: list[str] = Field(default_factory=list)
    ready_for_billing: bool = False


class EpcrChartHospitalHandoffEvent(BaseModel):
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
