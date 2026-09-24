"""Device evidence contracts (SYN-001).

Evidence is the raw material a device produced (an export file, a waveform
segment, a 12-lead PDF, an image) stored byte-for-byte by the Device service.
Every normalised signal can point at the evidence it was decoded from, which
is what makes normalisation replayable.

Rules carried by these contracts:

* Evidence is addressed by its SHA-256. The digest shape is validated.
* A reference never carries a secret: no credentials, no signed URL, no
  bucket URL. ``storage_key`` is a relative object key; ``source_reference``
  is an opaque vendor-side reference and may not be a URL (URLs can embed
  credentials and signatures).
* Evidence is immutable and hash-chained per device. Each stored object takes
  the next ``ledger_sequence`` in its device's evidence ledger and its
  ``entry_sha256`` covers the previous entry's digest, so removing, reordering
  or altering any stored object breaks every later link. The chain digest has
  exactly one definition, :func:`compute_evidence_ledger_entry_sha256`, which
  the writer (Device service) and every verifier (certification) share.
* Service code never deletes evidence. Retention is expressed with the
  existing platform vocabulary
  (:class:`adaptix_contracts.evidence.enums.EvidenceRetentionClass`) and
  sensitivity with :class:`adaptix_contracts.ai.connection.DataClassification`,
  never a second copy of either. ``SECRET`` is rejected outright, exactly as
  :class:`adaptix_contracts.evidence.models.EvidenceNode` rejects it.

Upload flow (Integrations -> Device presign): Integrations decodes a device
file, asks the Device service for an :class:`EvidenceUploadAuthorizationResponse`
with :class:`EvidenceUploadAuthorizationRequest`, PUTs the bytes to the
short-lived presigned URL with the required headers, then references the
returned ``evidence_id`` from its signal envelopes. The Device service derives
the tenant from the persisted Device row; the request carries no tenant.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import (
    AwareDatetime,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from adaptix_contracts.ai.connection import DataClassification
from adaptix_contracts.evidence.enums import EvidenceRetentionClass
from adaptix_contracts.synapse.provenance import (
    AdapterKey,
    CorrelationId,
    ExternalKey,
    MediaType,
    SemanticVersion,
    Sha256Hex,
    SynapseId,
    SynapseModel,
)

#: Largest object one presigned PUT can carry (the S3 single-PUT ceiling).
EVIDENCE_MAX_BYTE_SIZE = 5 * 1024 * 1024 * 1024

#: Relative object key: S3 "safe" characters only, no scheme, no leading "/".
StorageKey = Annotated[
    str,
    StringConstraints(
        min_length=1, max_length=1024, pattern=r"^[A-Za-z0-9][A-Za-z0-9!_.*'()/-]*$"
    ),
]

_HeaderName = Annotated[
    str, StringConstraints(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9-]+$")
]
_HeaderValue = Annotated[
    str, StringConstraints(max_length=2048, pattern=r"^[^\x00-\x1f\x7f]*$")
]


#: Domain-separation tag for the evidence ledger chain digest. A new chain
#: rule gets a new tag; an existing chain is never re-hashed under a new rule.
EVIDENCE_LEDGER_HASH_DOMAIN = "adaptix.synapse.evidence-ledger.v1"

_LEDGER_SEPARATOR = "\x1f"


def _reject_url(value: str) -> str:
    if "://" in value:
        raise ValueError(
            "source_reference must be an opaque reference, not a URL: URLs can "
            "carry credentials or signatures"
        )
    return value


def compute_evidence_ledger_entry_sha256(
    *,
    tenant_id: str,
    device_id: str,
    ledger_sequence: int,
    previous_entry_sha256: str | None,
    evidence_id: str,
    evidence_sha256: str,
    byte_size: int,
    media_type: str,
    received_at: datetime,
) -> str:
    """The single definition of one device evidence ledger link.

    SHA-256 over :data:`EVIDENCE_LEDGER_HASH_DOMAIN` and the entry's immutable
    facts, joined by the ASCII unit separator (which no validated field can
    contain). ``received_at`` is rendered in UTC at microsecond precision so
    the digest survives a round trip through a ``timestamptz`` column. The
    first entry of a device's ledger (``ledger_sequence == 1``) chains from the
    empty string.
    """

    if received_at.tzinfo is None or received_at.utcoffset() is None:
        raise ValueError("received_at must be timezone-aware")
    parts = (
        EVIDENCE_LEDGER_HASH_DOMAIN,
        tenant_id,
        device_id,
        str(ledger_sequence),
        previous_entry_sha256 or "",
        evidence_id,
        evidence_sha256,
        str(byte_size),
        media_type,
        received_at.astimezone(UTC).isoformat(timespec="microseconds"),
    )
    return hashlib.sha256(_LEDGER_SEPARATOR.join(parts).encode("utf-8")).hexdigest()


class DeviceEvidenceReference(SynapseModel):
    """A stored, immutable device evidence object and its ledger link.

    ``storage_version`` pins the exact stored object version so a later write
    to the same key can never silently change what this reference means.
    ``ledger_sequence`` is the object's position in its device's evidence
    ledger; ``previous_entry_sha256`` is the prior entry's ``entry_sha256``
    (absent only for the first entry); ``entry_sha256`` must equal
    :func:`compute_evidence_ledger_entry_sha256` of this entry.
    """

    id: SynapseId
    tenant_id: SynapseId
    device_id: SynapseId
    device_session_id: SynapseId | None = None
    rail_id: SynapseId
    sha256: Sha256Hex
    byte_size: int = Field(ge=1, le=EVIDENCE_MAX_BYTE_SIZE, strict=True)
    media_type: MediaType
    storage_key: StorageKey
    storage_version: Annotated[str, StringConstraints(min_length=1, max_length=1024)]
    adapter_key: AdapterKey
    adapter_version: SemanticVersion
    source_reference: ExternalKey
    received_at: AwareDatetime
    classification: DataClassification
    retention_class: EvidenceRetentionClass
    ledger_sequence: int = Field(ge=1, strict=True)
    previous_entry_sha256: Sha256Hex | None = None
    entry_sha256: Sha256Hex

    @model_validator(mode="after")
    def _ledger_link_is_intact(self) -> DeviceEvidenceReference:
        if (self.ledger_sequence == 1) != (self.previous_entry_sha256 is None):
            raise ValueError(
                "previous_entry_sha256 is absent for ledger_sequence 1 and "
                "required for every later entry"
            )
        expected = compute_evidence_ledger_entry_sha256(
            tenant_id=self.tenant_id,
            device_id=self.device_id,
            ledger_sequence=self.ledger_sequence,
            previous_entry_sha256=self.previous_entry_sha256,
            evidence_id=self.id,
            evidence_sha256=self.sha256,
            byte_size=self.byte_size,
            media_type=self.media_type,
            received_at=self.received_at,
        )
        if self.entry_sha256 != expected:
            raise ValueError(
                "entry_sha256 does not match this ledger entry; compute it with "
                "compute_evidence_ledger_entry_sha256"
            )
        return self

    def follows(self, previous: DeviceEvidenceReference) -> bool:
        """True when this entry is the direct successor of ``previous`` in the
        same device's ledger."""

        return (
            self.tenant_id == previous.tenant_id
            and self.device_id == previous.device_id
            and self.ledger_sequence == previous.ledger_sequence + 1
            and self.previous_entry_sha256 == previous.entry_sha256
        )

    @field_validator("storage_key")
    @classmethod
    def _key_is_confined(cls, value: str) -> str:
        segments = value.split("/")
        if any(segment in ("", ".", "..") for segment in segments):
            raise ValueError(
                "storage_key must not contain empty, '.' or '..' path segments"
            )
        return value

    @field_validator("source_reference")
    @classmethod
    def _source_reference_is_opaque(cls, value: str) -> str:
        return _reject_url(value)

    @field_validator("classification")
    @classmethod
    def _reject_secret(cls, value: DataClassification) -> DataClassification:
        if value is DataClassification.SECRET:
            raise ValueError(
                "device evidence may not be SECRET-classified: a credential is "
                "not evidence"
            )
        return value


