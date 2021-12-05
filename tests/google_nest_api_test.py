import datetime
import itertools
import json
from typing import Any, Awaitable, Callable, Dict
from unittest.mock import patch

import aiohttp
import pytest

from google_nest_sdm import google_nest_api
from google_nest_sdm.auth import AbstractAuth
from google_nest_sdm.camera_traits import EventImageType, StreamingProtocol
from google_nest_sdm.event import EventMessage, ImageEventBase
from google_nest_sdm.event_media import InMemoryEventMediaStore
from google_nest_sdm.exceptions import ApiException, AuthException

from .conftest import (
    NewDeviceHandler,
    NewHandler,
    NewImageHandler,
    NewStructureHandler,
    Recorder,
)

PROJECT_ID = "project-id1"
FAKE_TOKEN = "some-token"


@pytest.fixture
async def api_client(
    auth_client: Callable[[], Awaitable[AbstractAuth]],
) -> Callable[[], Awaitable[google_nest_api.GoogleNestAPI]]:
    async def make_api() -> google_nest_api.GoogleNestAPI:
        auth = await auth_client()
        return google_nest_api.GoogleNestAPI(auth, PROJECT_ID)

    return make_api


async def test_get_devices(
    app: aiohttp.web.Application,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
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

    app.router.add_get("/enterprises/project-id1/devices", handler)

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 2
    assert "enterprises/project-id1/devices/device-id1" == devices[0].name
    assert "sdm.devices.types.device-type1" == devices[0].type
    assert "enterprises/project-id1/devices/device-id2" == devices[1].name
    assert "sdm.devices.types.device-type2" == devices[1].type


async def test_fan_set_timer(
    app: aiohttp.web.Application,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
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

    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_post(
        "/enterprises/project-id1/devices/device-id1:executeCommand", post_handler
    )

    api = await api_client()
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


async def test_thermostat_eco_set_mode(
    app: aiohttp.web.Application,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
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

    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_post(
        "/enterprises/project-id1/devices/device-id1:executeCommand", post_handler
    )

    api = await api_client()
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


async def test_thermostat_mode_set_mode(
    app: aiohttp.web.Application,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
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

    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_post(
        "/enterprises/project-id1/devices/device-id1:executeCommand", post_handler
    )

    api = await api_client()
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


async def test_thermostat_temperature_set_point(
    app: aiohttp.web.Application,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
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

    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_post(
        "/enterprises/project-id1/devices/device-id1:executeCommand", post_handler
    )

    api = await api_client()
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


async def test_camera_live_stream_rtsp(
    app: aiohttp.web.Application,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
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
    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_post(
        "/enterprises/project-id1/devices/device-id1:executeCommand", post_handler
    )

    api = await api_client()
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
    assert "rtsps://someurl.com/CjY5Y3VKaTfMF?auth=g.0.token" == stream.rtsp_stream_url

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


async def test_camera_live_stream_web_rtc(
    app: aiohttp.web.Application,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
    r = Recorder()
    handler = NewDeviceHandler(
        r,
        [
            {
                "name": "enterprises/project-id1/devices/device-id1",
                "traits": {
                    "sdm.devices.traits.CameraLiveStream": {
                        "supportedProtocols": ["WEB_RTC"],
                    },
                },
            }
        ],
    )

    post_handler = NewHandler(
        r,
        [
            {
                "results": {
                    "answerSdp": "some-answer",
                    "expiresAt": "2018-01-04T18:30:00.000Z",
                    "mediaSessionId": "JxdTxkkatHk4kVnXlKzQICbfVR...",
                },
            },
            {
                "results": {
                    "expiresAt": "2019-01-04T18:30:00.000Z",
                    "mediaSessionId": "JxdTxkkatHk4kVnXlKzQICbfVR...",
                }
            },
            {
                "results": {
                    "expiresAt": "2020-01-04T18:30:00.000Z",
                    "mediaSessionId": "JxdTxkkatHk4kVnXlKzQICbfVR...",
                }
            },
            {},
        ],
    )
    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_post(
        "/enterprises/project-id1/devices/device-id1:executeCommand", post_handler
    )

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert "enterprises/project-id1/devices/device-id1" == device.name
    trait = device.traits["sdm.devices.traits.CameraLiveStream"]
    assert [StreamingProtocol.WEB_RTC] == trait.supported_protocols
    stream = await trait.generate_web_rtc_stream("a=recvonly")
    expected_request = {
        "command": "sdm.devices.commands.CameraLiveStream.GenerateWebRtcStream",
        "params": {
            "offerSdp": "a=recvonly",
        },
    }
    assert expected_request == r.request
    assert "some-answer" == stream.answer_sdp
    assert (
        datetime.datetime(2018, 1, 4, 18, 30, tzinfo=datetime.timezone.utc)
        == stream.expires_at
    )
    assert "JxdTxkkatHk4kVnXlKzQICbfVR..." == stream.media_session_id

    stream = await stream.extend_stream()
    expected_request = {
        "command": "sdm.devices.commands.CameraLiveStream.ExtendWebRtcStream",
        "params": {
            "mediaSessionId": "JxdTxkkatHk4kVnXlKzQICbfVR...",
        },
    }
    assert expected_request == r.request
    assert "some-answer" == stream.answer_sdp
    assert (
        datetime.datetime(2019, 1, 4, 18, 30, tzinfo=datetime.timezone.utc)
        == stream.expires_at
    )
    assert "JxdTxkkatHk4kVnXlKzQICbfVR..." == stream.media_session_id

    stream = await stream.extend_stream()
    expected_request = {
        "command": "sdm.devices.commands.CameraLiveStream.ExtendWebRtcStream",
        "params": {
            "mediaSessionId": "JxdTxkkatHk4kVnXlKzQICbfVR...",
        },
    }
    assert expected_request == r.request
    assert "some-answer" == stream.answer_sdp
    assert (
        datetime.datetime(2020, 1, 4, 18, 30, tzinfo=datetime.timezone.utc)
        == stream.expires_at
    )
    assert "JxdTxkkatHk4kVnXlKzQICbfVR..." == stream.media_session_id

    await stream.stop_stream()
    expected_request = {
        "command": "sdm.devices.commands.CameraLiveStream.StopWebRtcStream",
        "params": {
            "mediaSessionId": "JxdTxkkatHk4kVnXlKzQICbfVR...",
        },
    }
    assert expected_request == r.request


async def test_camera_event_image(
    app: aiohttp.web.Application,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
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

    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_post(
        "/enterprises/project-id1/devices/device-id1:executeCommand", post_handler
    )

    api = await api_client()
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
    assert image.event_image_type == EventImageType.IMAGE


@pytest.mark.parametrize(
    "test_trait,test_event_trait",
    [
        ("sdm.devices.traits.CameraMotion", "sdm.devices.events.CameraMotion.Motion"),
        ("sdm.devices.traits.CameraPerson", "sdm.devices.events.CameraPerson.Person"),
        ("sdm.devices.traits.CameraSound", "sdm.devices.events.CameraSound.Sound"),
        ("sdm.devices.traits.DoorbellChime", "sdm.devices.events.DoorbellChime.Chime"),
    ],
)
async def test_camera_active_event_image(
    test_trait: str,
    test_event_trait: str,
    app: aiohttp.web.Application,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
    r = Recorder()
    handler = NewDeviceHandler(
        r,
        [
            {
                "name": "enterprises/project-id1/devices/device-id1",
                "traits": {
                    "sdm.devices.traits.CameraEventImage": {},
                    test_trait: {},
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

    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_post(
        "/enterprises/project-id1/devices/device-id1:executeCommand", post_handler
    )

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert "enterprises/project-id1/devices/device-id1" == device.name

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": now.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": "enterprises/project-id1/devices/device-id1",
                    "events": {
                        test_event_trait: {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "eventId": "FWWVQVUdGNUlTU2V4MGV2aTNXV...",
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )

    trait = device.traits[test_trait]
    assert trait.active_event is not None
    image = await trait.generate_active_event_image()
    expected_request = {
        "command": "sdm.devices.commands.CameraEventImage.GenerateImage",
        "params": {"eventId": "FWWVQVUdGNUlTU2V4MGV2aTNXV..."},
    }
    assert expected_request == r.request
    assert "https://domain/sdm_event/dGNUlTU2CjY5Y3VKaTZwR3o4Y" == image.url
    assert "g.0.eventToken" == image.token
    assert image.event_image_type == EventImageType.IMAGE


async def test_camera_active_event_image_contents(
    app: aiohttp.web.Application,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
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
                    "url": "image-url-1",
                    "token": "g.1.eventToken",
                },
            },
            {
                "results": {
                    "url": "image-url-2",
                    "token": "g.2.eventToken",
                },
            },
        ],
    )

    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_post(
        "/enterprises/project-id1/devices/device-id1:executeCommand", post_handler
    )
    app.router.add_get(
        "/image-url-1", NewImageHandler([b"image-bytes-1"], token="g.1.eventToken")
    )
    app.router.add_get(
        "/image-url-2", NewImageHandler([b"image-bytes-2"], token="g.2.eventToken")
    )

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert "enterprises/project-id1/devices/device-id1" == device.name

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    await device.async_handle_event(
        await event_message(
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
            }
        )
    )

    trait = device.traits["sdm.devices.traits.CameraMotion"]
    assert trait.active_event is not None
    event_image = await trait.active_event_image_contents()
    assert event_image.event_id == "FWWVQVUdGNUlTU2V4MGV2aTNXV..."
    assert event_image.contents == b"image-bytes-1"

    # Another event image arrives
    now = datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(
        seconds=5
    )
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "a94b2115-3b57-4eb4-8830-80519f188ec9",
                "timestamp": now.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": "enterprises/project-id1/devices/device-id1",
                    "events": {
                        "sdm.devices.events.CameraMotion.Motion": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "eventId": "ABCZQRUdGNUlTU2V4MGV3bRZ23...",
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )
    # New image bytes are fetched for new event
    event_image = await trait.active_event_image_contents()
    assert event_image.event_id == "ABCZQRUdGNUlTU2V4MGV3bRZ23..."
    assert event_image.contents == b"image-bytes-2"


async def test_camera_last_active_event_image(
    app: aiohttp.web.Application,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
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

    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_post(
        "/enterprises/project-id1/devices/device-id1:executeCommand", post_handler
    )

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert "enterprises/project-id1/devices/device-id1" == device.name

    # Later message arrives first
    t2 = datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(seconds=5)
    await device.async_handle_event(
        await event_message(
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
            }
        )
    )
    t1 = datetime.datetime.now(tz=datetime.timezone.utc)
    await device.async_handle_event(
        await event_message(
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
            }
        )
    )

    trait = device.active_event_trait
    assert trait
    assert trait.active_event is not None
    assert trait.last_event is not None
    assert trait.last_event.event_session_id == "FMfVTbY91Y4o3RwZTaKV3Y5jC..."
    assert trait.last_event.event_id == "VXNTa2VGM4V2UTlUNGdUVQVWWF..."


async def test_camera_event_image_bytes(
    app: aiohttp.web.Application,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
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

    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_post(
        "/enterprises/project-id1/devices/device-id1:executeCommand", post_handler
    )
    app.router.add_get("/image-url", image_handler)

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert "enterprises/project-id1/devices/device-id1" == device.name
    trait = device.traits["sdm.devices.traits.CameraEventImage"]
    event_image = await trait.generate_image("some-eventId")
    image_bytes = await event_image.contents()
    assert image_bytes == b"image-bytes"


async def test_camera_active_clip_preview(
    app: aiohttp.web.Application,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
    r = Recorder()
    handler = NewDeviceHandler(
        r,
        [
            {
                "name": "enterprises/project-id1/devices/device-id1",
                "traits": {
                    "sdm.devices.traits.CameraClipPreview": {},
                },
            }
        ],
    )

    app.router.add_get("/enterprises/project-id1/devices", handler)

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert "enterprises/project-id1/devices/device-id1" == device.name

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": now.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": "enterprises/project-id1/devices/device-id1",
                    "events": {
                        "sdm.devices.events.CameraClipPreview.ClipPreview": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "previewUrl": "https://previewUrl/...",
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )

    trait = device.traits["sdm.devices.traits.CameraClipPreview"]
    assert trait.active_event is not None
    image = await trait.generate_active_event_image()
    assert "https://previewUrl/..." == image.url
    assert image.token is None
    assert image.event_image_type == EventImageType.CLIP_PREVIEW


async def test_get_structures(
    app: aiohttp.web.Application,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
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

    app.router.add_get("/enterprises/project-id1/structures", handler)

    api = await api_client()
    structures = await api.async_get_structures()
    assert len(structures) == 2
    assert "enterprises/project-id1/structures/structure-id1" == structures[0].name
    assert "sdm.structures.traits.Info" in structures[0].traits
    assert "enterprises/project-id1/structures/structure-id2" == structures[1].name
    assert "sdm.structures.traits.Info" in structures[1].traits


async def test_client_error(
    app: aiohttp.web.Application,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
    # No server endpoint registered
    api = await api_client()
    with patch(
        "google_nest_sdm.google_nest_api.AbstractAuth.request",
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
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
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

    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_post(
        "/enterprises/project-id1/devices/device-id1:executeCommand", fail_handler
    )

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert "enterprises/project-id1/devices/device-id1" == device.name
    trait = device.traits["sdm.devices.traits.ThermostatTemperatureSetpoint"]
    assert trait.heat_celsius == 23.0
    assert trait.cool_celsius == 24.0

    with pytest.raises(ApiException):
        await trait.set_heat(25.0)


async def test_auth_refresh(
    app: aiohttp.web.Application,
    refreshing_auth_client: Callable[[], Awaitable[AbstractAuth]],
) -> None:
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

    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_get("/refresh-auth", auth_handler)

    auth = await refreshing_auth_client()
    api = google_nest_api.GoogleNestAPI(auth, PROJECT_ID)

    devices = await api.async_get_devices()
    assert len(devices) == 1
    assert "enterprises/project-id1/devices/device-id1" == devices[0].name
    assert "sdm.devices.types.device-type1" == devices[0].type


async def test_auth_refresh_error(
    app: aiohttp.web.Application,
    refreshing_auth_client: Callable[[], Awaitable[AbstractAuth]],
) -> None:
    r = Recorder()

    async def auth_handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        return aiohttp.web.Response(status=401)

    app.router.add_get("/enterprises/project-id1/devices", NewDeviceHandler(r, []))
    app.router.add_get("/refresh-auth", auth_handler)

    auth = await refreshing_auth_client()
    api = google_nest_api.GoogleNestAPI(auth, PROJECT_ID)
    with pytest.raises(AuthException):
        await api.async_get_devices()


async def test_no_devices(
    app: aiohttp.web.Application,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
    r = Recorder()
    app.router.add_get("/enterprises/project-id1/devices", NewHandler(r, [{}]))

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 0


async def test_missing_device(
    app: aiohttp.web.Application,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
    r = Recorder()
    app.router.add_get("/enterprises/project-id1/devices/abc", NewHandler(r, [{}]))
    api = await api_client()
    device = await api.async_get_device("abc")
    assert device is None


async def test_no_structures(
    app: aiohttp.web.Application,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
    r = Recorder()
    app.router.add_get("/enterprises/project-id1/structures", NewHandler(r, [{}]))

    api = await api_client()
    structures = await api.async_get_structures()
    assert len(structures) == 0


async def test_missing_structures(
    app: aiohttp.web.Application,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
    r = Recorder()
    app.router.add_get("/enterprises/project-id1/structures/abc", NewHandler(r, [{}]))

    api = await api_client()
    structure = await api.async_get_structure("abc")
    assert structure is None


async def test_api_post_error_with_json_response(
    app: aiohttp.web.Application,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
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

    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_post(
        "/enterprises/project-id1/devices/device-id1:executeCommand", fail_handler
    )

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert "enterprises/project-id1/devices/device-id1" == device.name
    trait = device.traits["sdm.devices.traits.ThermostatTemperatureSetpoint"]

    with pytest.raises(
        ApiException, match=r".*FAILED_PRECONDITION: Some error message.*"
    ):
        await trait.set_heat(25.0)


async def test_event_manager_image(
    app: aiohttp.web.Application,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
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
                    "url": "image-url-1",
                    "token": "g.1.eventToken",
                },
            },
            {
                "results": {
                    "url": "image-url-2",
                    "token": "g.2.eventToken",
                },
            },
        ],
    )

    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_post(
        "/enterprises/project-id1/devices/device-id1:executeCommand", post_handler
    )
    app.router.add_get(
        "/image-url-1", NewImageHandler([b"image-bytes-1"], token="g.1.eventToken")
    )
    app.router.add_get(
        "/image-url-2", NewImageHandler([b"image-bytes-2"], token="g.2.eventToken")
    )

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert "enterprises/project-id1/devices/device-id1" == device.name

    ts1 = datetime.datetime.now(tz=datetime.timezone.utc)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": ts1.isoformat(timespec="seconds"),
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
            }
        )
    )
    ts2 = ts1 + datetime.timedelta(seconds=5)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "a94b2115-3b57-4eb4-8830-80519f188ec9",
                "timestamp": ts2.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": "enterprises/project-id1/devices/device-id1",
                    "events": {
                        "sdm.devices.events.CameraMotion.Motion": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "eventId": "ABCZQRUdGNUlTU2V4MGV3bRZ23...",
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )

    event_media_manager = device.event_media_manager

    event_media = await event_media_manager.get_media("FWWVQVUdGNUlTU2V4MGV2aTNXV...")
    assert event_media
    assert event_media.event_id == "FWWVQVUdGNUlTU2V4MGV2aTNXV..."
    assert event_media.event_type == "sdm.devices.events.CameraMotion.Motion"
    assert event_media.event_timestamp.isoformat(timespec="seconds") == ts1.isoformat(
        timespec="seconds"
    )
    assert event_media.media.contents == b"image-bytes-1"
    assert event_media.media.event_image_type.content_type == "image/jpeg"

    event_media = await event_media_manager.get_media("ABCZQRUdGNUlTU2V4MGV3bRZ23...")
    assert event_media
    assert event_media.event_id == "ABCZQRUdGNUlTU2V4MGV3bRZ23..."
    assert event_media.event_type == "sdm.devices.events.CameraMotion.Motion"
    assert event_media.event_timestamp.isoformat(timespec="seconds") == ts2.isoformat(
        timespec="seconds"
    )
    assert event_media.media.contents == b"image-bytes-2"
    assert event_media.media.event_image_type.content_type == "image/jpeg"

    assert len(list(await event_media_manager.async_events())) == 2


async def test_event_manager_prefetch_image(
    app: aiohttp.web.Application,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:

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
                    "url": "image-url-1",
                    "token": "g.1.eventToken",
                },
            },
            {
                "results": {
                    "url": "image-url-2",
                    "token": "g.2.eventToken",
                },
            },
        ],
    )

    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_post(
        "/enterprises/project-id1/devices/device-id1:executeCommand", post_handler
    )
    app.router.add_get(
        "/image-url-1", NewImageHandler([b"image-bytes-1"], token="g.1.eventToken")
    )
    app.router.add_get(
        "/image-url-2", NewImageHandler([b"image-bytes-2"], token="g.2.eventToken")
    )

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert "enterprises/project-id1/devices/device-id1" == device.name

    # Turn on event fetching
    device.event_media_manager.cache_policy.fetch = True

    ts1 = datetime.datetime(2019, 1, 1, 0, 0, 1, tzinfo=datetime.timezone.utc)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": ts1.isoformat(timespec="seconds"),
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
            }
        )
    )
    # Event is not fetched on event arrival since it was expired
    event_media_manager = device.event_media_manager
    assert len(list(await event_media_manager.async_events())) == 0

    # However, manually fetching it could still work
    event_media = await event_media_manager.get_media("FWWVQVUdGNUlTU2V4MGV2aTNXV...")
    assert event_media
    assert event_media.event_id == "FWWVQVUdGNUlTU2V4MGV2aTNXV..."
    assert event_media.event_type == "sdm.devices.events.CameraMotion.Motion"
    assert event_media.event_timestamp == ts1
    assert event_media.media.contents == b"image-bytes-1"
    assert event_media.media.event_image_type.content_type == "image/jpeg"

    assert len(list(await event_media_manager.async_events())) == 1

    # Publishing an active event is fetched immediately
    ts2 = datetime.datetime.now(tz=datetime.timezone.utc)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": ts2.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": "enterprises/project-id1/devices/device-id1",
                    "events": {
                        "sdm.devices.events.CameraMotion.Motion": {
                            "eventSessionId": "DkY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "eventId": "GXQADVUdGNUlTU2V4MGV2aTNXV...",
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )
    assert len(list(await event_media_manager.async_events())) == 2

    # However, manually fetching it could still work
    event_media_manager = device.event_media_manager
    event_media = await event_media_manager.get_media("GXQADVUdGNUlTU2V4MGV2aTNXV...")
    assert event_media
    assert event_media.event_id == "GXQADVUdGNUlTU2V4MGV2aTNXV..."
    assert event_media.event_type == "sdm.devices.events.CameraMotion.Motion"
    assert event_media.event_timestamp.isoformat(timespec="seconds") == ts2.isoformat(
        timespec="seconds"
    )
    assert event_media.media.contents == b"image-bytes-2"
    assert event_media.media.event_image_type.content_type == "image/jpeg"


async def test_event_manager_event_expiration(
    app: aiohttp.web.Application,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
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

    app.router.add_get("/enterprises/project-id1/devices", handler)

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert "enterprises/project-id1/devices/device-id1" == device.name

    device.event_media_manager.cache_policy.event_cache_size = 10

    ts1 = datetime.datetime.now(tz=datetime.timezone.utc)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": ts1.isoformat(timespec="seconds"),
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
            }
        )
    )
    ts2 = ts1 + datetime.timedelta(seconds=5)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "a94b2115-3b57-4eb4-8830-80519f188ec9",
                "timestamp": ts2.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": "enterprises/project-id1/devices/device-id1",
                    "events": {
                        "sdm.devices.events.CameraMotion.Motion": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "eventId": "ABCZQRUdGNUlTU2V4MGV3bRZ23...",
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )

    # Event is in the past and is expired
    ts3 = ts1 - datetime.timedelta(seconds=90)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "b83c2115-3b57-4eb4-8830-80519f167fa8",
                "timestamp": ts3.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": "enterprises/project-id1/devices/device-id1",
                    "events": {
                        "sdm.devices.events.CameraMotion.Motion": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "eventId": "1234QRUdGNUlTU2V4MGV3bRZ23...",
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )

    event_media_manager = device.event_media_manager
    assert len(list(await event_media_manager.async_events())) == 2


async def test_event_manager_cache_expiration(
    app: aiohttp.web.Application,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:

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
    app.router.add_get("/enterprises/project-id1/devices", handler)

    RESPONSE = {
        "results": {
            "url": "image-url-1",
            "token": "g.1.eventToken",
        },
    }
    num_events = 10
    post_handler = NewHandler(r, list(itertools.repeat(RESPONSE, num_events)))
    app.router.add_post(
        "/enterprises/project-id1/devices/device-id1:executeCommand", post_handler
    )
    app.router.add_get(
        "/image-url-1",
        NewImageHandler(
            list(itertools.repeat(b"image-bytes-1", num_events)), token="g.1.eventToken"
        ),
    )

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert "enterprises/project-id1/devices/device-id1" == device.name

    # Turn on event fetching
    device.event_media_manager.cache_policy.fetch = True
    device.event_media_manager.cache_policy.event_cache_size = 8

    class TestStore(InMemoryEventMediaStore):
        def get_media_key(self, device_id: str, event: ImageEventBase) -> str:
            """Return a predictable media key."""
            return event.event_id

    store = TestStore()
    device.event_media_manager.cache_policy.store = store

    for i in range(0, num_events):
        ts = datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(
            seconds=i
        )
        await device.async_handle_event(
            await event_message(
                {
                    "eventId": f"0120ecc7-{i}",
                    "timestamp": ts.isoformat(timespec="seconds"),
                    "resourceUpdate": {
                        "name": "enterprises/project-id1/devices/device-id1",
                        "events": {
                            "sdm.devices.events.CameraMotion.Motion": {
                                "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                                "eventId": f"FWWVQVU..{i}...",
                            },
                        },
                    },
                    "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
                }
            )
        )

    event_media_manager = device.event_media_manager
    # All old items are evicted from the cache
    assert len(list(await event_media_manager.async_events())) == 8

    # Old items are evicted from the media store
    assert await store.async_load_media("FWWVQVU..0...") is None
    assert await store.async_load_media("FWWVQVU..1...") is None
    for i in range(2, num_events):
        assert await store.async_load_media(f"FWWVQVU..{i}...") == b"image-bytes-1"


async def test_event_manager_prefetch_image_failure(
    app: aiohttp.web.Application,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:

    # Send one failure response, then 3 other valid responses. The cache size
    # is too so we're exercising events dropping out of the cache.
    responses = [
        aiohttp.web.json_response(
            {
                "devices": [
                    {
                        "name": "enterprises/project-id1/devices/device-id1",
                        "traits": {
                            "sdm.devices.traits.CameraEventImage": {},
                            "sdm.devices.traits.CameraMotion": {},
                        },
                    }
                ],
            }
        ),
        aiohttp.web.json_response(
            {
                "results": {
                    "url": "image-url-1",
                    "token": "g.1.eventToken",
                },
            }
        ),
        aiohttp.web.Response(status=502),
        aiohttp.web.json_response(
            {
                "results": {
                    "url": "image-url-1",
                    "token": "g.1.eventToken",
                },
            }
        ),
        aiohttp.web.json_response(
            {
                "results": {
                    "url": "image-url-1",
                    "token": "g.1.eventToken",
                },
            }
        ),
        aiohttp.web.json_response(
            {
                "results": {
                    "url": "image-url-1",
                    "token": "g.1.eventToken",
                },
            }
        ),
    ]

    async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert request.headers["Authorization"] == "Bearer %s" % FAKE_TOKEN
        return responses.pop(0)

    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_post(
        "/enterprises/project-id1/devices/device-id1:executeCommand", handler
    )
    app.router.add_get(
        "/image-url-1",
        NewImageHandler(
            list(itertools.repeat(b"image-bytes-1", 4)), token="g.1.eventToken"
        ),
    )

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert "enterprises/project-id1/devices/device-id1" == device.name

    # Turn on event fetching
    device.event_media_manager.cache_policy.fetch = True
    device.event_media_manager.cache_policy.event_cache_size = 3

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    for i in range(0, 5):
        ts = now + datetime.timedelta(seconds=i)
        await device.async_handle_event(
            await event_message(
                {
                    "eventId": f"0120ecc7-{i}",
                    "timestamp": ts.isoformat(timespec="seconds"),
                    "resourceUpdate": {
                        "name": "enterprises/project-id1/devices/device-id1",
                        "events": {
                            "sdm.devices.events.CameraMotion.Motion": {
                                "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                                "eventId": f"FWWVQVU..{i}...",
                            },
                        },
                    },
                    "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
                }
            )
        )

    event_media_manager = device.event_media_manager
    events = await event_media_manager.async_events()
    assert len(list(events)) == 3

    for i in range(1, 4):
        event_media = await event_media_manager.get_media(f"FWWVQVU..{i}...")
        if i == 1:
            assert not event_media
            continue

        ts = now + datetime.timedelta(seconds=i)
        assert event_media
        assert event_media.event_id == f"FWWVQVU..{i}..."
        assert event_media.event_type == "sdm.devices.events.CameraMotion.Motion"
        assert event_media.event_timestamp.isoformat(
            timespec="seconds"
        ) == ts.isoformat(timespec="seconds")
        assert event_media.media.contents == b"image-bytes-1"
        assert event_media.media.event_image_type.content_type == "image/jpeg"


async def test_multi_device_events(
    app: aiohttp.web.Application,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:

    r = Recorder()
    handler = NewDeviceHandler(
        r,
        [
            {
                "name": "device-id1",
                "traits": {
                    "sdm.devices.traits.CameraEventImage": {},
                    "sdm.devices.traits.CameraMotion": {},
                },
            },
            {
                "name": "device-id2",
                "traits": {
                    "sdm.devices.traits.CameraEventImage": {},
                    "sdm.devices.traits.CameraMotion": {},
                },
            },
        ],
    )
    app.router.add_get("/enterprises/project-id1/devices", handler)

    RESPONSE = {
        "results": {
            "url": "image-url-1",
            "token": "g.1.eventToken",
        },
    }
    num_events = 4
    post_handler = NewHandler(r, list(itertools.repeat(RESPONSE, num_events)))
    app.router.add_post(
        "/enterprises/project-id1/devices/device-id1:executeCommand", post_handler
    )
    app.router.add_get(
        "/image-url-1",
        NewImageHandler(
            list(itertools.repeat(b"image-bytes-1", num_events)), token="g.1.eventToken"
        ),
    )

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 2
    device = devices[0]
    assert "device-id1" == device.name
    device = devices[1]
    assert "device-id2" == device.name

    # Use shared event store for all devices
    store = InMemoryEventMediaStore()
    devices[0].event_media_manager.cache_policy.store = store
    devices[1].event_media_manager.cache_policy.store = store

    # Each device has
    event_media_manager = devices[0].event_media_manager
    assert len(list(await event_media_manager.async_events())) == 0
    event_media_manager = devices[1].event_media_manager
    assert len(list(await event_media_manager.async_events())) == 0

    ts = datetime.datetime.now(tz=datetime.timezone.utc)
    await devices[0].async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-1",
                "timestamp": ts.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": "device-id1",
                    "events": {
                        "sdm.devices.events.CameraMotion.Motion": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "eventId": "FWWVQVU..1...",
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )

    # Each device has a single event
    event_media_manager = devices[0].event_media_manager
    assert len(list(await event_media_manager.async_events())) == 1
    event_media_manager = devices[1].event_media_manager
    assert len(list(await event_media_manager.async_events())) == 0

    await devices[1].async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-2",
                "timestamp": ts.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": "device-id2",
                    "events": {
                        "sdm.devices.events.CameraMotion.Motion": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "eventId": "FWWVQVU..2...",
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )

    # Each device has a single event
    event_media_manager = devices[0].event_media_manager
    assert len(list(await event_media_manager.async_events())) == 1
    event_media_manager = devices[1].event_media_manager
    assert len(list(await event_media_manager.async_events())) == 1
