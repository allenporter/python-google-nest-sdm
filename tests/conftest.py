"""Fixtures and libraries shared by tests."""

from typing import Any, AsyncGenerator, Awaitable, Callable, Dict, List, Optional, cast

import aiohttp
import pytest
from aiohttp.test_utils import TestClient, TestServer

from google_nest_sdm.auth import AbstractAuth
from google_nest_sdm.device import Device
from google_nest_sdm.event import EventMessage

FAKE_TOKEN = "some-token"


@pytest.fixture
async def app() -> AsyncGenerator[aiohttp.web.Application, None]:
    app = aiohttp.web.Application()
    yield app


@pytest.fixture
async def server(
    app: aiohttp.web.Application,
    aiohttp_server: Callable[[aiohttp.web.Application], Awaitable[TestServer]],
) -> Callable[[], Awaitable[TestServer]]:
    async def _make_server() -> TestServer:
        server = await aiohttp_server(app)
        assert isinstance(server, TestServer)
        return server

    return _make_server


@pytest.fixture
async def client(
    loop: Any,
    server: Callable[[], Awaitable[TestServer]],
    aiohttp_client: Callable[[TestServer], Awaitable[TestClient]],
) -> Callable[[], Awaitable[TestClient]]:

    # Cache the value so that it can be mutated by a test
    cached_client: Optional[TestClient] = None

    async def _make_client() -> TestClient:
        nonlocal cached_client
        if not cached_client:
            cached_client = await aiohttp_client(await server())
            assert isinstance(cached_client, TestClient)
        return cached_client

    return _make_client


class FakeAuth(AbstractAuth):
    def __init__(self, test_client: TestClient, path_prefix: str = "") -> None:
        super().__init__(cast(aiohttp.ClientSession, test_client), path_prefix)

    async def async_get_access_token(self) -> str:
        return FAKE_TOKEN


@pytest.fixture
async def auth_client(
    app: aiohttp.web.Application, client: Any
) -> Callable[[str], Awaitable[AbstractAuth]]:
    async def _make_auth(path_prefix: str = "") -> AbstractAuth:
        return FakeAuth(await client(), path_prefix)

    return _make_auth


class RefreshingAuth(AbstractAuth):
    def __init__(self, test_client: TestClient) -> None:
        super().__init__(cast(aiohttp.ClientSession, test_client), "")

    async def async_get_access_token(self) -> str:
        resp = await self._websession.request("get", "/refresh-auth")
        resp.raise_for_status()
        json = await resp.json()
        assert isinstance(json["token"], str)
        return json["token"]


@pytest.fixture
async def refreshing_auth_client(
    app: aiohttp.web.Application, client: Any
) -> Callable[[], Awaitable[AbstractAuth]]:
    async def _make_auth() -> AbstractAuth:
        return RefreshingAuth(await client())

    return _make_auth


@pytest.fixture
def event_message(
    app: aiohttp.web.Application, auth_client: Callable[[], Awaitable[AbstractAuth]]
) -> Callable[[Dict[str, Any]], Awaitable[EventMessage]]:
    async def _make_event(raw_data: Dict[str, Any]) -> EventMessage:
        return EventMessage(raw_data, await auth_client())

    return _make_event


@pytest.fixture
def fake_event_message() -> Callable[[Dict[str, Any]], EventMessage]:
    def _make_event(raw_data: Dict[str, Any]) -> EventMessage:
        return EventMessage(raw_data, cast(AbstractAuth, None))

    return _make_event


@pytest.fixture
def fake_device() -> Callable[[Dict[str, Any]], Device]:
    def _make_device(raw_data: Dict[str, Any]) -> Device:
        return Device.MakeDevice(raw_data, cast(AbstractAuth, None))

    return _make_device


class Recorder:
    request: Optional[Dict[str, Any]] = None


def NewDeviceHandler(
    r: Recorder, devices: List[Dict[str, Any]], token: str = FAKE_TOKEN
) -> Callable[[aiohttp.web.Request], Awaitable[aiohttp.web.Response]]:
    return NewHandler(r, [{"devices": devices}], token=token)


def NewStructureHandler(
    r: Recorder, structures: List[Dict[str, Any]], token: str = FAKE_TOKEN
) -> Callable[[aiohttp.web.Request], Awaitable[aiohttp.web.Response]]:
    return NewHandler(r, [{"structures": structures}], token=token)


def NewHandler(
    r: Recorder, responses: List[Dict[str, Any]], token: str = FAKE_TOKEN
) -> Callable[[aiohttp.web.Request], Awaitable[aiohttp.web.Response]]:
    async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert request.headers["Authorization"] == "Bearer %s" % token
        s = await request.text()
        r.request = await request.json() if s else {}
        return aiohttp.web.json_response(responses.pop(0))

    return handler


def NewImageHandler(
    response: List[bytes], token: str = FAKE_TOKEN
) -> Callable[[aiohttp.web.Request], Awaitable[aiohttp.web.Response]]:
    async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert request.headers["Authorization"] == "Basic %s" % token
        return aiohttp.web.Response(body=response.pop(0))

    return handler
