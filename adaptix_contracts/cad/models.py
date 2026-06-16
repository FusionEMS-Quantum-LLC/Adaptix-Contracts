"""CAD domain Pydantic models for cross-service contracts.

All models are read-only contracts. CAD owns dispatch coordination only.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field

# ─── Enums ────────────────────────────────────────────────────────────────────


class TransportType(str, Enum):
    SCHEDULED = "SCHEDULED"
    UNSCHEDULED = "UNSCHEDULED"
    INTERFACILITY = "INTERFACILITY"
    DISCHARGE = "DISCHARGE"
    FACILITY_TO_FACILITY = "FACILITY_TO_FACILITY"
    SCENE_TO_FACILITY_MEDICAL = "SCENE_TO_FACILITY_MEDICAL"
    COMMUNITY_PARAMEDICINE = "COMMUNITY_PARAMEDICINE"
    STANDBY = "STANDBY"
    HEMS = "HEMS"


class LevelOfCare(str, Enum):
    BLS = "BLS"
    ALS = "ALS"
    CCT = "CCT"
    SCT = "SCT"
    WHEELCHAIR = "WHEELCHAIR"
    STRETCHER = "STRETCHER"
    HEMS = "HEMS"
    UNKNOWN = "UNKNOWN"


class UnitStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    ASSIGNED = "ASSIGNED"
    ENROUTE_TO_ORIGIN = "ENROUTE_TO_ORIGIN"
    ARRIVED_AT_ORIGIN = "ARRIVED_AT_ORIGIN"
    PATIENT_CONTACT = "PATIENT_CONTACT"
    LOADED = "LOADED"
    TRANSPORTING = "TRANSPORTING"
    ARRIVED_AT_DESTINATION = "ARRIVED_AT_DESTINATION"
    TRANSFER_OF_CARE = "TRANSFER_OF_CARE"
    CLEARING = "CLEARING"
    AVAILABLE_POST_CALL = "AVAILABLE_POST_CALL"
    OUT_OF_SERVICE = "OUT_OF_SERVICE"
    RESTRICTED = "RESTRICTED"
    CANCELLED = "CANCELLED"


class VehicleTrackingStatus(str, Enum):
    GPS_ACTIVE = "GPS_ACTIVE"
    GPS_STALE = "GPS_STALE"
    GPS_UNAVAILABLE = "GPS_UNAVAILABLE"
    MANUAL_STATUS_ONLY = "MANUAL_STATUS_ONLY"
    TELEMETRY_ERROR = "TELEMETRY_ERROR"


class HemsStatus(str, Enum):
    REQUESTED = "REQUESTED"
    ELIGIBILITY_REVIEW = "ELIGIBILITY_REVIEW"
    WEATHER_REVIEW = "WEATHER_REVIEW"
    AIRCRAFT_REVIEW = "AIRCRAFT_REVIEW"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    CANCELLED = "CANCELLED"
    LAUNCHED = "LAUNCHED"
    ARRIVED = "ARRIVED"
    COMPLETED = "COMPLETED"
    GROUND_FALLBACK_RECOMMENDED = "GROUND_FALLBACK_RECOMMENDED"


# ─── Facility Models ──────────────────────────────────────────────────────────


class CadOriginFacility(BaseModel):
    facility_name: str | None = None
    facility_address: str | None = None
    facility_department: str | None = None
    facility_room_bed: str | None = None
    facility_phone: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class CadDestinationFacility(BaseModel):
    facility_name: str | None = None
    facility_address: str | None = None
    facility_department: str | None = None
    facility_room_bed: str | None = None
    facility_phone: str | None = None
    latitude: float | None = None
    longitude: float | None = None


# ─── Patient / Payer Context ──────────────────────────────────────────────────


class CadPatientContext(BaseModel):
    """Minimum patient identifiers available at CAD intake. CAD does NOT own clinical data."""

    patient_first_name: str | None = None
    patient_last_name: str | None = None
    date_of_birth: str | None = None
    patient_id_external: str | None = None
    mrn: str | None = None
    mobility_status: str | None = None
    oxygen_required: bool = False
    monitoring_required: bool = False
    isolation_required: bool = False
    bariatric_required: bool = False
    escort_required: bool = False


class CadPayerContext(BaseModel):
    """Payer awareness from CAD intake. CAD does NOT own billing workflow."""

    payer_type: str | None = None
    payer_name: str | None = None
    authorization_number: str | None = None
    pcs_likely_required: bool = False
    abn_awareness: bool = False
    aob_awareness: bool = False
    document_dependency_notes: str | None = None


# ─── Transport Request ────────────────────────────────────────────────────────


class CadTransportRequestReason(BaseModel):
    reason_code: str | None = None
    reason_text: str | None = None
    diagnosis_context: str | None = None
    medical_necessity_notes: str | None = None


class CadMedicalTransportIntake(BaseModel):
    intake_id: str
    tenant_id: str
    transport_type: TransportType
    scheduled: bool = False
    recurring: bool = False
    caller_name: str | None = None
    caller_callback: str | None = None
    requesting_facility: str | None = None
    requesting_department: str | None = None
    origin: CadOriginFacility = Field(default_factory=CadOriginFacility)
    destination: CadDestinationFacility = Field(default_factory=CadDestinationFacility)
    requested_pickup_time: datetime | None = None
    appointment_time: datetime | None = None
    transport_reason: CadTransportRequestReason | None = None
    patient_context: CadPatientContext | None = None
    payer_context: CadPayerContext | None = None
    preferred_unit_type: str | None = None
    requested_crew_level: str | None = None
    sending_clinician: str | None = None
    receiving_clinician: str | None = None
    special_handling_notes: str | None = None
    equipment_requirements: list[str] = Field(default_factory=list)
    status: str = "new"
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None
    tenant_correlation_id: str | None = None


# ─── Dispatch ─────────────────────────────────────────────────────────────────


class CadTransportDispatch(BaseModel):
    dispatch_id: str
    intake_id: str
    tenant_id: str
    transport_type: TransportType
    level_of_care: LevelOfCare
    priority: str | None = None
    unit_id: str | None = None
    vehicle_id: str | None = None
    crew_ids: list[str] = Field(default_factory=list)
    origin: CadOriginFacility = Field(default_factory=CadOriginFacility)
    destination: CadDestinationFacility = Field(default_factory=CadDestinationFacility)
    status: str = "created"
    dispatcher_notes: str | None = None
    facility_notes: str | None = None
    crew_notes: str | None = None
    delay_reason: str | None = None
    cancellation_reason: str | None = None
    supervisor_review_flag: bool = False
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None


# ─── Assessments ──────────────────────────────────────────────────────────────


class CadLevelOfCareAssessment(BaseModel):
    assessment_id: str
    intake_id: str
    tenant_id: str
    recommended_level: LevelOfCare
    explanation: str | None = None
    indicators: list[str] = Field(default_factory=list)
    confidence_score: float | None = None
    risk_level: str | None = None
    rule_version: str | None = None
    policy_reference: str | None = None
    human_review_required: bool = True
    assessed_at: datetime
    assessed_by: str | None = None


class CadMedicalNecessityAssessment(BaseModel):
    assessment_id: str
    intake_id: str
    tenant_id: str
    qualifies_for_transport: bool
    support_text: str | None = None
    indicators: list[str] = Field(default_factory=list)
    missing_documentation: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    confidence_score: float | None = None
    risk_level: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    human_review_required: bool = True
    ai_may_not_approve: bool = True
    rule_version: str | None = None
    assessed_at: datetime
    assessed_by: str | None = None


class CadPCSRequirementAwareness(BaseModel):
    intake_id: str
    pcs_likely_required: bool
    explanation: str | None = None
    policy_reference: str | None = None


class CadABNRequirementAwareness(BaseModel):
    intake_id: str
    abn_awareness: bool
    explanation: str | None = None


class CadAOBRequirementAwareness(BaseModel):
    intake_id: str
    aob_awareness: bool
    explanation: str | None = None


# ─── Unit / Crew Recommendations ─────────────────────────────────────────────


class CadUnitRecommendation(BaseModel):
    recommendation_id: str
    intake_id: str
    tenant_id: str
    recommended_unit_id: str | None = None
    recommended_unit_type: str | None = None
    explanation: str | None = None
    alternatives: list[str] = Field(default_factory=list)
    confidence_score: float | None = None
    human_review_required: bool = True
    recommended_at: datetime


class CadCrewRecommendation(BaseModel):
    recommendation_id: str
    intake_id: str
    tenant_id: str
    recommended_crew_ids: list[str] = Field(default_factory=list)
    explanation: str | None = None
    credential_warnings: list[str] = Field(default_factory=list)
    fatigue_warnings: list[str] = Field(default_factory=list)
    human_review_required: bool = True
    recommended_at: datetime


class CadUnitAssignment(BaseModel):
    assignment_id: str
    dispatch_id: str
    tenant_id: str
    unit_id: str
    vehicle_id: str | None = None
    crew_ids: list[str] = Field(default_factory=list)
    assigned_at: datetime
    assigned_by: str
    reassignment: bool = False
    reassignment_reason: str | None = None


# ─── Vehicle Tracking ─────────────────────────────────────────────────────────


class CadVehicleTrackingSnapshot(BaseModel):
    snapshot_id: str
    vehicle_id: str
    unit_id: str | None = None
    tenant_id: str
    dispatch_id: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    heading: float | None = None
    speed_mph: float | None = None
    accuracy_meters: float | None = None
    tracking_status: VehicleTrackingStatus = VehicleTrackingStatus.GPS_UNAVAILABLE
    telemetry_source: str | None = None
    captured_at: datetime
    is_stale: bool = False


class CadVehicleTelemetryPoint(BaseModel):
    telemetry_id: str
    vehicle_id: str
    unit_id: str | None = None
    tenant_id: str
    dispatch_id: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    heading: float | None = None
    speed_mph: float | None = None
    odometer: float | None = None
    accuracy_meters: float | None = None
    source: str | None = None
    received_at: datetime


class CadUnitStatusUpdate(BaseModel):
    status_id: str
    unit_id: str
    dispatch_id: str | None = None
    tenant_id: str
    old_status: UnitStatus | None = None
    new_status: UnitStatus
    manual_override: bool = False
    override_reason: str | None = None
    updated_at: datetime
    updated_by: str | None = None
    mdt_source: bool = False


# ─── Timeline ─────────────────────────────────────────────────────────────────


class CadTransportTimeline(BaseModel):
    dispatch_id: str
    tenant_id: str
    call_received_at: datetime | None = None
    unit_notified_at: datetime | None = None
    unit_enroute_at: datetime | None = None
    unit_arrived_origin_at: datetime | None = None
    patient_contact_at: datetime | None = None
    unit_loaded_at: datetime | None = None
    transport_begin_at: datetime | None = None
    arrived_destination_at: datetime | None = None
    transfer_of_care_at: datetime | None = None
    unit_clear_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancellation_reason: str | None = None
    dispatch_created_at: datetime | None = None
    unit_assigned_at: datetime | None = None


# ─── Routing / ETA ────────────────────────────────────────────────────────────


class CadRoutingEta(BaseModel):
    eta_id: str
    dispatch_id: str
    tenant_id: str
    pickup_eta_minutes: float | None = None
    destination_eta_minutes: float | None = None
    route_distance_miles: float | None = None
    eta_confidence: str | None = None
    routing_risk: str | None = None
    provider_credential_gated: bool = False
    manual_override: bool = False
    override_reason: str | None = None
    calculated_at: datetime


class CadGeocodeResult(BaseModel):
    geocode_id: str
    input_address: str
    latitude: float | None = None
    longitude: float | None = None
    formatted_address: str | None = None
    confidence: str | None = None
    provider_credential_gated: bool = False
    geocoded_at: datetime


# ─── HEMS ─────────────────────────────────────────────────────────────────────


class CadHemsRequest(BaseModel):
    request_id: str
    tenant_id: str
    intake_id: str | None = None
    dispatch_id: str | None = None
    request_reason: str | None = None
    pickup_location: CadOriginFacility | None = None
    destination_facility: CadDestinationFacility | None = None
    landing_zone_details: str | None = None
    patient_context: CadPatientContext | None = None
    sending_clinician: str | None = None
    receiving_facility: str | None = None
    status: HemsStatus = HemsStatus.REQUESTED
    cancellation_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    created_by: str


class CadHemsEligibilityAssessment(BaseModel):
    assessment_id: str
    request_id: str
    tenant_id: str
    eligible: bool
    explanation: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    ground_alternative_available: bool = False
    human_review_required: bool = True
    ai_may_not_accept: bool = True
    assessed_at: datetime


class CadHemsBriefing(BaseModel):
    briefing_id: str
    request_id: str
    tenant_id: str
    briefing_text: str
    weather_status: str | None = None
    weather_credential_gated: bool = False
    aircraft_availability: str | None = None
    pilot_availability: str | None = None
    medical_crew_availability: str | None = None
    generated_at: datetime


class CadGroundFallbackRecommendation(BaseModel):
    recommendation_id: str
    request_id: str
    tenant_id: str
    recommended: bool
    reason: str | None = None
    explanation: str | None = None
    human_review_required: bool = True
    recommended_at: datetime


# ─── Handoffs ─────────────────────────────────────────────────────────────────


class CadTransportLinkHandoff(BaseModel):
    handoff_id: str
    dispatch_id: str
    intake_id: str | None = None
    tenant_id: str
    transport_request_id: str | None = None
    patient_context: CadPatientContext | None = None
    origin: CadOriginFacility | None = None
    destination: CadDestinationFacility | None = None
    level_of_care: LevelOfCare | None = None
    medical_necessity_assessment: str | None = None
    pcs_awareness: bool = False
    abn_awareness: bool = False
    aob_awareness: bool = False
    scheduling_status: str | None = None
    dispatch_readiness: str | None = None
    handoff_status: str = "created"
    handoff_failure_reason: str | None = None
    downstream_id: str | None = None
    created_at: datetime


class CadEpcrHandoff(BaseModel):
    handoff_id: str
    dispatch_id: str
    tenant_id: str
    hems_request_id: str | None = None
    transport_type: TransportType | None = None
    level_of_care: LevelOfCare | None = None
    timeline: CadTransportTimeline | None = None
    unit_id: str | None = None
    vehicle_id: str | None = None
    crew_ids: list[str] = Field(default_factory=list)
    patient_context: CadPatientContext | None = None
    origin: CadOriginFacility | None = None
    destination: CadDestinationFacility | None = None
    mileage_estimate: float | None = None
    medical_necessity_support_text: str | None = None
    handoff_status: str = "created"
    handoff_failure_reason: str | None = None
    downstream_epcr_id: str | None = None
    created_at: datetime


class CadBillingHandoff(BaseModel):
    handoff_id: str
    dispatch_id: str
    tenant_id: str
    payer_context: CadPayerContext | None = None
    level_of_care: LevelOfCare | None = None
    medical_necessity_text: str | None = None
    transport_mileage: float | None = None
    route_eta_minutes: float | None = None
    document_dependency_awareness: str | None = None
    handoff_status: str = "created"
    handoff_failure_reason: str | None = None
    downstream_billing_id: str | None = None
    created_at: datetime


class CadCrewLinkPageRequest(BaseModel):
    page_id: str
    dispatch_id: str
    tenant_id: str
    crew_ids: list[str] = Field(default_factory=list)
    crew_briefing: str | None = None
    route_briefing: str | None = None
    facility_handoff_notes: str | None = None
    acknowledgement_status: str = "pending"
    acknowledged_at: datetime | None = None
    escalated: bool = False
    created_at: datetime


# ─── MDT / Scheduling ─────────────────────────────────────────────────────────


class CadMdtSyncEvent(BaseModel):
    sync_id: str
    dispatch_id: str
    unit_id: str
    tenant_id: str
    sync_type: str
    payload_summary: str | None = None
    mdt_online: bool = True
    last_sync_at: datetime
    offline_queued: bool = False


class CadSchedulingAvailabilitySnapshot(BaseModel):
    snapshot_id: str
    tenant_id: str
    unit_id: str | None = None
    crew_id: str | None = None
    available: bool
    shift_end_at: datetime | None = None
    fatigue_warning: bool = False
    credential_warning: bool = False
    credential_expiry_notes: str | None = None
    captured_at: datetime


class CadVoiceRoomRequest(BaseModel):
    room_id: str
    dispatch_id: str
    tenant_id: str
    crew_ids: list[str] = Field(default_factory=list)
    room_status: str = "created"
    communications_audit_id: str | None = None
    created_at: datetime


# ─── AI Assessment ────────────────────────────────────────────────────────────


class CadAIAssessment(BaseModel):
    assessment_id: str
    dispatch_id: str | None = None
    intake_id: str | None = None
    tenant_id: str
    assessment_type: str
    summary: str | None = None
    recommendations: list[str] = Field(default_factory=list)
    input_fields_used: list[str] = Field(default_factory=list)
    confidence_score: float | None = None
    risk_level: str | None = None
    policy_references: list[str] = Field(default_factory=list)
    human_review_required: bool = True
    ai_may_not_dispatch: bool = True
    ai_may_not_request_hems: bool = True
    ai_may_not_create_epcr: bool = True
    ai_may_not_create_billing: bool = True
    assessed_at: datetime


# ─── Audit ────────────────────────────────────────────────────────────────────


class CadAuditEvent(BaseModel):
    audit_id: str
    tenant_id: str
    actor_id: str | None = None
    action: str
    resource_type: str
    resource_id: str
    changes_before: Optional[dict[str, Any]] = None
    changes_after: Optional[dict[str, Any]] = None
    override: bool = False
    override_reason: str | None = None
    supervisor_required: bool = False
    occurred_at: datetime
