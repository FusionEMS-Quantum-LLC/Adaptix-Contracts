"""CAD-to-ePCR NEMSIS handoff contract.

This contract defines the structured payload that CAD produces and ePCR consumes
to populate NEMSIS 3.5.1 dispatch, response, scene, destination, unit, crew,
and timeline elements.

CAD DOES NOT:
- Generate final NEMSIS XML
- Own NEMSIS validation
- Bypass ePCR chart review
- Invent clinical fields

ePCR OWNS:
- Final NEMSIS 3.5.1 mapping
- XML generation
- XSD validation
- Schematron validation
- Clinical chart review
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CadCrewMemberContext(BaseModel):
    """Crew member context from CAD dispatch."""

    crew_id: str
    role: str | None = None
    certification_level: str | None = None
    unit_id: str | None = None


class CadFacilityContext(BaseModel):
    """Facility context captured at CAD intake."""

    facility_name: str | None = None
    facility_address: str | None = None
    facility_department: str | None = None
    facility_room_bed: str | None = None
    facility_phone: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class CadPatientMinimumContext(BaseModel):
    """Minimum patient identifiers available at CAD intake.

    CAD does NOT own clinical patient data.
    These are dispatch-origin identifiers only.
    """

    patient_first_name: str | None = None
    patient_last_name: str | None = None
    date_of_birth: str | None = None
    patient_id_external: str | None = None
    mrn: str | None = None


class CadPayerDocumentAwareness(BaseModel):
    """Payer and document dependency awareness from CAD intake.

    CAD does NOT own billing or document workflow.
    This is awareness only — ePCR/TransportLink own the actual documents.
    """

    payer_type: str | None = None
    payer_name: str | None = None
    authorization_number: str | None = None
    pcs_likely_required: bool = False
    abn_awareness: bool = False
    aob_awareness: bool = False
    document_dependency_notes: str | None = None


class CadDispatchTimeline(BaseModel):
    """Dispatch timeline timestamps from CAD.

    Maps to NEMSIS eTimes section elements.
    All timestamps are ISO 8601 UTC.
    """

    # NEMSIS eTimes.01 — PSAP Call Date/Time (if available)
    call_received_at: datetime | None = None

    # NEMSIS eTimes.03 — Unit Notified by Dispatch Date/Time
    unit_notified_at: datetime | None = None

    # NEMSIS eTimes.05 — Unit En Route Date/Time
    unit_enroute_at: datetime | None = None

    # NEMSIS eTimes.06 — Unit Arrived on Scene Date/Time
    unit_arrived_origin_at: datetime | None = None

    # NEMSIS eTimes.07 — Arrived at Patient Date/Time
    patient_contact_at: datetime | None = None

    # NEMSIS eTimes.09 — Unit Left Scene Date/Time (loaded/transport begin)
    unit_loaded_at: datetime | None = None
    transport_begin_at: datetime | None = None

    # NEMSIS eTimes.11 — Patient Arrived at Destination Date/Time
    arrived_destination_at: datetime | None = None

    # NEMSIS eTimes.12 — Destination Patient Transfer of Care Date/Time
    transfer_of_care_at: datetime | None = None

    # NEMSIS eTimes.13 — Unit Back in Service Date/Time
    unit_clear_at: datetime | None = None

    # CAD internal timestamps
    dispatch_created_at: datetime | None = None
    dispatch_updated_at: datetime | None = None
    unit_assigned_at: datetime | None = None

    # Cancellation
    cancelled_at: datetime | None = None
    cancellation_reason: str | None = None


class CadDispatchContext(BaseModel):
    """eDispatch section data — CAD-owned dispatch metadata.

    Maps to NEMSIS 3.5.1 eDispatch elements. Previously unmapped; now required
    for complete state dataset submission.

    CAD owns these fields: dispatcher determines call type, EMD card, and area command.
    ePCR must NOT override these without explicit dispatcher correction.
    """

    # NEMSIS eDispatch.01 — Complaint Reported by Dispatch (call type code)
    call_type: str | None = Field(
        default=None,
        description="eDispatch.01 — Complaint/call type reported by dispatcher (e.g. CHEST_PAIN, TRAUMA, CARDIAC_ARREST)",
    )

    # NEMSIS eDispatch.02 — Unit Dispatched CAD Record ID
    cad_record_id: str | None = Field(
        default=None,
        description="eDispatch.02 — CAD system record/case ID for this dispatch",
    )

    # NEMSIS eDispatch.03 — Complaint Reported by Dispatch (free text description)
    complaint: str | None = Field(
        default=None,
        description="eDispatch.03 — Dispatch complaint description as reported by dispatcher",
    )

    # NEMSIS eDispatch.04 — EMD Performed (Yes/No)
    emd_performed: bool | None = Field(
        default=None,
        description="eDispatch.04 — Whether Emergency Medical Dispatch protocol was performed",
    )

    # NEMSIS eDispatch.05 — EMD Card Number Used
    emd_card: str | None = Field(
        default=None,
        description="eDispatch.05 — EMD card/protocol number used (e.g. ProQA, MPDS card number)",
    )

    # NEMSIS eDispatch.06 — Area Command
    area_command: str | None = Field(
        default=None,
        description="eDispatch.06 — Geographic area command identifier for this dispatch",
    )


class CadNemsisHandoffPayload(BaseModel):
    """Structured CAD-to-ePCR handoff payload for NEMSIS 3.5.1 field population.

    This is the authoritative contract between CAD and ePCR for dispatch-origin
    data. ePCR ingests this payload to pre-populate NEMSIS fields where applicable.

    ePCR must:
    - Preserve CAD source attribution
    - Not overwrite clinician-entered data without explicit review
    - Map timestamps to correct NEMSIS eTimes elements
    - Mark missing required NEMSIS elements clearly
    - Return validation warnings to ePCR UI
    - Store handoff mapping audit
    """

    # Correlation identifiers
    handoff_id: str = Field(description="Unique handoff record ID")
    cad_dispatch_id: str = Field(description="CAD dispatch/case ID")
    cad_intake_id: str | None = Field(
        default=None, description="CAD intake ID if separate"
    )
    tenant_id: str
    correlation_id: str | None = None

    # HEMS context (if applicable)
    hems_request_id: str | None = None
    hems_eligibility_summary: str | None = None
    ground_fallback_recommended: bool = False
    ground_fallback_reason: str | None = None

    # Transport metadata
    # NEMSIS eResponse.05 — Type of Service Requested
    transport_type: str = Field(
        description="SCHEDULED|UNSCHEDULED|INTERFACILITY|HEMS|etc."
    )

    # NEMSIS eResponse.07 — Primary Role of the Unit
    level_of_care: str = Field(
        description="BLS|ALS|CCT|SCT|HEMS|WHEELCHAIR|STRETCHER|UNKNOWN"
    )

    # NEMSIS eResponse.23 — Response Priority
    priority: str | None = None

    # Unit and vehicle
    # NEMSIS eResponse.13 — EMS Unit Number
    unit_id: str | None = None
    vehicle_id: str | None = None

    # NEMSIS eCrew section
    crew_members: list[CadCrewMemberContext] = Field(default_factory=list)

    # Origin/scene facility
    # NEMSIS eScene section
    origin_facility: CadFacilityContext = Field(default_factory=CadFacilityContext)

    # Destination facility
    # NEMSIS eDisposition section
    destination_facility: CadFacilityContext = Field(default_factory=CadFacilityContext)

    # Routing/mileage
    # NEMSIS eDisposition.17 — Transport Distance
    mileage_estimate: float | None = None
    route_eta_minutes: float | None = None

    # Patient minimum context (dispatch-origin only)
    patient_context: CadPatientMinimumContext | None = None

    # Payer/document awareness
    payer_document_awareness: CadPayerDocumentAwareness | None = None

    # eDispatch section — call type, EMD, area command (CAD-owned)
    # NEMSIS eDispatch.01–.06
    dispatch_context: CadDispatchContext | None = Field(
        default=None,
        description="eDispatch.01–.06 — CAD dispatch metadata: call type, complaint, EMD, area command",
    )

    # Medical necessity support text (CAD-generated, not clinical)
    medical_necessity_support_text: str | None = None

    # Dispatch timeline
    timeline: CadDispatchTimeline = Field(default_factory=CadDispatchTimeline)

    # Notes and briefings
    cad_notes: str | None = None
    crew_briefing: str | None = None
    facility_handoff_notes: str | None = None

    # Audit
    handoff_created_at: datetime
    handoff_source: str = "adaptix-cad"
    handoff_version: str = "1.0"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "handoff_id": "hndff-001",
                "cad_dispatch_id": "disp-001",
                "tenant_id": "tenant-001",
                "transport_type": "INTERFACILITY",
                "level_of_care": "ALS",
                "priority": "high",
                "unit_id": "UNIT-12",
                "vehicle_id": "VEH-12",
                "crew_members": [
                    {
                        "crew_id": "crew-001",
                        "role": "PARAMEDIC",
                        "certification_level": "ALS",
                    }
                ],
                "handoff_created_at": "2026-05-03T12:00:00Z",
            }
        }
    )


class CadNemsisHandoffCreatedEvent(BaseModel):
    """Event emitted when CAD creates a NEMSIS handoff payload."""

    event_type: str = "cad.medical_transport.nemsis_handoff.generated"
    handoff_id: str
    cad_dispatch_id: str
    tenant_id: str
    transport_type: str
    level_of_care: str
    emitted_at: datetime
