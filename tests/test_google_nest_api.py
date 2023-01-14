import json
from typing import Awaitable, Callable
from unittest.mock import patch

import aiohttp
import pytest

from google_nest_sdm import google_nest_api
from google_nest_sdm.auth import AbstractAuth
from google_nest_sdm.exceptions import ApiException, AuthException

from .conftest import (
    FAKE_TOKEN,
    PROJECT_ID,
    DeviceHandler,
    NewHandler,
    Recorder,
    StructureHandler,
    reply_handler,
)


async def test_get_device(
    device_handler: DeviceHandler,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
    device_id = device_handler.add_device(device_type="sdm.devices.types.device-type")

    api = await api_client()

    device = await api.async_get_device(device_id.split("/")[-1])
    assert device
    assert device.name == device_id
    assert device.type == "sdm.devices.types.device-type"


async def test_get_devices(
    device_handler: DeviceHandler,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
    device_id1 = device_handler.add_device(device_type="sdm.devices.types.device-type1")
    device_id2 = device_handler.add_device(device_type="sdm.devices.types.device-type2")

    api = await api_client()

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
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.Fan": {
                "timerMode": "OFF",
            },
        }
    )
    post_handler = NewHandler(recorder, [{}])
    app.router.add_post(f"/{device_id}:executeCommand", post_handler)

    api = await api_client()
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
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
    structure_id = structure_handler.add_structure(
        traits={
            "sdm.structures.traits.Info": {
                "customName": "some-name",
            }
        }
    )

    api = await api_client()
    structure = await api.async_get_structure(structure_id.split("/")[-1])
    assert structure
    assert structure.name == structure_id
    assert "sdm.structures.traits.Info" in structure.traits


async def test_get_structures(
    app: aiohttp.web.Application,
    structure_handler: StructureHandler,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
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

    api = await api_client()
    structures = await api.async_get_structures()
    assert len(structures) == 2
    assert structures[0].name == structure_id1
    assert "sdm.structures.traits.Info" in structures[0].traits
    assert structures[1].name == structure_id2
    assert "sdm.structures.traits.Info" in structures[1].traits


async def test_client_error(
    app: aiohttp.web.Application,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
    # No server endpoint registered
    api = await api_client()
    with patch(
        "google_nest_sdm.google_nest_api.AbstractAuth._request",
        side_effect=aiohttp.ClientConnectionError(),
    ), pytest.raises(ApiException):
        await api.async_get_structures()


async def test_api_get_error(
    app: aiohttp.web.Application,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
    # No server endpoint registered
    api = await api_client()
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
    device_handler.token = "updated-token"
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
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
    api = await api_client()
    devices = await api.async_get_devices()
    assert devices == []


async def test_get_devices_missing_devices(
    app: aiohttp.web.Application,
    project_id: str,
    recorder: Recorder,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
    reply_handler(app, f"/enterprises/{project_id}/devices", recorder, [{}])
    api = await api_client()
    devices = await api.async_get_devices()
    assert devices == []


async def test_get_device_missing_devices(
    app: aiohttp.web.Application,
    recorder: Recorder,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
    app.router.add_get(
        "/enterprises/project-id1/devices/abc", NewHandler(recorder, [{}])
    )
    api = await api_client()
    device = await api.async_get_device("abc")
    assert device is None


async def test_no_structures(
    app: aiohttp.web.Application,
    structure_handler: StructureHandler,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
    api = await api_client()
    structures = await api.async_get_structures()
    assert structures == []


async def test_get_structures_missing_structures(
    app: aiohttp.web.Application,
    project_id: str,
    recorder: Recorder,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
    reply_handler(app, "/enterprises/{project_id}/structures", recorder, [{}])
    api = await api_client()
    structures = await api.async_get_structures()
    assert structures == []


async def test_get_structure_missing_structures(
    app: aiohttp.web.Application,
    recorder: Recorder,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
    app.router.add_get(
        "/enterprises/project-id1/structures/abc", NewHandler(recorder, [{}])
    )
    api = await api_client()
    structure = await api.async_get_structure("abc")
    assert structure is None


async def test_api_post_error_with_json_response(
    app: aiohttp.web.Application,
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

    json_response = {
        "error": {
            "code": 400,
            "message": "Some error message",
            "status": "FAILED_PRECONDITION",
        },
    }

    async def fail_handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert request.headers["Authorization"] == "Bearer %s" % FAKE_TOKEN
        return aiohttp.web.Response(
            status=400, body=json.dumps(json_response), content_type="application/json"
        )

    app.router.add_post(f"/{device_id}:executeCommand", fail_handler)

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert device.name == device_id
    trait = device.traits["sdm.devices.traits.ThermostatTemperatureSetpoint"]

    with pytest.raises(
        ApiException, match=r".*FAILED_PRECONDITION: Some error message.*"
    ):
        await trait.set_heat(25.0)
