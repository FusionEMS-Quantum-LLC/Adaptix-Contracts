"""Provider adapter contracts — shared platform primitive D.

Every external provider AdaptixCore talks to — clearinghouses, signature
services, mail, telephony, QHIN partners, payers — is an unreliable boundary
that can succeed at the transport level while doing nothing, or do something
while failing to tell us.

The single most expensive mistake this contract exists to prevent:

    a provider HTTP 200 is not a business outcome.

So the record below keeps the two apart. :class:`ProviderTransportResult` is
what the wire said. :class:`ProviderOperationState` is what it means for the
domain. A transport success maps to ``ACCEPTED`` — the provider took the
request — never to ``COMPLETED``, which only a later authoritative provider
response establishes.

The second mistake: a timeout treated as a failure. An ambiguous outcome is
``UNKNOWN``; retrying it blindly is how a claim gets submitted twice and a
payment gets posted twice. ``UNKNOWN`` must be resolved by reconciliation
against the provider, not by guessing — which is why
:func:`requires_reconciliation` exists and why
:func:`is_safe_to_retry_without_idempotency` answers ``False`` for it.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProviderOperationState(str, Enum):
    """Canonical, provider-independent state of one provider operation.

    * ``REQUESTED`` — we are about to call, or the call is in flight.
    * ``ACCEPTED`` — the provider took the request. Nothing about the business
      outcome is known yet.
    * ``REJECTED`` — the provider refused it. Terminal without reconciliation.
    * ``PENDING`` — the provider acknowledged and is still working.
    * ``COMPLETED`` — the provider reported an authoritative successful outcome.
    * ``FAILED`` — the provider reported an authoritative failure.
    * ``UNKNOWN`` — we do not know. Timeout, connection reset, ambiguous
      response. The dangerous one: the operation may or may not have happened.
    * ``RECONCILIATION_REQUIRED`` — we know our state and the provider's
      disagree and a reconciliation pass must settle it.
    """

    REQUESTED = "requested"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    UNKNOWN = "unknown"
    RECONCILIATION_REQUIRED = "reconciliation_required"


class ProviderRetryability(str, Enum):
    """Whether the operation may be retried, and how.

    ``RETRY_AFTER`` is separate from ``RETRYABLE`` because a provider that told
    us when to come back (rate limit, maintenance window) must be obeyed rather
    than backed off against with our own guess.
    """

    RETRYABLE = "retryable"
    RETRY_AFTER = "retry_after"
    NOT_RETRYABLE = "not_retryable"
    UNKNOWN = "unknown"


#: States from which no further provider progress is expected without a new
#: operation or a reconciliation pass.
TERMINAL_PROVIDER_STATES: frozenset[ProviderOperationState] = frozenset(
    {
        ProviderOperationState.REJECTED,
        ProviderOperationState.COMPLETED,
        ProviderOperationState.FAILED,
    }
)

#: States that must be settled against the provider before the domain may act.
RECONCILIATION_PROVIDER_STATES: frozenset[ProviderOperationState] = frozenset(
    {
        ProviderOperationState.UNKNOWN,
        ProviderOperationState.RECONCILIATION_REQUIRED,
    }
)


def is_terminal(state: ProviderOperationState | str) -> bool:
    """Return ``True`` when the provider has given an authoritative final answer.

    Fails closed: an unrecognised state is not terminal, so a caller keeps
    tracking an operation it does not understand instead of closing it out.
    """

    try:
        resolved = ProviderOperationState(state)
    except ValueError:
        return False
    return resolved in TERMINAL_PROVIDER_STATES


def requires_reconciliation(state: ProviderOperationState | str) -> bool:
    """Return ``True`` when the domain must reconcile before acting.

    Fails closed the other way: an unrecognised state *does* require
    reconciliation. Not knowing what a state means is itself a reason to check.
    """

    try:
        resolved = ProviderOperationState(state)
    except ValueError:
        return True
    return resolved in RECONCILIATION_PROVIDER_STATES


def is_safe_to_retry_without_idempotency(state: ProviderOperationState | str) -> bool:
    """Return ``True`` only when a bare retry cannot duplicate a side effect.

    True for ``REQUESTED`` (never left us) and ``REJECTED`` (the provider
    definitively did nothing). Everything else — including ``UNKNOWN`` — needs an
    idempotency key or a reconciliation pass first, because the provider may
    already have acted.
    """

    try:
        resolved = ProviderOperationState(state)
    except ValueError:
        return False
    return resolved in {
        ProviderOperationState.REQUESTED,
        ProviderOperationState.REJECTED,
    }


class ProviderTransportResult(BaseModel):
    """What the wire actually reported. Not a business outcome.

    Kept as its own model so a reviewer can see at a glance where a service
    conflated the two: any code that reads ``status_code == 200`` and writes a
    domain state change is doing the thing this contract exists to stop.
    """

    model_config = ConfigDict(extra="forbid")

    succeeded: bool = Field(
        ..., description="The call completed at the transport level"
    )
    status_code: int | None = Field(
        default=None, description="HTTP status where the provider speaks HTTP"
    )
    error_class: str | None = Field(
        default=None,
        description=(
            "Normalised failure class (timeout, connection_reset, tls, "
            "rate_limited, auth). Never the raw provider error text, which can "
            "carry protected content."
        ),
    )
    latency_ms: int | None = Field(default=None, ge=0)


class ProviderOperationRecord(BaseModel):
    """One durable record of one operation against one external provider.

    ``idempotency_key`` is required, not optional. Every provider write in
    AdaptixCore must be replayable without duplicating a side effect; making the
    key optional is what allows a retry loop to submit a claim twice.

    ``request_hash`` / ``response_hash`` pin what was sent and received without
    storing either. Provider payloads routinely carry PHI and financial detail;
    the hash is enough to prove "this is the same request" during reconciliation.
    """

    model_config = ConfigDict(extra="forbid")

    provider_name: str = Field(..., min_length=1)
    provider_operation_id: str | None = Field(
        default=None,
        description="The provider's own id for this operation, when it issues one",
    )
    adaptix_operation_id: str = Field(
        ..., min_length=1, description="Our id for this operation"
    )
    tenant_id: str = Field(..., min_length=1)
    requested_at: datetime
    responded_at: datetime | None = None
    request_hash: str = Field(..., min_length=1)
    response_hash: str | None = Field(
        default=None, description="Hash or storage reference for the response"
    )
    correlation_id: str = Field(..., min_length=1)
    idempotency_key: str = Field(
        ...,
        min_length=1,
        description="Stable across retries of the same logical operation",
    )
    provider_status: str | None = Field(
        default=None, description="The provider's own status string, verbatim"
    )
    canonical_status: ProviderOperationState
    transport: ProviderTransportResult | None = None
    retryability: ProviderRetryability = ProviderRetryability.UNKNOWN
    next_reconciliation_at: datetime | None = Field(
        default=None,
        description="When a reconciliation pass must next check this operation",
    )

    @model_validator(mode="after")
    def _transport_success_is_not_business_success(self) -> ProviderOperationRecord:
        if (
            self.transport is not None
            and self.transport.succeeded
            and self.canonical_status is ProviderOperationState.REQUESTED
        ):
            raise ValueError(
                "transport succeeded but canonical_status is still REQUESTED; a "
                "provider that took the request is ACCEPTED at minimum"
            )
        if self.responded_at is not None and self.responded_at < self.requested_at:
            raise ValueError("responded_at precedes requested_at")
        if (
            self.retryability is ProviderRetryability.RETRY_AFTER
            and self.next_reconciliation_at is None
        ):
            raise ValueError(
                "RETRY_AFTER requires next_reconciliation_at — the provider told us "
                "when to come back and that time must be recorded"
            )
        return self

    def requires_reconciliation(self) -> bool:
        """Return ``True`` when this operation must be settled with the provider."""

        return requires_reconciliation(self.canonical_status)


__all__ = [
    "RECONCILIATION_PROVIDER_STATES",
    "TERMINAL_PROVIDER_STATES",
    "ProviderOperationRecord",
    "ProviderOperationState",
    "ProviderRetryability",
    "ProviderTransportResult",
    "is_safe_to_retry_without_idempotency",
    "is_terminal",
    "requires_reconciliation",
]
