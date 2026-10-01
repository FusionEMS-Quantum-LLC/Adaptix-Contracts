"""ePCR domain contract schemas for cross-domain communication."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, Optional

from pydantic import AwareDatetime, BaseModel, Field, StringConstraints

from adaptix_contracts.lineage.models import EncounterLineage


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

    TWO producers in ``Adaptix-EPCR-Service`` write this event as a
    ``ChartEventOutbox`` row (event type ``epcr.chart.amended``), and the
    generic relay ``epcr_app/outbox_worker.py`` (``_publish_generic``) forwards
    the row's payload unchanged. ``amendment_authority`` says which one:

    * ``"legacy_field_diff"`` -- ``epcr_app/chart_amendment_service.py``
      (``create_amendment``). ``amendment_id`` is the append-only
      ``ChartAmendment`` row id and ``field`` is the chart attribute that was
      amended (e.g. ``"narrative"``); the consumer can fetch the full
      before/after detail through the authorized ePCR read path.
    * ``"canonical_signed_version"`` -- ``epcr_app/api_chart_state_machine.py``
      (``trustsign_amendment``, the canonical TrustSign signed-version path).
      ``amendment_id`` is the ``EpcrSignatureArtifact`` id of the sealing
      signature, ``field`` is the fixed sentinel ``"canonical_signed_version"``
      (there is no single amended attribute -- a whole new signed version was
      sealed), and the additive keys ``signed_version_id``,
      ``supersedes_signed_version_id``, ``signature_id`` and ``document_hash``
      point at the canonical records.

    ``amendment_authority`` defaults to ``"legacy_field_diff"`` ONLY so that
    payloads emitted before the discriminator existed still validate; every
    producer MUST set it explicitly, and it becomes required in the next major.
    A consumer must branch on it: treating a canonical ``amendment_id`` as a
    ``ChartAmendment`` pointer misfiles the reference.

    ``tenant_id`` is REQUIRED: the relay's generic publish path refuses
    tenant-less events, so a payload without it can never reach the bus at
    all -- the field being mandatory here keeps the producer honest at
    validation time instead of at relay time.

    The consumer is Billing: a clinical amendment landing AFTER the chart was
    handed to billing must become visible against the claim that was built
    from the pre-amendment chart, never silently diverge from it.
    """

    event_type: str = "epcr.chart.amended"

    amendment_id: str
    chart_id: str
    tenant_id: str
    field: str

    amendment_authority: Literal["legacy_field_diff", "canonical_signed_version"] = (
        "legacy_field_diff"
    )

    actor_id: Optional[str] = None
    amended_at: Optional[datetime] = None

    # Canonical signed-version pointers. Present only when
    # ``amendment_authority == "canonical_signed_version"``.
    signed_version_id: Optional[str] = None
    supersedes_signed_version_id: Optional[str] = None
    signature_id: Optional[str] = None
    document_hash: Optional[str] = None


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

    # Why ``billing_snapshot`` is absent (5.31.0). Finalizing a chart is a
    # clinical and legal act and is never blocked by a billing fact set that
    # could not be built, so the event still ships; this names the failure
    # (an exception class name, never a message) instead of shipping ``None``
    # as though the chart simply had no facts. A consumer must hold the
    # encounter for the producer's re-emitted handoff rather than bill from
    # placeholders. ``None`` with a snapshot present is the normal case;
    # ``None`` with no snapshot is a producer that predates 5.31.0.
    billing_snapshot_error: Optional[str] = Field(default=None, max_length=120)


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
    # Medical-necessity facts (5.31.0). The crew's coded statement of urgency
    # and of why the patient could not travel another way, plus the two
    # narratives NEMSIS keeps beside them. A PCS "does not alone demonstrate"
    # necessity (42 CFR 410.40(e)(2)); these are what the record says.
    response_urgency_code: Optional[str] = None  # ePayment.40
    patient_transport_assessment_code: Optional[str] = None  # ePayment.41
    specialty_care_transport_provider_code: Optional[str] = None  # ePayment.42
    round_trip_purpose_description: Optional[str] = None  # ePayment.45
    stretcher_purpose_description: Optional[str] = None  # ePayment.46
    als_assessment_performed_warranted_code: Optional[str] = None  # ePayment.49


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

    Absence semantics are tri-state per list, matching
    ``EpcrBillingCertificationBlock``: ``None`` means the producer did not
    collect that category (predates this block, or export unavailable) and is
    NOT evidence that no interventions were performed — a consumer must not
    treat it as "zero interventions occurred." An explicit empty list ``[]``
    is an affirmative producer statement that the chart carried no structured
    rows of that category.
    """

    procedures: Optional[list[EpcrBillingProcedureItem]] = None
    medication_administrations: Optional[
        list[EpcrBillingMedicationAdministrationItem]
    ] = None
    procedure_total: Optional[int] = None
    medication_administration_total: Optional[int] = None


class EpcrBillingGuarantorBlock(BaseModel):  # pylint: disable=too-few-public-methods
    """Closest relative / guardian facts (NEMSIS ePayment.23-.32) for billing.

    The person a patient statement or a guarantor-billed claim is addressed to
    when the patient is a minor or cannot be billed directly. Raw stored values
    from EPCR's ``epcr_chart_payment`` row; nothing is inferred. ``None`` on a
    field means the crew did not document it. The block itself is ``None`` when
    the chart has no ePayment row or documents none of these elements.
    """

    last_name: Optional[str] = None  # ePayment.23
    first_name: Optional[str] = None  # ePayment.24
    middle_name: Optional[str] = None  # ePayment.25
    street_address: Optional[str] = None  # ePayment.26
    city: Optional[str] = None  # ePayment.27 (CityGnisCode, not a display name)
    state: Optional[str] = None  # ePayment.28 (ANSIStateCode)
    zip: Optional[str] = None  # ePayment.29
    country: Optional[str] = None  # ePayment.30
    phone: Optional[str] = None  # ePayment.31
    relationship_code: Optional[str] = None  # ePayment.32


class EpcrBillingEmployerBlock(BaseModel):  # pylint: disable=too-few-public-methods
    """Patient employer facts (NEMSIS ePayment.33-.39) for billing.

    What a workers' compensation claim needs to name the employer. Raw stored
    values; ``None`` means undocumented. The block is ``None`` when the chart
    documents none of these elements. Its presence is NOT evidence the
    encounter is work related: that is ``primary_method_of_payment_code``
    (ePayment.01) and the payer, which Billing evaluates.
    """

    name: Optional[str] = None  # ePayment.33
    address: Optional[str] = None  # ePayment.34
    city: Optional[str] = None  # ePayment.35
    state: Optional[str] = None  # ePayment.36
    zip: Optional[str] = None  # ePayment.37
    country: Optional[str] = None  # ePayment.38
    phone: Optional[str] = None  # ePayment.39


class EpcrBillingAttachmentRef(BaseModel):  # pylint: disable=too-few-public-methods
    """A reference to one file attached to the chart (face sheet, PCS scan, card).

    A pointer, never the file: no bytes, no storage location and no file name
    (crews name files after patients). Billing fetches the document through
    EPCR's authorized attachment read path using ``attachment_id`` and can prove
    it received the same bytes with ``sha256``.
    """

    attachment_id: str = Field(..., min_length=1)
    content_type: Optional[str] = None
    size_bytes: Optional[int] = Field(default=None, ge=0)
    sha256: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    uploaded_at: Optional[AwareDatetime] = None


class EpcrBillingSignatureFact(BaseModel):  # pylint: disable=too-few-public-methods
    """One signature the crew captured, or a documented reason none was obtained.

    These are the facts 42 CFR 424.36 turns on. EPCR states what was captured;
    it does not decide whether a claim may be filed. Billing applies the
    regulation to the whole set:

    * 424.36(a): the beneficiary signed (``signer_type_code`` 4512015 with a
      signed ``signature_status_code``).
    * 424.36(b)(1)-(5): the beneficiary was incapable
      (``patient_capable_to_sign`` is ``False``) and a representative signed
      (``signer_type_code`` 4512017, ``representative_type_code`` eOther.14).
    * 424.36(b)(6), the ambulance exception: nobody in (b)(1)-(4) was available
      or willing, and the record holds (A) a crew member's contemporaneous
      statement (``ambulance_employee_exception`` on a crew signature),
      (B) the date and time of transport and the receiving facility's name
      (``transfer_of_care_time``, ``receiving_facility_name``), and (C) a signed
      statement from a receiving-facility representative (a healthcare-provider
      signature, ``signer_type_code`` 4512005) or a secondary verification
      (``receiving_facility_verification_status``).

    PHI is kept to what Billing must evaluate: signer names, the incapacity
    narrative, the signature graphic and the signature-on-file reference stay
    in EPCR, which retains the record; this fact says only that each is
    documented. Codes are NEMSIS 3.5.1 eOther.12-.15 values as EPCR derives
    them for its state export; ``None`` means EPCR could not derive one without
    guessing.

    ``compliance_decision``, ``billing_readiness_effect`` and
    ``missing_requirements`` are EPCR's own evaluation of the stored fields,
    recomputed by the server when the snapshot is built. A value a capture
    client asserted is never forwarded.
    """

    signature_id: str = Field(..., min_length=1)
    signature_class: Optional[str] = None
    signature_method: Optional[str] = None
    # Who signed, as EPCR classifies its own ``signature_class`` vocabulary.
    # ``None`` means a class EPCR does not recognise; a consumer must not
    # count such a signature toward any requirement.
    signer_role: Optional[
        Literal[
            "patient",
            "patient_representative",
            "ems_crew",
            "receiving_facility",
            "witness",
            "medical_control",
            "medical_director",
            "other",
        ]
    ] = None
    # True when EPCR holds evidence the person signed: a captured graphic, a
    # completed TrustSign attestation, or a documented signature on file. False
    # for a documented not-signed reason (eOther.15 "Not Signed - ...").
    signature_obtained: bool = False
    signer_type_code: Optional[str] = Field(
        default=None, pattern=r"^4512\d{3}$"
    )  # eOther.12
    signature_reason_codes: list[
        Annotated[str, StringConstraints(pattern=r"^4513\d{3}$")]
    ] = Field(default_factory=list)  # eOther.13 (0:M)
    representative_type_code: Optional[str] = Field(
        default=None, pattern=r"^4514\d{3}$"
    )  # eOther.14
    signature_status_code: Optional[str] = Field(
        default=None, pattern=r"^4515\d{3}$"
    )  # eOther.15
    signed_at: Optional[AwareDatetime] = None  # eOther.19
    signer_identity_documented: bool = False
    signer_relationship: Optional[str] = None
    signer_authority_basis: Optional[str] = None
    patient_capable_to_sign: Optional[bool] = None
    incapacity_reason_documented: bool = False
    signature_graphic_captured: bool = False
    signature_on_file_documented: bool = False
    ambulance_employee_exception: bool = False
    receiving_facility_name: Optional[str] = None
    receiving_clinician_documented: bool = False
    receiving_role_title: Optional[str] = None
    transfer_of_care_time: Optional[AwareDatetime] = None
    transfer_exception_reason_code: Optional[str] = None
    receiving_facility_verification_status: Optional[str] = None
    compliance_decision: Optional[str] = None
    billing_readiness_effect: Optional[str] = None
    missing_requirements: list[str] = Field(default_factory=list)
    # True when an amendment changed the chart content after this signature
    # attested to it. The signature is real history, but it no longer attests
    # to the chart being billed.
    content_invalidated: bool = False
    trustsign_verification_id: Optional[str] = None


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
    # Date of service (5.26.0, BILL-PRE-001). ``encounter_occurred_at`` is the
    # authoritative encounter instant the producer takes from NEMSIS eTimes
    # (eTimes.01 PSAP call, else eTimes.02 dispatch notified, else eTimes.03
    # unit notified); it must be timezone-aware. ``date_of_service`` is that
    # instant's calendar date in the agency's local time zone — the date a
    # claim bills (837P DTP*472, 270 service date, timely filing). Neither is
    # ever the chart finalization time: a call before local midnight that is
    # finalized after 00:00Z would otherwise bill the wrong day. ``None``
    # means the producer had no eTimes to derive it from (or predates 5.26.0);
    # a consumer must hold the claim rather than substitute another date.
    date_of_service: Optional[date] = None
    encounter_occurred_at: Optional[AwareDatetime] = None
    # Encounter lineage (5.27.0). The canonical chain of opaque identifiers
    # (dispatch, transport request, trip, unit, vehicle, crew, patient, payer)
    # plus service start/completion and the requested -> dispatched ->
    # documented -> billed level-of-care chain, so Billing can query Fleet,
    # Crew and Workforce for the resources actually used. ePCR populates it;
    # ``None`` means the producer predates 5.27.0 or had no lineage to carry.
    # ``attending_crew`` and ``date_of_service`` above are unchanged.
    lineage: Optional[EncounterLineage] = None
    # CMS ambulance origin/destination TYPE tokens (5.29.0). ePCR derives them
    # from eScene.09 (incident location type) and eDisposition.21 (type of
    # destination), mapping only codes with one unambiguous CMS facility type;
    # Billing's ``auto_biller/claim_builder.py`` reads them as
    # ``origin_type`` / ``destination_type`` and resolves each to a CMS letter
    # through its facility letter table. ``None`` means unknown, ambiguous or a
    # producer that predates 5.29.0; a consumer must not substitute a guessed
    # letter. The raw location facts stay on ``transport``.
    origin_type: Optional[str] = Field(
        default=None,
        description=(
            "CMS ambulance origin token derived by ePCR from eScene.09 "
            "(unambiguous codes only); absent when unknown. Billing resolves "
            "it through its facility letter table."
        ),
    )
    destination_type: Optional[str] = Field(
        default=None,
        description=(
            "CMS ambulance destination token derived by ePCR from "
            "eDisposition.21 (unambiguous codes only); absent when unknown."
        ),
    )
    # Chart facts a claim needs that the snapshot never carried (5.31.0).
    # Every one is tri-state where it is a list or a block: ``None`` means the
    # producer predates 5.31.0 (or could not read that source), an empty list
    # is the producer's statement that the chart holds none.
    #
    # eSituation.12 Provider's Secondary Impressions, ICD-10-CM codes in the
    # order the crew ranked them. ``primary_impression_icd10`` above is
    # unchanged and is never repeated here.
    secondary_impression_icd10_codes: Optional[list[str]] = None
    # ePayment.01 Primary Method of Payment (National, Required) and
    # ePayment.08 Patient Resides in Service Area, raw NEMSIS codes.
    primary_method_of_payment_code: Optional[str] = None
    patient_resides_in_service_area_code: Optional[str] = None
    guarantor: Optional[EpcrBillingGuarantorBlock] = None
    employer: Optional[EpcrBillingEmployerBlock] = None
    # Signatures and documented not-signed reasons (eOther.12-.21). See
    # ``EpcrBillingSignatureFact`` for how Billing reads them under 424.36.
    signatures: Optional[list[EpcrBillingSignatureFact]] = None
    # References to the files attached to the chart. Pointers only.
    attachments: Optional[list[EpcrBillingAttachmentRef]] = None
    # When the producer assembled this snapshot (5.33.0). A chart can be handed
    # off again after it is finalized (a signature obtained later, a corrected
    # pickup ZIP), and the bus delivers at least once, so deliveries can arrive
    # out of order. A consumer that already holds facts for the chart keeps the
    # snapshot with the later ``built_at``; ``finalized_at`` cannot order them
    # because it does not move when the chart is handed off again.
    built_at: Optional[AwareDatetime] = None
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