class EvidenceUploadAuthorizationRequest(SynapseModel):
    """Integrations -> Device: authorise one evidence upload.

    Idempotent on ``(device_id, sha256)``: asking again for bytes the Device
    service already holds returns the existing ``evidence_id`` with
    ``upload_required`` false, so a retransmission is harmless.
    """

    device_id: SynapseId
    device_session_id: SynapseId | None = None
    rail_id: SynapseId
    sha256: Sha256Hex
    byte_size: int = Field(ge=1, le=EVIDENCE_MAX_BYTE_SIZE, strict=True)
    media_type: MediaType
    source_reference: ExternalKey
    adapter_key: AdapterKey
    adapter_version: SemanticVersion
    correlation_id: CorrelationId

    @field_validator("source_reference")
    @classmethod
    def _source_reference_is_opaque(cls, value: str) -> str:
        return _reject_url(value)


class EvidenceUploadAuthorizationResponse(SynapseModel):
    """Device -> Integrations: where and how to PUT the evidence bytes.

    ``upload_url`` is a short-lived presigned HTTPS PUT URL. It is a bearer
    credential until ``expires_at``: it is excluded from ``repr`` and must
    never be logged or persisted. When ``upload_required`` is false the bytes
    are already stored under ``evidence_id`` and there is nothing to upload.
    """

    evidence_id: SynapseId
    upload_required: bool = Field(strict=True)
    upload_url: str | None = Field(default=None, repr=False, max_length=8192)
    required_headers: dict[_HeaderName, _HeaderValue] = Field(default_factory=dict)
    expires_at: AwareDatetime | None = None

    @field_validator("upload_url")
    @classmethod
    def _https_only(cls, value: str | None) -> str | None:
        if value is None:
            return value
        parts = urlsplit(value)
        if parts.scheme != "https" or not parts.netloc:
            raise ValueError("upload_url must be an absolute https URL")
        return value

    @model_validator(mode="after")
    def _upload_fields_match_requirement(self) -> EvidenceUploadAuthorizationResponse:
        if self.upload_required:
            if self.upload_url is None or self.expires_at is None:
                raise ValueError(
                    "an upload that is required needs upload_url and expires_at"
                )
        elif (
            self.upload_url is not None
            or self.expires_at is not None
            or self.required_headers
        ):
            raise ValueError(
                "no upload is required: upload_url, expires_at and "
                "required_headers must be empty"
            )
        return self


__all__ = [
    "EVIDENCE_LEDGER_HASH_DOMAIN",
    "EVIDENCE_MAX_BYTE_SIZE",
    "DeviceEvidenceReference",
    "compute_evidence_ledger_entry_sha256",
    "EvidenceUploadAuthorizationResponse",
    "EvidenceUploadAuthorizationRequest",
    "StorageKey",
]
