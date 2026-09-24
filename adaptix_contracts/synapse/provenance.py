"""Synapse provenance: shared value shapes, signal lineage and replay contracts.

This module owns four things every other Synapse module builds on:

1. **Value shapes** - the constrained string types for identifiers, SHA-256
   digests, adapter keys/versions, canonical codes, media types, UCUM units
   and device-reported text. Declaring them once keeps the Device,
   Integrations, ePCR and Edge sides from each inventing a slightly different
   width or pattern.
2. :class:`SynapseModel` - the one base of every Synapse contract model, so
   "unknown fields are refused, fields cannot be reassigned and no timestamp
   is inferred from a bare epoch number" is declared once.
3. :class:`SignalProvenance` - the lineage a downstream record (for example an
   ePCR vital imported from a device) carries back to the device signal,
   evidence object, adapter and normalisation version that produced it.
4. :class:`ReplayRequest` / :class:`ReplayResult` - Device asks Integrations
   to re-normalise stored evidence. Normalisation is append-only: a replay
   produces NEW envelopes whose provenance names the event they supersede; it
   never rewrites or deletes the original.

Alignment with existing authorities
-----------------------------------
* ``AdapterKey`` / ``AdapterVersion`` use exactly the ``connector_key`` and
  ``version`` rules of Adaptix-Integrations-Service
  ``integrations_app/connector_sdk/manifest.py`` (``_KEY_RE``, ``_SEMVER_RE``,
  length 3-64), because a Synapse adapter IS a connector registered there.
* ``SynapseId`` fits the ``String(36)`` primary/tenant key columns of
  Adaptix-Device-Service ``device_app/models.py``; ``DeviceClass`` and
  ``IdentityText`` fit its ``device_type`` and manufacturer/model/serial
  columns.
* ``CorrelationId`` is bounded by
  :data:`adaptix_contracts.events.bus_limits.BUS_CORRELATION_ID_MAX_LENGTH`,
  read from its owner rather than restated.

Strict validation
-----------------
* Every integer, float and boolean field is strict (``Field(strict=True)``,
  or ``StrictInt`` / ``StrictFloat`` / ``StrictBool`` inside a union, where
  pydantic cannot apply ``strict`` to the whole union): ``True`` is not a
  sequence number, ``"7"`` is not a count and ``"false"`` is not a boolean.
  A float field still accepts an integer (``250`` is ``250.0`` Hz).
* Model-wide ``strict=True`` is deliberately NOT used: in Python-mode
  validation (the path a FastAPI body takes after JSON decoding) it would
  also refuse the ISO 8601 strings and enum values every JSON producer sends.
* :class:`SynapseModel` refuses a bare epoch number, or a string holding only
  a number, for every datetime field. Pydantic would otherwise read it as a
  Unix time and GUESS its unit (seconds below ``2e10``, milliseconds above)
  and its zone (UTC), silently re-interpreting a device's own time. The
  protocol driver, which knows the device's epoch unit, converts it to an
  aware datetime before it builds a contract.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from typing import Annotated, Any, get_args

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from adaptix_contracts.events.bus_limits import BUS_CORRELATION_ID_MAX_LENGTH
from adaptix_contracts.synapse.enums import (
    SynapseReplayFailureReason,
    SynapseReplayReason,
    SynapseReplayStatus,
)

#: Lowercase hex SHA-256 digest. Uppercase is rejected rather than folded so
#: one object has exactly one digest spelling and equality checks are exact.
Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]

#: Adaptix-issued identifier (UUID string or similar); fits ``String(36)``.
SynapseId = Annotated[
    str,
    StringConstraints(
        min_length=1, max_length=36, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
    ),
]

#: Opaque external key (device record id, idempotency key, vendor reference).
#: Printable, bounded; control characters are refused so a key can never
#: smuggle a log-injection or header-splitting payload.
ExternalKey = Annotated[
    str,
    StringConstraints(min_length=1, max_length=255, pattern=r"^[^\x00-\x1f\x7f]+$"),
]

#: Integrations ``connector_key`` rule (connector_sdk/manifest.py ``_KEY_RE``).
AdapterKey = Annotated[
    str,
    StringConstraints(
        min_length=3, max_length=64, pattern=r"^[a-z][a-z0-9_]*(?:[.-][a-z0-9_]+)*$"
    ),
]

#: Semantic version (connector_sdk/manifest.py ``_SEMVER_RE``).
SemanticVersion = Annotated[
    str,
    StringConstraints(
        max_length=64,
        pattern=r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?$",
    ),
]

#: Canonical Adaptix code (signal codes, channels, alert/therapy/state codes).
#: Lowercase dotted slug; a manufacturer-native code never reaches this layer.
CanonicalCode = Annotated[
    str,
    StringConstraints(
        min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)*$"
    ),
]

#: Correlation id, bounded by the event-bus owner of that width.
CorrelationId = Annotated[
    str, StringConstraints(min_length=1, max_length=BUS_CORRELATION_ID_MAX_LENGTH)
]

#: ``type/subtype`` media type, lowercase, without parameters.
MediaType = Annotated[
    str,
    StringConstraints(
        max_length=127,
        pattern=r"^[a-z0-9][a-z0-9!#$&^_.+-]*/[a-z0-9][a-z0-9!#$&^_.+-]*$",
    ),
]

#: Device class slug; fits ``Device.device_type`` (``String(64)``).
DeviceClass = Annotated[
    str,
    StringConstraints(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$"),
]

#: Manufacturer-reported identity text (manufacturer, model, serial number);
#: fits the ``String(128)`` identity columns of ``Device``. Control characters
#: are refused, which is what lets the physical identity digest separate its
#: parts with the ASCII unit separator.
IdentityText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[^\x00-\x1f\x7f]+$",
    ),
]

#: Driver pack id: upper-case dash-separated words ending in a three-digit
#: serial, e.g. ``COMPAT-<NAME>-001``.
DriverPackId = Annotated[
    str,
    StringConstraints(
        min_length=5, max_length=64, pattern=r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-[0-9]{3}$"
    ),
]

#: UCUM unit expression (printable ASCII, no whitespace), e.g. ``/min``,
#: ``%``, ``mm[Hg]``, ``Cel``.
UcumUnit = Annotated[
    str, StringConstraints(min_length=1, max_length=64, pattern=r"^[!-~]+$")
]

#: A text value a device reported (a rhythm label, a ventilator mode):
#: bounded and free of control characters.
ReportedText = Annotated[
    str,
    StringConstraints(min_length=1, max_length=256, pattern=r"^[^\x00-\x1f\x7f]+$"),
]

#: Upper bound on evidence objects addressed by one replay request.
REPLAY_MAX_EVIDENCE_IDS = 500


#: A string holding nothing but a number (optionally signed or fractional).
_NUMERIC_TEXT = re.compile(r"\s*[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)\s*")


def _is_bare_epoch(value: object) -> bool:
    """True for a number, or a numeric string, offered as a timestamp."""

    if isinstance(value, (int, float)):
        return True
    return isinstance(value, str) and _NUMERIC_TEXT.fullmatch(value) is not None


def _is_datetime_annotation(annotation: object) -> bool:
    return any(
        arg is AwareDatetime or (isinstance(arg, type) and issubclass(arg, datetime))
        for arg in (annotation, *get_args(annotation))
    )


#: Datetime field names per model class, filled on first validation. A race
#: between threads only computes the same immutable value twice.
_DATETIME_FIELDS: dict[type[BaseModel], frozenset[str]] = {}


def _datetime_field_names(model: type[BaseModel]) -> frozenset[str]:
    """Names of ``model``'s fields that hold a datetime (optional or not)."""

    names = _DATETIME_FIELDS.get(model)
    if names is None:
        names = frozenset(
            name
            for name, field in model.model_fields.items()
            if _is_datetime_annotation(field.annotation)
        )
        _DATETIME_FIELDS[model] = names
    return names


