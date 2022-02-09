"""Tests for the request client library."""

from typing import Awaitable, Callable

import aiohttp
import pytest
from aiohttp.test_utils import TestClient, TestServer
from yarl import URL

from google_nest_sdm.auth import AbstractAuth
from google_nest_sdm.exceptions import ApiException


async def test_request(
    app: aiohttp.web.Application, auth_client: Callable[[str], Awaitable[AbstractAuth]]
) -> None:
    async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert request.path == "/path-prefix/some-path"
        assert request.headers["header-1"] == "value-1"
        assert request.headers["Authorization"] == "Bearer some-token"
        assert request.query == {"client_id": "some-client-id"}
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
    assert data == {"some-key": "some-value"}


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
    assert data == {"some-key": "some-value"}


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
    assert data == {"some-key": "some-value"}


async def test_get_json_response(
    app: aiohttp.web.Application, auth_client: Callable[[str], Awaitable[AbstractAuth]]
) -> None:
    async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert request.query["client_id"] == "some-client-id"
        return aiohttp.web.json_response(
            {
                "some-key": "some-value",
            }
        )

    app.router.add_get("/path-prefix/some-path", handler)

    auth = await auth_client("/path-prefix")
    data = await auth.get_json("some-path", params={"client_id": "some-client-id"})
    assert data == {"some-key": "some-value"}


async def test_get_json_response_unexpected(
    app: aiohttp.web.Application, auth_client: Callable[[str], Awaitable[AbstractAuth]]
) -> None:
    async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        return aiohttp.web.json_response(["value1", "value2"])

    app.router.add_get("/path-prefix/some-path", handler)

    auth = await auth_client("/path-prefix")
    with pytest.raises(ApiException):
        await auth.get_json("some-path")


async def test_get_json_response_unexpected_text(
    app: aiohttp.web.Application, auth_client: Callable[[str], Awaitable[AbstractAuth]]
) -> None:
    async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        return aiohttp.web.Response(text="body")

    app.router.add_get("/path-prefix/some-path", handler)

    auth = await auth_client("/path-prefix")
    with pytest.raises(ApiException):
        await auth.get_json("some-path")


async def test_post_json_response(
    app: aiohttp.web.Application, auth_client: Callable[[str], Awaitable[AbstractAuth]]
) -> None:
    async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        body = await request.json()
        assert body == {"client_id": "some-client-id"}
        return aiohttp.web.json_response(
            {
                "some-key": "some-value",
            }
        )

    app.router.add_post("/path-prefix/some-path", handler)

    auth = await auth_client("/path-prefix")
    data = await auth.post_json("some-path", json={"client_id": "some-client-id"})
    assert data == {"some-key": "some-value"}


async def test_post_json_response_unexpected(
    app: aiohttp.web.Application, auth_client: Callable[[str], Awaitable[AbstractAuth]]
) -> None:
    async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        return aiohttp.web.json_response(["value1", "value2"])

    app.router.add_post("/path-prefix/some-path", handler)

    auth = await auth_client("/path-prefix")
    with pytest.raises(ApiException):
        await auth.post_json("some-path")


async def test_post_json_response_unexpected_text(
    app: aiohttp.web.Application, auth_client: Callable[[str], Awaitable[AbstractAuth]]
) -> None:
    async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        return aiohttp.web.Response(text="body")

    app.router.add_post("/path-prefix/some-path", handler)

    auth = await auth_client("/path-prefix")
    with pytest.raises(ApiException):
        await auth.post_json("some-path")
