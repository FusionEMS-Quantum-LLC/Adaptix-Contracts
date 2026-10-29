"""A refused request is answered without repeating what the caller sent (#375)."""

from __future__ import annotations

import asyncio
import json
import logging

import pytest

from fastapi import FastAPI, WebSocket
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from _asgi_client import ASGIClient
from adaptix_contracts.validation_errors import (
    SERVER_SIDE_VALIDATION_ERROR_DETAIL,
    input_free_server_side_validation_error_handler,
    input_free_validation_error_handler,
    input_free_validation_errors,
    install_input_free_validation_errors,
)

# Values that must never come back. They stand in for patient data.
_LAST_NAME = "Zyxwvutsrq"
_DOB = "1950-01-01"
_MRN = "MRN-0047731"


class _Lookup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone: str
    last_name: str
    dob: str


class _Window(BaseModel):
    start: str
    end: str

    @model_validator(mode="after")
    def _ordered(self) -> _Window:
        if self.end < self.start:
            raise ValueError("end must not be before start")
        return self


def _app(*, input_free: bool) -> FastAPI:
    app = FastAPI()

    @app.post("/lookup")
    async def lookup(body: _Lookup) -> dict[str, str]:
        return {"phone": body.phone}

    @app.post("/window")
    async def window(body: _Window) -> dict[str, str]:
        return {"start": body.start}

    @app.get("/charts")
    async def charts(limit: int) -> dict[str, int]:
        return {"limit": limit}

    if input_free:
        install_input_free_validation_errors(app)
    return app


def _post(app: FastAPI, path: str, body: object) -> tuple[int, str]:
    response = ASGIClient(app).post(path, json=body)
    return response.status_code, response.text


def test_framework_default_repeats_the_body_this_module_exists_to_stop() -> None:
    # The defect, pinned: without the installer a missing field returns the
    # whole body. If FastAPI ever stops doing this, the guard below is moot.
    status, text = _post(
        _app(input_free=False), "/lookup", {"last_name": _LAST_NAME, "dob": _DOB}
    )

    assert status == 422
    assert _LAST_NAME in text and _DOB in text


def test_missing_field_answer_carries_no_caller_values() -> None:
    status, text = _post(
        _app(input_free=True), "/lookup", {"last_name": _LAST_NAME, "dob": _DOB}
    )

    assert status == 422
    assert _LAST_NAME not in text and _DOB not in text
    assert json.loads(text) == {
        "detail": [
            {"type": "missing", "loc": ["body", "phone"], "msg": "Field required"}
        ]
    }


def test_unexpected_field_value_is_not_repeated() -> None:
    status, text = _post(
        _app(input_free=True),
        "/lookup",
        {"phone": "555", "last_name": "A", "dob": _DOB, "mrn": _MRN},
    )

    assert status == 422
    assert _MRN not in text
    assert json.loads(text)["detail"] == [
        {
            "type": "extra_forbidden",
            "loc": ["body", "mrn"],
            "msg": "Extra inputs are not permitted",
        }
    ]


def test_model_validator_refusal_does_not_repeat_the_block() -> None:
    status, text = _post(
        _app(input_free=True),
        "/window",
        {"start": "2026-10-19", "end": "2026-10-18", "note": _LAST_NAME},
    )

    assert status == 422
    assert _LAST_NAME not in text and "2026-10-18" not in text
    (error,) = json.loads(text)["detail"]
    assert set(error) == {"type", "loc", "msg"}
    assert error["msg"] == "Value error, end must not be before start"


def test_query_parameter_refusal_does_not_repeat_the_value() -> None:
    response = ASGIClient(_app(input_free=True)).get(f"/charts?limit={_MRN}")

    assert response.status_code == 422
    assert _MRN not in response.text
    (error,) = response.json()["detail"]
    assert error == {
        "type": "int_parsing",
        "loc": ["query", "limit"],
        "msg": "Input should be a valid integer, unable to parse string as an integer",
    }


def test_answer_keeps_the_framework_shape_minus_input_and_ctx() -> None:
    # Backward compatibility: every client that reads detail[].type/loc/msg
    # sees exactly what FastAPI's own answer gives it.
    body = {"phone": 5, "last_name": _LAST_NAME, "mrn": _MRN}
    _, default_text = _post(_app(input_free=False), "/lookup", body)
    _, safe_text = _post(_app(input_free=True), "/lookup", body)

    default_detail = json.loads(default_text)["detail"]
    assert [
        {key: error[key] for key in ("type", "loc", "msg")} for error in default_detail
    ] == json.loads(safe_text)["detail"]


def test_allow_list_drops_keys_it_does_not_know() -> None:
    errors = [
        {
            "type": "string_too_long",
            "loc": ("body", "note"),
            "msg": "String should have at most 4 characters",
            "input": _LAST_NAME,
            "ctx": {"max_length": 4},
            "url": "https://errors.pydantic.dev/2/v/string_too_long",
        }
    ]

    assert input_free_validation_errors(errors) == [
        {
            "type": "string_too_long",
            "loc": ["body", "note"],
            "msg": "String should have at most 4 characters",
        }
    ]


