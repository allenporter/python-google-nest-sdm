import json
from typing import Awaitable, Callable
from unittest.mock import patch
import re
from http import HTTPStatus

import aiohttp
import pytest

from google_nest_sdm import google_nest_api
from google_nest_sdm.auth import AbstractAuth
from google_nest_sdm.exceptions import (
    ApiException,
    AuthException,
    NotFoundException,
    ApiForbiddenException,
)

from .conftest import (
    FAKE_TOKEN,
    PROJECT_ID,
    DeviceHandler,
    Recorder,
    StructureHandler,
)


async def test_get_device(
    device_handler: DeviceHandler,
    api: google_nest_api.GoogleNestAPI,
) -> None:
    device_id = device_handler.add_device(device_type="sdm.devices.types.device-type")

    device = await api.async_get_device(device_id.split("/")[-1])
    assert device
    assert device.name == device_id
    assert device.type == "sdm.devices.types.device-type"


async def test_get_devices(
    device_handler: DeviceHandler,
    api: google_nest_api.GoogleNestAPI,
) -> None:
    device_id1 = device_handler.add_device(device_type="sdm.devices.types.device-type1")
    device_id2 = device_handler.add_device(device_type="sdm.devices.types.device-type2")

    devices = await api.async_get_devices()
    assert len(devices) == 2
    assert devices[0].name == device_id1
    assert devices[0].type == "sdm.devices.types.device-type1"
    assert devices[1].name == device_id2
    assert devices[1].type == "sdm.devices.types.device-type2"


async def test_fan_set_timer(
    app: aiohttp.web.Application,
    recorder: Recorder,
    device_handler: DeviceHandler,
    api: google_nest_api.GoogleNestAPI,
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.Fan": {
                "timerMode": "OFF",
            },
        }
    )
    device_handler.add_device_command(device_id, [{}])

    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert device_id == device.name
    trait = device.traits["sdm.devices.traits.Fan"]
    assert trait.timer_mode == "OFF"
    await trait.set_timer("ON", 3600)
    assert recorder.request == {
        "command": "sdm.devices.commands.Fan.SetTimer",
        "params": {
            "timerMode": "ON",
            "duration": "3600s",
        },
    }


async def test_get_structure(
    app: aiohttp.web.Application,
    structure_handler: StructureHandler,
    api: google_nest_api.GoogleNestAPI,
) -> None:
    structure_id = structure_handler.add_structure(
        traits={
            "sdm.structures.traits.Info": {
                "customName": "some-name",
            }
        }
    )

    structure = await api.async_get_structure(structure_id.split("/")[-1])
    assert structure
    assert structure.name == structure_id
    assert "sdm.structures.traits.Info" in structure.traits


async def test_get_structures(
    app: aiohttp.web.Application,
    structure_handler: StructureHandler,
    api: google_nest_api.GoogleNestAPI,
) -> None:
    structure_id1 = structure_handler.add_structure(
        traits={
            "sdm.structures.traits.Info": {
                "customName": "some-name1",
            }
        }
    )
    structure_id2 = structure_handler.add_structure(
        {
            "sdm.structures.traits.Info": {
                "customName": "some-name2",
            }
        }
    )

    structures = await api.async_get_structures()
    assert len(structures) == 2
    assert structures[0].name == structure_id1
    assert "sdm.structures.traits.Info" in structures[0].traits
    assert structures[1].name == structure_id2
    assert "sdm.structures.traits.Info" in structures[1].traits


async def test_client_error(
    app: aiohttp.web.Application,
    api: google_nest_api.GoogleNestAPI,
) -> None:
    # No server endpoint registered
    with (
        patch(
            "google_nest_sdm.google_nest_api.AbstractAuth._request",
            side_effect=aiohttp.ClientConnectionError(),
        ),
        pytest.raises(ApiException),
    ):
        await api.async_get_structures()


async def test_api_get_error(
    app: aiohttp.web.Application,
    api: google_nest_api.GoogleNestAPI,
) -> None:
    # No server endpoint registered
    with pytest.raises(ApiException):
        await api.async_get_structures()


async def test_api_post_error(
    app: aiohttp.web.Application,
    recorder: Recorder,
    device_handler: DeviceHandler,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 23.0,
                "coolCelsius": 24.0,
            },
        }
    )

    async def fail_handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert request.headers["Authorization"] == "Bearer %s" % FAKE_TOKEN
        return aiohttp.web.Response(status=502)

    app.router.add_post(f"/{device_id}:executeCommand", fail_handler)

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert device.name == device_id
    trait = device.traits["sdm.devices.traits.ThermostatTemperatureSetpoint"]
    assert trait.heat_celsius == 23.0
    assert trait.cool_celsius == 24.0

    with pytest.raises(ApiException):
        await trait.set_heat(25.0)


async def test_auth_refresh(
    app: aiohttp.web.Application,
    recorder: Recorder,
    device_handler: DeviceHandler,
    refreshing_auth_client: Callable[[], Awaitable[AbstractAuth]],
) -> None:
    device_handler.json_handler.token = "updated-token"
    device_id = device_handler.add_device(traits={})

    async def auth_handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        return aiohttp.web.json_response({"token": "updated-token"})

    app.router.add_get("/refresh-auth", auth_handler)

    auth = await refreshing_auth_client()
    api = google_nest_api.GoogleNestAPI(auth, PROJECT_ID)

    devices = await api.async_get_devices()
    assert len(devices) == 1
    assert devices[0].name == device_id
    assert devices[0].type == "sdm.devices.types.device-type1"


