"""Regression tests for the canonical signup application-creation contract."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from adaptix_contracts.schemas.signup_contracts import (
    SIGNUP_IDEMPOTENCY_HEADER,
    SignupApplicationCreateRequest,
    SignupApplicationCreateResponse,
    SignupIdempotencyKey,
)


def test_create_request_accepts_canonical_step_one_shape() -> None:
    body = SignupApplicationCreateRequest(
        agency_name="North Valley EMS",
        admin_email="ADMIN@north-valley.example",
        selected_modules=["core", "cad"],
        agency_address={"primary_line": "100 Main St", "state": "WI"},
    )
    assert body.agency_name == "North Valley EMS"
    assert str(body.admin_email) == "ADMIN@north-valley.example"
    assert body.agency_address is not None
    assert body.agency_address.primary_line == "100 Main St"


def test_create_response_requires_matching_canonical_and_compatibility_ids() -> None:
    application_id = uuid4()
    response = SignupApplicationCreateResponse(
        application_id=application_id,
        id=application_id,
        status="profile_captured",
        current_step="profile",
        future_additive_field={"preserved": True},
    )
    assert response.application_id == application_id
    assert response.id == application_id
    assert response.idempotent_replay is False
    assert response.model_extra == {"future_additive_field": {"preserved": True}}


def test_create_response_rejects_identifier_drift() -> None:
    with pytest.raises(ValidationError, match="id must equal application_id"):
        SignupApplicationCreateResponse(
            application_id=uuid4(),
            id=uuid4(),
            status="profile_captured",
            current_step="profile",
        )


@pytest.mark.parametrize(
    "key",
    [
        "3dc5f9d4-11da-4d9e-9af5-1b0bcab4696e",
        "signup.browser-session:01JQW4NQ0Q8S2RZ9",
    ],
)
def test_idempotency_key_contract_accepts_supported_opaque_keys(key: str) -> None:
    assert TypeAdapter(SignupIdempotencyKey).validate_python(key) == key
    assert SIGNUP_IDEMPOTENCY_HEADER == "Idempotency-Key"


@pytest.mark.parametrize(
    "key", ["short", "contains spaces in key", "!invalid-prefix-value"]
)
def test_idempotency_key_contract_rejects_unsafe_values(key: str) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(SignupIdempotencyKey).validate_python(key)


def test_json_schema_pins_load_bearing_response_fields() -> None:
    required = set(SignupApplicationCreateResponse.model_json_schema()["required"])
    assert {"application_id", "id", "status", "current_step"} <= required
