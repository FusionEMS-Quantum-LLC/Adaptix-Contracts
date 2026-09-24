"""Canonical vocabulary of the Adaptix Synapse Fabric (SYN-001).

LAW SYN-001: integrate capabilities, not manufacturers. Every enum here names
WHAT a device provides or HOW a signal travels, never WHO made the device.
Manufacturer behaviour terminates at the adapter boundary
(Adaptix-Integrations-Service ``connector_sdk``); above it only these canonical
names exist. No member of any enum in this module names a manufacturer, and
none names a command: the medical-device command plane is forbidden in v1.

Every enum is a :class:`~enum.StrEnum` so the wire value is a stable lowercase
string, matching the sibling subpackages (``adaptix_contracts.edge.enums``,
``adaptix_contracts.evidence.enums``). Pydantic rejects an unknown value for an
enum-typed field, which is deliberate: silently accepting an unrecognised
signal kind, capability, time quality or rejection reason could misclassify a
clinical record.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType


class SynapseSignalKind(StrEnum):
    """What kind of clinical or device signal an envelope carries.

    There is deliberately no command/control kind. A signal is something a
    device REPORTED; Adaptix never sends therapy or control instructions to a
    medical device through Synapse.
    """

    OBSERVATION = "observation"
    WAVEFORM = "waveform"
    ALERT = "alert"
    THERAPY_EVENT = "therapy_event"
    DOCUMENT = "document"
    IMAGE = "image"
    VENTILATOR_STATE = "ventilator_state"
    PUMP_STATE = "pump_state"
    TEMPERATURE = "temperature"
    DIAGNOSTIC = "diagnostic"
    DEVICE_STATE = "device_state"


class SynapseDeviceCapability(StrEnum):
    """A data capability a device provides. Applications ask for these.

    Every member is a READ capability (the device can report this data).
    Control capabilities are listed separately in
    :class:`SynapseForbiddenControlCapability` so certification can reject
    them by name.
    """

    OBSERVATIONS = "observations"
    WAVEFORMS = "waveforms"
    ALERTS = "alerts"
    THERAPY_EVENTS = "therapy_events"
    DOCUMENTS = "documents"
    IMAGES = "images"
    VENTILATOR_TELEMETRY = "ventilator_telemetry"
    PUMP_TELEMETRY = "pump_telemetry"
    TEMPERATURE = "temperature"
    DIAGNOSTICS = "diagnostics"


class SynapseTimeQuality(StrEnum):
    """How far the observed time of a signal can be trusted.

    * ``ORIGINAL`` - the device's own timestamp, trusted as reported.
    * ``CORRECTED`` - the device timestamp plus a measured clock offset.
      The original device timestamp is still carried, never overwritten.
    * ``ESTIMATED`` - the device gave no usable timestamp; Adaptix estimated
      one (for example from receipt time).
    * ``UNTRUSTED`` - the device reported a timestamp that could not be
      verified or corrected (unsynchronised clock, impossible value).
    """

    ORIGINAL = "original"
    ESTIMATED = "estimated"
    CORRECTED = "corrected"
    UNTRUSTED = "untrusted"


class SynapseRailType(StrEnum):
    """The ingest path ("rail") a signal arrived on.

    One physical device can feed several rails at once (for example a live
    Wi-Fi stream plus a later file export). Multi-rail arrivals of the same
    fact are resolved with :class:`SynapseRailResolution`.

    ``SDC`` names the IEEE 11073 SDC rail so a research capture can be labelled
    truthfully; sdc11073 remains research-only and has no production driver.
    """

    DIRECT_WIFI = "direct_wifi"
    BLUETOOTH = "bluetooth"
    USB = "usb"
    SERIAL = "serial"
    TCP = "tcp"
    UDP = "udp"
    MQTT = "mqtt"
    HTTP = "http"
    VENDOR_CLOUD = "vendor_cloud"
    WEBHOOK = "webhook"
    SFTP = "sftp"
    FILE_IMPORT = "file_import"
    DIRECTORY_WATCH = "directory_watch"
    SDC = "sdc"
    HL7_DEVICE = "hl7_device"


class SynapseRailResolution(StrEnum):
    """How a signal relates to one that already arrived on another rail.

    * ``EXACT_DUPLICATE`` - same fact, same content; it is not stored twice.
    * ``PROBABLE_DUPLICATE`` - same fact by every available key but not
      byte-identical; kept, flagged, never silently merged.
    * ``INDEPENDENT_CORROBORATING_SOURCE`` - a genuinely separate source
      agreeing with the first.
    * ``CONFLICTING_OBSERVATION`` - the two cannot both be true; a human must
      reconcile. Recording a conflict never auto-resolves it.
    """

    EXACT_DUPLICATE = "exact_duplicate"
    PROBABLE_DUPLICATE = "probable_duplicate"
    INDEPENDENT_CORROBORATING_SOURCE = "independent_corroborating_source"
    CONFLICTING_OBSERVATION = "conflicting_observation"


class SynapseForbiddenControlCapability(StrEnum):
    """Therapy/control vocabulary Synapse must REJECT at certification.

    These names exist only so an adapter, device genome or manifest that
    declares one of them can be refused by name. Nothing in Synapse may
    implement, route or relay any of these actions: the medical-device command
    plane is forbidden in v1. (Existing MDM administrative commands on the
    Device service are a separate, unrelated surface and are untouched.)
    """

    SHOCK = "shock"
    CARDIOVERT = "cardiovert"
    PACE = "pace"
    CHANGE_INFUSION = "change_infusion"
    ADMINISTER_MEDICATION = "administer_medication"
    ALTER_VENTILATOR_THERAPY = "alter_ventilator_therapy"
    START_CRITICAL_TREATMENT = "start_critical_treatment"
    STOP_CRITICAL_TREATMENT = "stop_critical_treatment"


#: The forbidden control vocabulary as a frozen set of wire values.
FORBIDDEN_CONTROL_CAPABILITIES: frozenset[str] = frozenset(
    member.value for member in SynapseForbiddenControlCapability
)


_NON_TOKEN_CHARACTERS = re.compile(r"[^0-9a-z]+")


def normalize_capability_token(value: str) -> str:
    """Reduce a declared capability name to its comparison token.

    The token is the NFKC-normalised, case-folded name with everything but
    ASCII letters and digits removed. ``"change_infusion"``,
    ``"Change-Infusion"``, ``"change infusion"``, ``"ChangeInfusion"``,
    ``"change.infusion"``, ``"CHANGE__INFUSION"`` and the same name in
    full-width characters all reduce to ``"changeinfusion"``, so a declaration
    cannot slip past the forbidden-vocabulary check by case, separator or
    character width alone.
    """

    folded = unicodedata.normalize("NFKC", value).casefold()
    return _NON_TOKEN_CHARACTERS.sub("", folded)


#: Comparison tokens of the forbidden control vocabulary.
_FORBIDDEN_CONTROL_TOKENS: frozenset[str] = frozenset(
    normalize_capability_token(value) for value in FORBIDDEN_CONTROL_CAPABILITIES
)


def is_forbidden_control_capability(value: str) -> bool:
    """Return ``True`` when ``value`` names a forbidden therapy/control action,
    however it is spelled (see :func:`normalize_capability_token`)."""

    return normalize_capability_token(value) in _FORBIDDEN_CONTROL_TOKENS


class TransportKind(StrEnum):
    """Physical or logical transport an Adaptix Transport Driver speaks.

    The Synapse core names transports only through this vocabulary; operating
    system device paths (COM ports, ``/dev/tty*``, Android Bluetooth handles,
    Windows device paths) belong inside a concrete ``TransportAdapter``
    configuration, never in the core contract.

    ``SDC`` exists so an IEEE 11073 SDC research capture is labelled truthfully;
    sdc11073 remains research-only and has no production transport driver.
    """

    BLE = "ble"
    USB = "usb"
    SERIAL = "serial"
    TCP = "tcp"
    UDP = "udp"
    WIFI = "wifi"
    MQTT = "mqtt"
    HTTP = "http"
    WEBHOOK = "webhook"
    SFTP = "sftp"
    FILE = "file"
    DIRECTORY_WATCH = "directory_watch"
    VENDOR_CLOUD = "vendor_cloud"
    SDC = "sdc"


class ProtocolKind(StrEnum):
    """Data protocol an Adaptix Protocol Driver decodes.

    Protocol drivers sit directly above transport drivers: every manufacturer
    and protocol difference terminates in one of these drivers, and nothing
    above it sees anything but canonical Synapse contracts.

    * ``HL7_DEVICE`` - HL7 v2 device data (for example ORU^R01 observation
      feeds).
    * ``IEEE_11073_PHD`` - IEEE 11073-20601 / Bluetooth SIG personal-health
      device profiles, where technically applicable.
    * ``STRUCTURED_JSON`` / ``STRUCTURED_XML`` / ``STRUCTURED_CSV`` - structured
      exports and feeds.
    * ``IMAGE_DOCUMENT`` - images and documents (12-lead PDFs, monitor stills).
    * ``WAVEFORM_STREAM`` - continuous waveform sample streams.
    * ``ADAPTIX_REFERENCE`` - the first-party Adaptix Reference Protocol spoken
      by the Adaptix Synapse Reference Device.
    """

    HL7_DEVICE = "hl7_device"
    IEEE_11073_PHD = "ieee_11073_phd"
    STRUCTURED_JSON = "structured_json"
    STRUCTURED_XML = "structured_xml"
    STRUCTURED_CSV = "structured_csv"
    IMAGE_DOCUMENT = "image_document"
    WAVEFORM_STREAM = "waveform_stream"
    ADAPTIX_REFERENCE = "adaptix_reference"


class SynapseConnectionState(StrEnum):
    """Connection state of a device link or a Synapse Edge transport.

    * ``CONNECTED`` - data is flowing.
    * ``DEGRADED`` - connected, but losing or delaying data.
    * ``RECONNECTING`` - the link dropped and the driver is re-establishing it.
    * ``DISCONNECTED`` - no link; nothing is flowing.
    """

    CONNECTED = "connected"
    DEGRADED = "degraded"
    RECONNECTING = "reconnecting"
    DISCONNECTED = "disconnected"


class DriverPackTier(StrEnum):
    """Who a Synapse driver pack belongs to.

    * ``FIRST_PARTY`` - an Adaptix-owned transport/protocol driver pack
      (including the Adaptix Reference Protocol). Adaptix builds and certifies
      it on its own production certification infrastructure, so it can never
      wait on an outside party.
    * ``OPTIONAL_COMPAT`` - an optional manufacturer compatibility pack (ids of
      the form ``COMPAT-<NAME>-<NNN>``). It is an interoperability extension
      certified independently when enabled; its absence never blocks or lowers
      the readiness of any first-party Adaptix capability.
    """

    FIRST_PARTY = "first_party"
    OPTIONAL_COMPAT = "optional_compat"


class DriverPackSupportStatus(StrEnum):
    """Certification/enablement status of one Synapse driver pack.

    This is not the release lifecycle of a registered connector (that is
    ``SupportStatus`` in Adaptix-Integrations-Service ``connector_sdk``); it is
    whether the pack is enabled and certified for use.

    * ``NOT_CONFIGURED`` - not enabled.
    * ``WAITING_EXTERNAL_ACCESS`` - an optional pack waiting on access an
      outside party controls (equipment, documentation, a sandbox).
    * ``WAITING_EXTERNAL_CREDENTIAL`` - an optional pack waiting on a
      credential an outside party issues.
    * ``IN_CERTIFICATION`` - enabled and running certification scenarios.
    * ``CERTIFIED`` - passed certification. The ONLY status in which a pack,
      or the equipment it decodes, may be described as supported.
    * ``CERTIFICATION_FAILED`` - certification ran and failed.
    * ``SUSPENDED`` - certification withdrawn; the pack must not be used.
    """

    NOT_CONFIGURED = "not_configured"
    WAITING_EXTERNAL_ACCESS = "waiting_external_access"
    WAITING_EXTERNAL_CREDENTIAL = "waiting_external_credential"
    IN_CERTIFICATION = "in_certification"
    CERTIFIED = "certified"
    CERTIFICATION_FAILED = "certification_failed"
    SUSPENDED = "suspended"


#: Statuses that mean "waiting on an outside party". Only an
#: ``OPTIONAL_COMPAT`` pack may be in one; a first-party pack never waits on
#: anyone outside Adaptix.
EXTERNAL_WAIT_DRIVER_PACK_STATUSES: frozenset[DriverPackSupportStatus] = frozenset(
    {
        DriverPackSupportStatus.WAITING_EXTERNAL_ACCESS,
        DriverPackSupportStatus.WAITING_EXTERNAL_CREDENTIAL,
    }
)


class EdgeRuntimeHealth(StrEnum):
    """Self-reported health of one Synapse Edge runtime instance.

    * ``HEALTHY`` - capturing, spooling and replaying normally.
    * ``DEGRADED`` - running, but a transport, the spool or the uplink is
      impaired (records may be delayed, none are being lost).
    * ``UNHEALTHY`` - the runtime cannot guarantee capture or spooling.
    """

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class EdgeClockSource(StrEnum):
    """Where a Synapse Edge instance's wall clock is disciplined from.

    ``UNSYNCHRONIZED`` is the truthful value when the host clock has no
    external reference; the Time Authority then treats edge capture times as
    estimates rather than trusted instants.
    """

    NTP = "ntp"
    GNSS = "gnss"
    CELLULAR_NETWORK = "cellular_network"
    ADAPTIX_TIME_AUTHORITY = "adaptix_time_authority"
    UNSYNCHRONIZED = "unsynchronized"


class DeploymentProfile(StrEnum):
    """Where a Synapse Edge runtime instance is deployed.

    Synapse Edge is a hardware-independent runtime contract; the profile
    records the host class so fleet validation can reason about it. It never
    changes the wire contract.
    """

    WINDOWS_MDT = "windows_mdt"
    LINUX_GATEWAY = "linux_gateway"
    ANDROID_FIELD = "android_field"


class SynapseMeasurementValidity(StrEnum):
    """Device-reported validity of one measurement.

    Modelled on the manufacturer-neutral IEEE 11073-10207 (SDC)
    ``MeasurementValidity`` vocabulary, so every adapter maps its native
    quality indicator into one shared set.
    """

    VALID = "valid"
    VALIDATED = "validated"
    ONGOING = "ongoing"
    QUESTIONABLE = "questionable"
    CALIBRATION_ONGOING = "calibration_ongoing"
    INVALID = "invalid"
    OVERFLOW = "overflow"
    UNDERFLOW = "underflow"
    NOT_AVAILABLE = "not_available"


class SynapseQualityFlag(StrEnum):
    """Normalisation-time quality annotations on a signal envelope.

    * ``STORE_AND_FORWARD`` - delivered after an offline buffer (edge replay).
    * ``RENORMALIZED`` - produced by re-normalising stored evidence.
    * ``OUT_OF_ORDER`` - arrived after a later signal of the same stream.
    * ``CLOCK_DRIFT_DETECTED`` - the device clock disagreed with the Adaptix
      reference clock beyond tolerance.
    * ``PROBABLE_DUPLICATE`` / ``CONFLICTING_OBSERVATION`` /
      ``INDEPENDENT_CORROBORATION`` - the multi-rail resolution outcome
      (:class:`SynapseRailResolution`) recorded on the later arrival.
    """

    STORE_AND_FORWARD = "store_and_forward"
    RENORMALIZED = "renormalized"
    OUT_OF_ORDER = "out_of_order"
    CLOCK_DRIFT_DETECTED = "clock_drift_detected"
    PROBABLE_DUPLICATE = "probable_duplicate"
    CONFLICTING_OBSERVATION = "conflicting_observation"
    INDEPENDENT_CORROBORATION = "independent_corroboration"


class SynapseAlertPriority(StrEnum):
    """Alarm priority, per the IEC 60601-1-8 low/medium/high scheme."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SynapseAlertCondition(StrEnum):
    """Whether an alarm concerns the patient or the device (IEC 60601-1-8)."""

    PHYSIOLOGICAL = "physiological"
    TECHNICAL = "technical"


