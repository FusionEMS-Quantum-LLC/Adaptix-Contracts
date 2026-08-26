"""Agency peer and trust relationship contracts."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PeerType(str, Enum):
    ADAPTIX = "ADAPTIX"
    EXTERNAL_API = "EXTERNAL_API"
    QHIN = "QHIN"
    HIE = "HIE"


class PeerStatus(str, Enum):
    PENDING = "PENDING"
    VERIFYING = "VERIFYING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    REVOKED = "REVOKED"
    ERROR = "ERROR"


class VerificationState(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"


class TrustDirection(str, Enum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"
    BIDIRECTIONAL = "BIDIRECTIONAL"


class TrustStatus(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    REVOKED = "REVOKED"


class AgencyPeer(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    peer_id: str = Field(..., min_length=1)
    peer_agency_id: str = Field(..., min_length=1)
    peer_tenant_id: str | None = None
    display_name: str = Field(..., min_length=1)
    peer_type: PeerType
    endpoint_url: str | None = None
    status: PeerStatus
    certificate_fingerprint: str | None = None
    verification_state: VerificationState = VerificationState.UNVERIFIED
    last_verified_at: datetime | None = None
    last_successful_exchange_at: datetime | None = None


class TrustRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    trust_id: str = Field(..., min_length=1)
    peer_id: str = Field(..., min_length=1)
    trust_direction: TrustDirection
    status: TrustStatus
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    allowed_purposes: tuple[str, ...] = ()
    allowed_resource_types: tuple[str, ...] = ()
    approved_by: str | None = None
    revoked_at: datetime | None = None

    @model_validator(mode="after")
    def validate_window(self) -> "TrustRelationship":
        if self.valid_from and self.valid_until and self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be after valid_from")
        return self


__all__ = [
    "AgencyPeer",
    "PeerStatus",
    "PeerType",
    "TrustDirection",
    "TrustRelationship",
    "TrustStatus",
    "VerificationState",
]
