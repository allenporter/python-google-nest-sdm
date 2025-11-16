"""Fixtures and libraries shared by tests."""

from __future__ import annotations

import uuid
from abc import ABC
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generator,
    Optional,
    cast,
)
import logging

import aiohttp
import pytest
from aiohttp.test_utils import TestClient, TestServer

from google_nest_sdm import diagnostics, google_nest_api
from google_nest_sdm.auth import AbstractAuth
from google_nest_sdm.device import Device
from google_nest_sdm.event import EventMessage

FAKE_TOKEN = "some-token"
PROJECT_ID = "project-id1"

_LOGGER = logging.getLogger(__name__)


def pytest_configure(config: pytest.Config) -> None:
    """Register marker for tests that log exceptions."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s.%(msecs)03d %(levelname)-8s %(name)s:%(filename)s:%(lineno)s %(message)s",  # noqa: E501
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    if config.getoption("verbose") > 0:
        logging.getLogger().setLevel(logging.DEBUG)


@pytest.fixture(name="app")
def mock_app() -> Generator[aiohttp.web.Application, None, None]:
    yield aiohttp.web.Application()


@pytest.fixture(name="server")
def mock_server(
    app: aiohttp.web.Application,
    aiohttp_server: Callable[[aiohttp.web.Application], Awaitable[TestServer]],
) -> Callable[[], Awaitable[TestServer]]:
    async def _make_server() -> TestServer:
        server = await aiohttp_server(app)
        server.skip_url_asserts = True
        assert isinstance(server, TestServer)
        return server

    return _make_server


@pytest.fixture(name="client")
def mock_client(
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


@pytest.fixture(name="api_client")
def mock_api_client(
    project_id: str,
    auth_client: Callable[[], Awaitable[AbstractAuth]],
) -> Callable[[], Awaitable[google_nest_api.GoogleNestAPI]]:
    """Fixture to provide an API client to avoid freezing the http router."""

    async def make_api() -> google_nest_api.GoogleNestAPI:
        auth = await auth_client()
        return google_nest_api.GoogleNestAPI(auth, project_id)

    return make_api


@pytest.fixture(name="api")
async def api_fixture(
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> google_nest_api.GoogleNestAPI:
    """Fixture to provide an API client."""
    return await api_client()


class FakeAuth(AbstractAuth):
    def __init__(self, test_client: TestClient, path_prefix: str = "") -> None:
        super().__init__(cast(aiohttp.ClientSession, test_client), path_prefix)

    async def async_get_access_token(self) -> str:
        return FAKE_TOKEN


@pytest.fixture(name="auth_client")
def mock_auth_client(
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
        return EventMessage.create_event(raw_data, await auth_client())

    return _make_event


@pytest.fixture
def fake_event_message() -> Callable[[Dict[str, Any]], EventMessage]:
    def _make_event(raw_data: Dict[str, Any]) -> EventMessage:
        return EventMessage.create_event(raw_data, cast(AbstractAuth, None))

    return _make_event


@pytest.fixture
def fake_device() -> Callable[[Dict[str, Any]], Device]:
    def _make_device(raw_data: Dict[str, Any]) -> Device:
        return Device.MakeDevice(raw_data, cast(AbstractAuth, None))

    return _make_device


class Recorder:
    request: Optional[Dict[str, Any]] = None


# Function type that returns a response for a given path
ResponseForPathFunc = Callable[[aiohttp.web.Request], dict[str, Any] | None]


class JsonHandler(ABC):
    """Request handler that replays mocks."""

    def __init__(
        self, recorder: Recorder, response_for_path: ResponseForPathFunc
    ) -> None:
        """Initialize Handler."""
        self.token: str = FAKE_TOKEN
        self.recorder = recorder
        self.response_for_path = response_for_path

    async def handler(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        _LOGGER.debug("Request: %s", request)
        assert request.headers["Authorization"] == "Bearer %s" % self.token
        s = await request.text()
        self.recorder.request = await request.json() if s else {}
        data = self.response_for_path(request)
        if data is None:
            raise aiohttp.web.HTTPNotFound()
        return aiohttp.web.json_response(data)


class DeviceHandler:
    """Handle requests to fetch devices."""

    def __init__(
        self, app: aiohttp.web.Application, project_id: str, recorder: Recorder
    ) -> None:
        """Initialize DeviceHandler."""
        self.json_handler = JsonHandler(recorder, self.get_response)
        self.app = app
        self.project_id = project_id
        self.devices: dict[str, dict[str, Any]] = {}
        self.device_commands: dict[str, list[dict[str, Any]]] = {}
        app.router.add_get(
            f"/enterprises/{project_id}/devices", self.json_handler.handler
        )
        app.router.add_get(
            f"/enterprises/{project_id}/devices/{{device_id:.+}}",
            self.json_handler.handler,
        )
        app.router.add_post(
            f"/enterprises/{project_id}/devices/{{device_id:.+}}:executeCommand",
            self.json_handler.handler,
        )

    def add_device(
        self,
        device_type: str = "sdm.devices.types.device-type1",
        traits: dict[str, Any] = {},
        parentRelations: list[dict[str, Any]] = [],
    ) -> str:
        """Add a fake device reply."""
        uid = uuid.uuid4().hex
        device_id = f"enterprises/{self.project_id}/devices/device-id-{uid}"
        self.devices[device_id] = {
            "name": device_id,
            "type": device_type,
            "traits": traits,
            "parentRelations": parentRelations,
        }
        return device_id

    def add_device_command(
        self, device_id: str, responses: list[dict[str, Any]]
    ) -> None:
        """Add a fake device command reply."""
        if device_id not in self.device_commands:
            self.device_commands[device_id] = []
        self.device_commands[device_id].extend(responses)

    def get_response(self, request: aiohttp.web.Request) -> dict[str, Any] | None:
        """Return devices API response."""
        if request.path_qs == f"/enterprises/{self.project_id}/devices":
            assert request.method == "GET"
            return {"devices": list(self.devices.values())}

        device_id = request.match_info["device_id"]
        assert device_id
        if device_data := self.devices.get(request.path_qs[1:]):
            assert request.method == "GET"
            return device_data
        if request.path_qs.startswith(
            f"/enterprises/{self.project_id}/devices/"
        ) and request.path_qs.endswith(":executeCommand"):
            device_id = request.path_qs[1:].split(":")[0]
            assert request.method == "POST"
            if device_id in self.device_commands and self.device_commands[device_id]:
                return self.device_commands[device_id].pop(0)
        return None


class StructureHandler:
    """Handle requests to fetch structures."""

    def __init__(
        self, app: aiohttp.web.Application, project_id: str, recorder: Recorder
    ) -> None:
        """Initialize StructureHandler."""
        self.json_handler = JsonHandler(recorder, self.get_response)
        self.app = app
        self.project_id = project_id
        self.structures: dict[str, dict[str, Any]] = {}
        app.router.add_get(
            f"/enterprises/{project_id}/structures", self.json_handler.handler
        )
        app.router.add_get(
            f"/enterprises/{project_id}/structures/{{structure_id:.+}}",
            self.json_handler.handler,
        )

    def add_structure(self, traits: dict[str, Any] = {}) -> str:
        """Add a structure to the response."""
        uid = uuid.uuid4().hex
        structure_id = f"enterprises/{self.project_id}/structures/structure-id-{uid}"
        self.structures[structure_id] = {
            "name": structure_id,
            "traits": traits,
        }
        return structure_id

    def get_response(self, request: aiohttp.web.Request) -> dict[str, Any] | None:
        """Return structure API response."""
        if request.path_qs == f"/enterprises/{self.project_id}/structures":
            assert request.method == "GET"
            return {"structures": list(self.structures.values())}
        if structure_data := self.structures.get(request.path_qs[1:]):
            assert request.method == "GET"
            return structure_data
        return None


@pytest.fixture
def project_id() -> str:
    return "project-id1"


@pytest.fixture
def recorder() -> Recorder:
    return Recorder()


@pytest.fixture(name="device_handler")
def mock_device_handler(
    app: aiohttp.web.Application, project_id: str, recorder: Recorder
) -> DeviceHandler:
    return DeviceHandler(app, project_id, recorder)


@pytest.fixture(name="structure_handler")
def mock_structure_handler(
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
        self.invoked: bool = False
        self.messages: list[EventMessage] = []

    async def async_handle_event(self, event_message: EventMessage) -> None:
        self.invoked = True
        self.messages.append(event_message)
