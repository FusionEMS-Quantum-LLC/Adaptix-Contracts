"""Adaptix TEFCA QHIN Sub-Participant — Pydantic v2 models.

Play P26. Shared contract surface for the QHIN-Service, Core, the ePCR /
patient-identity services that source FHIR resources, and downstream
audit/analytics.

Every tenant-scoped model carries ``tenant_id`` and ``correlation_id`` so
tenant isolation and cross-service tracing survive marshalling into events
and audit records.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from adaptix_contracts.qhin.enums import FhirVersion, Qhin, QhinPurpose


class _QhinBase(BaseModel):
    """Base model for every QHIN contract.

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
# Credential — the tenant's TEFCA sub-participant connection to a QHIN
# ---------------------------------------------------------------------------


class QhinCredential(_QhinBase):
    """A tenant's sub-participant credential/connection to one QHIN.

    Holds only references to secret material (``client_id`` and secret
    store pointers), never the secret itself — secrets live in the
    platform's approved secret store and are resolved at call time.
    """

    id: UUID = Field(default_factory=uuid4)
    qhin: Qhin

    participant_id: str = Field(
        ...,
        min_length=1,
        description="TEFCA participant/sub-participant identifier issued by the QHIN.",
    )
    client_id: str | None = Field(
        default=None,
        description="OAuth/mTLS client identifier registered with the QHIN.",
    )
    secret_ref: str | None = Field(
        default=None,
        description=(
            "Pointer into the approved secret store (e.g. AWS Secrets Manager "
            "ARN). Never the secret value itself."
        ),
    )
    fhir_base_url: str | None = Field(
        default=None,
        description="Base FHIR endpoint URL negotiated with the QHIN.",
    )
    fhir_version: FhirVersion = FhirVersion.R4

    supported_purposes: list[QhinPurpose] = Field(
        default_factory=list,
        description="Exchange purposes this credential is authorized to assert.",
    )

    active: bool = True
    onboarded_at: datetime | None = None
    last_verified_at: datetime | None = None
    expires_at: datetime | None = None

    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Patient / outbound bundles — FHIR payload envelopes
# ---------------------------------------------------------------------------


class PatientBundle(_QhinBase):
    """An inbound FHIR Bundle resolved for a patient via a QHIN query.

    ``resources`` holds the raw FHIR resource JSON as returned by the QHIN;
    this contract does not re-model FHIR resource shapes — Adaptix defers
    to the FHIR spec for resource-level structure and only wraps it with
    platform tenancy, provenance, and correlation.
    """

    id: UUID = Field(default_factory=uuid4)
    transaction_id: UUID
    qhin: Qhin
    fhir_version: FhirVersion = FhirVersion.R4

    patient_id: str = Field(
        ...,
        min_length=1,
        description="Platform patient identifier this bundle resolves to.",
    )
    source_patient_reference: str | None = Field(
        default=None,
        description="The FHIR Patient resource reference returned by the QHIN.",
    )

    resource_types: list[str] = Field(
        default_factory=list,
        description="FHIR resourceType values present in this bundle.",
    )
    resource_count: int = Field(default=0, ge=0)
    resources: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw FHIR Bundle JSON as returned by the QHIN.",
    )

    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OutboundBundle(_QhinBase):
    """A FHIR Bundle Adaptix constructs to publish/respond to a QHIN.

    Used both for proactive publication (e.g. document push) and for
    responding to an inbound QHIN query against Adaptix-held records.
    """

    id: UUID = Field(default_factory=uuid4)
    transaction_id: UUID
    qhin: Qhin
    fhir_version: FhirVersion = FhirVersion.R4

    patient_id: str = Field(..., min_length=1)
    purpose: QhinPurpose

    resource_types: list[str] = Field(default_factory=list)
    resource_count: int = Field(default=0, ge=0)
    resources: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw FHIR Bundle JSON to be transmitted to the QHIN.",
    )

    built_by: str | None = None
    built_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sent_at: datetime | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Transaction — one QHIN exchange (query/publish/subscription notification)
# ---------------------------------------------------------------------------


class QhinTransaction(_QhinBase):
    """One TEFCA exchange transaction with a QHIN.

    Tracks the full lifecycle of a single query/publish/notification
    exchange so audit, retry, and reconciliation can operate on a stable
    identifier independent of the underlying FHIR bundle payloads.
    """

    id: UUID = Field(default_factory=uuid4)
    credential_id: UUID
    qhin: Qhin
    fhir_version: FhirVersion = FhirVersion.R4

    purpose: QhinPurpose
    patient_id: str | None = Field(
        default=None,
        description="Platform patient identifier this transaction concerns, if patient-scoped.",
    )

    direction: str = Field(
        ...,
        pattern=r"^(inbound|outbound)$",
        description="'inbound' (Adaptix queried/received from the QHIN) or "
        "'outbound' (Adaptix published/responded to the QHIN).",
    )
    interaction: str = Field(
        ...,
        max_length=100,
        description="FHIR interaction, e.g. 'patient-discovery', 'document-query', "
        "'document-retrieve', 'subscription-notification'.",
    )

    status: str = Field(
        default="pending",
        pattern=r"^(pending|in_progress|completed|failed|acknowledged|timed_out)$",
    )

    inbound_bundle_id: UUID | None = None
    outbound_bundle_id: UUID | None = None

    request_url: str | None = None
    http_status: int | None = Field(default=None, ge=100, le=599)
    error_detail: str | None = Field(default=None, max_length=4000)

    retry_count: int = Field(default=0, ge=0)
    idempotency_key: str | None = None

    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    created_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Acknowledgment — QHIN's response confirming receipt/processing
# ---------------------------------------------------------------------------


class QhinAcknowledgment(_QhinBase):
    """A QHIN's acknowledgment of a transaction Adaptix sent or a
    notification Adaptix received.

    Distinct from :class:`QhinTransaction.status` because a QHIN may
    acknowledge receipt asynchronously (e.g. an async document-retrieve
    completing after the initial request returned 202).
    """

    id: UUID = Field(default_factory=uuid4)
    transaction_id: UUID
    qhin: Qhin

    accepted: bool
    ack_code: str | None = Field(
        default=None,
        max_length=100,
        description="QHIN-issued acknowledgment/status code, if any.",
    )
    message: str | None = Field(default=None, max_length=2000)

    acknowledged_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


__all__ = [
    "OutboundBundle",
    "PatientBundle",
    "QhinAcknowledgment",
    "QhinCredential",
    "QhinTransaction",
]
