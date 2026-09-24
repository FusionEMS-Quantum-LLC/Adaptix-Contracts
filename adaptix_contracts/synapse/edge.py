"""Adaptix Synapse Edge protocol contracts (SYN-001).

Synapse Edge is a hardware-independent runtime (deployed as a
:class:`~adaptix_contracts.synapse.enums.DeploymentProfile`) that captures
device signals through Adaptix transport and protocol drivers, spools every
record locally and immutably, and replays the spool to the cloud in order,
idempotently, after any period offline. These are the shapes it exchanges with
the cloud side (Adaptix-Device-Service).

It is NOT the apparatus compute-node registry: that is
:mod:`adaptix_contracts.edge` (Adaptix-Edge-Service). A Synapse Edge instance
may run on such a node, on a Windows MDT or on an Android field device.

Authentication and tenancy
--------------------------
No model here carries a tenant or a credential. Every Synapse Edge instance
authenticates with its OWN per-instance credential through the existing device
credential / proof-of-possession / edge certificate mechanisms, never the
shared platform ingest token; the cloud derives the tenant from that credential
and from the persisted ``Device`` row, and treats the envelope's ``tenant_id``
as a claim to verify.

Ordering, acknowledgement and cleanup
-------------------------------------
* ``local_sequence`` is assigned by the edge when a record enters its spool:
  strictly increasing per ``edge_instance_id``, starting at 1, never reused.
  A re-installed runtime is a new instance with a new id and a new sequence.
* An :class:`EdgeBatch` carries records in ascending ``local_sequence``.
* An :class:`EdgeBatchAck` answers every record in the batch exactly once
  (``ACCEPTED`` / ``DUPLICATE`` / ``REJECTED``) and reports
  ``highest_contiguous_acknowledged_sequence``: the largest ``N`` such that
  every record of this instance with ``local_sequence <= N`` has a FINAL
  disposition. Final means accepted, duplicate, or rejected for a reason that
  is not retryable (:data:`~adaptix_contracts.synapse.enums.RETRYABLE_EDGE_REJECTIONS`).
  The edge resumes replay at ``N + 1``.
* The edge may delete its local copy of a record only when it was
  ``ACCEPTED`` or ``DUPLICATE`` (the cloud durably holds it). A terminally
  rejected record is kept in local quarantine and surfaced
  (``quarantined_record_count`` in the heartbeat), never silently dropped and
  never retried.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Annotated

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from adaptix_contracts.synapse.enums import (
    RETRYABLE_EDGE_REJECTIONS,
    DeploymentProfile,
    EdgeClockSource,
    EdgeProtocolRefusalReason,
    EdgeRecordOutcome,
    EdgeRecordRejectionReason,
    EdgeRuntimeHealth,
    ProtocolKind,
    SynapseConnectionState,
    TransportKind,
)
from adaptix_contracts.synapse.provenance import (
    AdapterKey,
    CorrelationId,
    ExternalKey,
    SemanticVersion,
    Sha256Hex,
    SynapseId,
)
from adaptix_contracts.synapse.signals import (
    MAX_CLOCK_OFFSET_MS,
    ClinicalSignalEnvelope,
)

#: ``MAJOR.MINOR`` version of the Synapse Edge wire protocol.
EdgeProtocolVersion = Annotated[
    str,
    StringConstraints(max_length=16, pattern=r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$"),
]

#: The edge protocol version this package defines.
SYNAPSE_EDGE_PROTOCOL_VERSION = "1.0"

#: Every edge protocol version this package can express, oldest first.
SUPPORTED_EDGE_PROTOCOL_VERSIONS: tuple[str, ...] = (SYNAPSE_EDGE_PROTOCOL_VERSION,)

#: Most records one :class:`EdgeBatch` (and so one :class:`EdgeBatchAck`) holds.
EDGE_BATCH_MAX_RECORDS = 500

_STRICT = ConfigDict(extra="forbid", frozen=True)


def _version_key(version: str) -> tuple[int, int]:
    major, minor = version.split(".")
    return int(major), int(minor)


def _check_unique(name: str, values: list[object]) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must not repeat")


def select_edge_protocol_version(
    offered: Iterable[str], supported: Iterable[str]
) -> str | None:
    """The negotiation rule: the HIGHEST version both sides support, else ``None``.

    Both the cloud (deciding) and the edge (checking the decision it received)
    apply this same rule, so a negotiation can never silently settle on an
    older version than both sides share.
    """

    common = set(offered) & set(supported)
    if not common:
        return None
    return max(common, key=_version_key)


def advance_contiguous_watermark(
    previous: int, finalized_sequences: Iterable[int]
) -> int:
    """Advance ``highest_contiguous_acknowledged_sequence``.

    ``previous`` is the current watermark (0 before anything is finalized);
    ``finalized_sequences`` are local sequences of this edge instance that now
    have a final disposition. The watermark moves forward only across an
    unbroken run: a single missing or retryable-rejected record stops it, so
    the edge replays from exactly the first record the cloud does not yet
    hold.
    """

    if previous < 0:
        raise ValueError("the watermark cannot be negative")
    done = set(finalized_sequences)
    watermark = previous
    while watermark + 1 in done:
        watermark += 1
    return watermark


class EdgeInstanceRegistration(BaseModel):
    """What a Synapse Edge instance declares when it registers.

    ``supported_protocol_versions`` are edge WIRE protocol versions;
    ``supported_transports`` and ``supported_protocols`` are the Adaptix
    transport and protocol drivers the runtime hosts.
    """

    model_config = _STRICT

    edge_instance_id: SynapseId
    deployment_profile: DeploymentProfile
    runtime_version: SemanticVersion
    supported_protocol_versions: list[EdgeProtocolVersion] = Field(
        min_length=1, max_length=16
    )
    supported_transports: list[TransportKind] = Field(min_length=1)
    supported_protocols: list[ProtocolKind] = Field(min_length=1)
    correlation_id: CorrelationId

    @model_validator(mode="after")
    def _no_repeats(self) -> EdgeInstanceRegistration:
        _check_unique(
            "supported_protocol_versions", list(self.supported_protocol_versions)
        )
        _check_unique("supported_transports", list(self.supported_transports))
        _check_unique("supported_protocols", list(self.supported_protocols))
        return self


class EdgeProtocolOffer(BaseModel):
    """Edge -> cloud: the protocol versions this instance can speak.

    ``edge_sent_at`` is the edge wall clock when the offer left; with the
    answer's ``server_received_at`` / ``server_sent_at`` and the edge's own
    receipt time it gives the edge a round-trip clock-offset estimate.
    """

    model_config = _STRICT

    edge_instance_id: SynapseId
    runtime_version: SemanticVersion
    offered_protocol_versions: list[EdgeProtocolVersion] = Field(
        min_length=1, max_length=16
    )
    edge_sent_at: AwareDatetime
    correlation_id: CorrelationId

    @model_validator(mode="after")
    def _no_repeats(self) -> EdgeProtocolOffer:
        _check_unique("offered_protocol_versions", list(self.offered_protocol_versions))
        return self


class EdgeProtocolNegotiation(BaseModel):
    """Cloud -> edge: the decision on one :class:`EdgeProtocolOffer`.

    Accepted: ``selected_protocol_version`` is set and no refusal reason.
    Refused: a ``refusal_reason`` and no selected version.
    """

    model_config = _STRICT

    edge_instance_id: SynapseId
    accepted: bool
    selected_protocol_version: EdgeProtocolVersion | None = None
    refusal_reason: EdgeProtocolRefusalReason | None = None
    server_received_at: AwareDatetime
    server_sent_at: AwareDatetime
    correlation_id: CorrelationId

    @model_validator(mode="after")
    def _decision_is_coherent(self) -> EdgeProtocolNegotiation:
        if self.accepted:
            if (
                self.selected_protocol_version is None
                or self.refusal_reason is not None
            ):
                raise ValueError(
                    "an accepted negotiation selects a version and has no refusal reason"
                )
        elif self.refusal_reason is None or self.selected_protocol_version is not None:
            raise ValueError(
                "a refused negotiation carries a refusal reason and no selected version"
            )
        if self.server_sent_at < self.server_received_at:
            raise ValueError("server_sent_at precedes server_received_at")
        return self

    def answers(self, offer: EdgeProtocolOffer) -> bool:
        """True when this decision is a valid answer to ``offer``: same
        instance, and an accepted version the edge actually offered."""

        if offer.edge_instance_id != self.edge_instance_id:
            return False
        if self.accepted:
            return self.selected_protocol_version in offer.offered_protocol_versions
        return True


class EdgeSignalRecord(BaseModel):
    """One spooled record: a canonical envelope plus its edge capture facts.

    The capture facts are the edge's own record of the capture and must agree
    with the envelope they wrap; a record whose outer and inner facts disagree
    is refused, because either copy could otherwise be silently wrong.

    * ``observed_at`` - the time the DEVICE reported (``None`` when the device
      reported none); equals ``envelope.device_observed_at``.
    * ``captured_at`` - the edge wall clock at capture; the edge is where
      Adaptix first receives the signal, so it equals
      ``envelope.adaptix_received_at``.
    * ``evidence_sha256`` - SHA-256 of the exact raw bytes the edge captured
      and spooled. When the envelope references stored evidence, that evidence
      IS these bytes, so the digests must match.
    """

    model_config = _STRICT

    edge_instance_id: SynapseId
    device_id: SynapseId
    device_session_id: SynapseId
    local_sequence: int = Field(ge=1)
    source_record_id: ExternalKey
    observed_at: AwareDatetime | None
    captured_at: AwareDatetime
    evidence_sha256: Sha256Hex
    idempotency_key: ExternalKey
    adapter_key: AdapterKey
    adapter_version: SemanticVersion
    correlation_id: CorrelationId
    envelope: ClinicalSignalEnvelope

    @model_validator(mode="after")
    def _capture_facts_match_envelope(self) -> EdgeSignalRecord:
        env = self.envelope
        mismatched = [
            name
            for name, outer, inner in (
                ("device_id", self.device_id, env.device_id),
                ("device_session_id", self.device_session_id, env.device_session_id),
                ("source_record_id", self.source_record_id, env.source_record_id),
                ("observed_at", self.observed_at, env.device_observed_at),
                ("captured_at", self.captured_at, env.adaptix_received_at),
                ("idempotency_key", self.idempotency_key, env.idempotency_key),
                ("adapter_key", self.adapter_key, env.adapter_key),
                ("adapter_version", self.adapter_version, env.adapter_version),
                ("correlation_id", self.correlation_id, env.correlation_id),
            )
            if outer != inner
        ]
        if (
            env.evidence_sha256 is not None
            and env.evidence_sha256 != self.evidence_sha256
        ):
            mismatched.append("evidence_sha256")
        if mismatched:
            raise ValueError(
                f"edge record capture facts disagree with its envelope: {mismatched}"
            )
        return self


class EdgeBatch(BaseModel):
    """Edge -> cloud: an ordered slice of the spool.

    ``batch_id`` makes the batch itself idempotent: re-sending a batch after a
    lost acknowledgement returns the same answers. Records all belong to this
    instance, ascend strictly by ``local_sequence`` and never repeat an
    idempotency key.
    """

    model_config = _STRICT

    batch_id: SynapseId
    edge_instance_id: SynapseId
    protocol_version: EdgeProtocolVersion
    sent_at: AwareDatetime
    records: list[EdgeSignalRecord] = Field(
        min_length=1, max_length=EDGE_BATCH_MAX_RECORDS
    )
    correlation_id: CorrelationId

    @model_validator(mode="after")
    def _ordered_single_instance(self) -> EdgeBatch:
        foreign = sorted(
            {r.edge_instance_id for r in self.records} - {self.edge_instance_id}
        )
        if foreign:
            raise ValueError(f"records from another edge instance: {foreign}")
        sequences = [r.local_sequence for r in self.records]
        if any(later <= earlier for earlier, later in zip(sequences, sequences[1:])):
            raise ValueError("records must ascend strictly by local_sequence")
        _check_unique("idempotency keys", [r.idempotency_key for r in self.records])
        return self


class EdgeRecordAck(BaseModel):
    """The cloud's answer for one record of an :class:`EdgeBatch`."""

    model_config = _STRICT

    local_sequence: int = Field(ge=1)
    idempotency_key: ExternalKey
    outcome: EdgeRecordOutcome
    rejection_reason: EdgeRecordRejectionReason | None = None

    @model_validator(mode="after")
    def _reason_matches_outcome(self) -> EdgeRecordAck:
        rejected = self.outcome is EdgeRecordOutcome.REJECTED
        if rejected != (self.rejection_reason is not None):
            raise ValueError("a rejection_reason is carried by, and only by, REJECTED")
        return self

    @property
    def releasable(self) -> bool:
        """True when the cloud durably holds the record, so the edge may
        delete its local copy."""

        return self.outcome in (EdgeRecordOutcome.ACCEPTED, EdgeRecordOutcome.DUPLICATE)

    @property
    def final(self) -> bool:
        """True when the record needs no resend: held, or rejected terminally."""

        return self.rejection_reason not in RETRYABLE_EDGE_REJECTIONS


