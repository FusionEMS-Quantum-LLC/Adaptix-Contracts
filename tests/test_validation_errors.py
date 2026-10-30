"""A refused request is answered without repeating what the caller sent (#375)."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator

import pytest

from fastapi import FastAPI, Request, WebSocket
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationError,
    field_validator,
    model_validator,
)

from _asgi_client import ASGIClient
from adaptix_contracts.validation_errors import (
    LOGGED_SERVER_SIDE_ERRORS,
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


class _Echoing(BaseModel):
    """A model whose own validator repeats the value in ``msg``."""

    mrn: str

    @field_validator("mrn")
    @classmethod
    def _numeric(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError(f"{value} is not a numeric MRN")
        return value


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

    @app.get("/patients/{mrn}")
    async def patient(mrn: str) -> dict[str, int]:
        # The served path carries the identifier; the stored record fails.
        return {"mrn": _Record.model_validate({"mrn": mrn}).mrn}

    @app.get("/echo")
    async def echo() -> dict[str, str]:
        return {"mrn": _Echoing.model_validate({"mrn": _MRN}).mrn}

    @app.get("/rows", response_model=list[_Record])
    async def rows() -> list[dict[str, str]]:
        # One error per bad row: the shape that makes an unbounded record.
        return [{"mrn": f"{_MRN}-{i}"} for i in range(500)]

    @app.get("/stream")
    async def stream() -> StreamingResponse:
        async def chunks() -> AsyncIterator[bytes]:
            yield b"first chunk\n"
            _Record.model_validate({"mrn": _MRN})

        return StreamingResponse(chunks())

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


def _only_server_side_record(caplog: pytest.LogCaptureFixture) -> logging.LogRecord:
    (record,) = [
        r for r in caplog.records if r.name == "adaptix_contracts.validation_errors"
    ]
    return record


def test_log_names_the_route_template_not_the_served_path(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)

    status, text = _get_unraised(_server_side_app(input_free=True), f"/patients/{_MRN}")

    assert status == 500 and _MRN not in text
    message = _only_server_side_record(caplog).getMessage()
    assert "GET /patients/{mrn}" in message
    assert f"/patients/{_MRN}" not in message
    assert _MRN not in message


def test_custom_validator_message_that_echoes_the_value_is_not_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # The defect, pinned: the validator's own text carries the value, in
    # errors()[...]["msg"] and in str(exc).
    with pytest.raises(ValidationError) as caught:
        _Echoing.model_validate({"mrn": _MRN})
    assert _MRN in caught.value.errors()[0]["msg"]
    assert _MRN in str(caught.value)

    caplog.set_level(logging.DEBUG)
    status, text = _get_unraised(_server_side_app(input_free=True), "/echo")

    assert status == 500 and _MRN not in text
    message = _only_server_side_record(caplog).getMessage()
    assert _MRN not in message
    assert "value_error" in message and '["mrn"]' in message
    assert "msg" not in message


def test_log_is_bounded_and_puts_the_traceback_before_the_list(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)

    status, text = _get_unraised(_server_side_app(input_free=True), "/rows")

    assert status == 500 and _MRN not in text
    message = _only_server_side_record(caplog).getMessage()
    assert _MRN not in message
    head, _, listed = message.partition(
        f"first {LOGGED_SERVER_SIDE_ERRORS} error type(s) and location(s): "
    )
    assert head.startswith("ResponseValidationError on GET /rows: 500 error(s)\n")
    assert "Traceback" not in head and 'File "' in head  # the frames come first
    entries = json.loads(listed)
    assert len(entries) == LOGGED_SERVER_SIDE_ERRORS == 20
    assert entries[0] == {"type": "int_parsing", "loc": ["response", 0, "mrn"]}
    assert len(message) < 20_000


def test_handler_does_not_cover_an_exception_after_the_response_started() -> None:
    # The limit, pinned: Starlette dispatches exception handlers only before
    # http.response.start. A ValidationError raised in a streaming generator
    # after its first chunk (likewise in a BackgroundTask) is re-raised to
    # the server as the __cause__ of a RuntimeError, value included, so a
    # service must catch it there itself.
    with pytest.raises(RuntimeError, match="response already started") as caught:
        ASGIClient(_server_side_app(input_free=True)).get("/stream")
    assert isinstance(caught.value.__cause__, ValidationError)
    assert _MRN in str(caught.value.__cause__)


def _ws_server_side_app(*, input_free: bool) -> FastAPI:
    app = FastAPI()

    @app.websocket("/records/{mrn}")
    async def records(websocket: WebSocket, mrn: str) -> None:
        await websocket.accept()
        # A frame parsed by hand: the usual way a pydantic ValidationError is
        # raised inside a WebSocket endpoint.
        _Record.model_validate_json(await websocket.receive_text())

    @app.websocket("/closed/{mrn}")
    async def closed(websocket: WebSocket, mrn: str) -> None:
        await websocket.accept()
        frame = await websocket.receive_text()
        await websocket.close()
        # Raised after the endpoint closed the socket itself.
        _Record.model_validate_json(frame)

    if input_free:
        install_input_free_validation_errors(app)
    return app


async def _ws_frames(
    app: FastAPI, path: str, frames: list[str]
) -> list[dict[str, object]]:
    sent: list[dict[str, object]] = []
    messages = iter(
        [
            {"type": "websocket.connect"},
            *({"type": "websocket.receive", "text": frame} for frame in frames),
        ]
    )

    async def receive() -> dict[str, object]:
        return next(messages)

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    scope = {
        "type": "websocket",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "scheme": "ws",
        "server": ("testserver", 80),
        "client": ("testclient", 50000),
        "root_path": "",
        "subprotocols": [],
        "asgi": {"version": "3.0"},
    }
    await app(scope, receive, send)
    return sent


def test_websocket_default_lets_the_exception_carry_the_value() -> None:
    with pytest.raises(ValidationError) as caught:
        asyncio.run(
            _ws_frames(
                _ws_server_side_app(input_free=False),
                f"/records/{_MRN}",
                [json.dumps({"mrn": _MRN})],
            )
        )
    assert _MRN in str(caught.value)


def test_websocket_server_side_failure_closes_1011_without_the_value(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)

    sent = asyncio.run(
        _ws_frames(
            _ws_server_side_app(input_free=True),
            f"/records/{_MRN}",
            [json.dumps({"mrn": _MRN})],
        )
    )

    assert [m["type"] for m in sent] == ["websocket.accept", "websocket.close"]
    assert sent[-1]["code"] == 1011
    assert _MRN not in json.dumps(sent)
    message = _only_server_side_record(caplog).getMessage()
    assert "ValidationError on WEBSOCKET /records/{mrn}" in message
    assert _MRN not in message
    assert "int_parsing" in message
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert _MRN not in logged


def test_websocket_already_closed_by_the_endpoint_is_not_closed_twice(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)

    sent = asyncio.run(
        _ws_frames(
            _ws_server_side_app(input_free=True),
            f"/closed/{_MRN}",
            [json.dumps({"mrn": _MRN})],
        )
    )

    assert [m["type"] for m in sent] == ["websocket.accept", "websocket.close"]
    assert sent[-1]["code"] == 1000  # the endpoint's own close, not a second one
    message = _only_server_side_record(caplog).getMessage()
    assert "ValidationError on WEBSOCKET /closed/{mrn}" in message
    assert _MRN not in message


def _exception_envelope_app(*, server_side_errors: bool) -> FastAPI:
    app = FastAPI()

    @app.exception_handler(Exception)
    async def envelope(_request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=500, content={"error": "envelope"})

    @app.get("/record")
    async def record() -> dict[str, int]:
        return {"mrn": _Record.model_validate({"mrn": _MRN}).mrn}

    install_input_free_validation_errors(app, server_side_errors=server_side_errors)
    return app


def test_exception_handler_is_pre_empted_unless_opted_out() -> None:
    # Documented: an Exception/500 handler lives in the outermost
    # ServerErrorMiddleware; the ValidationError handler in ExceptionMiddleware
    # answers first.
    status, text = _get_unraised(
        _exception_envelope_app(server_side_errors=True), "/record"
    )
    assert status == 500
    assert json.loads(text) == {"detail": SERVER_SIDE_VALIDATION_ERROR_DETAIL}

    status, text = _get_unraised(
        _exception_envelope_app(server_side_errors=False), "/record"
    )
    assert status == 500
    assert json.loads(text) == {"error": "envelope"}


def test_installer_keeps_an_existing_server_side_handler() -> None:
    app = FastAPI()

    async def own(_request: Request, _exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=500, content={})

    app.add_exception_handler(ValidationError, own)

    install_input_free_validation_errors(app)

    assert app.exception_handlers[ValidationError] is own
    assert app.exception_handlers[ResponseValidationError] is (
        input_free_server_side_validation_error_handler
    )


def _value_error_app(*, server_side_errors: bool) -> FastAPI:
    app = FastAPI()

    @app.exception_handler(ValueError)
    async def bad_value(_request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": "bad value"})

    @app.get("/record")
    async def record() -> dict[str, int]:
        return {"mrn": _Record.model_validate({"mrn": _MRN}).mrn}

    install_input_free_validation_errors(app, server_side_errors=server_side_errors)
    return app


def test_value_error_handler_is_pre_empted_unless_opted_out() -> None:
    # Documented: pydantic's ValidationError subclasses ValueError, and
    # Starlette picks the most specific registered class.
    status, text = _get_unraised(_value_error_app(server_side_errors=True), "/record")
    assert status == 500
    assert json.loads(text) == {"detail": SERVER_SIDE_VALIDATION_ERROR_DETAIL}

    status, text = _get_unraised(_value_error_app(server_side_errors=False), "/record")
    assert status == 400
    assert json.loads(text) == {"detail": "bad value"}


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
