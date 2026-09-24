"""Device session reference contract (SYN-001).

A device session is one continuous use of a device as the device itself
reports it (for example a monitor "case" from power-on to power-off). The
Device service owns sessions; this contract is how other services refer to
one.

No PHI. A session never carries a patient name, identifier or chart number.
The link to patient care is an opaque, optional SHA-256 pairing reference
(``care_pairing_reference_sha256``) that only the service holding the pairing
can resolve; the legal chart association itself is owned by the ePCR service.
"""

from __future__ import annotations

from pydantic import AwareDatetime, model_validator

from adaptix_contracts.synapse.enums import SynapseSessionState, SynapseSessionType
from adaptix_contracts.synapse.provenance import (
    ExternalKey,
    Sha256Hex,
    SynapseId,
    SynapseModel,
)


class DeviceSessionReference(SynapseModel):
    """A reference to one device session.

    ``external_session_key`` is the device-native session/case key as the
    adapter decoded it, kept so the same session arriving on two rails
    resolves to one reference. Timestamps are timezone-aware; an ``OPEN``
    session has no ``ended_at`` and a ``CLOSED`` one must have it.
    """

    id: SynapseId
    tenant_id: SynapseId
    device_id: SynapseId
    external_session_key: ExternalKey
    session_type: SynapseSessionType
    started_at: AwareDatetime
    ended_at: AwareDatetime | None = None
    state: SynapseSessionState
    first_signal_at: AwareDatetime | None = None
    last_signal_at: AwareDatetime | None = None
    primary_rail_id: SynapseId
    assigned_unit_id: SynapseId | None = None
    care_pairing_reference_sha256: Sha256Hex | None = None

    @model_validator(mode="after")
    def _lifecycle_is_consistent(self) -> DeviceSessionReference:
        if self.state is SynapseSessionState.OPEN and self.ended_at is not None:
            raise ValueError("an OPEN session cannot have ended_at")
        if self.state is SynapseSessionState.CLOSED and self.ended_at is None:
            raise ValueError("a CLOSED session requires ended_at")
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("ended_at precedes started_at")
        if (self.first_signal_at is None) != (self.last_signal_at is None):
            raise ValueError(
                "first_signal_at and last_signal_at are set together: a session "
                "either has received signals or it has not"
            )
        if (
            self.first_signal_at is not None
            and self.last_signal_at is not None
            and self.last_signal_at < self.first_signal_at
        ):
            raise ValueError("last_signal_at precedes first_signal_at")
        return self


__all__ = ["DeviceSessionReference"]