async def test_auth_refresh_error(
    app: aiohttp.web.Application,
    device_handler: DeviceHandler,
    refreshing_auth_client: Callable[[], Awaitable[AbstractAuth]],
) -> None:
    async def auth_handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        return aiohttp.web.Response(status=401)

    app.router.add_get("/refresh-auth", auth_handler)

    auth = await refreshing_auth_client()
    api = google_nest_api.GoogleNestAPI(auth, PROJECT_ID)
    with pytest.raises(AuthException):
        await api.async_get_devices()


async def test_no_devices(
    app: aiohttp.web.Application,
    recorder: Recorder,
    device_handler: DeviceHandler,
    api: google_nest_api.GoogleNestAPI,
) -> None:
    devices = await api.async_get_devices()
    assert devices == []


async def test_get_devices_missing_devices(
    app: aiohttp.web.Application,
    project_id: str,
    recorder: Recorder,
    device_handler: DeviceHandler,
    api: google_nest_api.GoogleNestAPI,
) -> None:
    devices = await api.async_get_devices()
    assert devices == []


async def test_get_device_missing_devices(
    app: aiohttp.web.Application,
    recorder: Recorder,
    api: google_nest_api.GoogleNestAPI,
) -> None:
    with pytest.raises(NotFoundException):
        await api.async_get_device("abc")


async def test_no_structures(
    app: aiohttp.web.Application,
    structure_handler: StructureHandler,
    api: google_nest_api.GoogleNestAPI,
) -> None:
    structures = await api.async_get_structures()
    assert structures == []


async def test_get_structures_missing_structures(
    app: aiohttp.web.Application,
    project_id: str,
    recorder: Recorder,
    structure_handler: StructureHandler,
    api: google_nest_api.GoogleNestAPI,
) -> None:
    structures = await api.async_get_structures()
    assert structures == []


async def test_get_structure_missing_structures(
    app: aiohttp.web.Application,
    recorder: Recorder,
    structure_handler: StructureHandler,
    api: google_nest_api.GoogleNestAPI,
) -> None:
    structure_id = structure_handler.add_structure(traits={})
    structure_handler.structures[structure_id] = {"traits": {}}  # Remove name
    structure = await api.async_get_structure(structure_id.split("/")[-1])
    assert structure is None


@pytest.mark.parametrize(
    "status,error_dict,exc_type,err_match",
    [
        (
            HTTPStatus.BAD_REQUEST,
            {
                "code": 400,
                "message": "Some error message",
                "status": "FAILED_PRECONDITION",
            },
            ApiException,
            re.compile(r"Bad Request response from API \(400\).*Some error message"),
        ),
        (
            HTTPStatus.UNAUTHORIZED,
            {
                "code": 401,
                "message": "Some error message",
                "status": "UNAUTHENTICATED",
            },
            AuthException,
            re.compile(r"Unauthorized response from API \(401\).*Some error message"),
        ),
        (
            HTTPStatus.FORBIDDEN,
            {
                "code": 403,
                "message": "Some error message",
                "status": "PERMISSION_DENIED",
            },
            ApiForbiddenException,
            re.compile(r"Forbidden response from API \(403\):.*Some error message"),
        ),
        (
            HTTPStatus.NOT_FOUND,
            {
                "code": 404,
                "message": "Some error message",
                "status": "NOT_FOUND",
            },
            NotFoundException,
            re.compile(r"Not Found response from API \(404\):.*Some error message"),
        ),
        (
            HTTPStatus.INTERNAL_SERVER_ERROR,
            {
                "code": 500,
                "message": "Some error message",
                "status": "INTERNAL",
            },
            ApiException,
            re.compile(
                r"Internal Server Error response from API \(500\).*Some error message"
            ),
        ),
        (
            503,
            {
                "code": 503,
                "message": "Some error message",
                "status": "UNAVAILABLE",
            },
            ApiException,
            re.escape("Service Unavailable response from API (503)"),
        ),
    ],
)
async def test_api_post_error_with_json_response(
    app: aiohttp.web.Application,
    device_handler: DeviceHandler,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
    status: int,
    error_dict: dict,
    exc_type: type[Exception],
    err_match: str,
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 23.0,
                "coolCelsius": 24.0,
            },
        }
    )

    json_response = {
        "error": error_dict,
    }

    async def fail_handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert request.headers["Authorization"] == "Bearer %s" % FAKE_TOKEN
        return aiohttp.web.Response(
            status=status,
            body=json.dumps(json_response),
            content_type="application/json",
        )

    app.router.add_post(f"/{device_id}:executeCommand", fail_handler)

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert device.name == device_id
    trait = device.traits["sdm.devices.traits.ThermostatTemperatureSetpoint"]

    with pytest.raises(exc_type, match=err_match):
        await trait.set_heat(25.0)
