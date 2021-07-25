"""Tests for the request client library."""

import aiohttp


async def test_request(app, auth_client) -> None:
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

    auth = await auth_client()
    resp = await auth.request(
        "get",
        "some-path",
        headers={"header-1": "value-1"},
        params={"client_id": "some-client-id"},
    )
    resp.raise_for_status()
    data = await resp.json()
    assert data["some-key"] == "some-value"


async def test_auth_header(app, auth_client) -> None:
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

    auth = await auth_client()
    resp = await auth.request(
        "get",
        "some-path",
        headers={"header-1": "value-1", "Authorization": "Basic other-token"},
        params={"client_id": "some-client-id"},
    )
    resp.raise_for_status()
    data = await resp.json()
    assert data["some-key"] == "some-value"


async def test_full_url(app, client, server, auth_client) -> None:
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

    def client_make_url(url):
        assert url == "https://example/path-prefix/some-path"
        return test_server.make_url("/path-prefix/some-path")

    test_client = await client()
    test_client.make_url = client_make_url  # type: ignore

    auth = await auth_client()
    resp = await auth.request(
        "get",
        "https://example/path-prefix/some-path",
        headers={"header-1": "value-1"},
        params={"client_id": "some-client-id"},
    )
    resp.raise_for_status()
    data = await resp.json()
    assert data["some-key"] == "some-value"
