"""Fixtures and libraries shared by tests."""

from typing import AsyncGenerator, Awaitable, Callable, Optional, cast

import aiohttp
import pytest

from google_nest_sdm.auth import AbstractAuth
from google_nest_sdm.event import EventMessage

FAKE_TOKEN = "some-token"


@pytest.fixture
async def app() -> AsyncGenerator[aiohttp.web.Application, None]:
    app = aiohttp.web.Application()
    yield app


@pytest.fixture
async def server(
    app, aiohttp_server
) -> Callable[[], Awaitable[aiohttp.test_utils.TestServer]]:
    async def _make_server() -> aiohttp.test_utils.TestServer:
        server = await aiohttp_server(app)
        assert isinstance(server, aiohttp.test_utils.TestServer)
        return server

    return _make_server


@pytest.fixture
async def client(
    loop, server, aiohttp_client
) -> Callable[[], Awaitable[aiohttp.test_utils.TestClient]]:

    # Cache the value so that it can be mutated by a test
    cached_client: Optional[aiohttp.test_utils.TestClient] = None

    async def _make_client() -> aiohttp.test_utils.TestClient:
        nonlocal cached_client
        if not cached_client:
            cached_client = await aiohttp_client(await server())
            assert isinstance(cached_client, aiohttp.test_utils.TestClient)
        return cached_client

    return _make_client


class FakeAuth(AbstractAuth):
    def __init__(self, test_client: aiohttp.test_utils.TestClient) -> None:
        super().__init__(cast(aiohttp.ClientSession, test_client), "path-prefix")

    async def async_get_access_token(self) -> str:
        return FAKE_TOKEN


@pytest.fixture
async def auth_client(client) -> Callable[[], Awaitable[AbstractAuth]]:
    async def _make_auth() -> AbstractAuth:
        return FakeAuth(await client())

    return _make_auth


@pytest.fixture
def event(auth) -> Callable[[dict], EventMessage]:
    def _make_event(raw_data: dict) -> EventMessage:
        return EventMessage(raw_data, auth)

    return _make_event
