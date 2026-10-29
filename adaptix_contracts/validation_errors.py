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
message line. The installer also registers handlers for those two: an HTTP
caller gets a 500 with no detail, a WebSocket is closed with 1011, and one
``ERROR`` record (the error types and locations, the route template and the
traceback frames; never ``msg``, never ``str(exc)``) keeps the defect
diagnosable. The two server-side handlers are registered only where the app
has none of its own (``dict.setdefault``), and because pydantic's
``ValidationError`` subclasses ``ValueError``, an app that handles
``ValueError`` itself sees pydantic errors raised in routes go to this
handler instead once the installer runs; ``server_side_errors=False`` keeps
the app's own routing.

``msg`` is the validator's own text. Pydantic's built-in messages name the rule,
not the value, but a custom validator that lets an exception's text through (for
example ``date.fromisoformat``'s "day 30 must be in range 1..28 for month 2 in
year 1950") repeats the value in ``msg``. That is the validator's defect, fixed in
the validator; rewriting every ``msg`` here would also erase the field-level
guidance callers rely on. The server-side ``ERROR`` record has no caller to
guide, so it drops ``msg`` and keeps only ``type`` and ``loc``; ``loc`` can
still name a mapping key, which is a value when a model is keyed by one.
"""

from __future__ import annotations

import json
import logging
import traceback
from collections.abc import Iterable, Mapping
from typing import overload

from fastapi import FastAPI, Request, WebSocket, status
from fastapi.exceptions import (
    RequestValidationError,
    ResponseValidationError,
    WebSocketRequestValidationError,
)
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.websockets import WebSocketState

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


@overload
async def input_free_server_side_validation_error_handler(
    connection: Request, exc: Exception
) -> JSONResponse: ...


@overload
async def input_free_server_side_validation_error_handler(
    connection: WebSocket, exc: Exception
) -> None: ...


async def input_free_server_side_validation_error_handler(
    connection: Request | WebSocket, exc: Exception
) -> JSONResponse | None:
    """Answer a server-side validation failure without repeating anything.

    Registered for pydantic ``ValidationError`` and FastAPI
    ``ResponseValidationError``. Both are normally defects in the service (a
    stored record or an upstream answer that no longer fits its model, a
    return value that does not fit ``response_model``), so the status stays
    500 and the body is only :data:`SERVER_SIDE_VALIDATION_ERROR_DETAIL`. A
    route that validates caller input by hand (``Model.model_validate(...)``
    on a body or frame it read itself) raises the same exception and gets
    the same 500; such a route should raise ``RequestValidationError`` (or a
    422 ``HTTPException``) itself if it wants the caller told.

    Starlette dispatches exception handlers for both scope types, so this
    handler is called with a ``Request`` on an HTTP route and with a
    ``WebSocket`` on a WebSocket route (a frame parsed by hand with
    ``Model.model_validate_json(await websocket.receive_text())`` is the usual
    source). The WebSocket is closed with 1011 (internal error) and nothing
    is returned; a ``JSONResponse`` cannot be sent on a websocket scope.

    One ``ERROR`` record is logged so the defect stays diagnosable: the
    exception class, the method (``WEBSOCKET`` for a socket), the route
    template (never the served path, which can carry an identifier), each
    error's ``type`` and ``loc`` and the traceback frames. Neither ``msg``
    (a custom validator's text can repeat the value) nor ``str(exc)``
    (pydantic puts ``input_value=...`` in it) is logged.
    """
    if not isinstance(exc, (ValidationError, ResponseValidationError)):
        raise exc
    route = connection.scope.get("route")
    _logger.error(
        "%s on %s %s: %s\n%s",
        type(exc).__name__,
        connection.scope.get("method", "WEBSOCKET"),
        getattr(route, "path", "<unrouted>"),
        json.dumps(_types_and_locations(exc.errors())),
        "".join(traceback.format_tb(exc.__traceback__)),
    )
    if isinstance(connection, WebSocket):
        if connection.application_state is not WebSocketState.DISCONNECTED:
            await connection.close(code=status.WS_1011_INTERNAL_ERROR)
        return None
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

    With ``server_side_errors`` (the default since 5.48.0; 5.47.0 installed
    only the two above) it also registers
    :func:`input_free_server_side_validation_error_handler` for pydantic
    ``ValidationError`` and FastAPI ``ResponseValidationError``, so neither
    reaches the ASGI server's traceback with the failing value in its message.
    Those two are registered only where the app has no handler of its own for
    exactly that class (``setdefault``; an existing one is kept as it is).
    Starlette picks a handler by walking the exception's MRO, and pydantic's
    ``ValidationError`` subclasses ``ValueError``, so an app that handles
    ``ValueError`` itself (answering 400, for example) stops seeing pydantic
    errors raised in its routes once this runs: they are answered 500 here.
    Pass ``server_side_errors=False`` to keep such an app's own routing, or
    when its own handler for those two is known not to log ``str(exc)``.
    """
    app.add_exception_handler(
        RequestValidationError, input_free_validation_error_handler
    )
    app.add_exception_handler(
        WebSocketRequestValidationError,
        input_free_websocket_validation_error_handler,
    )
    if server_side_errors:
        for exc_type in (ValidationError, ResponseValidationError):
            app.exception_handlers.setdefault(
                exc_type, input_free_server_side_validation_error_handler
            )


def _types_and_locations(
    errors: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    """What the server-side ``ERROR`` record carries per error: no ``msg``."""
    return [
        {"type": error["type"], "loc": list(_location(error["loc"]))}
        for error in errors
    ]


def _location(loc: object) -> Iterable[object]:
    if isinstance(loc, (list, tuple)):
        return loc
    return (loc,)
