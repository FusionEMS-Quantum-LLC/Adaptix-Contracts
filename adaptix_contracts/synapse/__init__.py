"""Adaptix Synapse Fabric canonical contracts (SYN-001).

LAW SYN-001: integrate capabilities, not manufacturers. Manufacturer and
protocol differences terminate at the Adaptix driver layer (transport and
protocol drivers in Adaptix-Integrations-Service ``connector_sdk``); above it
only these versioned capability, signal, evidence, session, provenance and
edge contracts exist. Nothing in this package names a manufacturer as a type,
and nothing expresses a command to a medical device: the medical-device
command plane is forbidden in v1.

Pipeline these contracts carry, end to end::

    Physical Source -> Synapse Edge -> Transport Driver -> Protocol Driver
    -> Device Genome -> Signal Compiler -> Evidence Ledger -> Device Truth
    -> Care Session Binder (ePCR) -> ePCR projection / downstream

This package defines shapes only; it runs no Synapse behaviour. Import from
the subpackage root::

    from adaptix_contracts.synapse import ClinicalSignalEnvelope, DeviceGenome
"""

from adaptix_contracts.synapse import devices as _devices
from adaptix_contracts.synapse import edge as _edge
from adaptix_contracts.synapse import enums as _enums
from adaptix_contracts.synapse import evidence as _evidence
from adaptix_contracts.synapse import provenance as _provenance
from adaptix_contracts.synapse import sessions as _sessions
from adaptix_contracts.synapse import signals as _signals