class SynapseModel(BaseModel):
    """Base of every Synapse contract model.

    Unknown fields are refused (``extra="forbid"``), so nothing - a patient
    identifier, a tenant claim, a credential - can ride along on a contract
    that does not declare it. Instances are ``frozen``: no field can be
    reassigned after the validators ran. List-valued fields are ordinary
    lists, so a consumer must not mutate one in place; build a new instance
    through ``model_validate`` (``model_copy(update=...)`` does NOT
    re-validate) when a changed contract is needed.

    No datetime field accepts a bare epoch number or numeric string (see the
    module docstring, "Strict validation").
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def _refuse_bare_epoch_timestamps(cls, data: Any) -> Any:
        for name in _datetime_field_names(cls):
            if isinstance(data, Mapping):
                value = data.get(name)
            else:
                value = getattr(data, name, None)
            if _is_bare_epoch(value):
                raise ValueError(
                    f"{name}: a timestamp must be a timezone-aware ISO 8601 "
                    "date-time, not a bare number: an epoch value has no "
                    "declared unit or zone"
                )
        return data


class SignalProvenance(SynapseModel):
    """Lineage from a downstream record back to the device signal behind it.

    ``device_event_id`` is the Device-service event that holds the normalised
    signal. ``supersedes_event_id`` is set only when that event was produced by
    a re-normalisation replay; the superseded event is retained, never deleted.
    """

    device_event_id: SynapseId
    device_session_id: SynapseId | None = None
    evidence_id: SynapseId | None = None
    evidence_sha256: Sha256Hex | None = None
    adapter_key: AdapterKey
    adapter_version: SemanticVersion
    normalization_version: SemanticVersion
    supersedes_event_id: SynapseId | None = None

    @model_validator(mode="after")
    def _evidence_pair_and_supersession(self) -> SignalProvenance:
        if (self.evidence_id is None) != (self.evidence_sha256 is None):
            raise ValueError(
                "evidence_id and evidence_sha256 must be provided together: an "
                "evidence pointer without its digest cannot be verified"
            )
        if self.supersedes_event_id == self.device_event_id:
            raise ValueError("an event cannot supersede itself")
        return self


class ReplayRequest(SynapseModel):
    """Device -> Integrations: re-normalise stored device evidence.

    ``replay_id`` is the idempotency key: Integrations executes one
    ``replay_id`` once and answers a re-delivery with the recorded
    :class:`ReplayResult`. ``tenant_id`` is set by the Device service from the
    persisted Device row, never from a caller-supplied body.
    """

    replay_id: SynapseId
    tenant_id: SynapseId
    device_id: SynapseId
    adapter_key: AdapterKey
    evidence_ids: list[SynapseId] = Field(
        min_length=1, max_length=REPLAY_MAX_EVIDENCE_IDS
    )
    target_normalization_version: SemanticVersion
    reason: SynapseReplayReason
    requested_at: AwareDatetime
    correlation_id: CorrelationId

    @model_validator(mode="after")
    def _evidence_ids_unique(self) -> ReplayRequest:
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("evidence_ids must not repeat")
        return self


class ReplayEvidenceFailure(SynapseModel):
    """One evidence object a replay could not re-normalise, and why."""

    evidence_id: SynapseId
    reason: SynapseReplayFailureReason


class ReplayResult(SynapseModel):
    """Integrations -> Device: the outcome of one :class:`ReplayRequest`.

    ``status`` must agree with what actually happened. ``COMPLETED`` with a
    failure, or ``FAILED`` with re-normalised evidence, is rejected: a partial
    replay is reported as ``PARTIALLY_COMPLETED``, never as success.
    """

    replay_id: SynapseId
    tenant_id: SynapseId
    device_id: SynapseId
    status: SynapseReplayStatus
    normalization_version: SemanticVersion
    renormalized_evidence_ids: list[SynapseId] = Field(default_factory=list)
    produced_event_ids: list[SynapseId] = Field(default_factory=list)
    failures: list[ReplayEvidenceFailure] = Field(default_factory=list)
    completed_at: AwareDatetime
    correlation_id: CorrelationId

    @model_validator(mode="after")
    def _status_matches_outcome(self) -> ReplayResult:
        done = set(self.renormalized_evidence_ids)
        failed = [failure.evidence_id for failure in self.failures]
        if len(done) != len(self.renormalized_evidence_ids):
            raise ValueError("renormalized_evidence_ids must not repeat")
        if len(set(failed)) != len(failed):
            raise ValueError("an evidence id may fail at most once per replay")
        if done & set(failed):
            raise ValueError("an evidence id cannot be both re-normalised and failed")
        if len(set(self.produced_event_ids)) != len(self.produced_event_ids):
            raise ValueError("produced_event_ids must not repeat")
        if self.status is SynapseReplayStatus.COMPLETED and (failed or not done):
            raise ValueError(
                "COMPLETED requires every evidence id re-normalised and no failures"
            )
        if self.status is SynapseReplayStatus.FAILED and (
            done or self.produced_event_ids or not failed
        ):
            raise ValueError(
                "FAILED requires at least one failure and no re-normalised output"
            )
        if self.status is SynapseReplayStatus.PARTIALLY_COMPLETED and not (
            done and failed
        ):
            raise ValueError(
                "PARTIALLY_COMPLETED requires both re-normalised and failed evidence"
            )
        return self

    def unaccounted_evidence_ids(self, request: ReplayRequest) -> frozenset[str]:
        """Evidence ids the request named that this result neither re-normalised
        nor reported as failed. Anything returned here was silently dropped."""

        if (request.replay_id, request.tenant_id, request.device_id) != (
            self.replay_id,
            self.tenant_id,
            self.device_id,
        ):
            raise ValueError("result does not answer this replay request")
        accounted = set(self.renormalized_evidence_ids) | {
            failure.evidence_id for failure in self.failures
        }
        return frozenset(set(request.evidence_ids) - accounted)


__all__ = [
    "REPLAY_MAX_EVIDENCE_IDS",
    "AdapterKey",
    "CanonicalCode",
    "CorrelationId",
    "DeviceClass",
    "DriverPackId",
    "ExternalKey",
    "IdentityText",
    "MediaType",
    "ReplayEvidenceFailure",
    "ReplayRequest",
    "ReplayResult",
    "ReportedText",
    "SemanticVersion",
    "Sha256Hex",
    "SignalProvenance",
    "SynapseId",
    "SynapseModel",
    "UcumUnit",
]
