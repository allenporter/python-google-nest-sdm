from .context import google_nest_sdm

import aiohttp
import datetime
import pytest
from pytest_aiohttp import aiohttp_server

from google_nest_sdm.device import AbstractAuth
from google_nest_sdm import google_nest_api


PROJECT_ID = "project-id1"


class FakeAuth(AbstractAuth):
    def __init__(self, websession):
        super().__init__(websession, "")

    async def async_get_access_token(self) -> str:
        return "some-token"


class Recorder:
    request = None


def NewDeviceHandler(r: Recorder, devices: dict):
    return NewRequestRecorder(r, [{"devices": devices}])


def NewStructureHandler(r: Recorder, structures: dict):
    return NewRequestRecorder(r, [{"structures": structures}])


def NewRequestRecorder(r: Recorder, response: list):
    async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert request.headers["Authorization"] == "Bearer some-token"
        s = await request.text()
        r.request = await request.json() if s else {}
        return aiohttp.web.json_response(response.pop(0))

    return handler


async def test_get_devices(aiohttp_server) -> None:
    r = Recorder()
    handler = NewDeviceHandler(
        r,
        [
            {
                "name": "enterprises/project-id1/devices/device-id1",
                "type": "sdm.devices.types.device-type1",
                "traits": {},
                "parentRelations": [],
            },
            {
                "name": "enterprises/project-id1/devices/device-id2",
                "type": "sdm.devices.types.device-type2",
                "traits": {},
                "parentRelations": [],
            },
        ],
    )

    app = aiohttp.web.Application()
    app.router.add_get("/enterprises/project-id1/devices", handler)
    server = await aiohttp_server(app)

    async with aiohttp.test_utils.TestClient(server) as client:
        api = google_nest_api.GoogleNestAPI(FakeAuth(client), PROJECT_ID)
        devices = await api.async_get_devices()
        assert len(devices) == 2
        assert "enterprises/project-id1/devices/device-id1" == devices[0].name
        assert "sdm.devices.types.device-type1" == devices[0].type
        assert "enterprises/project-id1/devices/device-id2" == devices[1].name
        assert "sdm.devices.types.device-type2" == devices[1].type


async def test_thermostat_eco_set_mode(aiohttp_server) -> None:
    r = Recorder()
    handler = NewDeviceHandler(
        r,
        [
            {
                "name": "enterprises/project-id1/devices/device-id1",
                "traits": {
                    "sdm.devices.traits.ThermostatEco": {
                        "availableModes": ["MANUAL_ECO", "OFF"],
                        "mode": "MANUAL_ECO",
                        "heatCelsius": 20.0,
                        "coolCelsius": 22.0,
                    },
                },
            }
        ],
    )
    post_handler = NewRequestRecorder(r, [])

    app = aiohttp.web.Application()
    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_post(
        "/enterprises/project-id1/devices/device-id1:executeCommand", post_handler
    )
    server = await aiohttp_server(app)

    async with aiohttp.test_utils.TestClient(server) as client:
        api = google_nest_api.GoogleNestAPI(FakeAuth(client), PROJECT_ID)
        devices = await api.async_get_devices()
        assert len(devices) == 1
        device = devices[0]
        assert "enterprises/project-id1/devices/device-id1" == device.name
        trait = device.traits["sdm.devices.traits.ThermostatEco"]
        assert trait.mode == "MANUAL_ECO"
        await trait.set_mode("OFF")
        expected_request = {
            "command": "sdm.devices.commands.ThermostatEco.SetMode",
            "params": {"mode": "OFF"},
        }
        assert expected_request == r.request


async def test_thermostat_mode_set_mode(aiohttp_server) -> None:
    r = Recorder()
    handler = NewDeviceHandler(
        r,
        [
            {
                "name": "enterprises/project-id1/devices/device-id1",
                "traits": {
                    "sdm.devices.traits.ThermostatMode": {
                        "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                        "mode": "COOL",
                    },
                },
            }
        ],
    )
    post_handler = NewRequestRecorder(r, [])

    app = aiohttp.web.Application()
    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_post(
        "/enterprises/project-id1/devices/device-id1:executeCommand", post_handler
    )
    server = await aiohttp_server(app)

    async with aiohttp.test_utils.TestClient(server) as client:
        api = google_nest_api.GoogleNestAPI(FakeAuth(client), PROJECT_ID)
        devices = await api.async_get_devices()
        assert len(devices) == 1
        device = devices[0]
        assert "enterprises/project-id1/devices/device-id1" == device.name
        trait = device.traits["sdm.devices.traits.ThermostatMode"]
        assert trait.mode == "COOL"
        await trait.set_mode("HEAT")
        expected_request = {
            "command": "sdm.devices.commands.ThermostatMode.SetMode",
            "params": {"mode": "HEAT"},
        }
        assert expected_request == r.request


