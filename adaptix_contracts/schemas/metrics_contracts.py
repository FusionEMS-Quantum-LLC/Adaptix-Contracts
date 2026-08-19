"""Metrics and observability contracts.

Defines typed contracts for service health, queue depth, latency,
throughput, and error-rate reporting across Adaptix services.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MetricSeverity(str, Enum):
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


class ServiceHealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class QueueMetric(BaseModel):
    queue_name: str
    depth: int = Field(..., ge=0)
    oldest_age_seconds: Optional[int] = Field(None, ge=0)
    measured_at: datetime


class LatencyMetric(BaseModel):
    operation_name: str
    p50_ms: float = Field(..., ge=0.0)
    p95_ms: float = Field(..., ge=0.0)
    p99_ms: float = Field(..., ge=0.0)
    measured_at: datetime


class ErrorRateMetric(BaseModel):
    operation_name: str
    error_rate_pct: float = Field(..., ge=0.0, le=100.0)
    sample_size: int = Field(..., ge=0)
    measured_at: datetime


class ThroughputMetric(BaseModel):
    operation_name: str
    requests_per_minute: float = Field(..., ge=0.0)
    measured_at: datetime


class ServiceHealthSummary(BaseModel):
    service_name: str
    tenant_id: Optional[str] = None

    status: ServiceHealthStatus
    severity: MetricSeverity = MetricSeverity.NORMAL

    uptime_seconds: Optional[int] = Field(None, ge=0)
    version: Optional[str] = None
    message: Optional[str] = None

    queue_metrics: list[QueueMetric] = Field(default_factory=list)
    latency_metrics: list[LatencyMetric] = Field(default_factory=list)
    error_rate_metrics: list[ErrorRateMetric] = Field(default_factory=list)
    throughput_metrics: list[ThroughputMetric] = Field(default_factory=list)

    measured_at: datetime


class ServiceHealthReportedEvent(BaseModel):
    event_type: str = "metrics.service_health.reported"

    service_name: str
    tenant_id: Optional[str] = None
    status: ServiceHealthStatus
    severity: MetricSeverity = MetricSeverity.NORMAL

    measured_at: datetime


# ---------------------------------------------------------------------------
# PHI-safe product telemetry (shared platform primitive L)
# ---------------------------------------------------------------------------
#
# The metrics above describe service health. Product telemetry describes what
# people actually did — which feature, how long it took, whether it worked — and
# that is where protected data leaks, because the natural thing to attach to
# "chart finalised" is the chart.
#
# So this contract carries an opaque tenant reference rather than a tenant id,
# a fixed set of measurement fields, and a dimensions map that is validated
# against a deny-list of protected key names at construction time. A leak
# becomes a ValidationError at the emit site instead of a discovery in an
# analytics export.


#: Dimension keys that must never be attached to product telemetry. Matching is
#: case-insensitive and substring-based, so ``patient_name``, ``PatientName``
#: and ``primary_patient_name_display`` are all refused.
FORBIDDEN_TELEMETRY_DIMENSION_KEYS: frozenset[str] = frozenset(
    {
        "patient",
        "name",
        "dob",
        "birth",
        "address",
        "mrn",
        "ssn",
        "narrative",
        "transcript",
        "claim_text",
        "diagnosis",
        "medication",
        "phone",
        "email",
        "token",
        "secret",
        "password",
        "credential",
    }
)


class TelemetryOutcome(str, Enum):
    """How an instrumented operation ended.

    ``DEGRADED`` is separate from ``SUCCESS`` and ``FAILURE``: an operation that
    completed on a fallback path is not the same product experience as one that
    completed normally, and collapsing the two hides exactly the regression
    telemetry exists to catch.
    """

    SUCCESS = "success"
    FAILURE = "failure"
    DEGRADED = "degraded"
    ABANDONED = "abandoned"


def forbidden_telemetry_dimensions(dimensions: dict[str, str]) -> list[str]:
    """Return the dimension keys that must not be emitted.

    Case-insensitive substring match against
    :data:`FORBIDDEN_TELEMETRY_DIMENSION_KEYS`. Over-refusal is the intended
    trade: a rejected safe key costs one rename, a leaked one costs a breach.
    """

    offending: list[str] = []
    for key in dimensions:
        lowered = key.lower()
        if any(banned in lowered for banned in FORBIDDEN_TELEMETRY_DIMENSION_KEYS):
            offending.append(key)
    return sorted(offending)


class ProductTelemetryEvent(BaseModel):
    """One PHI-safe product usage measurement.

    ``tenant_ref`` is an opaque per-tenant identifier — a stable hash or
    pseudonym — not the tenant id, so telemetry that reaches a third-party
    analytics surface cannot be joined back to an agency without the platform's
    own mapping.
    """

    model_config = ConfigDict(extra="forbid")

    tenant_ref: str = Field(
        ...,
        min_length=1,
        description="Opaque per-tenant reference. Never the raw tenant_id.",
    )
    feature: str = Field(..., min_length=1)
    operation: str = Field(..., min_length=1)
    outcome: TelemetryOutcome
    duration_ms: int | None = Field(default=None, ge=0)
    count: int | None = Field(default=None, ge=0)
    bytes_processed: int | None = Field(default=None, ge=0)
    pages: int | None = Field(default=None, ge=0)
    tokens: int | None = Field(default=None, ge=0)
    error_class: str | None = Field(
        default=None,
        description="Normalised error class. Never a raw exception message.",
    )
    provider: str | None = None
    model_id: str | None = None
    dimensions: dict[str, str] = Field(
        default_factory=dict,
        description="Low-cardinality non-protected dimensions only",
    )
    measured_at: datetime

    @field_validator("dimensions")
    @classmethod
    def _dimensions_carry_no_protected_keys(
        cls, value: dict[str, str]
    ) -> dict[str, str]:
        offending = forbidden_telemetry_dimensions(value)
        if offending:
            raise ValueError(
                "telemetry dimensions must not carry protected keys: "
                + ", ".join(offending)
            )
        return value
