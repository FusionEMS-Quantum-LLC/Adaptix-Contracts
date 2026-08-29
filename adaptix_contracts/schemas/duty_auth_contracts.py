"""Shared contracts for field duty authentication.

Used by Adaptix-Core-Service (duty_auth_router, duty_auth_service) and any
field-facing service that issues or validates duty session tokens.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class FieldLoginRequest(BaseModel):
    """Payload for POST /api/auth/duty/resolve — credential resolution."""

    tenant_id: str = Field(
        ..., description="UUID of the tenant issuing the credential."
    )
    device_id: str = Field(..., description="Registered device identifier.")
    app: str = Field(
        ...,
        description="Requesting app identifier: mdt | crewlink | epcr | fire.",
    )
    credential_type: str = Field(
        ...,
        description="Credential type: nfc_badge | qr_code | pin | biometric.",
    )
    raw_payload: str = Field(
        ...,
        description="Raw encoded credential payload (NFC UID, QR content, etc.).",
    )
    unit_id: Optional[str] = Field(
        default=None,
        description="Optional unit/vehicle ID to pre-assign on session creation.",
    )


class FieldLoginResolved(BaseModel):
    """Response from credential resolution — truthful outcome only."""

    result: str = Field(
        ...,
        description="Resolution outcome: ok | denied | challenge_required.",
    )
    responder_id: Optional[str] = Field(
        default=None,
        description="UUID of the resolved responder (present when result is ok).",
    )
    display_name: Optional[str] = Field(
        default=None,
        description="Display name of the resolved responder.",
    )
    role: Optional[str] = Field(
        default=None,
        description="Resolved role for the responder.",
    )
    requires_second_factor: bool = Field(
        default=False,
        description="True when a second authentication factor is still required.",
    )
    denial_reason: Optional[str] = Field(
        default=None,
        description="Human-readable denial reason (present when result is denied).",
    )


class CreateDutySessionRequest(BaseModel):
    """Payload for POST /api/auth/duty/sessions — duty session creation."""

    tenant_id: str = Field(..., description="UUID of the tenant.")
    responder_id: str = Field(
        ..., description="UUID of the responder starting their shift."
    )
    device_id: str = Field(..., description="Registered device identifier.")
    app: str = Field(
        ...,
        description="App requesting the duty session: mdt | crewlink | epcr | fire.",
    )
    auth_method: str = Field(
        ...,
        description="Authentication method used: nfc_badge | qr_code | pin | biometric.",
    )
    assign_unit: bool = Field(
        default=False,
        description="Whether to assign the responder to a unit on session start.",
    )
    unit_id: Optional[str] = Field(
        default=None,
        description="Unit UUID to assign when assign_unit is True.",
    )
    assign_station: bool = Field(
        default=False,
        description="Whether to assign the responder to a station on session start.",
    )
    station_id: Optional[str] = Field(
        default=None,
        description="Station UUID to assign when assign_station is True.",
    )
    start_shift: bool = Field(
        default=True,
        description="Whether to record a shift start event for this session.",
    )


class DutySessionResponse(BaseModel):
    """Response for a created or retrieved duty session."""

    session_id: str = Field(..., description="UUID of the duty session.")
    jwt: str = Field(..., description="Signed duty session JWT.")
    expires_at: datetime = Field(..., description="UTC expiry timestamp.")
    session_state: str = Field(
        ...,
        description="Current session state: active | ended | revoked | expired.",
    )


class EndDutySessionRequest(BaseModel):
    """Payload for POST /api/auth/duty/sessions/{id}/end."""

    tenant_id: str = Field(..., description="UUID of the tenant.")
    device_id: str = Field(..., description="Registered device identifier.")
    logout_reason: Optional[str] = Field(
        default=None,
        description="Optional human-readable reason for ending the session.",
    )


class EndDutySessionResponse(BaseModel):
    """Response confirming duty session termination."""

    session_id: str = Field(..., description="UUID of the ended session.")
    ended_at: datetime = Field(
        ..., description="UTC timestamp when the session was ended."
    )
    reason: Optional[str] = Field(
        default=None, description="Reason for session termination."
    )


class RevokeBadgeRequest(BaseModel):
    """Payload for POST /api/auth/duty/badges/revoke."""

    tenant_id: str = Field(..., description="UUID of the tenant.")
    badge_id: str = Field(..., description="UUID of the badge to revoke.")
    reason: str = Field(..., description="Reason for revocation (required for audit).")
    revoked_by: str = Field(
        ..., description="UUID of the admin user performing the revocation."
    )


class RevokeBadgeResponse(BaseModel):
    """Response confirming badge revocation."""

    status: str = Field(
        ..., description="Revocation status: revoked | already_revoked | not_found."
    )
    badge_id: str = Field(..., description="UUID of the badge that was processed.")


# ---------------------------------------------------------------------------
# Audit event — legacy alias for DutyAuthAuditEvent
# ---------------------------------------------------------------------------


class AuthAuditEvent(BaseModel):
    """Shared duty auth audit event contract.

    This class mirrors the DutyAuthAuditEvent ORM model shape for use in
    cross-service contract payloads. Kept lightweight intentionally — full
    audit lineage lives in the Core Service DB.
    """

    tenant_id: str = Field(..., description="UUID of the tenant.")
    actor_user_id: Optional[str] = Field(
        default=None,
        description="UUID of the acting user or None for system events.",
    )
    device_id: Optional[str] = Field(
        default=None, description="Device involved in the event."
    )
    app: Optional[str] = Field(default=None, description="App context for the event.")
    action: str = Field(..., description="Audit action identifier.")
    outcome: str = Field(..., description="Outcome: success | failure | denied.")
    detail: Optional[str] = Field(
        default=None, description="Optional human-readable detail."
    )
    occurred_at: datetime = Field(..., description="UTC timestamp of the event.")
