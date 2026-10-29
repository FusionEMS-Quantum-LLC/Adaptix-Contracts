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

The same leak exists on the server side of a route. A pydantic
``ValidationError`` raised while the route runs (a model built from a record
or an upstream answer), and FastAPI's ``ResponseValidationError`` (a return
value that does not fit ``response_model``), both carry ``input`` in their
``errors()`` and quote it in ``str(exc)``. Unhandled, they reach the ASGI
server's "Exception in ASGI application" traceback with the value in the
message line. The installer also registers handlers for those two: the
caller gets a 500 with no detail, and one input-free ``ERROR`` record (the
error types and locations, the route template and the traceback frames,
never ``str(exc)``) keeps the defect diagnosable.

``msg`` is the validator's own text. Pydantic's built-in messages name the rule,
not the value, but a custom validator that lets an exception's text through (for
example ``date.fromisoformat``'s "day 30 must be in range 1..28 for month 2 in
year 1950") repeats the value in ``msg``. That is the validator's defect, fixed in
the validator; rewriting every ``msg`` here would also erase the field-level
guidance callers rely on.
"""

from __future__ import annotations

import json
import logging
import traceback
from collections.abc import Iterable, Mapping

from fastapi import FastAPI, Request, WebSocket, status
from fastapi.exceptions import (
    RequestValidationError,
    ResponseValidationError,
    WebSocketRequestValidationError,
)
from fastapi.responses import JSONResponse
from pydantic import ValidationError

__all__ = [
    "SERVER_SIDE_VALIDATION_ERROR_DETAIL",
    "input_free_server_side_validation_error_handler",
    "input_free_validation_error_handler",
    "input_free_validation_errors",
    "input_free_websocket_validation_error_handler",
    "install_input_free_validation_errors",
]

#: The whole body of the 500 answered for a server-side validation failure.
#: It names nothing about the request or the record that failed.
SERVER_SIDE_VALIDATION_ERROR_DETAIL = "Internal Server Error"

_logger = logging.getLogger("adaptix_contracts.validation_errors")


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


async def input_free_server_side_validation_error_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Answer a server-side validation failure with a 500 that repeats nothing.

    Registered for pydantic ``ValidationError`` and FastAPI
    ``ResponseValidationError``. Both are defects in the service, not in the
    request, so the status stays 500 and the body is only
    :data:`SERVER_SIDE_VALIDATION_ERROR_DETAIL`.

    One ``ERROR`` record is logged so the defect stays diagnosable: the
    exception class, the route template (never the served path, which can
    carry an identifier), the input-free errors and the traceback frames.
    ``str(exc)`` is never logged; pydantic puts ``input_value=...`` in it.
    """
    if not isinstance(exc, (ValidationError, ResponseValidationError)):
        raise exc
    errors = input_free_validation_errors(exc.errors())
    route = request.scope.get("route")
    _logger.error(
        "%s on %s %s: %s\n%s",
        type(exc).__name__,
        request.method,
        getattr(route, "path", "<unrouted>"),
        json.dumps(errors),
        "".join(traceback.format_tb(exc.__traceback__)),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": SERVER_SIDE_VALIDATION_ERROR_DETAIL},
    )


def install_input_free_validation_errors(
    app: FastAPI, *, server_side_errors: bool = True
) -> None:
    """Make ``app`` answer every refused request without the caller's input.

    Call once in the app factory, after ``FastAPI(...)``. It replaces FastAPI's
    default ``RequestValidationError`` and ``WebSocketRequestValidationError``
    handlers for that app only.

    With ``server_side_errors`` (the default) it also registers
    :func:`input_free_server_side_validation_error_handler` for pydantic
    ``ValidationError`` and FastAPI ``ResponseValidationError``, so neither
    reaches the ASGI server's traceback with the failing value in its message.
    Pass ``server_side_errors=False`` when the app already routes those two
    through its own handler that is known not to log ``str(exc)``.
    """
    app.add_exception_handler(
        RequestValidationError, input_free_validation_error_handler
    )
    app.add_exception_handler(
        WebSocketRequestValidationError,
        input_free_websocket_validation_error_handler,
    )
    if server_side_errors:
        app.add_exception_handler(
            ValidationError, input_free_server_side_validation_error_handler
        )
        app.add_exception_handler(
            ResponseValidationError, input_free_server_side_validation_error_handler
        )


def _location(loc: object) -> Iterable[object]:
    if isinstance(loc, (list, tuple)):
        return loc
    return (loc,)
