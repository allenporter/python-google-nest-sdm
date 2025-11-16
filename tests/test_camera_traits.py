"""Test for camera traits."""

import datetime
from typing import Any, Awaitable, Callable, Dict

import aiohttp
import pytest

from google_nest_sdm import google_nest_api
from google_nest_sdm.camera_traits import EventImageType, StreamingProtocol
from google_nest_sdm.device import Device

from .conftest import (
    DeviceHandler,
    Recorder,
    assert_diagnostics,
)

IMAGE_EVENT_TOKEN = "g.0.eventToken"
IMAGE_BYTES = b"<image-bytes>"

@pytest.fixture(name="image_handler")
async def image_handler_fixture(app: aiohttp.web.Application) -> None: 
    """Fixture to add image handler to app."""

    async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert request.headers["Authorization"] == f"Basic {IMAGE_EVENT_TOKEN}"
        return aiohttp.web.Response(body=IMAGE_BYTES)

    app.router.add_get(
        "/image-url",
        handler,
    )


def test_camera_image_traits(fake_device: Callable[[Dict[str, Any]], Device]) -> None:
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.CameraImage": {
                "maxImageResolution": {
                    "width": 500,
                    "height": 300,
                }
            },
        },
    }
    device = fake_device(raw)
    assert "sdm.devices.traits.CameraImage" in device.traits
    trait = device.traits["sdm.devices.traits.CameraImage"]
    assert trait.max_image_resolution.width == 500
    assert trait.max_image_resolution.height == 300


@pytest.mark.parametrize(
    "data",
    [
        ({}),
        ({"maxImageResolution": {}}),
        ({"maxImageResolution": {"width": 1024}}),
        ({"maxImageResolution": {"height": 1024}}),
    ],
)
def test_otional_fields(
    fake_device: Callable[[Dict[str, Any]], Device], data: dict[str, Any]
) -> None:
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.CameraImage": data,
        },
    }
    device = fake_device(raw)
    assert "sdm.devices.traits.CameraImage" in device.traits
    assert device.camera_image


def test_camera_live_stream_traits(
    fake_device: Callable[[Dict[str, Any]], Device],
) -> None:
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.CameraLiveStream": {
                "maxVideoResolution": {
                    "width": 500,
                    "height": 300,
                },
                "videoCodecs": ["H264"],
                "audioCodecs": ["AAC"],
            },
        },
    }
    device = fake_device(raw)
    assert "sdm.devices.traits.CameraLiveStream" in device.traits
    trait = device.traits["sdm.devices.traits.CameraLiveStream"]
    assert trait.max_video_resolution.width == 500
    assert trait.max_video_resolution.height == 300
    assert trait.video_codecs == ["H264"]
    assert trait.audio_codecs == ["AAC"]
    # Default value
    assert trait.supported_protocols == [StreamingProtocol.RTSP]


def test_camera_live_stream_webrtc_protocol(
    fake_device: Callable[[Dict[str, Any]], Device],
) -> None:
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.CameraLiveStream": {
                "supportedProtocols": ["WEB_RTC"],
            },
        },
    }
    device = fake_device(raw)
    assert "sdm.devices.traits.CameraLiveStream" in device.traits
    trait = device.traits["sdm.devices.traits.CameraLiveStream"]
    assert trait.supported_protocols == [StreamingProtocol.WEB_RTC]


def test_camera_live_stream_multiple_protocols(
    fake_device: Callable[[Dict[str, Any]], Device],
) -> None:
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.CameraLiveStream": {
                "supportedProtocols": ["WEB_RTC", "RTSP"],
            },
        },
    }
    device = fake_device(raw)
    assert "sdm.devices.traits.CameraLiveStream" in device.traits
    trait = device.traits["sdm.devices.traits.CameraLiveStream"]
    assert trait.supported_protocols == [
        StreamingProtocol.WEB_RTC,
        StreamingProtocol.RTSP,
    ]


def test_camera_live_stream_unknown_protocols(
    fake_device: Callable[[Dict[str, Any]], Device],
) -> None:
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.CameraLiveStream": {
                "supportedProtocols": ["WEB_RTC", "XXX"],
            },
        },
    }
    device = fake_device(raw)
    assert "sdm.devices.traits.CameraLiveStream" in device.traits
    trait = device.traits["sdm.devices.traits.CameraLiveStream"]
    assert trait.supported_protocols == [StreamingProtocol.WEB_RTC]