def test_installer_registers_the_handler_for_request_validation_errors() -> None:
    app = FastAPI()

    install_input_free_validation_errors(app)

    assert app.exception_handlers[RequestValidationError] is (
        input_free_validation_error_handler
    )


def _ws_app(*, input_free: bool) -> FastAPI:
    app = FastAPI()

    @app.websocket("/stream")
    async def stream(websocket: WebSocket, mrn: int) -> None:
        await websocket.accept()
        await websocket.close()

    if input_free:
        install_input_free_validation_errors(app)
    return app


async def _ws_close_reason(app: FastAPI) -> tuple[int, str]:
    sent: list[dict[str, object]] = []
    messages = iter([{"type": "websocket.connect"}])

    async def receive() -> dict[str, object]:
        return next(messages)

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    scope = {
        "type": "websocket",
        "path": "/stream",
        "raw_path": b"/stream",
        "query_string": f"mrn={_MRN}".encode(),
        "headers": [],
        "scheme": "ws",
        "server": ("testserver", 80),
        "client": ("testclient", 50000),
        "root_path": "",
        "subprotocols": [],
        "asgi": {"version": "3.0"},
    }
    await app(scope, receive, send)
    (close,) = [m for m in sent if m["type"] == "websocket.close"]
    return int(str(close["code"])), str(close.get("reason", ""))


def test_websocket_default_repeats_the_value_this_module_exists_to_stop() -> None:
    code, reason = asyncio.run(_ws_close_reason(_ws_app(input_free=False)))

    assert code == 1008
    assert _MRN in reason


def test_websocket_refusal_closes_without_the_value() -> None:
    code, reason = asyncio.run(_ws_close_reason(_ws_app(input_free=True)))

    assert code == 1008
    assert _MRN not in reason
    assert json.loads(reason) == [
        {
            "type": "int_parsing",
            "loc": ["query", "mrn"],
            "msg": "Input should be a valid integer, unable to parse string as an integer",
        }
    ]


# --- logs and server-side validation failures (#375, follow-up) --------------


def test_refused_request_leaves_no_caller_value_in_any_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)

    status, text = _post(
        _app(input_free=True), "/lookup", {"last_name": _LAST_NAME, "dob": _DOB}
    )

    assert status == 422
    assert _LAST_NAME not in text and _DOB not in text
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert _LAST_NAME not in logged and _DOB not in logged


class _Record(BaseModel):
    mrn: int


def _server_side_app(*, input_free: bool) -> FastAPI:
    app = FastAPI()

    @app.get("/record")
    async def record() -> dict[str, int]:
        # A model built from a stored record, not from the request: the
        # failing value is the service's own data, and pydantic quotes it.
        return {"mrn": _Record.model_validate({"mrn": _MRN}).mrn}

    @app.get("/typed", response_model=_Record)
    async def typed() -> dict[str, str]:
        return {"mrn": _MRN}

    if input_free:
        install_input_free_validation_errors(app)
    return app


def _get_unraised(app: FastAPI, path: str) -> tuple[int, str]:
    response = ASGIClient(app, raise_server_exceptions=False).get(path)
    return response.status_code, response.text


def test_framework_default_quotes_the_value_in_the_exception_text() -> None:
    # The defect, pinned: unhandled, both exceptions reach the ASGI server's
    # traceback with the value in their message line.
    with pytest.raises(ValidationError) as caught:
        _Record.model_validate({"mrn": _MRN})
    assert _MRN in str(caught.value)

    response_error = ResponseValidationError(
        [
            {
                "type": "int_parsing",
                "loc": ("response", "mrn"),
                "msg": "x",
                "input": _MRN,
            }
        ],
        body={"mrn": _MRN},
    )
    assert _MRN in str(response_error)


@pytest.mark.parametrize("path", ["/record", "/typed"])
def test_server_side_validation_failure_answers_500_without_the_value(
    path: str, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    status, text = _get_unraised(_server_side_app(input_free=True), path)

    assert status == 500
    assert _MRN not in text
    assert json.loads(text) == {"detail": SERVER_SIDE_VALIDATION_ERROR_DETAIL}
    (record,) = [
        r for r in caplog.records if r.name == "adaptix_contracts.validation_errors"
    ]
    assert record.levelno == logging.ERROR
    assert _MRN not in record.getMessage()
    assert "int_parsing" in record.getMessage()
    assert path in record.getMessage()


def test_server_side_handlers_can_be_left_out() -> None:
    app = FastAPI()

    install_input_free_validation_errors(app, server_side_errors=False)

    assert RequestValidationError in app.exception_handlers
    assert ValidationError not in app.exception_handlers
    assert ResponseValidationError not in app.exception_handlers


def test_installer_registers_the_server_side_handlers_by_default() -> None:
    app = FastAPI()

    install_input_free_validation_errors(app)

    for exc_type in (ValidationError, ResponseValidationError):
        assert app.exception_handlers[exc_type] is (
            input_free_server_side_validation_error_handler
        )