# Redundant aliases mark explicit re-exports, as in the package-root
# ``adaptix_contracts/__init__.py``. Each public name is declared once, in the
# ``__all__`` of the module that defines it; this package's ``__all__`` is
# assembled from those lists rather than restating them.
from adaptix_contracts.synapse.devices import (
    COMPAT_DRIVER_PACK_PREFIX as COMPAT_DRIVER_PACK_PREFIX,
    DeviceAdapterRef as DeviceAdapterRef,
    DeviceCapabilityProfile as DeviceCapabilityProfile,
    DeviceClass as DeviceClass,
    DeviceGenome as DeviceGenome,
    DeviceIdentity as DeviceIdentity,
    DriverPackId as DriverPackId,
    DriverPackSupport as DriverPackSupport,
    compute_physical_identity_hash as compute_physical_identity_hash,
)
from adaptix_contracts.synapse.edge import (
    EDGE_BATCH_MAX_RECORDS as EDGE_BATCH_MAX_RECORDS,
    EdgeBatch as EdgeBatch,
    EdgeBatchAck as EdgeBatchAck,
    EdgeClockMetadata as EdgeClockMetadata,
    EdgeHeartbeat as EdgeHeartbeat,
    EdgeInstanceRegistration as EdgeInstanceRegistration,
    EdgeProtocolNegotiation as EdgeProtocolNegotiation,
    EdgeProtocolOffer as EdgeProtocolOffer,
    EdgeProtocolVersion as EdgeProtocolVersion,
    EdgeRecordAck as EdgeRecordAck,
    EdgeSignalRecord as EdgeSignalRecord,
    EdgeTransportStatus as EdgeTransportStatus,
    SUPPORTED_EDGE_PROTOCOL_VERSIONS as SUPPORTED_EDGE_PROTOCOL_VERSIONS,
    SYNAPSE_EDGE_PROTOCOL_VERSION as SYNAPSE_EDGE_PROTOCOL_VERSION,
    advance_contiguous_watermark as advance_contiguous_watermark,
    select_edge_protocol_version as select_edge_protocol_version,
)
from adaptix_contracts.synapse.enums import (
    DeploymentProfile as DeploymentProfile,
    DriverPackSupportStatus as DriverPackSupportStatus,
    DriverPackTier as DriverPackTier,
    EXTERNAL_WAIT_DRIVER_PACK_STATUSES as EXTERNAL_WAIT_DRIVER_PACK_STATUSES,
    EdgeClockSource as EdgeClockSource,
    EdgeProtocolRefusalReason as EdgeProtocolRefusalReason,
    EdgeRecordOutcome as EdgeRecordOutcome,
    EdgeRecordRejectionReason as EdgeRecordRejectionReason,
    EdgeRuntimeHealth as EdgeRuntimeHealth,
    FORBIDDEN_CONTROL_CAPABILITIES as FORBIDDEN_CONTROL_CAPABILITIES,
    ProtocolKind as ProtocolKind,
    RETRYABLE_EDGE_REJECTIONS as RETRYABLE_EDGE_REJECTIONS,
    SIGNAL_KIND_REQUIRED_CAPABILITY as SIGNAL_KIND_REQUIRED_CAPABILITY,
    SynapseAlertCondition as SynapseAlertCondition,
    SynapseAlertPriority as SynapseAlertPriority,
    SynapseAlertState as SynapseAlertState,
    SynapseConnectionState as SynapseConnectionState,
    SynapseDeviceCapability as SynapseDeviceCapability,
    SynapseForbiddenControlCapability as SynapseForbiddenControlCapability,
    SynapseMeasurementValidity as SynapseMeasurementValidity,
    SynapseQualityFlag as SynapseQualityFlag,
    SynapseRailResolution as SynapseRailResolution,
    SynapseRailType as SynapseRailType,
    SynapseReplayFailureReason as SynapseReplayFailureReason,
    SynapseReplayReason as SynapseReplayReason,
    SynapseReplayStatus as SynapseReplayStatus,
    SynapseSessionState as SynapseSessionState,
    SynapseSessionType as SynapseSessionType,
    SynapseSignalKind as SynapseSignalKind,
    SynapseTherapyEventPhase as SynapseTherapyEventPhase,
    SynapseTimeQuality as SynapseTimeQuality,
    SynapseWaveformEncoding as SynapseWaveformEncoding,
    TransportKind as TransportKind,
    is_forbidden_control_capability as is_forbidden_control_capability,
    normalize_capability_token as normalize_capability_token,
)
from adaptix_contracts.synapse.evidence import (
    DeviceEvidenceReference as DeviceEvidenceReference,
    EVIDENCE_LEDGER_HASH_DOMAIN as EVIDENCE_LEDGER_HASH_DOMAIN,
    EVIDENCE_MAX_BYTE_SIZE as EVIDENCE_MAX_BYTE_SIZE,
    EvidenceUploadAuthorizationRequest as EvidenceUploadAuthorizationRequest,
    EvidenceUploadAuthorizationResponse as EvidenceUploadAuthorizationResponse,
    StorageKey as StorageKey,
    compute_evidence_ledger_entry_sha256 as compute_evidence_ledger_entry_sha256,
)
from adaptix_contracts.synapse.provenance import (
    AdapterKey as AdapterKey,
    CanonicalCode as CanonicalCode,
    CorrelationId as CorrelationId,
    ExternalKey as ExternalKey,
    MediaType as MediaType,
    REPLAY_MAX_EVIDENCE_IDS as REPLAY_MAX_EVIDENCE_IDS,
    ReplayEvidenceFailure as ReplayEvidenceFailure,
    ReplayRequest as ReplayRequest,
    ReplayResult as ReplayResult,
    SemanticVersion as SemanticVersion,
    Sha256Hex as Sha256Hex,
    SignalProvenance as SignalProvenance,
    SynapseId as SynapseId,
)
from adaptix_contracts.synapse.sessions import (
    DeviceSessionReference as DeviceSessionReference,
)
from adaptix_contracts.synapse.signals import (
    AlertPayload as AlertPayload,
    ClinicalSignalEnvelope as ClinicalSignalEnvelope,
    DeviceBatteryState as DeviceBatteryState,
    DeviceStatePayload as DeviceStatePayload,
    DocumentReferencePayload as DocumentReferencePayload,
    MAX_CLOCK_OFFSET_MS as MAX_CLOCK_OFFSET_MS,
    ObservationPayload as ObservationPayload,
    ObservationReferenceRange as ObservationReferenceRange,
    SIGNAL_KIND_PAYLOAD_TYPES as SIGNAL_KIND_PAYLOAD_TYPES,
    SYNAPSE_SIGNAL_SCHEMA_VERSION as SYNAPSE_SIGNAL_SCHEMA_VERSION,
    SignalQuantity as SignalQuantity,
    SynapseSignalPayload as SynapseSignalPayload,
    TherapyEventPayload as TherapyEventPayload,
    UcumUnit as UcumUnit,
    WaveformCalibration as WaveformCalibration,
    WaveformReferencePayload as WaveformReferencePayload,
)

__all__: list[str] = []
__all__ += _devices.__all__
__all__ += _edge.__all__
__all__ += _enums.__all__
__all__ += _evidence.__all__
__all__ += _provenance.__all__
__all__ += _sessions.__all__
__all__ += _signals.__all__