async def test_thermostat_temperature_set_point(aiohttp_server) -> None:
    r = Recorder()
    handler = NewDeviceHandler(
        r,
        [
            {
                "name": "enterprises/project-id1/devices/device-id1",
                "traits": {
                    "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                        "heatCelsius": 23.0,
                        "coolCelsius": 24.0,
                    },
                },
            }
        ],
    )
    post_handler = NewRequestRecorder(r, [])

    app = aiohttp.web.Application()
    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_post(
        "/enterprises/project-id1/devices/device-id1:executeCommand", post_handler
    )
    server = await aiohttp_server(app)

    async with aiohttp.test_utils.TestClient(server) as client:
        api = google_nest_api.GoogleNestAPI(FakeAuth(client), PROJECT_ID)
        devices = await api.async_get_devices()
        assert len(devices) == 1
        device = devices[0]
        assert "enterprises/project-id1/devices/device-id1" == device.name
        trait = device.traits["sdm.devices.traits.ThermostatTemperatureSetpoint"]
        assert trait.heat_celsius == 23.0
        assert trait.cool_celsius == 24.0
        await trait.set_heat(25.0)
        expected_request = {
            "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetHeat",
            "params": {"heatCelsius": 25.0},
        }
        assert expected_request == r.request

        await trait.set_cool(26.0)
        expected_request = {
            "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetCool",
            "params": {"coolCelsius": 26.0},
        }
        assert expected_request == r.request

        await trait.set_range(27.0, 28.0)
        expected_request = {
            "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetRange",
            "params": {
                "heatCelsius": 27.0,
                "coolCelsius": 28.0,
            },
        }
        assert expected_request == r.request


async def test_camera_live_stream(aiohttp_server) -> None:
    r = Recorder()
    handler = NewDeviceHandler(
        r,
        [
            {
                "name": "enterprises/project-id1/devices/device-id1",
                "traits": {
                    "sdm.devices.traits.CameraLiveStream": {},
                },
            }
        ],
    )

    post_handler = NewRequestRecorder(
        r,
        [
            {
                "results": {
                    "streamUrls": {
                        "rtsp_url": "rtsps://someurl.com/CjY5Y3VKaTZwR3o4Y19YbTVfMF...?auth=g.0.streamingToken"
                    },
                    "streamExtensionToken": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                    "streamToken": "g.0.streamingToken",
                    "expiresAt": "2018-01-04T18:30:00.000Z",
                },
            },
            {
                "results": {
                    "streamExtensionToken": "dGNUlTU2CjY5Y3VKaTZwR3o4Y1...",
                    "streamToken": "g.1.newStreamingToken",
                    "expiresAt": "2019-01-04T18:30:00.000Z",
                }
            },
            {
                "results": {
                    "streamExtensionToken": "last-token...",
                    "streamToken": "g.2.newStreamingToken",
                    "expiresAt": "2020-01-04T18:30:00.000Z",
                }
            },
            {},
        ],
    )
    app = aiohttp.web.Application()
    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_post(
        "/enterprises/project-id1/devices/device-id1:executeCommand", post_handler
    )
    server = await aiohttp_server(app)

    async with aiohttp.test_utils.TestClient(server) as client:
        api = google_nest_api.GoogleNestAPI(FakeAuth(client), PROJECT_ID)
        devices = await api.async_get_devices()
        assert len(devices) == 1
        device = devices[0]
        assert "enterprises/project-id1/devices/device-id1" == device.name
        trait = device.traits["sdm.devices.traits.CameraLiveStream"]
        stream = await trait.generate_rtsp_stream()
        expected_request = {
            "command": "sdm.devices.commands.CameraLiveStream.GenerateRtspStream",
            "params": {},
        }
        assert expected_request == r.request
        assert "g.0.streamingToken" == stream.stream_token
        assert (
            datetime.datetime(2018, 1, 4, 18, 30, tzinfo=datetime.timezone.utc)
            == stream.expires_at
        )

        stream = await stream.extend_rtsp_stream()
        expected_request = {
            "command": "sdm.devices.commands.CameraLiveStream.ExtendRtspStream",
            "params": {
                "streamExtensionToken": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
            },
        }
        assert expected_request == r.request
        assert "g.1.newStreamingToken" == stream.stream_token
        assert (
            datetime.datetime(2019, 1, 4, 18, 30, tzinfo=datetime.timezone.utc)
            == stream.expires_at
        )

        stream = await stream.extend_rtsp_stream()
        expected_request = {
            "command": "sdm.devices.commands.CameraLiveStream.ExtendRtspStream",
            "params": {
                "streamExtensionToken": "dGNUlTU2CjY5Y3VKaTZwR3o4Y1...",
            },
        }
        assert expected_request == r.request
        assert "g.2.newStreamingToken" == stream.stream_token
        assert (
            datetime.datetime(2020, 1, 4, 18, 30, tzinfo=datetime.timezone.utc)
            == stream.expires_at
        )

        await stream.stop_rtsp_stream()
        expected_request = {
            "command": "sdm.devices.commands.CameraLiveStream.StopRtspStream",
            "params": {
                "streamExtensionToken": "last-token...",
            },
        }
        assert expected_request == r.request


