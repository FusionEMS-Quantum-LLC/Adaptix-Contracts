"""Canonical contracts for Step 1 of self-service agency signup.

The application identifier is issued once and is the correlation key for every
later signup step. application_id is canonical. id remains a required
compatibility alias during the rolling Web/Core deployment and must equal the
canonical identifier.

HTTP clients send Idempotency-Key on application creation. The key is opaque,
browser-generated, persisted with the wizard draft, and reused only for an
exact retry of the same creation payload.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    model_validator,
)


SIGNUP_IDEMPOTENCY_HEADER = "Idempotency-Key"
SignupIdempotencyKey = Annotated[
    str,
    StringConstraints(
        min_length=16,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
        strip_whitespace=True,
    ),
]


class SignupAgencyAddress(BaseModel):
    """Optional physical address captured during agency-profile creation."""

    model_config = ConfigDict(extra="ignore")

    primary_line: str = Field(..., min_length=1, max_length=255)
    secondary_line: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=128)
    state: str | None = Field(default=None, max_length=8)
    zip_code: str | None = Field(default=None, max_length=10)


class SignupApplicationCreateRequest(BaseModel):
    """Canonical body for POST /api/v1/signup/applications."""

    model_config = ConfigDict(extra="ignore")

    agency_name: str = Field(..., min_length=1, max_length=255)
    admin_email: EmailStr
    admin_full_name: str | None = Field(default=None, max_length=255)
    admin_phone: str | None = Field(default=None, max_length=64)
    agency_state: str | None = Field(default=None, max_length=8)
    agency_size: str | None = Field(default=None, max_length=32)
    selected_modules: list[str] | None = None
    metadata_json: dict[str, Any] | None = None
    agency_address: SignupAgencyAddress | None = None


class SignupApplicationCreateResponse(BaseModel):
    """Canonical response for application creation and exact replays.

    Extra fields remain allowed because Core returns a richer application
    snapshot to existing callers. The load-bearing contract is the canonical
    identifier, its temporary alias, status, step, and replay flag.
    """

    model_config = ConfigDict(extra="allow")

    application_id: UUID
    id: UUID = Field(
        ...,
        description="Deprecated compatibility alias; must equal application_id.",
    )
    status: str = Field(..., min_length=1, max_length=48)
    current_step: str = Field(..., min_length=1, max_length=48)
    idempotent_replay: bool = False

    @model_validator(mode="after")
    def identifiers_must_match(self) -> "SignupApplicationCreateResponse":
        if self.id != self.application_id:
            raise ValueError("id must equal application_id")
        return self


__all__ = [
    "SIGNUP_IDEMPOTENCY_HEADER",
    "SignupAgencyAddress",
    "SignupApplicationCreateRequest",
    "SignupApplicationCreateResponse",
    "SignupIdempotencyKey",
]
