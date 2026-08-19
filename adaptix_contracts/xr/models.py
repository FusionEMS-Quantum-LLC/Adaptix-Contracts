"""Adaptix AR/XR Remote Physician Overwatch + Training — Pydantic v2 models.

Play P04. Shared contract surface for the XR service, the AdaptixCore UI,
the ePCR service (session-to-chart linkage), and downstream analytics.

Every tenant-scoped model carries ``tenant_id`` and ``correlation_id`` so
tenant isolation and cross-service tracing survive marshalling into events
and audit records.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from adaptix_contracts.xr.enums import (
    AnnotationType,
    RecordingStatus,
    SessionStatus,
    SessionType,
    TrainingDifficulty,
    XrDevice,
)


class _XrBase(BaseModel):
    """Base model for every XR contract.

    Enforces tenant scope and correlation on every payload that crosses a
    service or event boundary. ``model_config`` uses Pydantic v2's
    ``populate_by_name`` so downstream consumers may deserialize either the
    canonical snake_case names or common camelCase aliases already used by
    the UI donors.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=False,
        extra="forbid",
        str_strip_whitespace=True,
    )

    tenant_id: str = Field(
        ...,
        description=(
            "Tenant scope — resolved server-side from trusted auth context. "
            "Never accept a client-supplied tenant_id as authorization truth."
        ),
    )
    correlation_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Correlation ID for tracing across services and events.",
    )


# ---------------------------------------------------------------------------
# Session — a live overwatch or training XR encounter
# ---------------------------------------------------------------------------


class XrSession(_XrBase):
    """A remote-physician overwatch session or a training simulation session.

    ``patient_id`` is populated only for ``overwatch`` sessions tied to a
    real patient encounter and is intentionally omitted (never defaulted to
    a placeholder) for ``training`` sessions, which do not involve a real
    patient. PHI is not duplicated onto this contract beyond the platform
    patient identifier; look up demographics through the patient identity
    service using ``patient_id`` under tenant scope.
    """

    id: UUID = Field(default_factory=uuid4)
    session_type: SessionType
    status: SessionStatus = SessionStatus.PENDING
    device: XrDevice

    field_provider_id: str = Field(
        ..., min_length=1, description="User id of the field-side operator wearing/holding the device."
    )
    remote_physician_id: str | None = Field(
        default=None,
        description="User id of the remote physician. Required for overwatch once status leaves PENDING.",
    )

    patient_id: str | None = Field(
        default=None,
        description="Platform patient identifier. Only set for overwatch sessions tied to a real encounter.",
    )
    training_scenario_id: UUID | None = Field(
        default=None,
        description="TrainingScenario this session is running. Only set for training sessions.",
    )

    linked_epcr_chart_id: str | None = None
    linked_cad_incident_id: str | None = None

    scheduled_start_at: datetime | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    ended_reason: str | None = Field(default=None, max_length=2000)

    connection_quality_notes: str | None = Field(default=None, max_length=2000)
    device_firmware_version: str | None = Field(default=None, max_length=100)

    recording_manifest_id: UUID | None = None
    annotation_ids: list[UUID] = Field(default_factory=list)

    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Physician annotation — an overlay a remote physician places in-session
# ---------------------------------------------------------------------------


class PhysicianAnnotation(_XrBase):
    """A single overlay/annotation a remote physician places during a session."""

    id: UUID = Field(default_factory=uuid4)
    session_id: UUID

    annotation_type: AnnotationType
    content: str = Field(..., min_length=1, max_length=4000)

    spatial_anchor_x: float | None = Field(
        default=None, description="Normalized X coordinate (0.0-1.0) in the field-of-view frame."
    )
    spatial_anchor_y: float | None = Field(
        default=None, description="Normalized Y coordinate (0.0-1.0) in the field-of-view frame."
    )
    session_timestamp_ms: int = Field(
        ..., ge=0, description="Milliseconds from session start when the annotation was placed."
    )

    created_by: str = Field(..., min_length=1, description="User id of the remote physician.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    acknowledged_by_field_provider: bool = False
    acknowledged_at: datetime | None = None

    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Annotation-type-specific fields not modelled above (e.g. drawing vector paths).",
    )


# ---------------------------------------------------------------------------
# Recording manifest — durable pointer to a session's stored recording
# ---------------------------------------------------------------------------


class RecordingManifest(_XrBase):
    """Storage manifest for a session recording.

    The manifest, not the media itself, is the contract surface — the media
    lives in object storage. ``content_hash`` lets a consumer verify the
    recording has not been altered since it was sealed.
    """

    id: UUID = Field(default_factory=uuid4)
    session_id: UUID

    status: RecordingStatus = RecordingStatus.PENDING

    storage_uri: str | None = Field(
        default=None, description="Object storage URI. Populated once status is AVAILABLE."
    )
    duration_seconds: float | None = Field(default=None, ge=0)
    size_bytes: int | None = Field(default=None, ge=0)
    content_hash: str | None = Field(
        default=None, description="SHA-256 hash of the sealed recording, hex-encoded."
    )

    segment_count: int = Field(default=0, ge=0)
    includes_audio: bool = True
    includes_annotations_overlay: bool = True

    retention_expires_at: datetime | None = Field(
        default=None,
        description="When this recording is eligible for purge per the tenant's retention policy.",
    )
    purged_at: datetime | None = None

    consent_on_file: bool = Field(
        default=False,
        description="True once required recording consent is confirmed for this session.",
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Training scenario — a reusable simulation definition
# ---------------------------------------------------------------------------


class TrainingScenario(_XrBase):
    """A reusable training simulation scenario definition.

    ``TrainingScenario`` is agency-configured content, not a per-session
    record — ``XrSession.training_scenario_id`` points back to one of these
    when ``session_type`` is ``training``.
    """

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)

    difficulty: TrainingDifficulty = TrainingDifficulty.INTRODUCTORY
    supported_devices: list[XrDevice] = Field(default_factory=list)

    objectives: list[str] = Field(default_factory=list)
    scenario_steps: list[str] = Field(
        default_factory=list,
        description="Ordered list of scripted step descriptions the scenario walks a trainee through.",
    )
    estimated_duration_minutes: int | None = Field(default=None, ge=0)

    active: bool = True

    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


__all__ = [
    "PhysicianAnnotation",
    "RecordingManifest",
    "TrainingScenario",
    "XrSession",
]