class SynapseAlertState(StrEnum):
    """Lifecycle state of a device alarm as the device reported it."""

    ACTIVE = "active"
    SILENCED = "silenced"
    RESOLVED = "resolved"


class SynapseTherapyEventPhase(StrEnum):
    """What the device REPORTS happened to a therapy it delivered.

    A therapy event is a record of what occurred on the device (for example
    a shock the clinician delivered), never an instruction to the device.
    """

    DELIVERED = "delivered"
    STARTED = "started"
    STOPPED = "stopped"
    SETTING_CHANGED = "setting_changed"
    ABORTED = "aborted"


class SynapseWaveformEncoding(StrEnum):
    """Sample encoding of a waveform segment stored as device evidence."""

    INT16_LE = "int16_le"
    INT32_LE = "int32_le"
    FLOAT32_LE = "float32_le"
    FLOAT64_LE = "float64_le"


class SynapseSessionType(StrEnum):
    """What a device session was used for.

    ``UNCLASSIFIED`` is the truthful value when the device does not say; a
    consumer must never treat it as ``CLINICAL`` without a human decision.
    """

    CLINICAL = "clinical"
    DEVICE_CHECK = "device_check"
    TRAINING = "training"
    UNCLASSIFIED = "unclassified"


class SynapseSessionState(StrEnum):
    """Lifecycle state of a device session."""

    OPEN = "open"
    CLOSED = "closed"
    TIMED_OUT = "timed_out"