class EdgeBatchAck(BaseModel):
    """Cloud -> edge: the per-record answers for one :class:`EdgeBatch`.

    ``highest_contiguous_acknowledged_sequence`` is this instance's watermark
    after the batch (see the module docstring; computed with
    :func:`advance_contiguous_watermark`). A record still awaiting a resend
    can never sit at or below it.
    """

    model_config = _STRICT

    batch_id: SynapseId
    edge_instance_id: SynapseId
    results: list[EdgeRecordAck] = Field(
        min_length=1, max_length=EDGE_BATCH_MAX_RECORDS
    )
    highest_contiguous_acknowledged_sequence: int = Field(ge=0)
    server_received_at: AwareDatetime
    correlation_id: CorrelationId

    @model_validator(mode="after")
    def _watermark_is_honest(self) -> EdgeBatchAck:
        _check_unique("result local_sequence", [r.local_sequence for r in self.results])
        pending = sorted(
            r.local_sequence
            for r in self.results
            if not r.final
            and r.local_sequence <= self.highest_contiguous_acknowledged_sequence
        )
        if pending:
            raise ValueError(
                "records awaiting resend cannot be at or below "
                f"highest_contiguous_acknowledged_sequence: {pending}"
            )
        return self

    def unanswered_local_sequences(self, batch: EdgeBatch) -> frozenset[int]:
        """Sequences in ``batch`` this ack does not answer (silently dropped).

        Raises ``ValueError`` when the ack is not for ``batch``, answers a
        record the batch did not contain, or names the wrong idempotency key
        for a sequence.
        """

        if (batch.batch_id, batch.edge_instance_id) != (
            self.batch_id,
            self.edge_instance_id,
        ):
            raise ValueError("ack does not answer this batch")
        sent = {r.local_sequence: r.idempotency_key for r in batch.records}
        for result in self.results:
            if result.local_sequence not in sent:
                raise ValueError(
                    f"ack answers local_sequence {result.local_sequence}, "
                    "which the batch did not contain"
                )
            if sent[result.local_sequence] != result.idempotency_key:
                raise ValueError(
                    f"ack for local_sequence {result.local_sequence} names a "
                    "different idempotency key than the batch record"
                )
        return frozenset(set(sent) - {r.local_sequence for r in self.results})

    def releasable_local_sequences(self) -> frozenset[int]:
        """Sequences whose local copy the edge may now delete."""

        return frozenset(r.local_sequence for r in self.results if r.releasable)