async def test_camera_event_image(aiohttp_server) -> None:
    r = Recorder()
    handler = NewDeviceHandler(
        r,
        [
            {
                "name": "enterprises/project-id1/devices/device-id1",
                "traits": {
                    "sdm.devices.traits.CameraEventImage": {},
                },
            }
        ],
    )

    post_handler = NewRequestRecorder(
        r,
        [
            {
                "results": {
                    "url": "https://domain/sdm_event_snapshot/dGNUlTU2CjY5Y3VKaTZwR3o4Y",
                    "token": "g.0.eventToken",
                },
            }
        ],
    )

    app = aiohttp.web.Application()
    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_post(
        "/enterprises/project-id1/devices/device-id1:executeCommand", post_handler
    )
    server = await aiohttp_server(app)

    async with aiohttp.test_utils.TestClient(server) as client:
        api = google_nest_api.GoogleNestAPI(FakeAuth(client), PROJECT_ID)
        devices = await api.async_get_devices()
        assert len(devices) == 1
        device = devices[0]
        assert "enterprises/project-id1/devices/device-id1" == device.name
        trait = device.traits["sdm.devices.traits.CameraEventImage"]
        image = await trait.generate_image("some-eventId")
        expected_request = {
            "command": "sdm.devices.commands.CameraEventImage.GenerateImage",
            "params": {"eventId": "some-eventId"},
        }
        assert expected_request == r.request
        assert (
            "https://domain/sdm_event_snapshot/dGNUlTU2CjY5Y3VKaTZwR3o4Y" == image.url
        )
        assert "g.0.eventToken" == image.token


async def test_get_structures(aiohttp_server) -> None:
    r = Recorder()
    handler = NewStructureHandler(
        r,
        [
            {
                "name": "enterprises/project-id1/structures/structure-id1",
                "traits": {
                    "sdm.structures.traits.Info": {
                        "customName": "some-name1",
                    }
                },
            },
            {
                "name": "enterprises/project-id1/structures/structure-id2",
                "traits": {
                    "sdm.structures.traits.Info": {
                        "customName": "some-name2",
                    }
                },
            },
        ],
    )

    app = aiohttp.web.Application()
    app.router.add_get("/enterprises/project-id1/structures", handler)
    server = await aiohttp_server(app)

    async with aiohttp.test_utils.TestClient(server) as client:
        api = google_nest_api.GoogleNestAPI(FakeAuth(client), PROJECT_ID)
        structures = await api.async_get_structures()
        assert len(structures) == 2
        assert "enterprises/project-id1/structures/structure-id1" == structures[0].name
        assert "sdm.structures.traits.Info" in structures[0].traits
        assert "enterprises/project-id1/structures/structure-id2" == structures[1].name
        assert "sdm.structures.traits.Info" in structures[1].traits
