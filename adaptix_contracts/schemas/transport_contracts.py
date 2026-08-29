"""TransportLink domain contract schemas for cross-domain communication."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TransportRequestTypeContract(str, Enum):
    BLS = "bls"
    ALS = "als"
    CCT = "cct"
    WHEELCHAIR = "wheelchair"
    BARIATRIC = "bariatric"
    AIR = "air"


class TransportRequestStatusContract(str, Enum):
    DRAFT = "draft"
    INTAKE = "intake"
    QUALIFIED = "qualified"
    SCHEDULED = "scheduled"
    DISPATCH_READY = "dispatch_ready"
    IN_TRANSIT = "in_transit"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RecurrencePatternContract(str, Enum):
    DAILY = "daily"
    WEEKDAYS = "weekdays"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class TransportRequestCreate(BaseModel):
    patient_name: str = Field(..., max_length=255)
    patient_dob: Optional[str] = Field(default=None, description="ISO 8601 date string")
    patient_mrn: Optional[str] = Field(default=None, max_length=100)
    pickup_facility_id: str
    destination_facility_id: str
    transport_type: TransportRequestTypeContract
    level_of_care: str = Field(..., max_length=100)
    requested_pickup_at: datetime
    appointment_at: Optional[datetime] = None
    pcs_required: bool = False
    authorization_required: bool = False
    payer_name: Optional[str] = Field(default=None, max_length=255)
    payer_id: Optional[str] = Field(default=None, max_length=100)
    is_recurring: bool = False
    recurrence_pattern: Optional[RecurrencePatternContract] = None
    recurrence_end_date: Optional[datetime] = None
    notes: Optional[str] = Field(default=None, max_length=2000)


class TransportRequestResponse(BaseModel):
    id: str
    tenant_id: str
    patient_name: str
    patient_dob: Optional[str] = None
    patient_mrn: Optional[str] = None
    pickup_facility_id: str
    destination_facility_id: str
    transport_type: TransportRequestTypeContract
    level_of_care: str
    status: TransportRequestStatusContract
    requested_pickup_at: datetime
    appointment_at: Optional[datetime] = None
    pcs_required: bool
    authorization_required: bool
    authorization_status: Optional[str] = None
    authorization_number: Optional[str] = None
    payer_name: Optional[str] = None
    payer_id: Optional[str] = None
    is_recurring: bool
    recurrence_pattern: Optional[RecurrencePatternContract] = None
    recurrence_end_date: Optional[datetime] = None
    notes: Optional[str] = None
    documents_ready: bool
    signature_complete: bool
    created_at: datetime
    updated_at: Optional[datetime] = None


class TripScheduleRequest(BaseModel):
    transport_request_id: str
    scheduled_pickup_at: datetime
    scheduled_dropoff_at: Optional[datetime] = None
    unit_id: Optional[str] = None
    crew_ids: list[str] = Field(default_factory=list)
    notes: Optional[str] = Field(default=None, max_length=2000)


class TripResponse(BaseModel):
    id: str
    tenant_id: str
    transport_request_id: str
    scheduled_pickup_at: datetime
    scheduled_dropoff_at: Optional[datetime] = None
    unit_id: Optional[str] = None
    crew_ids: list[str]
    status: TransportRequestStatusContract
    cad_linked: bool
    created_at: datetime
    updated_at: Optional[datetime] = None


class RecurringSeriesCreate(BaseModel):
    transport_request_id: str
    pattern: RecurrencePatternContract
    series_start_date: datetime
    series_end_date: Optional[datetime] = None
    preferred_pickup_time: str = Field(..., description="HH:MM in 24-hour format")
    max_occurrences: Optional[int] = Field(default=None, ge=1, le=365)


class RecurringSeriesResponse(BaseModel):
    id: str
    tenant_id: str
    transport_request_id: str
    pattern: RecurrencePatternContract
    series_start_date: datetime
    series_end_date: Optional[datetime] = None
    preferred_pickup_time: str
    max_occurrences: Optional[int] = None
    occurrences_generated: int
    occurrences_remaining: int
    status: str
    created_at: datetime


class CalendarEventResponse(BaseModel):
    id: str
    trip_id: str
    transport_request_id: str
    patient_name: str
    pickup_facility_id: str
    destination_facility_id: str
    transport_type: TransportRequestTypeContract
    scheduled_pickup_at: datetime
    scheduled_dropoff_at: Optional[datetime] = None
    status: TransportRequestStatusContract
    readiness_state: str
    unit_id: Optional[str] = None
    is_recurring: bool
    series_id: Optional[str] = None


class SlotSuggestionRequest(BaseModel):
    transport_request_id: str
    preferred_date: datetime
    window_hours: int = Field(default=4, ge=1, le=24)
    avoid_unit_ids: list[str] = Field(default_factory=list)


class SlotSuggestionResponse(BaseModel):
    suggested_pickup_at: datetime
    suggested_dropoff_at: Optional[datetime] = None
    available_unit_ids: list[str]
    conflict_score: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str


class DocumentItemResponse(BaseModel):
    id: str
    document_type: str
    status: str
    signed: bool
    download_url: Optional[str] = None
    generated_at: Optional[datetime] = None
    signed_at: Optional[datetime] = None


class DocumentPackageResponse(BaseModel):
    request_id: str
    documents: list[DocumentItemResponse]
    all_requirements_met: bool
    missing_requirements: list[str]


class SignerStatusResponse(BaseModel):
    signer_email: str
    signer_name: str
    status: str
    signed_at: Optional[datetime] = None


class SignatureStatusResponse(BaseModel):
    id: str
    transport_request_id: str
    signature_request_id: str
    embedded_sign_url: Optional[str] = None
    status: str
    signers: list[SignerStatusResponse]
    completed_at: Optional[datetime] = None
    created_at: datetime


class ReadinessGate(BaseModel):
    gate: str
    passed: bool
    reason: Optional[str] = None


class ReadinessStateResponse(BaseModel):
    request_id: str
    overall_ready: bool
    gates: list[ReadinessGate]
    blocking_count: int
    evaluated_at: datetime


class FacilityResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    facility_type: str
    address: str
    city: str
    state: str
    zip_code: str
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    active: bool
    created_at: datetime


class CadPushRequest(BaseModel):
    trip_id: str
    force: bool = False
    operator_note: Optional[str] = Field(default=None, max_length=500)


class CadPushResponse(BaseModel):
    trip_id: str
    cad_link_id: str
    pushed_at: datetime
    status: str


class TransportRequestCreatedEvent(BaseModel):
    event_type: str = "transportlink.request.created"
    request_id: str
    tenant_id: str
    transport_type: TransportRequestTypeContract
    pickup_facility_id: str
    destination_facility_id: str
    created_at: datetime


class TripScheduledEvent(BaseModel):
    event_type: str = "transportlink.trip.scheduled"
    trip_id: str
    request_id: str
    tenant_id: str
    scheduled_pickup_at: datetime
    unit_id: Optional[str] = None
    created_at: datetime


class SignatureCompletedEvent(BaseModel):
    event_type: str = "transportlink.signature.completed"
    signature_request_id: str
    request_id: str
    tenant_id: str
    document_types: list[str]
    completed_at: datetime


class CadPushRequestedEvent(BaseModel):
    event_type: str = "transportlink.cad.push_requested"
    trip_id: str
    request_id: str
    tenant_id: str
    unit_id: Optional[str] = None
    crew_ids: list[str] = Field(default_factory=list)
    pushed_at: datetime
