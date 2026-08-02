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


# pylint too-few-public-methods (R0903) is disabled per class below. These are
# declarative Pydantic schemas — pure data carriers whose entire contract is
# their field set, exactly the shape pylint already exempts for @dataclass. The
# rule's intent (a class doing so little it should be a function or a tuple)
# cannot apply to a validated wire contract, so it is a false positive here.
# The disables are per class, never module-wide, so a future non-schema class
# added to this module is still checked.
class SignupAgencyAddress(BaseModel):  # pylint: disable=too-few-public-methods
    """Optional physical address captured during agency-profile creation."""

    model_config = ConfigDict(extra="ignore")

    primary_line: str = Field(..., min_length=1, max_length=255)
    secondary_line: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=128)
    state: str | None = Field(default=None, max_length=8)
    zip_code: str | None = Field(default=None, max_length=10)


class SignupApplicationCreateRequest(BaseModel):  # pylint: disable=too-few-public-methods
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


class SignupApplicationCreateResponse(BaseModel):  # pylint: disable=too-few-public-methods
    """Canonical response for application creation and exact replays.

    Extra fields remain allowed because Core returns a richer application
    snapshot to existing callers. The load-bearing contract is the canonical
    identifier, its temporary alias, status, step, and replay flag.
    """

    model_config = ConfigDict(extra="allow")

    application_id: UUID
    # pylint invalid-name (C0103) is a false positive here: ``id`` is not a
    # naming choice this module is free to make. It is the literal JSON key
    # Adaptix-Core already returns and Adaptix-Web-App already reads during the
    # rolling deployment, and it is pinned as a required property by
    # tests/test_signup_contracts.py::test_json_schema_pins_load_bearing_response_fields.
    # A minimum-identifier-length convention cannot govern an externally fixed
    # wire field name; renaming it would break the compatibility alias this
    # contract exists to guarantee.
    id: UUID = Field(  # pylint: disable=invalid-name
        ...,
        description="Deprecated compatibility alias; must equal application_id.",
    )
    status: str = Field(..., min_length=1, max_length=48)
    current_step: str = Field(..., min_length=1, max_length=48)
    idempotent_replay: bool = False

    @model_validator(mode="after")
    def identifiers_must_match(self) -> "SignupApplicationCreateResponse":
        """Reject a response whose compatibility alias has drifted.

        ``id`` is a temporary duplicate of ``application_id``. If the two ever
        disagree, a caller keyed on one of them would correlate later signup
        steps to the wrong application, so the mismatch is rejected at the
        contract boundary rather than allowed to propagate.
        """
        if self.id != self.application_id:
            raise ValueError("id must equal application_id")
        return self


# No module-level ``__all__``: the export list lived here AND verbatim in
# adaptix_contracts/schemas/__init__.py, which is the duplication pylint
# reported (R0801). The package __init__ is the single owner of the public
# surface — 71 of the 75 schema modules already define no ``__all__``, and
# tests/test_contract_surface.py asserts against ``schemas.__all__``, never a
# submodule's. Removing the copy here leaves exactly one source of truth.
