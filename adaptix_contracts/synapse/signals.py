"""The canonical Synapse signal envelope and its payloads (SYN-001).

:class:`ClinicalSignalEnvelope` is the ONE shape every device signal takes
above the adapter boundary. Integrations adapters decode manufacturer data and
emit only this envelope (plus genome, session identity and evidence metadata);
they never emit ePCR, NEMSIS, CCT or FHIR shapes. The Device service persists
envelopes on its single normalised telemetry path; ePCR imports from the
Device service's authoritative state, treating bus events as notifications.

Payloads form a discriminated union on ``payload_type``. The envelope checks
that the payload fits the ``signal_kind`` (see
:data:`SIGNAL_KIND_PAYLOAD_TYPES`), so a waveform signal can never carry an
observation payload.

Waveform samples never travel in an envelope. A
:class:`WaveformReferencePayload` points at a stored evidence object that
holds the samples.

Time is carried, never overwritten: ``device_observed_at`` is exactly what
the device reported; any correction lands in ``corrected_observed_at`` with
the ``clock_offset_ms`` that produced it, and ``time_quality`` says which one
to trust. Every datetime must be timezone-aware.

``tenant_id`` on the envelope is a claim the receiver verifies, not an
authority: the Device service derives the owning tenant from the persisted
Device row (``resolve_ingest_tenant``) and rejects a mismatch.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import timedelta
from types import MappingProxyType
from typing import Annotated, Any, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from adaptix_contracts.synapse.enums import (
    SynapseAlertCondition,
    SynapseAlertPriority,
    SynapseAlertState,
    SynapseConnectionState,
    SynapseMeasurementValidity,
    SynapseQualityFlag,
    SynapseSignalKind,
    SynapseTherapyEventPhase,
    SynapseTimeQuality,
    SynapseWaveformEncoding,
)
from adaptix_contracts.synapse.provenance import (
    AdapterKey,
    CanonicalCode,
    CorrelationId,
    ExternalKey,
    MediaType,
    SemanticVersion,
    Sha256Hex,
    SynapseId,
)

#: The envelope schema version this package emits and accepts.
SYNAPSE_SIGNAL_SCHEMA_VERSION: Literal["1.0"] = "1.0"

#: Largest device-clock correction an envelope may carry: ten years, in
#: milliseconds. A device clock further out than that is not "drifted", it is
#: unset, and its time must be reported as ``UNTRUSTED`` or ``ESTIMATED``.
MAX_CLOCK_OFFSET_MS = 10 * 366 * 24 * 60 * 60 * 1000

#: UCUM unit expression (printable ASCII, no whitespace), e.g. ``/min``,
#: ``%``, ``mm[Hg]``, ``Cel``.
UcumUnit = Annotated[
    str, StringConstraints(min_length=1, max_length=64, pattern=r"^[!-~]+$")
]

_TextValue = Annotated[
    str,
    StringConstraints(min_length=1, max_length=256, pattern=r"^[^\x00-\x1f\x7f]+$"),
]

_STRICT = ConfigDict(extra="forbid", frozen=True)

#: Payload ``payload_type`` values each signal kind may carry.
SIGNAL_KIND_PAYLOAD_TYPES: Mapping[SynapseSignalKind, frozenset[str]] = (
    MappingProxyType(
        {
            SynapseSignalKind.OBSERVATION: frozenset({"observation"}),
            SynapseSignalKind.TEMPERATURE: frozenset({"observation"}),
            SynapseSignalKind.DIAGNOSTIC: frozenset(
                {"observation", "document_reference"}
            ),
            SynapseSignalKind.WAVEFORM: frozenset({"waveform_reference"}),
            SynapseSignalKind.ALERT: frozenset({"alert"}),
            SynapseSignalKind.THERAPY_EVENT: frozenset({"therapy_event"}),
            SynapseSignalKind.DOCUMENT: frozenset({"document_reference"}),
            SynapseSignalKind.IMAGE: frozenset({"document_reference"}),
            SynapseSignalKind.VENTILATOR_STATE: frozenset(
                {"device_state", "observation"}
            ),
            SynapseSignalKind.PUMP_STATE: frozenset({"device_state", "observation"}),
            SynapseSignalKind.DEVICE_STATE: frozenset({"device_state"}),
        }
    )
)

#: Media types an IMAGE signal's document reference may use.
_IMAGE_MEDIA_PREFIX = "image/"
_IMAGE_EXTRA_MEDIA_TYPES = frozenset({"application/dicom"})


def _reject_bool_and_non_finite(value: Any) -> Any:
    if isinstance(value, bool):
        raise ValueError("a measured value must be a number or text, not a boolean")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("a measured value must be finite")
    return value


def _check_unit_matches_value(value: object, unit: str | None) -> None:
    numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
    if numeric and unit is None:
        raise ValueError("a numeric value requires a UCUM unit")
    if not numeric and unit is not None:
        raise ValueError("a text or boolean value must not carry a unit")


class SignalQuantity(BaseModel):
    """A coded numeric quantity with its UCUM unit."""

    model_config = _STRICT

    code: CanonicalCode
    value: int | float
    unit: UcumUnit

    @field_validator("value", mode="before")
    @classmethod
    def _finite_number(cls, value: Any) -> Any:
        return _reject_bool_and_non_finite(value)


class ObservationReferenceRange(BaseModel):
    """The normal range the device reported for an observation."""

    model_config = _STRICT

    low: float | None = None
    high: float | None = None

    @model_validator(mode="after")
    def _bounded(self) -> ObservationReferenceRange:
        if self.low is None and self.high is None:
            raise ValueError("a reference range needs low, high or both")
        for bound in (self.low, self.high):
            if bound is not None and not math.isfinite(bound):
                raise ValueError("reference range bounds must be finite")
        if self.low is not None and self.high is not None and self.low > self.high:
            raise ValueError("reference range low exceeds high")
        return self


class ObservationPayload(BaseModel):
    """One measured observation (a vital sign, a temperature, a lab-like value).

    ``code`` is the canonical Synapse observation code. A numeric ``value``
    requires a UCUM ``unit``; a coded text value (for example a rhythm label)
    carries none.
    """

    model_config = _STRICT

    payload_type: Literal["observation"] = "observation"
    code: CanonicalCode
    value: int | float | _TextValue
    unit: UcumUnit | None = None
    reference_range: ObservationReferenceRange | None = None
    device_quality: SynapseMeasurementValidity | None = None

    @field_validator("value", mode="before")
    @classmethod
    def _value_shape(cls, value: Any) -> Any:
        return _reject_bool_and_non_finite(value)

    @model_validator(mode="after")
    def _unit_and_range(self) -> ObservationPayload:
        _check_unit_matches_value(self.value, self.unit)
        if isinstance(self.value, str) and self.reference_range is not None:
            raise ValueError(
                "a text observation cannot carry a numeric reference range"
            )
        return self


class WaveformCalibration(BaseModel):
    """Maps stored sample counts to physical units.

    ``physical = offset + scale_factor * sample``.
    """

    model_config = _STRICT

    unit: UcumUnit
    scale_factor: float
    offset: float = 0.0

    @model_validator(mode="after")
    def _usable(self) -> WaveformCalibration:
        if not (math.isfinite(self.scale_factor) and math.isfinite(self.offset)):
            raise ValueError("calibration values must be finite")
        if not self.scale_factor:
            raise ValueError("scale_factor of zero would erase the waveform")
        return self


class WaveformReferencePayload(BaseModel):
    """A pointer to one stored waveform segment. It carries NO samples.

    The samples live in the evidence object ``evidence_id``, encoded as
    ``encoding`` with media type ``content_type``. ``sample_count`` may be
    lower than the window allows (dropouts) but never higher.
    """

    model_config = _STRICT

    payload_type: Literal["waveform_reference"] = "waveform_reference"
    channel: CanonicalCode
    sample_rate_hz: float = Field(gt=0, le=100_000)
    start_at: AwareDatetime
    end_at: AwareDatetime
    sample_count: int = Field(ge=1)
    calibration: WaveformCalibration
    evidence_id: SynapseId
    content_type: MediaType
    encoding: SynapseWaveformEncoding

    @model_validator(mode="after")
    def _window_is_consistent(self) -> WaveformReferencePayload:
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        duration_s = (self.end_at - self.start_at).total_seconds()
        max_samples = math.floor(duration_s * self.sample_rate_hz + 1e-6) + 1
        if self.sample_count > max_samples:
            raise ValueError(
                f"sample_count {self.sample_count} exceeds the {max_samples} "
                "samples the window and sample rate allow"
            )
        return self


class TherapyEventPayload(BaseModel):
    """A therapy the device REPORTS it delivered (a record, never a command)."""

    model_config = _STRICT

    payload_type: Literal["therapy_event"] = "therapy_event"
    therapy_code: CanonicalCode
    phase: SynapseTherapyEventPhase
    parameters: list[SignalQuantity] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def _parameter_codes_unique(self) -> TherapyEventPayload:
        codes = [parameter.code for parameter in self.parameters]
        if len(set(codes)) != len(codes):
            raise ValueError("therapy parameters must not repeat a code")
        return self


class AlertPayload(BaseModel):
    """A device alarm as the device reported it."""

    model_config = _STRICT

    payload_type: Literal["alert"] = "alert"
    alert_code: CanonicalCode
    priority: SynapseAlertPriority
    condition: SynapseAlertCondition
    state: SynapseAlertState
    triggering_value: SignalQuantity | None = None


class DocumentReferencePayload(BaseModel):
    """A pointer to a stored device document or image (report, 12-lead, still)."""

    model_config = _STRICT

    payload_type: Literal["document_reference"] = "document_reference"
    document_type: CanonicalCode
    evidence_id: SynapseId
    media_type: MediaType


class DeviceBatteryState(BaseModel):
    """The device's own battery as it reported it.

    At least one field is present; a device that reports nothing about its
    battery sends no ``battery`` object rather than an empty one.
    """

    model_config = _STRICT

    level_percent: float | None = Field(default=None, ge=0, le=100)
    charging: bool | None = None
    remaining_minutes: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _reports_something(self) -> DeviceBatteryState:
        if (
            self.level_percent is None
            and self.charging is None
            and self.remaining_minutes is None
        ):
            raise ValueError(
                "a battery state needs level_percent, charging or remaining_minutes"
            )
        return self


class DeviceStatePayload(BaseModel):
    """Operational state of the device itself (not the patient).

    ``state_code`` names what is being reported. ``battery`` and
    ``connection_state`` are first-class because every device reports them and
    the Device Truth timeline reasons about them (battery exhaustion, link
    loss). ``value`` carries any other state (a ventilator mode, a pump state).
    At least one of ``value``, ``battery`` or ``connection_state`` is present.
    Numeric values require a UCUM unit; boolean and text values carry none.
    """

    model_config = _STRICT

    payload_type: Literal["device_state"] = "device_state"
    state_code: CanonicalCode
    value: bool | int | float | _TextValue | None = None
    unit: UcumUnit | None = None
    battery: DeviceBatteryState | None = None
    connection_state: SynapseConnectionState | None = None

    @field_validator("value", mode="before")
    @classmethod
    def _finite(cls, value: Any) -> Any:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("a state value must be finite")
        return value

    @model_validator(mode="after")
    def _reports_state(self) -> DeviceStatePayload:
        if (
            self.value is None
            and self.battery is None
            and self.connection_state is None
        ):
            raise ValueError("a device state needs value, battery or connection_state")
        if self.value is None:
            if self.unit is not None:
                raise ValueError("unit is only carried with a value")
        else:
            _check_unit_matches_value(self.value, self.unit)
        return self


#: The discriminated union of every payload an envelope may carry.
SynapseSignalPayload = Annotated[
    ObservationPayload
    | WaveformReferencePayload
    | TherapyEventPayload
    | AlertPayload
    | DocumentReferencePayload
    | DeviceStatePayload,
    Field(discriminator="payload_type"),
]


class ClinicalSignalEnvelope(BaseModel):
    """The canonical, manufacturer-neutral envelope for one device signal.

    Identity and replay safety: ``event_id`` names this normalised signal;
    ``idempotency_key`` is REQUIRED and is what makes a retransmission (from
    an adapter retry, a second rail, or an edge replay) harmless;
    ``source_record_id`` is the device-native record the adapter decoded.
    ``normalization_version`` names the normalisation rules that produced the
    envelope, so a later re-normalisation can supersede it without deleting it.
    """

    model_config = _STRICT

    schema_version: Literal["1.0"] = SYNAPSE_SIGNAL_SCHEMA_VERSION
    event_id: SynapseId
    tenant_id: SynapseId
    device_id: SynapseId
    device_session_id: SynapseId | None = None
    rail_id: SynapseId
    signal_kind: SynapseSignalKind
    signal_code: CanonicalCode
    device_observed_at: AwareDatetime | None = None
    adaptix_received_at: AwareDatetime
    corrected_observed_at: AwareDatetime | None = None
    time_quality: SynapseTimeQuality
    clock_offset_ms: int | None = Field(
        default=None, ge=-MAX_CLOCK_OFFSET_MS, le=MAX_CLOCK_OFFSET_MS
    )
    adapter_key: AdapterKey
    adapter_version: SemanticVersion
    source_record_id: ExternalKey
    idempotency_key: ExternalKey
    evidence_id: SynapseId | None = None
    evidence_sha256: Sha256Hex | None = None
    normalization_version: SemanticVersion
    quality_flags: list[SynapseQualityFlag] = Field(default_factory=list)
    correlation_id: CorrelationId
    payload: SynapseSignalPayload

    @model_validator(mode="after")
    def _payload_fits_signal_kind(self) -> ClinicalSignalEnvelope:
        allowed = SIGNAL_KIND_PAYLOAD_TYPES[self.signal_kind]
        if self.payload.payload_type not in allowed:
            raise ValueError(
                f"signal_kind {self.signal_kind.value!r} cannot carry a "
                f"{self.payload.payload_type!r} payload (allowed: {sorted(allowed)})"
            )
        if (
            self.signal_kind is SynapseSignalKind.IMAGE
            and isinstance(self.payload, DocumentReferencePayload)
            and not (
                self.payload.media_type.startswith(_IMAGE_MEDIA_PREFIX)
                or self.payload.media_type in _IMAGE_EXTRA_MEDIA_TYPES
            )
        ):
            raise ValueError(
                "an IMAGE signal must reference an image/* or application/dicom "
                "evidence object"
            )
        return self

    @model_validator(mode="after")
    def _evidence_is_consistent(self) -> ClinicalSignalEnvelope:
        if (self.evidence_id is None) != (self.evidence_sha256 is None):
            raise ValueError(
                "evidence_id and evidence_sha256 must be provided together"
            )
        payload_evidence = getattr(self.payload, "evidence_id", None)
        if payload_evidence is not None and payload_evidence != self.evidence_id:
            raise ValueError(
                "the payload references evidence the envelope does not: "
                "envelope evidence_id must equal payload evidence_id"
            )
        return self

    @model_validator(mode="after")
    def _time_is_consistent(self) -> ClinicalSignalEnvelope:
        quality = self.time_quality
        if (
            quality is not SynapseTimeQuality.CORRECTED
            and self.clock_offset_ms is not None
        ):
            raise ValueError("clock_offset_ms is only carried by CORRECTED time")
        if quality is SynapseTimeQuality.ORIGINAL:
            if self.device_observed_at is None:
                raise ValueError("ORIGINAL time requires device_observed_at")
            if self.corrected_observed_at is not None:
                raise ValueError("ORIGINAL time cannot carry corrected_observed_at")
        elif quality is SynapseTimeQuality.CORRECTED:
            if (
                self.device_observed_at is None
                or self.corrected_observed_at is None
                or self.clock_offset_ms is None
            ):
                raise ValueError(
                    "CORRECTED time requires device_observed_at, "
                    "corrected_observed_at and clock_offset_ms"
                )
            try:
                expected = self.device_observed_at + timedelta(
                    milliseconds=self.clock_offset_ms
                )
            except OverflowError:
                raise ValueError(
                    "device_observed_at + clock_offset_ms is outside the "
                    "representable time range"
                ) from None
            if abs(expected - self.corrected_observed_at) >= timedelta(milliseconds=1):
                raise ValueError(
                    "corrected_observed_at must equal device_observed_at + "
                    "clock_offset_ms"
                )
        elif quality is SynapseTimeQuality.ESTIMATED:
            if self.corrected_observed_at is None:
                raise ValueError(
                    "ESTIMATED time requires the estimate in corrected_observed_at"
                )
        elif quality is SynapseTimeQuality.UNTRUSTED:
            if self.device_observed_at is None:
                raise ValueError(
                    "UNTRUSTED time requires the device_observed_at it distrusts"
                )
            if self.corrected_observed_at is not None:
                raise ValueError("UNTRUSTED time cannot carry corrected_observed_at")
        return self

    @model_validator(mode="after")
    def _quality_flags_unique(self) -> ClinicalSignalEnvelope:
        if len(set(self.quality_flags)) != len(self.quality_flags):
            raise ValueError("quality_flags must not repeat")
        return self


__all__ = [
    "MAX_CLOCK_OFFSET_MS",
    "SIGNAL_KIND_PAYLOAD_TYPES",
    "SYNAPSE_SIGNAL_SCHEMA_VERSION",
    "AlertPayload",
    "ClinicalSignalEnvelope",
    "DeviceBatteryState",
    "DeviceStatePayload",
    "DocumentReferencePayload",
    "ObservationPayload",
    "ObservationReferenceRange",
    "SignalQuantity",
    "SynapseSignalPayload",
    "TherapyEventPayload",
    "UcumUnit",
    "WaveformCalibration",
    "WaveformReferencePayload",
]
