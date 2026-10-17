"""Synchronous requests against an ASGI app, sent through httpx.ASGITransport.

Starlette 1.3+ types ``starlette.testclient.TestClient`` against httpx2, and
importing it (``fastapi.testclient``) raises StarletteDeprecationWarning. These
tests only need what this covers: an app, ``raise_server_exceptions``, and GET/POST
with headers. Like a bare ``TestClient(app)`` (not used as a context manager), it
does not run the app's lifespan. Cookies persist across one client's requests.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping

import httpx
from starlette.types import ASGIApp


class ASGIClient:
    def __init__(
        self,
        app: ASGIApp,
        *,
        raise_server_exceptions: bool = True,
        base_url: str = "http://testserver",
    ) -> None:
        super().__init__()
        self._app = app
        self._raise_server_exceptions = raise_server_exceptions
        self._base_url = base_url
        self.cookies = httpx.Cookies()

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        json: object = None,
    ) -> httpx.Response:
        async def send() -> httpx.Response:
            transport = httpx.ASGITransport(
                app=self._app, raise_app_exceptions=self._raise_server_exceptions
            )
            async with httpx.AsyncClient(
                transport=transport, base_url=self._base_url, cookies=self.cookies
            ) as client:
                response = await client.request(method, url, headers=headers, json=json)
                self.cookies.update(client.cookies)
                return response

        return asyncio.run(send())

    def get(
        self, url: str, *, headers: Mapping[str, str] | None = None
    ) -> httpx.Response:
        return self.request("GET", url, headers=headers)

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        json: object = None,
    ) -> httpx.Response:
        return self.request("POST", url, headers=headers, json=json)
