import datetime
import json
from unittest.mock import patch

import aiohttp
from aiohttp.test_utils import TestClient
import pytest

from google_nest_sdm import google_nest_api
from google_nest_sdm.device import AbstractAuth
from google_nest_sdm.event import EventMessage
from google_nest_sdm.exceptions import ApiException, AuthException

PROJECT_ID = "project-id1"
FAKE_TOKEN = "some-token"


class FakeAuth(AbstractAuth):
    def __init__(self, websession):
        super().__init__(websession, "")

    async def async_get_access_token(self) -> str:
        return FAKE_TOKEN


class RefreshingAuth(AbstractAuth):
    def __init__(self, websession):
        super().__init__(websession, "")

    async def async_get_access_token(self) -> str:
        resp = await self._websession.request("get", "/refresh-auth")
        resp.raise_for_status()
        json = await resp.json()
        assert isinstance(json["token"], str)
        return json["token"]


class Recorder:
    request = None


def NewDeviceHandler(r: Recorder, devices: list, token=FAKE_TOKEN):
    return NewHandler(r, [{"devices": devices}], token=token)


def NewStructureHandler(r: Recorder, structures: list, token=FAKE_TOKEN):
    return NewHandler(r, [{"structures": structures}], token=token)


def NewHandler(r: Recorder, response: list, token=FAKE_TOKEN):
    async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert request.headers["Authorization"] == "Bearer %s" % token
        s = await request.text()
        r.request = await request.json() if s else {}
        return aiohttp.web.json_response(response.pop(0))

    return handler


def NewImageHandler(response: list, token=FAKE_TOKEN):
    async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert request.headers["Authorization"] == "Basic %s" % token
        return aiohttp.web.Response(body=response.pop(0))

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

    async with TestClient(server) as client:
        api = google_nest_api.GoogleNestAPI(FakeAuth(client), PROJECT_ID)
        devices = await api.async_get_devices()
        assert len(devices) == 2
        assert "enterprises/project-id1/devices/device-id1" == devices[0].name
        assert "sdm.devices.types.device-type1" == devices[0].type
        assert "enterprises/project-id1/devices/device-id2" == devices[1].name
        assert "sdm.devices.types.device-type2" == devices[1].type