class EdgeClockMetadata(BaseModel):
    """The edge's account of its own wall clock.

    ``estimated_offset_ms`` is edge clock minus the Adaptix reference clock
    (positive: the edge runs ahead). ``estimated_uncertainty_ms`` bounds that
    estimate and is only carried with it.
    """

    model_config = _STRICT

    edge_clock_at: AwareDatetime
    clock_source: EdgeClockSource
    last_synchronized_at: AwareDatetime | None = None
    estimated_offset_ms: int | None = Field(
        default=None, ge=-MAX_CLOCK_OFFSET_MS, le=MAX_CLOCK_OFFSET_MS
    )
    estimated_uncertainty_ms: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _uncertainty_needs_offset(self) -> EdgeClockMetadata:
        if (
            self.estimated_uncertainty_ms is not None
            and self.estimated_offset_ms is None
        ):
            raise ValueError(
                "estimated_uncertainty_ms is only carried with estimated_offset_ms"
            )
        return self


class EdgeTransportStatus(BaseModel):
    """State of one transport driver hosted by the edge instance."""

    model_config = _STRICT

    transport: TransportKind
    state: SynapseConnectionState
    connected_device_count: int = Field(ge=0)
    last_activity_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def _disconnected_has_no_devices(self) -> EdgeTransportStatus:
        if (
            self.state is SynapseConnectionState.DISCONNECTED
            and self.connected_device_count != 0
        ):
            raise ValueError("a DISCONNECTED transport has no connected devices")
        return self