class SynapseReplayReason(StrEnum):
    """Why stored device evidence is being re-normalised."""

    NORMALIZATION_UPGRADE = "normalization_upgrade"
    ADAPTER_DEFECT_CORRECTION = "adapter_defect_correction"
    AUDIT_VERIFICATION = "audit_verification"


class SynapseReplayStatus(StrEnum):
    """Outcome of a re-normalisation replay. Partial failure is explicit."""

    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"


class EdgeRecordOutcome(StrEnum):
    """Per-record outcome in an :class:`~adaptix_contracts.synapse.edge.EdgeBatchAck`.

    ``ACCEPTED`` and ``DUPLICATE`` both mean the cloud durably holds the
    record, so the edge may clean up its local copy. ``REJECTED`` means it
    does not; the edge must keep the record.
    """

    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"


class EdgeRecordRejectionReason(StrEnum):
    """Why the cloud refused one edge record.

    * ``INVALID_ENVELOPE`` - the record failed contract validation.
    * ``UNKNOWN_DEVICE`` - no persisted Device row for ``device_id``.
    * ``TENANT_MISMATCH`` - the envelope tenant is not the device's owner.
    * ``IDEMPOTENCY_CONFLICT`` - the idempotency key was already used for
      DIFFERENT content (a true retransmission is ``DUPLICATE``, not this).
    * ``EVIDENCE_NOT_RECEIVED`` - the record references evidence the cloud
      does not hold yet; upload the evidence, then resend.
    * ``CAPABILITY_NOT_DECLARED`` - the device genome does not declare the
      capability this signal kind requires.
    """

    INVALID_ENVELOPE = "invalid_envelope"
    UNKNOWN_DEVICE = "unknown_device"
    TENANT_MISMATCH = "tenant_mismatch"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    EVIDENCE_NOT_RECEIVED = "evidence_not_received"
    CAPABILITY_NOT_DECLARED = "capability_not_declared"