async def test_fan_set_timer(aiohttp_server) -> None:
    r = Recorder()
    handler = NewDeviceHandler(
        r,
        [
            {
                "name": "enterprises/project-id1/devices/device-id1",
                "traits": {
                    "sdm.devices.traits.Fan": {
                        "timerMode": "OFF",
                    },
                },
            }
        ],
    )
    post_handler = NewHandler(r, [{}])

    app = aiohttp.web.Application()
    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_post(
        "/enterprises/project-id1/devices/device-id1:executeCommand", post_handler
    )
    server = await aiohttp_server(app)

    async with TestClient(server) as client:
        api = google_nest_api.GoogleNestAPI(FakeAuth(client), PROJECT_ID)
        devices = await api.async_get_devices()
        assert len(devices) == 1
        device = devices[0]
        assert "enterprises/project-id1/devices/device-id1" == device.name
        trait = device.traits["sdm.devices.traits.Fan"]
        assert trait.timer_mode == "OFF"
        await trait.set_timer("ON", 3600)
        expected_request = {
            "command": "sdm.devices.commands.Fan.SetTimer",
            "params": {
                "timerMode": "ON",
                "duration": "3600s",
            },
        }
        assert expected_request == r.request


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
    post_handler = NewHandler(r, [{}])

    app = aiohttp.web.Application()
    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_post(
        "/enterprises/project-id1/devices/device-id1:executeCommand", post_handler
    )
    server = await aiohttp_server(app)

    async with TestClient(server) as client:
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
    post_handler = NewHandler(r, [{}])

    app = aiohttp.web.Application()
    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_post(
        "/enterprises/project-id1/devices/device-id1:executeCommand", post_handler
    )
    server = await aiohttp_server(app)

    async with TestClient(server) as client:
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
    post_handler = NewHandler(r, [{}, {}, {}])

    app = aiohttp.web.Application()
    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_post(
        "/enterprises/project-id1/devices/device-id1:executeCommand", post_handler
    )
    server = await aiohttp_server(app)

    async with TestClient(server) as client:
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

    post_handler = NewHandler(
        r,
        [
            {
                "results": {
                    "streamUrls": {
                        "rtspUrl": "rtsps://someurl.com/CjY5Y3VKaTfMF?auth=g.0.token"
                    },
                    "streamExtensionToken": "CjY5Y3VKaTfMF",
                    "streamToken": "g.0.token",
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

    async with TestClient(server) as client:
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
        assert "g.0.token" == stream.stream_token
        assert (
            datetime.datetime(2018, 1, 4, 18, 30, tzinfo=datetime.timezone.utc)
            == stream.expires_at
        )
        assert (
            "rtsps://someurl.com/CjY5Y3VKaTfMF?auth=g.0.token" == stream.rtsp_stream_url
        )

        stream = await stream.extend_rtsp_stream()
        expected_request = {
            "command": "sdm.devices.commands.CameraLiveStream.ExtendRtspStream",
            "params": {
                "streamExtensionToken": "CjY5Y3VKaTfMF",
            },
        }
        assert expected_request == r.request
        assert "g.1.newStreamingToken" == stream.stream_token
        assert (
            datetime.datetime(2019, 1, 4, 18, 30, tzinfo=datetime.timezone.utc)
            == stream.expires_at
        )
        assert (
            "rtsps://someurl.com/CjY5Y3VKaTfMF?auth=g.1.newStreamingToken"
            == stream.rtsp_stream_url
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
        assert (
            "rtsps://someurl.com/CjY5Y3VKaTfMF?auth=g.2.newStreamingToken"
            == stream.rtsp_stream_url
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

    post_handler = NewHandler(
        r,
        [
            {
                "results": {
                    "url": "https://domain/sdm_event/dGNUlTU2CjY5Y3VKaTZwR3o4Y",
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

    async with TestClient(server) as client:
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
        assert "https://domain/sdm_event/dGNUlTU2CjY5Y3VKaTZwR3o4Y" == image.url
        assert "g.0.eventToken" == image.token


async def test_camera_active_event_image(aiohttp_server) -> None:
    r = Recorder()
    handler = NewDeviceHandler(
        r,
        [
            {
                "name": "enterprises/project-id1/devices/device-id1",
                "traits": {
                    "sdm.devices.traits.CameraEventImage": {},
                    "sdm.devices.traits.CameraMotion": {},
                },
            }
        ],
    )

    post_handler = NewHandler(
        r,
        [
            {
                "results": {
                    "url": "https://domain/sdm_event/dGNUlTU2CjY5Y3VKaTZwR3o4Y",
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

    async with TestClient(server) as client:
        auth = FakeAuth(client)
        api = google_nest_api.GoogleNestAPI(auth, PROJECT_ID)
        devices = await api.async_get_devices()
        assert len(devices) == 1
        device = devices[0]
        assert "enterprises/project-id1/devices/device-id1" == device.name

        now = datetime.datetime.now(tz=datetime.timezone.utc)
        await device.async_handle_event(
            EventMessage(
                {
                    "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                    "timestamp": now.isoformat(timespec="seconds"),
                    "resourceUpdate": {
                        "name": "enterprises/project-id1/devices/device-id1",
                        "events": {
                            "sdm.devices.events.CameraMotion.Motion": {
                                "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                                "eventId": "FWWVQVUdGNUlTU2V4MGV2aTNXV...",
                            },
                        },
                    },
                    "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
                },
                auth=auth,
            )
        )

        trait = device.traits["sdm.devices.traits.CameraMotion"]
        assert trait.active_event is not None
        image = await trait.generate_active_event_image()
        expected_request = {
            "command": "sdm.devices.commands.CameraEventImage.GenerateImage",
            "params": {"eventId": "FWWVQVUdGNUlTU2V4MGV2aTNXV..."},
        }
        assert expected_request == r.request
        assert "https://domain/sdm_event/dGNUlTU2CjY5Y3VKaTZwR3o4Y" == image.url
        assert "g.0.eventToken" == image.token


async def test_camera_last_active_event_image(aiohttp_server) -> None:
    r = Recorder()
    handler = NewDeviceHandler(
        r,
        [
            {
                "name": "enterprises/project-id1/devices/device-id1",
                "traits": {
                    "sdm.devices.traits.CameraEventImage": {},
                    "sdm.devices.traits.CameraMotion": {},
                    "sdm.devices.traits.CameraSound": {},
                },
            }
        ],
    )

    post_handler = NewHandler(
        r,
        [
            {
                "results": {
                    "url": "https://domain/sdm_event/dGNUlTU2CjY5Y3VKaTZwR3o4Y",
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

    async with TestClient(server) as client:
        auth = FakeAuth(client)
        api = google_nest_api.GoogleNestAPI(auth, PROJECT_ID)
        devices = await api.async_get_devices()
        assert len(devices) == 1
        device = devices[0]
        assert "enterprises/project-id1/devices/device-id1" == device.name

        # Later message arrives first
        t2 = datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(
            seconds=5
        )
        await device.async_handle_event(
            EventMessage(
                {
                    "eventId": "4bf981f90619-1499-4be4-75b3-7cce0210",
                    "timestamp": t2.isoformat(timespec="seconds"),
                    "resourceUpdate": {
                        "name": "enterprises/project-id1/devices/device-id1",
                        "events": {
                            "sdm.devices.events.CameraSound.Sound": {
                                "eventSessionId": "FMfVTbY91Y4o3RwZTaKV3Y5jC...",
                                "eventId": "VXNTa2VGM4V2UTlUNGdUVQVWWF...",
                            },
                        },
                    },
                    "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
                },
                auth=auth,
            )
        )
        t1 = datetime.datetime.now(tz=datetime.timezone.utc)
        await device.async_handle_event(
            EventMessage(
                {
                    "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                    "timestamp": t1.isoformat(timespec="seconds"),
                    "resourceUpdate": {
                        "name": "enterprises/project-id1/devices/device-id1",
                        "events": {
                            "sdm.devices.events.CameraMotion.Motion": {
                                "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                                "eventId": "FWWVQVUdGNUlTU2V4MGV2aTNXV...",
                            },
                        },
                    },
                    "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
                },
                auth=auth,
            )
        )

        trait = device.active_event_trait
        assert trait.active_event is not None
        assert trait.last_event is not None
        assert trait.last_event.event_session_id == "FMfVTbY91Y4o3RwZTaKV3Y5jC..."
        assert trait.last_event.event_id == "VXNTa2VGM4V2UTlUNGdUVQVWWF..."


async def test_camera_event_image_bytes(aiohttp_server) -> None:
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

    post_handler = NewHandler(
        r,
        [
            {
                "results": {
                    "url": "image-url",
                    "token": "g.0.eventToken",
                },
            }
        ],
    )
    image_handler = NewImageHandler([b"image-bytes"], token="g.0.eventToken")

    app = aiohttp.web.Application()
    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_post(
        "/enterprises/project-id1/devices/device-id1:executeCommand", post_handler
    )
    app.router.add_get("/image-url", image_handler)
    server = await aiohttp_server(app)

    async with TestClient(server) as client:
        api = google_nest_api.GoogleNestAPI(FakeAuth(client), PROJECT_ID)
        devices = await api.async_get_devices()
        assert len(devices) == 1
        device = devices[0]
        assert "enterprises/project-id1/devices/device-id1" == device.name
        trait = device.traits["sdm.devices.traits.CameraEventImage"]
        event_image = await trait.generate_image("some-eventId")
        image_bytes = await event_image.contents()
        assert image_bytes == b"image-bytes"


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

    async with TestClient(server) as client:
        api = google_nest_api.GoogleNestAPI(FakeAuth(client), PROJECT_ID)
        structures = await api.async_get_structures()
        assert len(structures) == 2
        assert "enterprises/project-id1/structures/structure-id1" == structures[0].name
        assert "sdm.structures.traits.Info" in structures[0].traits
        assert "enterprises/project-id1/structures/structure-id2" == structures[1].name
        assert "sdm.structures.traits.Info" in structures[1].traits


async def test_client_error(aiohttp_server) -> None:
    # No server endpoint registered
    app = aiohttp.web.Application()
    server = await aiohttp_server(app)

    async with TestClient(server) as client:
        api = google_nest_api.GoogleNestAPI(FakeAuth(client), PROJECT_ID)
        with patch(
            "google_nest_sdm.google_nest_api.AbstractAuth.request",
            side_effect=aiohttp.ClientConnectionError(),
        ), pytest.raises(ApiException):
            await api.async_get_structures()


async def test_api_get_error(aiohttp_server) -> None:
    # No server endpoint registered
    app = aiohttp.web.Application()
    server = await aiohttp_server(app)

    async with TestClient(server) as client:
        api = google_nest_api.GoogleNestAPI(FakeAuth(client), PROJECT_ID)
        with pytest.raises(ApiException):
            await api.async_get_structures()


async def test_api_post_error(aiohttp_server) -> None:
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

    async def fail_handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert request.headers["Authorization"] == "Bearer %s" % FAKE_TOKEN
        return aiohttp.web.Response(status=502)

    app = aiohttp.web.Application()
    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_post(
        "/enterprises/project-id1/devices/device-id1:executeCommand", fail_handler
    )
    server = await aiohttp_server(app)

    async with TestClient(server) as client:
        api = google_nest_api.GoogleNestAPI(FakeAuth(client), PROJECT_ID)
        devices = await api.async_get_devices()
        assert len(devices) == 1
        device = devices[0]
        assert "enterprises/project-id1/devices/device-id1" == device.name
        trait = device.traits["sdm.devices.traits.ThermostatTemperatureSetpoint"]
        assert trait.heat_celsius == 23.0
        assert trait.cool_celsius == 24.0

        with pytest.raises(ApiException):
            await trait.set_heat(25.0)


async def test_auth_refresh(aiohttp_server) -> None:
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
        ],
        token="updated-token",
    )

    async def auth_handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        return aiohttp.web.json_response({"token": "updated-token"})

    app = aiohttp.web.Application()
    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_get("/refresh-auth", auth_handler)
    server = await aiohttp_server(app)

    async with TestClient(server) as client:
        api = google_nest_api.GoogleNestAPI(RefreshingAuth(client), PROJECT_ID)
        devices = await api.async_get_devices()
        assert len(devices) == 1
        assert "enterprises/project-id1/devices/device-id1" == devices[0].name
        assert "sdm.devices.types.device-type1" == devices[0].type


async def test_auth_refresh_error(aiohttp_server) -> None:
    r = Recorder()

    async def auth_handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        return aiohttp.web.Response(status=401)

    app = aiohttp.web.Application()
    app.router.add_get("/enterprises/project-id1/devices", NewDeviceHandler(r, []))
    app.router.add_get("/refresh-auth", auth_handler)
    server = await aiohttp_server(app)

    async with TestClient(server) as client:
        api = google_nest_api.GoogleNestAPI(RefreshingAuth(client), PROJECT_ID)
        with pytest.raises(AuthException):
            await api.async_get_devices()


async def test_no_devices(aiohttp_server) -> None:
    r = Recorder()
    app = aiohttp.web.Application()
    app.router.add_get("/enterprises/project-id1/devices", NewHandler(r, [{}]))
    server = await aiohttp_server(app)

    async with TestClient(server) as client:
        api = google_nest_api.GoogleNestAPI(FakeAuth(client), PROJECT_ID)
        devices = await api.async_get_devices()
        assert len(devices) == 0


async def test_missing_device(aiohttp_server) -> None:
    r = Recorder()
    app = aiohttp.web.Application()
    app.router.add_get("/enterprises/project-id1/devices/abc", NewHandler(r, [{}]))
    server = await aiohttp_server(app)

    async with TestClient(server) as client:
        api = google_nest_api.GoogleNestAPI(FakeAuth(client), PROJECT_ID)
        device = await api.async_get_device("abc")
        assert device is None


async def test_no_structures(aiohttp_server) -> None:
    r = Recorder()
    app = aiohttp.web.Application()
    app.router.add_get("/enterprises/project-id1/structures", NewHandler(r, [{}]))
    server = await aiohttp_server(app)

    async with TestClient(server) as client:
        api = google_nest_api.GoogleNestAPI(FakeAuth(client), PROJECT_ID)
        structures = await api.async_get_structures()
        assert len(structures) == 0


async def test_missing_structures(aiohttp_server) -> None:
    r = Recorder()
    app = aiohttp.web.Application()
    app.router.add_get("/enterprises/project-id1/structures/abc", NewHandler(r, [{}]))
    server = await aiohttp_server(app)

    async with TestClient(server) as client:
        api = google_nest_api.GoogleNestAPI(FakeAuth(client), PROJECT_ID)
        structure = await api.async_get_structure("abc")
        assert structure is None


async def test_api_post_error_with_json_response(aiohttp_server) -> None:
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

    app = aiohttp.web.Application()
    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_post(
        "/enterprises/project-id1/devices/device-id1:executeCommand", fail_handler
    )
    server = await aiohttp_server(app)

    async with TestClient(server) as client:
        api = google_nest_api.GoogleNestAPI(FakeAuth(client), PROJECT_ID)
        devices = await api.async_get_devices()
        assert len(devices) == 1
        device = devices[0]
        assert "enterprises/project-id1/devices/device-id1" == device.name
        trait = device.traits["sdm.devices.traits.ThermostatTemperatureSetpoint"]

        with pytest.raises(
            ApiException, match=r".*FAILED_PRECONDITION: Some error message.*"
        ):
            await trait.set_heat(25.0)
