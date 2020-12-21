import aiohttp
from yarl import URL

from google_nest_sdm.device import AbstractAuth


class FakeAuth(AbstractAuth):
    def __init__(self, websession):
        super().__init__(websession, "path-prefix")

    async def async_get_access_token(self) -> str:
        return "some-token"


async def test_request(aiohttp_server) -> None:
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

    app = aiohttp.web.Application()
    app.router.add_get("/path-prefix/some-path", handler)
    server = await aiohttp_server(app)

    async with aiohttp.test_utils.TestClient(server) as client:
        auth = FakeAuth(client)
        resp = await auth.request(
            "get",
            "some-path",
            headers={"header-1": "value-1"},
            params={"client_id": "some-client-id"},
        )
        resp.raise_for_status()
        data = await resp.json()
        assert data["some-key"] == "some-value"


async def test_auth_header(aiohttp_server) -> None:
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

    app = aiohttp.web.Application()
    app.router.add_get("/path-prefix/some-path", handler)
    server = await aiohttp_server(app)

    async with aiohttp.test_utils.TestClient(server) as client:
        auth = FakeAuth(client)
        resp = await auth.request(
            "get",
            "some-path",
            headers={"header-1": "value-1", "Authorization": "Basic other-token"},
            params={"client_id": "some-client-id"},
        )
        resp.raise_for_status()
        data = await resp.json()
        assert data["some-key"] == "some-value"


async def test_full_url(aiohttp_server) -> None:
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

    app = aiohttp.web.Application()
    app.router.add_get("/path-prefix/some-path", handler)
    server = await aiohttp_server(app)

    def client_make_url(url):
        assert url == "https://example/path-prefix/some-path"
        return server.make_url("/path-prefix/some-path")

    async with aiohttp.test_utils.TestClient(server) as client:
        client.make_url = client_make_url
        auth = FakeAuth(client)
        resp = await auth.request(
            "get",
            "https://example/path-prefix/some-path",
            headers={"header-1": "value-1"},
            params={"client_id": "some-client-id"},
        )
        resp.raise_for_status()
        data = await resp.json()
        assert data["some-key"] == "some-value"


