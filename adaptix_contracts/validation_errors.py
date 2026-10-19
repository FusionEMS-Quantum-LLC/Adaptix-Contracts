"""Answer a refused request (HTTP 422) without repeating what the caller sent.

FastAPI's default ``RequestValidationError`` answer carries each error's
``input`` -- the rejected value, or the whole body or block when a required
field is missing or a model validator refuses it -- and its ``ctx``. Adaptix
request bodies hold patient names, dates of birth, MRNs, addresses, clinical
notes, credentials and payment references, so the default sends them back to
the caller and into everything that records responses (Adaptix-Contracts#375).

:func:`install_input_free_validation_errors` replaces that default for one
app. Each error keeps ``type``, ``loc`` and ``msg`` in FastAPI's own
``{"detail": [...]}`` shape, so a client that reads ``loc`` and ``msg`` sees no
change. It is the answer Gateway (#379), Integrations (#335) and Transport
(#350) already give.

``msg`` is the validator's own text. Pydantic's built-in messages name the rule,
not the value, but a custom validator that lets an exception's text through (for
example ``date.fromisoformat``'s "day 30 must be in range 1..28 for month 2 in
year 1950") repeats the value in ``msg``. That is the validator's defect, fixed in
the validator; rewriting every ``msg`` here would also erase the field-level
guidance callers rely on.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping

from fastapi import FastAPI, Request, WebSocket, status
from fastapi.exceptions import RequestValidationError, WebSocketRequestValidationError
from fastapi.responses import JSONResponse

__all__ = [
    "input_free_validation_error_handler",
    "input_free_validation_errors",
    "input_free_websocket_validation_error_handler",
    "install_input_free_validation_errors",
]


def input_free_validation_errors(
    errors: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Keep each error's ``type``, ``loc`` and ``msg``; drop everything else.

    Dropped keys include ``input`` and ``ctx`` and anything a future Pydantic
    adds (``url``, for instance): an allow-list cannot start echoing a new field.
    """
    return [
        {
            "type": error["type"],
            "loc": list(_location(error["loc"])),
            "msg": error["msg"],
        }
        for error in errors
    ]


async def input_free_validation_error_handler(
    _request: Request, exc: Exception
) -> JSONResponse:
    """``RequestValidationError`` handler that never repeats the caller's input.

    Nothing is logged here: the access log already records the path and the 422,
    and logging the errors would copy ``input`` into the logs instead.
    """
    if not isinstance(exc, RequestValidationError):
        # Registered only for RequestValidationError; anything else reaching
        # here is a wiring defect, so let it surface as a server error.
        raise exc
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": input_free_validation_errors(exc.errors())},
    )


async def input_free_websocket_validation_error_handler(
    websocket: WebSocket, exc: Exception
) -> None:
    """``WebSocketRequestValidationError`` handler without the caller's input.

    FastAPI's default closes the socket (1008) with every error, ``input``
    included, as the close reason; this closes it the same way with the
    input-free errors.
    """
    if not isinstance(exc, WebSocketRequestValidationError):
        raise exc
    await websocket.close(
        code=status.WS_1008_POLICY_VIOLATION,
        reason=json.dumps(input_free_validation_errors(exc.errors())),
    )


def install_input_free_validation_errors(app: FastAPI) -> None:
    """Make ``app`` answer every refused request without the caller's input.

    Call once in the app factory, after ``FastAPI(...)``. It replaces FastAPI's
    default ``RequestValidationError`` and ``WebSocketRequestValidationError``
    handlers for that app only.
    """
    app.add_exception_handler(
        RequestValidationError, input_free_validation_error_handler
    )
    app.add_exception_handler(
        WebSocketRequestValidationError,
        input_free_websocket_validation_error_handler,
    )


def _location(loc: object) -> Iterable[object]:
    if isinstance(loc, (list, tuple)):
        return loc
    return (loc,)