#: Rejections the edge may resolve and resend. Every other reason is terminal
#: for that record: the edge keeps it and surfaces it, it does not retry it.
RETRYABLE_EDGE_REJECTIONS: frozenset[EdgeRecordRejectionReason] = frozenset(
    {EdgeRecordRejectionReason.EVIDENCE_NOT_RECEIVED}
)


class SynapseReplayFailureReason(StrEnum):
    """Why one evidence object could not be re-normalised during a replay."""

    EVIDENCE_NOT_FOUND = "evidence_not_found"
    EVIDENCE_HASH_MISMATCH = "evidence_hash_mismatch"
    DECODE_FAILED = "decode_failed"
    ADAPTER_VERSION_UNAVAILABLE = "adapter_version_unavailable"


class EdgeProtocolRefusalReason(StrEnum):
    """Why the cloud refused an edge protocol offer."""

    NO_COMMON_VERSION = "no_common_version"
    RUNTIME_VERSION_UNSUPPORTED = "runtime_version_unsupported"


#: The device capability each signal kind requires. ``DEVICE_STATE`` needs
#: none: every device may report its own operational state.
SIGNAL_KIND_REQUIRED_CAPABILITY: Mapping[
    SynapseSignalKind, SynapseDeviceCapability | None
] = MappingProxyType(
    {
        SynapseSignalKind.OBSERVATION: SynapseDeviceCapability.OBSERVATIONS,
        SynapseSignalKind.WAVEFORM: SynapseDeviceCapability.WAVEFORMS,
        SynapseSignalKind.ALERT: SynapseDeviceCapability.ALERTS,
        SynapseSignalKind.THERAPY_EVENT: SynapseDeviceCapability.THERAPY_EVENTS,
        SynapseSignalKind.DOCUMENT: SynapseDeviceCapability.DOCUMENTS,
        SynapseSignalKind.IMAGE: SynapseDeviceCapability.IMAGES,
        SynapseSignalKind.VENTILATOR_STATE: (
            SynapseDeviceCapability.VENTILATOR_TELEMETRY
        ),
        SynapseSignalKind.PUMP_STATE: SynapseDeviceCapability.PUMP_TELEMETRY,
        SynapseSignalKind.TEMPERATURE: SynapseDeviceCapability.TEMPERATURE,
        SynapseSignalKind.DIAGNOSTIC: SynapseDeviceCapability.DIAGNOSTICS,
        SynapseSignalKind.DEVICE_STATE: None,
    }
)