class EdgeHeartbeat(BaseModel):
    """Edge -> cloud: liveness, spool, clock and transport state.

    ``spool_depth`` counts records captured and not yet released (including
    quarantined ones); ``oldest_spooled_captured_at`` is present exactly when
    the spool is not empty. ``highest_spooled_sequence`` is the last
    ``local_sequence`` assigned (0 before the first record);
    ``highest_acknowledged_sequence`` is the watermark the edge last received
    and can never exceed it.
    """

    model_config = _STRICT

    edge_instance_id: SynapseId
    runtime_version: SemanticVersion
    protocol_version: EdgeProtocolVersion
    health: EdgeRuntimeHealth
    spool_depth: int = Field(ge=0)
    oldest_spooled_captured_at: AwareDatetime | None = None
    highest_spooled_sequence: int = Field(ge=0)
    highest_acknowledged_sequence: int = Field(ge=0)
    quarantined_record_count: int = Field(ge=0)
    clock: EdgeClockMetadata
    transport_states: list[EdgeTransportStatus] = Field(default_factory=list)
    correlation_id: CorrelationId

    @model_validator(mode="after")
    def _spool_is_coherent(self) -> EdgeHeartbeat:
        if (self.spool_depth == 0) != (self.oldest_spooled_captured_at is None):
            raise ValueError(
                "oldest_spooled_captured_at is present exactly when spool_depth > 0"
            )
        if self.highest_acknowledged_sequence > self.highest_spooled_sequence:
            raise ValueError(
                "highest_acknowledged_sequence cannot exceed highest_spooled_sequence"
            )
        if self.quarantined_record_count > self.spool_depth:
            raise ValueError("quarantined records are part of spool_depth")
        _check_unique("transport_states", [t.transport for t in self.transport_states])
        return self


__all__ = [
    "EDGE_BATCH_MAX_RECORDS",
    "SUPPORTED_EDGE_PROTOCOL_VERSIONS",
    "SYNAPSE_EDGE_PROTOCOL_VERSION",
    "EdgeBatch",
    "EdgeBatchAck",
    "EdgeClockMetadata",
    "EdgeHeartbeat",
    "EdgeInstanceRegistration",
    "EdgeProtocolNegotiation",
    "EdgeProtocolOffer",
    "EdgeProtocolVersion",
    "EdgeRecordAck",
    "EdgeSignalRecord",
    "EdgeTransportStatus",
    "advance_contiguous_watermark",
    "select_edge_protocol_version",
]
