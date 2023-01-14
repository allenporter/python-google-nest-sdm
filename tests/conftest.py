"""Fixtures and libraries shared by tests."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Dict,
    Generator,
    List,
    Optional,
    cast,
)

import aiohttp
import pytest
from aiohttp.test_utils import TestClient, TestServer

from google_nest_sdm import diagnostics, google_nest_api
from google_nest_sdm.auth import AbstractAuth
from google_nest_sdm.device import Device
from google_nest_sdm.event import EventMessage

FAKE_TOKEN = "some-token"
PROJECT_ID = "project-id1"


@pytest.fixture
def loop(event_loop: Any) -> Any:
    return event_loop


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


@pytest.fixture
async def api_client(
    project_id: str,
    auth_client: Callable[[], Awaitable[AbstractAuth]],
) -> Callable[[], Awaitable[google_nest_api.GoogleNestAPI]]:
    async def make_api() -> google_nest_api.GoogleNestAPI:
        auth = await auth_client()
        return google_nest_api.GoogleNestAPI(auth, project_id)

    return make_api


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


class JsonHandler(ABC):
    """Request handler that replays mocks."""

    def __init__(self, recorder: Recorder) -> None:
        """Initialize Handler."""
        self.token: str = FAKE_TOKEN
        self.recorder = recorder

    @abstractmethod
    def get_response(self) -> dict[str, Any]:
        """Implemented by subclasses to return a response."""

    async def handler(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert request.headers["Authorization"] == "Bearer %s" % self.token
        s = await request.text()
        self.recorder.request = await request.json() if s else {}
        return aiohttp.web.json_response(self.get_response())


class ReplyHandler(JsonHandler):
    def __init__(self, recorder: Recorder, responses: List[Dict[str, Any]]) -> None:
        """Initialize ReplyHandler."""
        super().__init__(recorder)
        self.responses = responses

    def get_response(self) -> dict[str, Any]:
        """Return an API response."""
        return self.responses.pop(0)


def reply_handler(
    app: aiohttp.web.Application,
    path: str,
    recorder: Recorder,
    responses: List[Dict[str, Any]],
) -> ReplyHandler:
    """Create a new reply handler."""
    handler = ReplyHandler(recorder, responses)
    app.router.add_get(path, handler.handler)
    return handler


class DeviceHandler(JsonHandler):
    """Handle requests to fetch devices."""

    def __init__(
        self, app: aiohttp.web.Application, project_id: str, recorder: Recorder
    ) -> None:
        """Initialize DeviceHandler."""
        super().__init__(recorder)
        self.app = app
        self.project_id = project_id
        self.devices: List[Dict[str, Any]] = []
        app.router.add_get(f"/enterprises/{project_id}/devices", self.handler)

    def add_device(
        self,
        device_type: str = "sdm.devices.types.device-type1",
        traits: dict[str, Any] = {},
        parentRelations: List[dict[str, Any]] = [],
    ) -> str:
        """Add a fake device reply."""
        uid = uuid.uuid4().hex
        device_id = f"enterprises/{self.project_id}/devices/device-id-{uid}"
        device = {
            "name": device_id,
            "type": device_type,
            "traits": traits,
            "parentRelations": parentRelations,
        }
        # Setup device lookup reply
        reply_handler(self.app, f"/{device_id}", self.recorder, [device])
        # Setup device list reply
        self.devices.append(device)
        return device_id

    def get_response(self) -> dict[str, Any]:
        """Return devices API response."""
        return {"devices": self.devices}


class StructureHandler(JsonHandler):
    """Handle requests to fetch structures."""

    def __init__(
        self, app: aiohttp.web.Application, project_id: str, recorder: Recorder
    ) -> None:
        """Initialize StructureHandler."""
        super().__init__(recorder)
        self.app = app
        self.project_id = project_id
        self.structures: List[Dict[str, Any]] = []
        app.router.add_get(f"/enterprises/{project_id}/structures", self.handler)

    def add_structure(self, traits: dict[str, Any] = {}) -> str:
        """Add a structure to the response."""
        uid = uuid.uuid4().hex
        structure_id = f"enterprises/{self.project_id}/structures/structure-id-{uid}"
        structure = {
            "name": structure_id,
            "traits": traits,
        }
        # Setup structure lookup reply
        reply_handler(self.app, f"/{structure_id}", self.recorder, [structure])
        # Setup structure list reply
        self.structures.append(structure)
        return structure_id

    def get_response(self) -> dict[str, Any]:
        """Return structure API response."""
        return {"structures": self.structures}


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


@pytest.fixture
def project_id() -> str:
    return "project-id1"


@pytest.fixture
def recorder() -> Recorder:
    return Recorder()


@pytest.fixture
def device_handler(
    app: aiohttp.web.Application, project_id: str, recorder: Recorder
) -> DeviceHandler:
    return DeviceHandler(app, project_id, recorder)


@pytest.fixture
def structure_handler(
    app: aiohttp.web.Application, project_id: str, recorder: Recorder
) -> StructureHandler:
    return StructureHandler(app, project_id, recorder)


@pytest.fixture(autouse=True)
def reset_diagnostics() -> Generator[None, None, None]:
    yield
    diagnostics.reset()


def assert_diagnostics(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    """Helper method for stripping timing based daignostics."""

    def scrub_dict(data: dict[str, Any]) -> dict[str, Any]:
        drop_keys = []
        for k1, v1 in data.items():
            if k1.endswith("_sum"):
                drop_keys.append(k1)
        for k in drop_keys:
            del data[k]
        return data

    actual = scrub_dict(actual)

    for k1, v1 in actual.items():
        if isinstance(v1, dict):
            actual[k1] = scrub_dict(v1)

    assert actual == expected


class EventCallback:
    """A callback that can be used in tests for assertions."""

    def __init__(self) -> None:
        """Initialize EventCallback."""
        self.invoked = False
        self.messages: list[EventMessage] = []

    async def async_handle_event(self, event_message: EventMessage) -> None:
        self.invoked = True
        self.messages.append(event_message)
