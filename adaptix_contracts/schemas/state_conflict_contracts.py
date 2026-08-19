"""Protected-state conflict contracts — shared platform primitive G.

Some AdaptixCore records must never be silently overwritten by a second writer:
a locked chart, a submitted claim, a posted payment, a destroyed vial, a
completed signature, a revoked credential, an effective protocol, an effective
rule pack. Losing one of those updates is not a UX annoyance; it is a falsified
clinical, financial, or custody record.

The rule is therefore uniform across the platform: every write to a protected
record carries the ``state_version`` the writer believed it was changing, the
update is applied conditionally on that version, and a mismatch returns
``409 Conflict`` rather than winning.

    UPDATE protected_resource
       SET status = :new_status,
           state_version = state_version + 1
     WHERE id = :id
       AND tenant_id = :tenant_id
       AND state_version = :expected_version;

If that statement affects zero rows, the write lost the race and the caller must
be told. Read-then-write, last-write-wins, and CRDT merge are all forbidden here
— they are correct for collaborative text and wrong for a controlled-substance
ledger.

Relationship to continuity
--------------------------
``adaptix_contracts.schemas.continuity_contracts.ConflictResponse`` covers a
different axis: the ``sync_version`` of a shared *workspace* being edited by
several devices, where a merge is often the right answer. This module covers the
``state_version`` of a *protected domain record*, where a merge never is. Both
exist on purpose; neither replaces the other.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProtectedStateKind(str, Enum):
    """Record states that must never be silently overwritten.

    Each value names a state a record can be *in*, not the record type: a chart
    is only protected once ``CHART_LOCKED``, and a draft chart is ordinary
    mutable data.
    """

    CHART_LOCKED = "chart.locked"
    CLAIM_SUBMITTED = "claim.submitted"
    PAYMENT_POSTED = "payment.posted"
    VIAL_DESTROYED = "vial.destroyed"
    SIGNATURE_COMPLETED = "signature.completed"
    CREDENTIAL_REVOKED = "credential.revoked"
    PROTOCOL_EFFECTIVE = "protocol.effective"
    RULE_PACK_EFFECTIVE = "rule_pack.effective"


class ProtectedStateWrite(BaseModel):
    """A conditional write against a protected record.

    ``expected_state_version`` is required and has no default. A default would
    let a caller omit it and silently get last-write-wins, which is exactly the
    failure this contract exists to prevent.
    """

    model_config = ConfigDict(extra="forbid")

    tenant_id: str = Field(..., min_length=1)
    resource_type: str = Field(..., min_length=1)
    resource_id: str = Field(..., min_length=1)
    protected_state: ProtectedStateKind
    expected_state_version: int = Field(
        ...,
        ge=0,
        description="Version the writer read; the update applies only against it",
    )
    actor_id: str = Field(
        ..., min_length=1, description="Server-derived identity of the writer"
    )
    correlation_id: str = Field(..., min_length=1)
    idempotency_key: str | None = Field(
        default=None,
        description="Set when the same logical write may legitimately be retried",
    )


class StateConflict(BaseModel):
    """The 409 body returned when a protected write lost the race.

    ``current_state_version`` lets the client re-read exactly once and retry
    deliberately. ``conflicting_fields`` is advisory: it tells a user what
    changed underneath them so they can decide, and never authorises an
    automatic merge.
    """

    model_config = ConfigDict(extra="forbid")

    tenant_id: str = Field(..., min_length=1)
    resource_type: str = Field(..., min_length=1)
    resource_id: str = Field(..., min_length=1)
    protected_state: ProtectedStateKind
    expected_state_version: int = Field(..., ge=0)
    current_state_version: int = Field(..., ge=0)
    conflicting_fields: list[str] = Field(default_factory=list)
    detected_at: datetime
    correlation_id: str = Field(..., min_length=1)
    message: str = Field(
        default="The record changed after it was loaded.",
        min_length=1,
        description="Operator-facing text. No protected data.",
    )
    server_state: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Non-protected summary of what the server now holds, for display. "
            "Never the full record: this response crosses to the client and into "
            "logs."
        ),
    )

    @model_validator(mode="after")
    def _versions_must_actually_conflict(self) -> StateConflict:
        if self.current_state_version == self.expected_state_version:
            raise ValueError(
                "expected_state_version equals current_state_version: this is not a "
                "conflict and must not be reported as one"
            )
        return self


def has_state_conflict(expected_state_version: int, current_state_version: int) -> bool:
    """Return ``True`` when a conditional write must be rejected.

    Any difference is a conflict, including a *lower* current version. A record
    whose version went backwards has been restored or rewritten underneath the
    writer, which is at least as dangerous as an ordinary lost update.
    """

    return expected_state_version != current_state_version


def next_state_version(current_state_version: int) -> int:
    """Return the version a successful protected write must store.

    Monotonic increment by one. Never a timestamp, a hash, or a client-supplied
    value: the comparison in the ``WHERE`` clause is only meaningful if the
    server alone advances it.
    """

    if current_state_version < 0:
        raise ValueError("state_version must not be negative")
    return current_state_version + 1


__all__ = [
    "ProtectedStateKind",
    "ProtectedStateWrite",
    "StateConflict",
    "has_state_conflict",
    "next_state_version",
]
