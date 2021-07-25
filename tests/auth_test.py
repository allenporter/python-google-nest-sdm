"""Tests for the request client library."""

from typing import Awaitable, Callable

import aiohttp
from aiohttp.test_utils import TestClient, TestServer
from yarl import URL

from google_nest_sdm.auth import AbstractAuth


async def test_request(
    app: aiohttp.web.Application, auth_client: Callable[[str], Awaitable[AbstractAuth]]
) -> None:
    async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert request.path == "/path-prefix/some-path"
        assert request.headers["header-1"] == "value-1"
        assert request.headers["Authorization"] == "Bearer some-token"
        assert request.query["client_id"] == "some-client-id"
        return aiohttp.web.json_response(
            {
                "some-key": "some-value",
            }
        )

    app.router.add_get("/path-prefix/some-path", handler)

    auth = await auth_client("/path-prefix")
    resp = await auth.request(
        "get",
        "some-path",
        headers={"header-1": "value-1"},
        params={"client_id": "some-client-id"},
    )
    resp.raise_for_status()
    data = await resp.json()
    assert data["some-key"] == "some-value"


async def test_auth_header(
    app: aiohttp.web.Application, auth_client: Callable[[str], Awaitable[AbstractAuth]]
) -> None:
    """Test that a request with an Ahthorization header is preserved."""

    async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert request.path == "/path-prefix/some-path"
        assert request.headers["header-1"] == "value-1"
        assert request.headers["Authorization"] == "Basic other-token"
        assert request.query["client_id"] == "some-client-id"
        return aiohttp.web.json_response(
            {
                "some-key": "some-value",
            }
        )

    app.router.add_get("/path-prefix/some-path", handler)

    auth = await auth_client("/path-prefix")
    resp = await auth.request(
        "get",
        "some-path",
        headers={"header-1": "value-1", "Authorization": "Basic other-token"},
        params={"client_id": "some-client-id"},
    )
    resp.raise_for_status()
    data = await resp.json()
    assert data["some-key"] == "some-value"


async def test_full_url(
    app: aiohttp.web.Application,
    client: Callable[[], Awaitable[TestClient]],
    server: Callable[[], Awaitable[TestServer]],
    auth_client: Callable[[str], Awaitable[AbstractAuth]],
) -> None:
    """Test that a request with an Ahthorization header is preserved."""

    async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert request.path == "/path-prefix/some-path"
        assert request.headers["header-1"] == "value-1"
        assert request.headers["Authorization"] == "Bearer some-token"
        assert request.query["client_id"] == "some-client-id"
        return aiohttp.web.json_response(
            {
                "some-key": "some-value",
            }
        )

    app.router.add_get("/path-prefix/some-path", handler)

    test_server = await server()

    def client_make_url(url: str) -> URL:
        assert url == "https://example/path-prefix/some-path"
        return test_server.make_url("/path-prefix/some-path")

    test_client = await client()
    test_client.make_url = client_make_url  # type: ignore

    auth = await auth_client("/path-prefix")
    resp = await auth.request(
        "get",
        "https://example/path-prefix/some-path",
        headers={"header-1": "value-1"},
        params={"client_id": "some-client-id"},
    )
    resp.raise_for_status()
    data = await resp.json()
    assert data["some-key"] == "some-value"