__all__ = [
    "EXTERNAL_WAIT_DRIVER_PACK_STATUSES",
    "FORBIDDEN_CONTROL_CAPABILITIES",
    "RETRYABLE_EDGE_REJECTIONS",
    "SIGNAL_KIND_REQUIRED_CAPABILITY",
    "DeploymentProfile",
    "DriverPackSupportStatus",
    "DriverPackTier",
    "EdgeClockSource",
    "EdgeProtocolRefusalReason",
    "EdgeRecordOutcome",
    "EdgeRecordRejectionReason",
    "EdgeRuntimeHealth",
    "ProtocolKind",
    "SynapseAlertCondition",
    "SynapseAlertPriority",
    "SynapseAlertState",
    "SynapseConnectionState",
    "SynapseDeviceCapability",
    "SynapseForbiddenControlCapability",
    "SynapseMeasurementValidity",
    "SynapseQualityFlag",
    "SynapseRailResolution",
    "SynapseRailType",
    "SynapseReplayFailureReason",
    "SynapseReplayReason",
    "SynapseReplayStatus",
    "SynapseSessionState",
    "SynapseSessionType",
    "SynapseSignalKind",
    "SynapseTherapyEventPhase",
    "SynapseTimeQuality",
    "SynapseWaveformEncoding",
    "TransportKind",
    "is_forbidden_control_capability",
    "normalize_capability_token",
]