@pytest.mark.parametrize(
    "data",
    [
        ({}),
        ({"maxVideoResolution": {}}),
        ({"maxVideoResolution": {"width": 1024}}),
        ({"maxVideoResolution": {"height": 1024}}),
        ({"videoCodecs": []}),
        ({"audioCodecs": []}),
    ],
)
def test_camera_live_stream_optional_fields(
    fake_device: Callable[[Dict[str, Any]], Device], data: dict[str, Any]
) -> None:
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.CameraLiveStream": data,
        },
    }
    device = fake_device(raw)
    assert "sdm.devices.traits.CameraLiveStream" in device.traits
    assert device.camera_live_stream


@pytest.mark.parametrize(
    "trait",
    [
        "sdm.devices.traits.CameraMotion",
        "sdm.devices.traits.CameraPerson",
        "sdm.devices.traits.CameraSound",
        "sdm.devices.traits.CameraClipPreview",
        "sdm.devices.traits.CameraEventImage",
    ],
)
def test_image_event_traits(
    trait: str, fake_device: Callable[[Dict[str, Any]], Device]
) -> None:
    raw = {
        "name": "my/device/name",
        "traits": {
            trait: {},
        },
    }
    device = fake_device(raw)
    assert trait in device.traits


async def test_camera_live_stream_rtsp(
    app: aiohttp.web.Application,
    recorder: Recorder,
    device_handler: DeviceHandler,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.CameraLiveStream": {
                "maxVideoResolution": {
                    "width": 500,
                    "height": 300,
                },
                "videoCodecs": ["H264"],
                "audioCodecs": ["AAC"],
            },
        }
    )
    device_handler.add_device_command(
        device_id,
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

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert device.name == device_id
    trait = device.traits["sdm.devices.traits.CameraLiveStream"]
    stream = await trait.generate_rtsp_stream()
    assert recorder.request == {
        "command": "sdm.devices.commands.CameraLiveStream.GenerateRtspStream",
        "params": {},
    }
    assert stream.stream_token == "g.0.token"
    assert stream.expires_at == datetime.datetime(
        2018, 1, 4, 18, 30, tzinfo=datetime.timezone.utc
    )
    assert stream.rtsp_stream_url == "rtsps://someurl.com/CjY5Y3VKaTfMF?auth=g.0.token"

    stream = await stream.extend_rtsp_stream()
    assert recorder.request == {
        "command": "sdm.devices.commands.CameraLiveStream.ExtendRtspStream",
        "params": {
            "streamExtensionToken": "CjY5Y3VKaTfMF",
        },
    }
    assert stream.stream_token == "g.1.newStreamingToken"
    assert stream.expires_at == datetime.datetime(
        2019, 1, 4, 18, 30, tzinfo=datetime.timezone.utc
    )
    assert (
        stream.rtsp_stream_url
        == "rtsps://someurl.com/CjY5Y3VKaTfMF?auth=g.1.newStreamingToken"
    )

    stream = await stream.extend_rtsp_stream()
    assert recorder.request == {
        "command": "sdm.devices.commands.CameraLiveStream.ExtendRtspStream",
        "params": {
            "streamExtensionToken": "dGNUlTU2CjY5Y3VKaTZwR3o4Y1...",
        },
    }
    assert stream.stream_token == "g.2.newStreamingToken"
    assert stream.expires_at == datetime.datetime(
        2020, 1, 4, 18, 30, tzinfo=datetime.timezone.utc
    )
    assert (
        stream.rtsp_stream_url
        == "rtsps://someurl.com/CjY5Y3VKaTfMF?auth=g.2.newStreamingToken"
    )

    await stream.stop_rtsp_stream()
    assert recorder.request == {
        "command": "sdm.devices.commands.CameraLiveStream.StopRtspStream",
        "params": {
            "streamExtensionToken": "last-token...",
        },
    }

    assert_diagnostics(
        device.get_diagnostics(),
        {
            "data": {
                "name": "**REDACTED**",
                "parentRelations": [],
                "traits": {
                    "sdm.devices.traits.CameraLiveStream": {
                        "maxVideoResolution": {
                            "width": 500,
                            "height": 300,
                        },
                        "videoCodecs": ["H264"],
                        "audioCodecs": ["AAC"],
                        "supportedProtocols": ["RTSP"],
                    }
                },
                "type": "sdm.devices.types.device-type1",
            },
            "command": {
                "sdm.devices.commands.CameraLiveStream.ExtendRtspStream_count": 2,
                "sdm.devices.commands.CameraLiveStream.GenerateRtspStream_count": 1,
                "sdm.devices.commands.CameraLiveStream.StopRtspStream_count": 1,
            },
        },
    )


async def test_camera_live_stream_web_rtc(
    app: aiohttp.web.Application,
    recorder: Recorder,
    device_handler: DeviceHandler,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.CameraLiveStream": {
                "supportedProtocols": ["WEB_RTC"],
            },
        }
    )
    device_handler.add_device_command(
        device_id,
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

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert device.name == device_id
    trait = device.traits["sdm.devices.traits.CameraLiveStream"]
    assert trait.supported_protocols == [StreamingProtocol.WEB_RTC]
    stream = await trait.generate_web_rtc_stream("a=recvonly")
    assert recorder.request == {
        "command": "sdm.devices.commands.CameraLiveStream.GenerateWebRtcStream",
        "params": {
            "offerSdp": "a=recvonly",
        },
    }
    assert stream.answer_sdp == "some-answer"
    assert stream.expires_at == datetime.datetime(
        2018, 1, 4, 18, 30, tzinfo=datetime.timezone.utc
    )
    assert stream.media_session_id == "JxdTxkkatHk4kVnXlKzQICbfVR..."

    stream = await stream.extend_stream()
    expected_request = {
        "command": "sdm.devices.commands.CameraLiveStream.ExtendWebRtcStream",
        "params": {
            "mediaSessionId": "JxdTxkkatHk4kVnXlKzQICbfVR...",
        },
    }
    assert expected_request == recorder.request
    assert "some-answer" == stream.answer_sdp
    assert (
        datetime.datetime(2019, 1, 4, 18, 30, tzinfo=datetime.timezone.utc)
        == stream.expires_at
    )
    assert "JxdTxkkatHk4kVnXlKzQICbfVR..." == stream.media_session_id

    stream = await stream.extend_stream()
    assert recorder.request == {
        "command": "sdm.devices.commands.CameraLiveStream.ExtendWebRtcStream",
        "params": {
            "mediaSessionId": "JxdTxkkatHk4kVnXlKzQICbfVR...",
        },
    }
    assert stream.answer_sdp == "some-answer"
    assert stream.expires_at == datetime.datetime(
        2020, 1, 4, 18, 30, tzinfo=datetime.timezone.utc
    )
    assert "JxdTxkkatHk4kVnXlKzQICbfVR..." == stream.media_session_id

    await stream.stop_stream()
    assert recorder.request == {
        "command": "sdm.devices.commands.CameraLiveStream.StopWebRtcStream",
        "params": {
            "mediaSessionId": "JxdTxkkatHk4kVnXlKzQICbfVR...",
        },
    }


async def test_camera_event_image(
    app: aiohttp.web.Application,
    recorder: Recorder,
    image_handler: None,
    device_handler: DeviceHandler,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
    device_id = device_handler.add_device(
        traits={"sdm.devices.traits.CameraEventImage": {}}
    )
    device_handler.add_device_command(
        device_id,
        [
            {
                "results": {
                    "url": "https://domain/sdm_event/dGNUlTU2CjY5Y3VKaTZwR3o4Y",
                    "token": IMAGE_EVENT_TOKEN,
                },
            }
        ],
    )

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert device.name == device_id
    trait = device.traits["sdm.devices.traits.CameraEventImage"]
    image = await trait.generate_image("some-eventId")
    assert recorder.request == {
        "command": "sdm.devices.commands.CameraEventImage.GenerateImage",
        "params": {"eventId": "some-eventId"},
    }
    assert image.url == "https://domain/sdm_event/dGNUlTU2CjY5Y3VKaTZwR3o4Y"
    assert image.token == IMAGE_EVENT_TOKEN
    assert image.event_image_type == EventImageType.IMAGE


async def test_camera_event_image_bytes(
    app: aiohttp.web.Application,
    recorder: Recorder,
    image_handler: None,
    device_handler: DeviceHandler,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> None:
    device_id = device_handler.add_device(
        traits={"sdm.devices.traits.CameraEventImage": {}}
    )
    device_handler.add_device_command(
        device_id,
        [
            {
                "results": {
                    "url": "image-url",
                    "token": IMAGE_EVENT_TOKEN,
                },
            }
        ],
    )

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert device.name == device_id
    trait = device.traits["sdm.devices.traits.CameraEventImage"]
    event_image = await trait.generate_image("some-eventId")
    image_bytes = await event_image.contents()
    assert image_bytes == IMAGE_BYTES
