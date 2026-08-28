"""Application-level exchange contracts for interagency delivery."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .provenance import DataProvenance


# pylint too-few-public-methods (R0903) is disabled per class below. These are
# declarative Pydantic wire contracts whose entire contract IS their field set,
# exactly the shape pylint already exempts for @dataclass; the rule's intent (a
# class doing so little it should be a function or a tuple) cannot apply to a
# validated wire contract. Per class, never module-wide, so a future non-schema
# class added to this module is still checked.
class PublicSafetyExchangeEnvelope(BaseModel):  # pylint: disable=too-few-public-methods
    """Reference-based, provenance-complete interagency exchange envelope.

    The authoritative payload lives behind ``payload_ref``. Core exchange
    metadata must not become a convenient duplicate PHI store.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    exchange_id: str = Field(..., min_length=1)
    correlation_id: str = Field(..., min_length=1)
    schema_version: str = Field(default="1.0", min_length=1)
    origin_tenant_id: str = Field(..., min_length=1)
    origin_agency_id: str = Field(..., min_length=1)
    origin_service: str = Field(..., min_length=1)
    origin_record_id: str = Field(..., min_length=1)
    origin_record_version: str = Field(..., min_length=1)
    recipient_agency_id: str = Field(..., min_length=1)
    recipient_peer_id: str = Field(..., min_length=1)
    global_incident_id: str | None = None
    source_incident_id: str | None = None
    global_encounter_id: str | None = None
    source_encounter_id: str | None = None
    patient_identity_ref: str | None = None
    external_patient_identity_ref: str | None = None
    resource_type: str = Field(..., min_length=1)
    source_standard: str | None = None
    source_standard_version: str | None = None
    canonical_resource_version: str = Field(..., min_length=1)
    payload_ref: str = Field(..., min_length=1)
    payload_sha256: str = Field(..., pattern=r"^[0-9a-fA-F]{64}$")
    purpose_of_use: str = Field(..., min_length=1)
    sharing_policy_id: str = Field(..., min_length=1)
    consent_decision_ref: str | None = None
    sensitivity: str = Field(..., min_length=1)
    provenance: list[DataProvenance] = Field(default_factory=list)
    occurred_at: datetime
    created_at: datetime
    expires_at: datetime | None = None
    idempotency_key: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_expiry(self) -> "PublicSafetyExchangeEnvelope":
        """Reject an expiry that is not strictly after creation.

        An ``expires_at`` at or before ``created_at`` describes an envelope
        that was already expired when it was built, so a recipient honouring
        the window would drop a delivery that was never given a usable
        validity period — far more likely a timezone or data-entry error
        than an intent.
        """
        if self.expires_at is not None and self.expires_at <= self.created_at:
            raise ValueError("expires_at must be after created_at")
        return self


__all__ = ["PublicSafetyExchangeEnvelope"]
